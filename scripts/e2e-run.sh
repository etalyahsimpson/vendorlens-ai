#!/usr/bin/env bash
# Start the backend (SQLite) and a built frontend, then run the Playwright
# e2e suite against them. Used by `make e2e` and the CI workflow.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backend/.venv/bin/python}"
BACKEND_PID=""
FRONTEND_PID=""
mkdir -p "$ROOT/.local-run"

cleanup() {
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

cd "$ROOT"

# 1. Backend (SQLite quick-start configuration).
if [ ! -f artifacts/model_bundle.joblib ]; then
  echo ">> model bundle missing; training first"
  "$PYTHON" backend/scripts/generate_dataset.py
  "$PYTHON" backend/scripts/train_model.py
fi

DATABASE_URL="sqlite:///$ROOT/.local-run/e2e.db" \
  "$PYTHON" -m uvicorn vendorlens.api.app:app \
  --app-dir "$ROOT/backend" --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/api/v1/health > /dev/null; then break; fi
  sleep 1
done
echo ">> backend ready"

# 2. Frontend (production build + preview with /api proxy).
if [ ! -d frontend/dist ]; then
  (cd frontend && npm run build)
fi
(cd frontend && VITE_BACKEND_URL=http://127.0.0.1:8000 npx vite preview --port 4173 --strictPort --host 127.0.0.1) &
FRONTEND_PID=$!

for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:4173/ > /dev/null; then break; fi
  sleep 1
done
echo ">> frontend ready"

# 3. Playwright (baseURL points at the preview server; it resolves via
#    localhost, so force IPv4/IPv6 resolution consistently).
cd tests/e2e
E2E_BASE_URL="http://127.0.0.1:4173" npx playwright test "$@"
