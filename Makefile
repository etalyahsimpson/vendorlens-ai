# VendorLens AI - developer entrypoints.
#
# Quick start (no Docker):
#   make setup      # create the backend venv + install frontend/e2e deps
#   make train      # generate the dataset, train + evaluate the model
#   make backend    # start FastAPI (SQLite) on :8000
#   make frontend   # start Vite dev server on :5173 (proxies /api)
#
# Docker (PostgreSQL stack):
#   make docker-up  # builds and starts db + backend + frontend (:8080)
#
# Verification:
#   make test       # backend pytest suite
#   make e2e        # Playwright browser flow (needs backend+frontend running)
#   make verify     # full local verification used before publishing

SHELL := /bin/bash
PYTHON := backend/.venv/bin/python
PIP := backend/.venv/bin/pip

.PHONY: setup backend frontend generate train test e2e e2e-run docker-up docker-down \
        mlflow-ui verify clean typecheck build

setup:
	python3 -m venv backend/.venv
	$(PIP) install --upgrade pip
	$(PIP) install -e "backend[dev]"
	cd frontend && npm ci
	cd tests/e2e && npm ci && npx playwright install --with-deps chromium

generate:
	$(PYTHON) backend/scripts/generate_dataset.py

train: generate
	$(PYTHON) backend/scripts/train_model.py

backend:
	DATABASE_URL=sqlite:///./backend/vendorlens.db uvicorn vendorlens.api.app:app \
		--app-dir backend --host 127.0.0.1 --port 8000 --reload

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python -m pytest tests/ -q

typecheck:
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

# Requires: backend on :8000 (make backend) and built frontend (make build).
e2e: build
	bash scripts/e2e-run.sh

# Full pipeline used before publishing (does NOT require Docker).
verify:
	bash scripts/verify.sh

docker-up:
	docker compose up --build -d
	@echo "Frontend: http://localhost:8080  |  Backend: http://localhost:8000/docs"

docker-down:
	docker compose down

mlflow-ui:
	$(PYTHON) -m mlflow ui --backend-store-uri ./mlruns --port 5000
	@echo "MLflow UI: http://localhost:5000"

clean:
	rm -rf frontend/dist tests/e2e/test-results tests/e2e/playwright-report
	rm -f backend/vendorlens.db
	find backend -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
