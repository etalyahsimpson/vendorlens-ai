"""Shared pytest fixtures: isolated SQLite databases, app client, scorer."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def tmp_db_url(tmp_path, monkeypatch) -> str:
    """Point the app at a fresh SQLite database per test."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url


@pytest.fixture()
def client(tmp_db_url) -> TestClient:
    """FastAPI test client with a clean database and the committed model."""
    from vendorlens.api.app import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sample_csv_bytes() -> bytes:
    path = REPO_ROOT / "data" / "sample_suppliers.csv"
    return path.read_bytes()


@pytest.fixture(scope="session")
def labeled_csv() -> Path:
    path = REPO_ROOT / "data" / "generated" / "suppliers_labeled.csv"
    if not path.exists():
        pytest.skip("labeled dataset not generated yet")
    return path
