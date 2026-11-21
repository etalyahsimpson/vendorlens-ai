#!/usr/bin/env bash
# Full local verification pipeline (Docker-independent). Mirrors the GitHub
# Actions jobs: dataset generation, model training, backend tests, frontend
# typecheck + production build, and Playwright end-to-end flows.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/backend/.venv/bin/python}"
cd "$ROOT"

echo "== [1/6] Backend environment =="
"$PYTHON" -c "import faiss, mlflow, sklearn, fastapi, sqlalchemy; print('faiss OK · mlflow', mlflow.__version__, '· sklearn', sklearn.__version__)"

echo "== [2/6] Regenerate deterministic dataset =="
"$PYTHON" backend/scripts/generate_dataset.py

echo "== [3/6] Train + evaluate the model =="
"$PYTHON" backend/scripts/train_model.py

echo "== [4/6] Backend test suite =="
(cd backend && "${PYTHON}" -m pytest tests/ -q)

echo "== [5/6] Frontend typecheck + production build =="
(cd frontend && npm run build)

echo "== [6/6] Playwright end-to-end =="
bash scripts/e2e-run.sh

echo ""
echo "ALL LOCAL CHECKS PASSED"
