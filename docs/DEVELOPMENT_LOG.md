# Development Log

A factual technical record of the VendorLens AI build: what was implemented,
what failed, what was fixed, and how it was verified. Dates are UTC.

## Phase 1 — Environment and scaffolding

- Verified toolchain: Python 3.12.16, Node 24, npm 11, git 2.47; installed
  GitHub CLI 2.63.2 (binary) for repository publication. Docker is not
  available in the build sandbox — Docker packaging is verified in CI.
- Created the repository layout (`backend/`, `frontend/`, `data/`, `artifacts/`,
  `reports/`, `assets/`, `docs/`, `scripts/`, `tests/e2e/`, `.github/workflows/`)
  with `.gitignore`, `.dockerignore`, `.env.example`, `LICENSE_NOTICE.md`.
- Backend venv with pinned dependencies (fastapi 0.115.6, scikit-learn 1.6.0,
  faiss-cpu 1.9.0.post1, mlflow 2.17.2, SQLAlchemy 2.0.36, psycopg 3.2.3,
  pandas 2.2.3, numpy 2.1.3, scipy 1.14.1, matplotlib 3.9.3, …).

## Phase 2 — ML core

- Implemented the deterministic generator (seed 42): 292 canonical entities /
  850 records with alias corruption, 40 hard-negative sibling pairs, 12
  namesake companies; sample CSV selection mixes clusters, siblings and
  namesakes.
  - *Fix:* initial version wrote outputs to the repository root instead of
    `data/` — corrected path handling in `generate_all()`.
  - *Fix:* sample selection originally guaranteed only "some sibling
    entities"; refactored to `generate_labeled_dataset_with_meta()` so both
    sides of sibling pairs and namesake pairs are deterministically included,
    giving the demo all three recommendation bands.
  - *Fix:* namesake entities initially had a single record, violating the
    2–4-records-per-entity contract; each namesake now contributes 2 records.
- Implemented normalization (suffix stripping as feature transformation,
  website domain canonicalization, address abbreviation map, control-character
  stripping).
- Implemented candidate retrieval: char_wb 2–4-gram TF-IDF → TruncatedSVD(48)
  → float32 L2 → `faiss.IndexFlatIP` top-8, unioned with website and
  city+postal blocking; 6,000-pair bound; NumPy exact fallback.
- Implemented 19 pair features with tri-state present/present-different/
  missing indicators and a human-readable signals builder.

## Phase 3 — Training, evaluation, MLflow

- First end-to-end training run succeeded (baseline F1 0.8618, model F1 0.9640).
  - *Issue found:* the F1-maximizing validation threshold collapsed all three
    recommendation bands to a single point (0.2) because scores are strongly
    bimodal — the "needs review" band would have been empty.
    *Fix:* band selection now combines precision ≥ 0.97 / recall ≥ 0.98
    thresholds with score-distribution percentiles (P05 of true-match scores,
    P95 of true-non-match scores), yielding bands 0.93 / 0.02–0.93 / <0.02.
  - *Issue found:* `scipy 1.18` emitted an lbfgs warning; pinned `scipy 1.14.1`.
  - *Issue found:* MLflow artifact logging happened outside the active run
    context and a second in-process training run inherited stale fluent state.
    *Fix:* bundle serialization + `log_artifact` moved inside the model run;
    reports attached via `MlflowClient.log_artifact`; defensive
    `mlflow.end_run()` guard added.
- Final measured results (test split): baseline P 0.9381 / R 0.7852 / F1
  0.8548; model P 0.9310 / R 1.0000 / F1 0.9643; candidate recall 1.000/1.000;
  confusion matrices and difficult cases written to `reports/metrics.json`,
  `reports/model_evaluation.md`, `reports/figures/`.
- Sanity-checked the product behaviour on crafted cases: true alias pair with
  URL-form variance scores 1.000 (likely); identical name + different
  city/website scores 0.159 (needs review) — nothing is auto-confirmed.

## Phase 4 — API and persistence

- Implemented SQLAlchemy models (AnalysisSession, SupplierRecord,
  MatchSuggestion, ReviewDecision), engine/session with SQLite and PostgreSQL
  support, reproducible `create_all` initialization.
- Implemented CSV validation (extension/size/rows/encoding/headers/unique IDs/
  control characters/unknown-column warnings) with structured errors.
- Implemented services: analysis orchestration, review upsert, export with
  per-cell formula neutralization.
- Implemented FastAPI: 9 documented endpoints + sample download, CORS
  allowlist, normalized error handler, health with model/db/engine status.
