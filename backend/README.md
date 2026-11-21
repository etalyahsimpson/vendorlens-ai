# VendorLens AI — Backend

FastAPI service implementing supplier duplicate detection with a trained
scikit-learn model, FAISS candidate retrieval, SQLAlchemy persistence
(PostgreSQL or SQLite) and MLflow-tracked training.

See the repository root `README.md` for the full product story, and
`docs/API_REFERENCE.md` for the endpoint contract.

## Install (editable, from the repository root)

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"
```

## Run (SQLite quick start)

```bash
backend/.venv/bin/python -m uvicorn vendorlens.api.app:app \
    --app-dir backend --host 127.0.0.1 --port 8000
```

The API serves at http://localhost:8000 (docs at `/docs`). Requires the
trained model bundle — run `make train` from the repository root first if
`artifacts/model_bundle.joblib` is missing.

## Test

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```
