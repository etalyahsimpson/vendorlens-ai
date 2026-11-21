# API Reference

Base URL (local): `http://localhost:8000`. All application endpoints are
prefixed with `/api/v1`. Interactive OpenAPI documentation is served at
[`/docs`](http://localhost:8000/docs) (Swagger UI) once the backend is running,
generated directly from the Pydantic schemas in `backend/vendorlens/api/schemas.py`.

## Error contract

Validation and not-found failures return a stable JSON error shape — never a
Python traceback:

```json
{
  "error": {
    "code": "duplicate_supplier_ids",
    "message": "supplier_id values must be unique within the uploaded file.",
    "details": ["Duplicate IDs: SUP-1, SUP-2"]
  }
}
```

Common codes: `unsupported_file_type` (422), `empty_file` (422),
`invalid_encoding` (422), `missing_required_columns` (422),
`missing_required_value` (422), `duplicate_supplier_ids` (422),
`too_many_rows` (422), `file_too_large` (413/422), `no_data_rows` (422),
`analysis_not_found` (404), `suggestion_not_found` (404),
`model_not_trained` (503), `metrics_unavailable` (503).

---

## GET /api/v1/health

Liveness and readiness: model load state, retrieval engine, database check.

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "vendorlens-match-v1",
  "app_version": "1.0.0",
  "retrieval_engine": "faiss",
  "database": "ok"
}
```

## GET /api/v1/demo

Metadata about the bundled sample dataset.

```json
{
  "available": true,
  "record_count": 78,
  "description": "Bundled sample supplier register with duplicates, lookalike companies and missing fields...",
  "provenance": "Synthetic sample data generated deterministically for this project (see docs/ML_METHODOLOGY.md); not real supplier data.",
  "sample_download_path": "/api/v1/demo/sample"
}
```

## GET /api/v1/demo/sample

Downloads the sample CSV (`text/csv`, attachment). Suitable as an upload
template.

## POST /api/v1/analyses/demo

Runs duplicate detection over the bundled sample. `201` returns the analysis
summary (same shape as GET /analyses/{id}).

## POST /api/v1/analyses/upload

Multipart upload (`file` field). Validates then analyzes the CSV.

```
curl -F "file=@suppliers.csv" http://localhost:8000/api/v1/analyses/upload
```

`201` response (analysis summary):

```json
{
  "analysis_id": "e7775960-1f3e-4a2b-9c0d-3f4a5b6c7d8e",
  "source_type": "upload",
  "filename": "suppliers.csv",
  "created_at": "2026-11-21T05:09:20.106469",
  "row_count": 4,
  "model_version": "vendorlens-match-v1",
  "status": "completed",
  "counts": {
    "records": 4, "suggestions": 6,
    "likely": 3, "needs_review": 2, "unlikely": 1,
    "reviewed": 0, "confirmed": 0, "rejected": 0, "investigation": 0
  },
  "warnings": ["Ignored columns not in the schema: internal_note"]
}
```

## GET /api/v1/analyses/{id}

Returns the analysis summary above for an existing session; `404` otherwise.

## GET /api/v1/analyses/{id}/matches

Ranked candidate suggestions (score descending). Query parameters:

| Param | Effect |
|---|---|
| `band` | `likely_match` / `needs_review` / `unlikely_match` |
| `decision` | `confirm_same` / `reject_match` / `needs_investigation` |
| `q` | Case-insensitive substring on supplier names/IDs |
| `limit` | 1–500 (default 100) |
| `offset` | Pagination offset |

```json
{
  "total": 6,
  "items": [
    {
      "suggestion_id": "9f0c…",
      "score": 1.0,
      "band": "likely_match",
      "signals": {
        "name_similarity": 1.0, "name_evidence": "strong",
        "token_jaccard": 1.0, "legal_suffix": "same",
        "city": "same", "state": "same", "postal_code": "same",
        "website": "same", "address_similarity": 1.0
      },
      "left":  { "supplier_id": "SUP-0001", "supplier_name": "…", "city": "…", "...": "…" },
      "right": { "supplier_id": "SUP-0002", "supplier_name": "…", "...": "…" },
      "review_decision": null
    }
  ]
}
```

## PATCH /api/v1/matches/{suggestion_id}/review

Create or update the human decision for one suggestion (upsert).

```json
{ "decision": "confirm_same", "notes": "same address and website" }
```

- `decision` ∈ `confirm_same` | `reject_match` | `needs_investigation` (422 otherwise)
- `notes` optional, ≤ 500 characters
- Returns the updated suggestion item with `review_decision` populated;
  `404` if the suggestion does not exist.

## GET /api/v1/analyses/{id}/export

Downloads the findings report (`text/csv`, attachment): every suggestion with
scores, bands, evidence, and current review decisions. Cells that could be
interpreted as spreadsheet formulas are neutralized with a leading apostrophe
(see [DATA_DICTIONARY.md](DATA_DICTIONARY.md)).

## GET /api/v1/model/metrics

Returns the contents of `reports/metrics.json` — the actual measured
evaluation: dataset provenance, entity-disjoint split sizes, baseline and
model metrics (precision/recall/F1, confusion matrices) for validation and
test, thresholds, candidate-generation recall, difficult cases, MLflow run
IDs, environment versions, and the benchmark qualification statement.