- TestClient smoke run verified the full flow (demo → matches → review →
  filtered matches → export → metrics → 404 shape).

## Phase 5 — Test suite

- 84 tests written across 9 files (validation, normalization, generator,
  candidates incl. FAISS-specific assertions, features incl. leakage guards,
  training incl. reproducibility + real MLflow runs, API, export, PostgreSQL
  integration).
  - *Fix:* two tests passed `str` instead of `bytes` to the validator; one
    "missing value" test row used a quoted-space pattern that CSV parsing
    kept nonempty — replaced with a truly empty field.
  - *Fix:* the formula-injection test asserted `payload not in export`, which
    false-positives on the neutralized form (`'=…` contains `=…`). Replaced
    with cell-level assertions (no exported cell may start with a formula
    prefix) plus presence checks for the neutralized payloads.
- Final local result: **82 passed, 2 skipped** (the 2 skips are the PostgreSQL
  tests, which execute against a real PostgreSQL service in CI).

## Phase 6 — Frontend

- Built the React/Vite/TS/Tailwind SPA: overview, upload with drag & drop +
  schema docs, review workspace (summary cards, band/decision/search filters,
  sortable table, comparison drawer, decision controls with notes), model
  evidence (metrics, confusion matrix, baseline table, thresholds, features,
  methodology links), export, toasts, sticky footer with the required
  "Official Portfolio" link to `https://etalyahsimpson.github.io/`.
  - *Fix:* `tsc` flagged unused imports and a missing `@types/node`; corrected.
  - *Fix:* upload errors fell through to a generic "Upload failed." because
    the raw AxiosError wasn't normalized — routed through `toRequestError`
    so the API's structured message (e.g. "Required columns are missing…")
    reaches the user.

## Phase 7 — Playwright e2e and screenshots

- 9 browser flows: overview copy/links, sample analysis, evidence rendering,
  band filters, comparison drawer, decision persistence across reload,
  export download, invalid upload error, valid upload flow, model page.
  - *Fixes (locator precision):* strict-mode violations for duplicated
    buttons/text ("Explore Sample Data" appears twice by design; "Needs
    review" appears in badges and filters; "Precision" in cards and headers)
    resolved with `.first()`/exact matches; the dropzone is located by its
    accessible name; "Review decision" matched by role.
  - *Fix (reload flow):* after reload the SPA correctly returns to the
    overview with the analysis restored; the persistence test now navigates
    back into the workspace and asserts the decision served from the database.
- Captured five authentic screenshots (overview desktop fullPage, review
  workspace, comparison drawer, model performance, mobile 390px) from the
  running application.
- UI polish pass driven by an independent visual review: removed the truncated
  step-card clamp, added `whitespace-nowrap` to decision placeholders, widened
  name columns, added numeric column padding in the baseline table, waited for
  transient toasts before capturing.

## Phase 8 — Packaging and verification

- Wrote backend/frontend Dockerfiles (non-root, healthcheck, nginx proxy),
  docker-compose (PostgreSQL 16 + backend + frontend), Makefile, e2e runner
  and full `scripts/verify.sh`.
- Full local verification passed: environment check → dataset regeneration →
  training (real MLflow runs) → 82 backend tests → typecheck + production
  build → 9 Playwright flows. ("ALL LOCAL CHECKS PASSED".)

## Phase 9 — Documentation and assets

- Hand-authored `assets/banner.svg`; rendered `assets/social-preview.png`
  (1280×640) and `assets/portfolio-card.png` (1200×675) from owned HTML via
  Playwright at exact dimensions.
  - *Fix:* banner subtitle initially collided with the record-card motif;
    wrapped to two lines and re-verified visually.
- Wrote ARCHITECTURE, ML_METHODOLOGY, DATA_DICTIONARY, SECURITY_AND_LIMITATIONS,
  API_REFERENCE, ENGINEERING_DECISIONS, PROJECT_CASE_STUDY, SKILLS_EVIDENCE,
  PORTFOLIO_INTEGRATION, this log, data/README, backend/README and the root
  README — all numbers cross-checked against `reports/metrics.json`.

## Phase 10 — CI and publication

- GitHub Actions workflow with jobs: backend tests (incl. FAISS/MLflow), a
  PostgreSQL-service integration job, frontend typecheck+build, Playwright
  e2e, Docker image builds, and a compose health smoke.
- Published to `etalyahsimpson/vendorlens-ai` (public, main branch), then
  iterated on remote CI results until all jobs passed on the final commit.
  See the README CI badge and the release report for run URLs.
