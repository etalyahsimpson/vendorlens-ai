"""PostgreSQL-backed integration tests.

Skipped unless ``TEST_DATABASE_URL`` points at a PostgreSQL database, e.g.:

    TEST_DATABASE_URL=postgresql+psycopg://vendorlens:vendorlens@localhost:5432/vendorlens_test

The GitHub Actions workflow runs this suite against a real PostgreSQL service.
"""

from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="TEST_DATABASE_URL does not point at a PostgreSQL database",
)


@pytest.fixture()
def pg_client(tmp_path):
    from fastapi.testclient import TestClient

    from vendorlens.api.app import create_app
    from vendorlens.db.session import build_engine, init_db, session_factory

    url = os.environ["TEST_DATABASE_URL"]
    engine = build_engine(url)
    init_db(engine)
    import vendorlens.api.app as app_module

    # Drop leftover rows from previous runs for a clean slate.
    from vendorlens.db.models import Base

    Base.metadata.drop_all(engine)
    init_db(engine)

    app = create_app()
    app.state.engine = engine
    app.state.db_session = session_factory(engine)

    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_postgres_health(pg_client):
    r = pg_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["database"] == "ok"


def test_postgres_analysis_review_export_roundtrip(pg_client):
    r = pg_client.post("/api/v1/analyses/demo")
    assert r.status_code == 201, r.text
    analysis_id = r.json()["analysis_id"]

    matches = pg_client.get(f"/api/v1/analyses/{analysis_id}/matches").json()
    assert matches["total"] > 0

    sid = matches["items"][0]["suggestion_id"]
    r = pg_client.patch(
        f"/api/v1/matches/{sid}/review",
        json={"decision": "needs_investigation", "notes": "check with procurement"},
    )
    assert r.status_code == 200

    again = pg_client.get(f"/api/v1/analyses/{analysis_id}/matches").json()
    match = next(m for m in again["items"] if m["suggestion_id"] == sid)
    assert match["review_decision"]["decision"] == "needs_investigation"

    export = pg_client.get(f"/api/v1/analyses/{analysis_id}/export")
    assert export.status_code == 200
    assert "Needs investigation" in export.text
