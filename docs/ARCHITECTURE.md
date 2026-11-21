# Architecture

VendorLens AI is a compact, reproducible three-tier application: a React SPA,
a FastAPI service, and a relational database, with an offline ML pipeline that
produces the served model.

```
┌─────────────────────────────── Repository ────────────────────────────────┐
│                                                                           │
│  ML pipeline (offline, deterministic)            Application (online)     │
│  ┌──────────────────────────────┐                ┌─────────────────────┐  │
│  │ generator.py (seed=42)       │                │ FastAPI             │  │
│  │  → data/generated/*.csv      │                │  api/  routes       │  │
│  │ training.py                  │  model bundle  │  services/          │  │
│  │  ├─ normalize → TF-IDF/SVD   │ ─────────────▶ │   analysis/review/  │  │
│  │  ├─ FAISS candidates         │  artifacts/    │   export            │  │
│  │  ├─ pair features            │  model_bundle  │  db/ SQLAlchemy     │  │
│  │  ├─ baseline + LogReg        │  .joblib       │   PostgreSQL/SQLite │  │
│  │  ├─ metrics + figures        │                │  ml/ inference      │  │
│  │  └─ MLflow runs (./mlruns)   │                └─────────┬───────────┘  │
│  └──────────────────────────────┘                          │              │
│        │ reports/metrics.json                              │ REST /api/v1 │
│        ▼                                                   ▼              │
│  ┌──────────────┐                                   ┌─────────────────┐   │
│  │  React SPA   │ ◀─── Axios (typed) ─────────────── │  Vite build     │   │
│  │  review UI   │                                   │  nginx proxy    │   │
│  └──────────────┘                                   └─────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

## Components and ownership

| Component | Location | Responsibility |
|---|---|---|
| Data generator | `backend/vendorlens/data/generator.py` | Deterministic synthetic supplier register (seed 42) with canonical-entity labels, hard negatives, namesakes |
| CSV validation | `backend/vendorlens/data/validation.py` | Trust boundary for uploads: schema, limits, encoding, control characters |
| Normalization | `backend/vendorlens/ml/normalization.py` | Case/punctuation/suffix/URL normalization shared by training and serving |
| Candidate retrieval | `backend/vendorlens/ml/candidates.py` | TF-IDF char n-grams + TruncatedSVD + `faiss.IndexFlatIP` top-k, unioned with website/city+postal blocking |
| Pair features | `backend/vendorlens/ml/features.py` | 19 interpretable features + human-readable signals; identical code path in training and serving |
| Training | `backend/vendorlens/ml/training.py` | Entity-disjoint splits, baseline rule, LogisticRegression, threshold selection on validation, MLflow runs, reports |
| Inference | `backend/vendorlens/ml/inference.py` | Loads the versioned bundle; applies the *training-fitted* vectorizer/SVD and classifier |
| API | `backend/vendorlens/api/` | FastAPI app, Pydantic schemas, 9 endpoints + sample download |
| Persistence | `backend/vendorlens/db/` | SQLAlchemy models: `AnalysisSession`, `SupplierRecord`, `MatchSuggestion`, `ReviewDecision` |
| Services | `backend/vendorlens/services/` | Analysis orchestration, review upserts, export with formula neutralization |
| Frontend | `frontend/src/` | Overview, upload/validation, review workspace with comparison drawer, model evidence |
| E2E tests | `tests/e2e/` | Playwright browser flows and authentic screenshot capture |

## Data path (upload → export)

1. `POST /api/v1/analyses/upload` receives multipart CSV (≤ 5 MB, ≤ 2,000 rows).
2. `validate_csv_bytes` enforces the schema, uniqueness of `supplier_id`, UTF-8,
   and strips control characters. Failures return structured 422 errors.
3. `run_analysis` persists the session and every original + normalized record.
4. `MatchScorer.analyze` reuses the training-fitted TF-IDF/SVD to embed names,
   builds a per-analysis FAISS index, retrieves top-8 neighbours per record,
   unions deterministic blocks, computes the 19 pair features and
   `predict_proba` scores, then maps scores to recommendation bands.
5. Suggestions persist with score, band and evidence signals.
6. Analysts submit `PATCH /api/v1/matches/{id}/review` decisions; the decision
   rows are the durable source of truth (they survive reloads and appear in exports).
7. `GET /api/v1/analyses/{id}/export` streams a CSV report with both model
   output and human decisions, with spreadsheet-formula neutralization applied.

## Database options

- **PostgreSQL (Docker Compose default).** `DATABASE_URL=postgresql+psycopg://…`;
  the compose file starts PostgreSQL 16 with a healthcheck; the backend waits
  for readiness and creates its tables on startup.
- **SQLite (quick start / tests).** `DATABASE_URL=sqlite:///./vendorlens.db`.
  Table initialization is reproducible via `Base.metadata.create_all`; the
  schema is deliberately narrow, so formal migrations are not used (see
  [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md)).

## FAISS in the request path

Candidate retrieval is genuinely FAISS-backed in the standard environment
(`faiss-cpu==1.9.0.post1`): `CandidateRetriever.build_index` constructs a real
`faiss.IndexFlatIP`, and the test suite asserts the active engine and index
type. A pure-NumPy exact fallback exists solely for platforms where `faiss-cpu`
cannot be installed; it is reported as `numpy-fallback` in the health endpoint
and never claimed as FAISS validation.

## MLflow

Training logs two runs (baseline rule + trained model) to a local file store
under `./mlruns` (git-ignored; run IDs are recorded in `reports/metrics.json`).
`make mlflow-ui` serves the UI on `http://localhost:5000`. No hosted tracking
server or third-party account is required.

## Failure modes

| Failure | Behaviour |
|---|---|
| Model bundle missing | `/api/v1/health` reports `model_loaded: false`; analysis endpoints return 503 with a remediation hint |
| `reports/metrics.json` missing | `/api/v1/model/metrics` returns 503 |
| Oversized/invalid upload | Structured 422 with `code`, `message`, `details` — never a traceback |
| Candidate explosion | `CandidateLimitExceeded` (6,000-pair bound) surfaced as a descriptive 422 |
| Blocks larger than 30 records | Skipped deterministically and counted in retrieval stats (bounded behaviour on degenerate uploads) |
| Database unavailable | Health degrades to `database: unavailable`; startup fails fast in compose via healthcheck ordering |
