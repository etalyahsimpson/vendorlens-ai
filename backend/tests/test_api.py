"""End-to-end API tests over an isolated SQLite database."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _valid_csv_bytes() -> bytes:
    return (
        "supplier_id,supplier_name,street_address,city,state,postal_code,country,website\n"
        "SUP-0001,Northstar Industrial Supplies LLC,1200 Market St,Philadelphia,PA,19103,USA,northstarindustrial.example\n"
        "SUP-0002,North Star Industrial Supply,1200 Market Street,Philadelphia,PA,19103,USA,https://www.northstarindustrial.example/\n"
        "SUP-0003,Northstar Office Services LLC,98 Chestnut Ave,Philadelphia,PA,19103,USA,northstaroffice.example\n"
        "SUP-0004,Silverline Packaging Corp.,55 Oak Blvd,Chicago,IL,60601,USA,silverlinepackaging.example\n"
    ).encode("utf-8")


def test_health_reports_model_and_database(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"] == "vendorlens-match-v1"
    assert body["retrieval_engine"] == "faiss"
    assert body["database"] == "ok"


def test_demo_metadata(client):
    r = client.get("/api/v1/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["record_count"] > 10
    assert "synthetic" in body["provenance"].lower()
    assert body["sample_download_path"] == "/api/v1/demo/sample"


def test_demo_sample_download(client):
    r = client.get("/api/v1/demo/sample")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "supplier_id,supplier_name" in r.text


def test_demo_analysis_full_flow(client):
    r = client.post("/api/v1/analyses/demo")
    assert r.status_code == 201
    summary = r.json()
    assert summary["source_type"] == "sample"
    assert summary["counts"]["records"] > 10
    assert summary["counts"]["suggestions"] > 0

    analysis_id = summary["analysis_id"]

    r = client.get(f"/api/v1/analyses/{analysis_id}")
    assert r.status_code == 200
    assert r.json()["counts"] == summary["counts"]

    r = client.get(f"/api/v1/analyses/{analysis_id}/matches")
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == summary["counts"]["suggestions"]
    items_sorted = [i["score"] for i in page["items"]]
    assert items_sorted == sorted(items_sorted, reverse=True)
    first = page["items"][0]
    assert first["review_decision"] is None, "nothing is auto-confirmed"
    assert set(first["signals"]) >= {
        "name_similarity", "website", "city", "legal_suffix"
    }


def test_upload_valid_csv(client):
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.csv", _valid_csv_bytes(), "text/csv")},
    )
    assert r.status_code == 201
    summary = r.json()
    assert summary["source_type"] == "upload"
    assert summary["counts"]["records"] == 4
    # The alias pair must surface as a candidate with strong evidence.
    matches = client.get(f"/api/v1/analyses/{summary['analysis_id']}/matches").json()
    names = [(m["left"]["supplier_name"], m["right"]["supplier_name"]) for m in matches["items"]]
    assert any("Northstar Industrial" in a and "North Star Industrial" in b for a, b in names)
    assert any(m["signals"]["website"] == "same" for m in matches["items"])


def test_upload_rejects_wrong_extension(client):
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.exe", _valid_csv_bytes(), "application/octet-stream")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_missing_headers(client):
    bad = b"supplier_id,city\nSUP-1,Philadelphia\n"
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.csv", bad, "text/csv")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "missing_required_columns"


def test_upload_rejects_duplicate_ids(client):
    dup = (
        "supplier_id,supplier_name\n"
        "SUP-1,Alpha Supply\n"
        "SUP-1,Alpha Supply Inc.\n"
    ).encode()
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.csv", dup, "text/csv")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "duplicate_supplier_ids"


def test_upload_rejects_bad_encoding(client):
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.csv", b"\xff\xfe garbage", "text/csv")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_encoding"


def test_upload_rejects_empty_file(client):
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.csv", b"", "text/csv")},
    )
    assert r.status_code == 422


def test_unknown_analysis_returns_clean_404(client):
    r = client.get("/api/v1/analyses/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "analysis_not_found"


def test_unknown_match_review_returns_404(client):
    r = client.patch(
        "/api/v1/matches/00000000-0000-0000-0000-000000000000/review",
        json={"decision": "confirm_same"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "suggestion_not_found"


def test_review_decision_validation(client):
    r = client.post("/api/v1/analyses/demo")
    suggestion = client.get(
        f"/api/v1/analyses/{r.json()['analysis_id']}/matches"
    ).json()["items"][0]

    r = client.patch(
        f"/api/v1/matches/{suggestion['suggestion_id']}/review",
        json={"decision": "not-a-decision"},
    )
    assert r.status_code == 422
    assert "detail" in r.json()


def test_review_decisions_persist_across_reload(client):
    """Decisions must come from the database, not client state."""
    r = client.post("/api/v1/analyses/demo")
    analysis_id = r.json()["analysis_id"]
    items = client.get(f"/api/v1/analyses/{analysis_id}/matches").json()["items"]
    target = items[0]

    r = client.patch(
        f"/api/v1/matches/{target['suggestion_id']}/review",
        json={"decision": "reject_match", "notes": "different companies"},
    )
    assert r.status_code == 200
    assert r.json()["review_decision"]["decision"] == "reject_match"

    # "Reload": a brand-new request cycle must still see the decision.
    refreshed = client.get(f"/api/v1/analyses/{analysis_id}/matches").json()
    match = next(
        m for m in refreshed["items"] if m["suggestion_id"] == target["suggestion_id"]
    )
    assert match["review_decision"]["decision"] == "reject_match"
    assert match["review_decision"]["notes"] == "different companies"

    # Upsert path: change the decision.
    r = client.patch(
        f"/api/v1/matches/{target['suggestion_id']}/review",
        json={"decision": "confirm_same"},
    )
    assert r.json()["review_decision"]["decision"] == "confirm_same"


def test_match_filters(client):
    r = client.post("/api/v1/analyses/demo")
    analysis_id = r.json()["analysis_id"]
    all_items = client.get(f"/api/v1/analyses/{analysis_id}/matches").json()["items"]

    likely = client.get(
        f"/api/v1/analyses/{analysis_id}/matches", params={"band": "likely_match"}
    ).json()["items"]
    assert likely and all(m["band"] == "likely_match" for m in likely)

    needle = likely[0]["left"]["supplier_name"].split()[0]
    search = client.get(
        f"/api/v1/analyses/{analysis_id}/matches", params={"q": needle}
    ).json()["items"]
    assert search, "text search must find matching names"


def test_export_contains_findings_and_decisions(client):
    r = client.post("/api/v1/analyses/demo")
    analysis_id = r.json()["analysis_id"]
    items = client.get(f"/api/v1/analyses/{analysis_id}/matches").json()["items"]
    client.patch(
        f"/api/v1/matches/{items[0]['suggestion_id']}/review",
        json={"decision": "confirm_same"},
    )

    r = client.get(f"/api/v1/analyses/{analysis_id}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) > 0
    assert "model_score" in rows[0] and "review_decision" in rows[0]
    decided = [row for row in rows if row["review_decision"]]
    assert any(row["review_decision"] == "Confirmed same entity" for row in decided)
    # Original identifiers preserved.
    assert all(row["left_supplier_id"] and row["right_supplier_id"] for row in rows)


def test_export_neutralizes_formula_injection(client):
    """CSV injection must be neutralized on export (documented transformation)."""
    malicious = (
        "supplier_id,supplier_name,city,state,website\n"
        "SUP-9001,=HYPERLINK(http://evil.example;Click),Philadelphia,PA,a.example\n"
        "SUP-9002,@SUM(1+1)*cmd|' /C calc'!A0,Philadelphia,PA,a.example\n"
        "SUP-9003,+cmd|/C calc,Philadelphia,PA,a.example\n"
        "SUP-9004,-2+3|cmd,Philadelphia,PA,a.example\n"
        "SUP-9005,Normal Company LLC,Philadelphia,PA,a.example\n"
    ).encode()
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.csv", malicious, "text/csv")},
    )
    assert r.status_code == 201
    analysis_id = r.json()["analysis_id"]

    export = client.get(f"/api/v1/analyses/{analysis_id}/export").text
    rows = list(csv.reader(io.StringIO(export)))
    assert len(rows) > 1
    for row in rows:
        for cell in row:
            assert not cell.startswith(("=", "+", "-", "@", "\t", "\r")), (
                f"unneutralized formula cell: {cell!r}"
            )
            if cell.startswith("'"):
                # Neutralized cells keep their original content after the quote.
                assert len(cell) > 1
    # The payloads are present in neutralized (quote-prefixed) form.
    body = export
    assert "'=HYPERLINK" in body and "'@SUM" in body and "'+cmd" in body and "'-2+3" in body
    # Normal data is untouched.
    assert "Normal Company LLC" in body
    assert "'Normal Company" not in body


def test_model_metrics_endpoint_returns_actual_report(client):
    r = client.get("/api/v1/model/metrics")
    assert r.status_code == 200
    body = r.json()
    metrics_file = json.loads((REPO_ROOT / "reports" / "metrics.json").read_text())
    assert body["model"]["test"] == metrics_file["model"]["test"]
    assert body["thresholds"]["decision"] > 0
    assert "mlflow" in body and body["mlflow"]["model_run_id"]
    assert "qualification" in body


def test_openapi_documentation_available(client):
    r = client.get("/docs")
    assert r.status_code == 200
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for expected in (
        "/api/v1/health",
        "/api/v1/demo",
        "/api/v1/analyses/demo",
        "/api/v1/analyses/upload",
        "/api/v1/analyses/{analysis_id}",
        "/api/v1/analyses/{analysis_id}/matches",
        "/api/v1/matches/{suggestion_id}/review",
        "/api/v1/analyses/{analysis_id}/export",
        "/api/v1/model/metrics",
    ):
        assert expected in paths, f"missing documented endpoint {expected}"


def test_identical_names_different_websites_not_auto_verified(client):
    """Spec guard: lookalikes must require human review, never auto-confirm."""
    csv_data = (
        "supplier_id,supplier_name,city,state,postal_code,website\n"
        "SUP-0001,Acme Industrial Supplies LLC,Philadelphia,PA,19103,acmeindustrial.example\n"
        "SUP-0002,Acme Industrial Supplies LLC,Seattle,WA,98101,acme-grp.example\n"
        "SUP-0003,Acme Industrial Suplies Inc.,Philadelphia,PA,19103,acmeindustrial.example\n"
    ).encode()
    r = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("suppliers.csv", csv_data, "text/csv")},
    )
    assert r.status_code == 201
    analysis_id = r.json()["analysis_id"]
    items = client.get(f"/api/v1/analyses/{analysis_id}/matches").json()["items"]

    for item in items:
        assert item["review_decision"] is None, "no automatic verification"

    # The true alias pair (same city + website) is a strong candidate...
    alias_pair = next(
        i for i in items
        if i["signals"]["website"] == "same" and i["signals"]["city"] == "same"
    )
    assert alias_pair["score"] > 0.5
    # ...while the identical-name/different-identity pair is downgraded.
    namesake = next(
        i for i in items
        if i["signals"]["website"] == "different" and i["left"]["supplier_name"] == i["right"]["supplier_name"]
    )
    assert namesake["band"] in {"needs_review", "unlikely_match"}, (
        "identical names with different websites/regions must not be a confident match"
    )
