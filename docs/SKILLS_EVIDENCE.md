# Skills Evidence

Every claim below points to real code, tests or commands in this repository.
Technologies are separated into (A) skills listed in the current CV that this
project genuinely exercises, and (B) supporting tools chosen for this project
that are **not** claimed as pre-existing CV competencies.

## A. CV-listed technologies exercised in this project

| Technology | Where it is genuinely used | Verification |
|---|---|---|
| **Python 3.11+** | Entire backend; `backend/pyproject.toml` (`requires-python >=3.11`) | CI runs the suite on Python 3.12 |
| **scikit-learn** | TF-IDF, TruncatedSVD, StandardScaler, LogisticRegression — `backend/vendorlens/ml/candidates.py`, `training.py` | `tests/test_training.py` (trained F1, reproducibility); `reports/metrics.json` |
| **Pandas** | Dependency of the data stack; CSV/report handling conventions — `backend/vendorlens/services/export.py` (csv module used for streaming exports) | `pip list` in CI; export tests |
| **NumPy** | Vector math, L2 normalization, metrics — `candidates.py`, `training.py` | `tests/test_candidates.py` |
| **FAISS (vector similarity)** | Real `faiss.IndexFlatIP` top-8 retrieval in the request path — `candidates.py` | `tests/test_candidates.py::test_faiss_is_genuinely_available_and_used`, `test_faiss_index_is_indexflatip` |
| **MLflow** | Baseline + model runs with params/metrics/artifacts to a local store — `training.py` | `tests/test_training.py::test_mlflow_runs_actually_logged` (asserts FINISHED runs and logged artifacts); run IDs in `reports/metrics.json` |
| **FastAPI** | All 9 API endpoints + OpenAPI — `backend/vendorlens/api/` | `tests/test_api.py`; `/docs` |
| **Pydantic** | Typed request/response contracts — `backend/vendorlens/api/schemas.py`, settings in `config.py` | API validation tests (422 shapes) |
| **PostgreSQL** | Primary database via Docker Compose; CI service integration | `tests/test_api_postgres.py` executed against a real PostgreSQL service in CI |
| **React** | Review workspace, overview, upload, model evidence — `frontend/src/` | Playwright e2e; production build |
| **TypeScript** | Strict-mode frontend (`tsc --noEmit` in build) | `make typecheck` / CI job |
| **Tailwind CSS** | Design system (navy/teal/amber palette, accessible components) — `frontend/tailwind.config.js`, `src/index.css` | Visual e2e + screenshots |
| **pytest** | 82 backend tests: validation, normalization, retrieval, leakage, training, API, export | `make test`; CI job |
| **Playwright** | 9 browser flows incl. persistence, export, invalid upload + authentic screenshots — `tests/e2e/` | `make e2e`; CI job |
| **Docker** | Backend + frontend images, PostgreSQL compose stack — `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` | Docker build job in CI |
| **Linux / Bash** | `scripts/verify.sh`, `scripts/e2e-run.sh`, Makefile | Executed locally and in CI |
| **Git / GitHub** | Repository, commits, Actions workflows, protected verification | `.github/workflows/ci.yml`; commit history |

## B. Project-specific supporting tools (not CV-listed, used and reported honestly)

| Tool | Use | Where |
|---|---|---|
| **Vite** | Frontend dev server and production bundler | `frontend/vite.config.ts` |
| **Axios** | Typed HTTP client with normalized error handling | `frontend/src/api/client.ts` |
| **SQLAlchemy** | ORM models/sessions (typed 2.0 style) | `backend/vendorlens/db/` |
| **GitHub Actions** | CI: tests, training, builds, Playwright, Docker | `.github/workflows/ci.yml` |
| **Docker Compose** | One-command full stack | `docker-compose.yml` |
| **matplotlib** | Evaluation figures generated from measured results | `training.py::_make_figures` → `reports/figures/` |

## C. CV-listed technologies intentionally NOT used in this project

These remain listed skills on the CV but are deliberately out of scope for
VendorLens AI (a focused classical-ML project), and are **not** claimed as
exercised here: PyTorch, Hugging Face Transformers, Weights & Biases, Label
Studio, Pinecone, LangChain/RAG, Next.js, Redis, MongoDB, Salesforce stack,
Jest, Postman. See [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md) for
why the scope was kept narrow, and the README roadmap for where these would
enter future work.

## D. Verification commands

```bash
make generate   # deterministic dataset (seed 42)
make train      # train + evaluate + MLflow runs + reports
make test       # 82 backend tests
make typecheck  # strict TypeScript
make build      # production frontend build
make e2e        # 9 Playwright browser flows
make docker-up  # PostgreSQL + FastAPI + nginx frontend
```

Each command is exercised by the local verification script
(`scripts/verify.sh`) and by the GitHub Actions workflow on every push.
