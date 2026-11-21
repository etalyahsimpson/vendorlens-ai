# Engineering Decisions

A record of the significant trade-offs made in VendorLens AI and why.

## ML design

**Logistic regression instead of deep learning.** The dataset is small
(~850 records, ~2,700 labeled pairs), tabular, and benefits from inspectable
weights. A `StandardScaler + LogisticRegression(class_weight="balanced")`
pipeline trains in seconds, stays deterministic, and makes every prediction
explainable from 19 named features — which matters for a product whose value
proposition is *evidence for human reviewers*. Gradient-boosted trees or a
siamese text network might squeeze out extra F1 but would obscure the signal
attribution and complicate reproducibility. Deep NLP matching is listed as
future work, not a claim.

**FAISS + blocking instead of brute force.** All-pairs comparison is O(n²):
2,000 uploaded rows would mean ~2M pairs. Character n-gram TF-IDF + SVD
embeddings with `faiss.IndexFlatIP` top-8 retrieval plus deterministic
website / city+postal blocking keeps candidate sets near-linear (the demo's
78 records produce 388 pairs, not 3,003). `IndexFlatIP` (exact search) was
chosen over IVF/HNSW because at this scale exactness costs nothing and
removes index-tuning from the reproducibility story. A NumPy exact fallback
exists only for platforms that cannot install `faiss-cpu`; the health
endpoint and metrics report distinguish the engines.

**Baseline rule kept in the product.** The deterministic name-similarity rule
is evaluated on the same held-out pairs as the trained model and appears in
the UI and reports. It anchors the claim that the trained model adds value
(F1 0.8548 → 0.9643) and gives future contributors a regression canary.

**Thresholds from validation, frozen before test.** Bands are selected on
the validation split only; the test split is scored once. Because scores are
strongly bimodal, a plain F1-maximizing threshold collapsed all bands to one
point (0.2), so band edges combine precision/recall criteria with score
percentiles (5th of true matches, 95th of true non-matches) to preserve a
genuine *needs review* band.

**Entity-disjoint splits.** Splitting by canonical entity (not record) is the
only way to measure generalization to *unseen suppliers* rather than memorized
aliases. The TF-IDF/SVD representation is likewise fitted on training names
only. Tests assert the disjointness and that no label/split identifier can
enter the feature path.

**Per-analysis FAISS index over the training-fitted embedding.** At serving
time the bundle's vectorizer/SVD are *applied* (never refit), and a fresh
index is built over the upload's vectors. This keeps retrieval consistent
with the validated representation while scaling to whatever the analyst
uploads.

## Application design

**Human-in-the-loop by construction.** The API has no merge/delete/route
endpoint for supplier records — only `PATCH …/review` on suggestions.
Recommendations cannot become facts without a stored human decision; the
export separates `recommendation_band` from `review_decision`.

**PostgreSQL via Docker Compose, SQLite for quick start.** The compose stack
(PostgreSQL 16 + backend + nginx frontend) is the primary developer
experience; SQLite removes friction for a one-command local try and powers
the test suite, with a CI job dedicated to the PostgreSQL path. The schema is
four tables and intentionally narrow, so `Base.metadata.create_all` at startup
is reproducible without a migration framework — for a portfolio-scale schema,
migrations would be ceremony without benefit.

**FastAPI + Pydantic + SQLAlchemy 2.0 typed models.** Request/response
contracts, CSV row shape, and ORM rows are all typed; the OpenAPI page is
generated from the same schemas the frontend's TypeScript types mirror.

**Vite SPA with a simple view state.** Four views (overview, upload, review,
model) managed with `useState` — no router, no Redux/Zustand/React Query.
Server state lives in the database (that is the product's point); the only
client persistence is the last analysis id in `localStorage` so a reload
restores the working session. Axios calls are typed and normalized into one
error type the UI renders consistently.

**Export neutralization.** CSV export is a classic spreadsheet-formula
injection vector; every cell passes a documented `'`-prefix neutralizer with
a dedicated test covering `=`, `+`, `-`, `@`, tab and CR payloads.

## Process decisions

**Deterministic everything.** Fixed seed (42) for the generator, seeded
numpy generators for splits/negative sampling, pinned dependency versions,
deterministic FAISS search, and a byte-identical regeneration test. A reader
can reproduce every number in the README.

**Committed artifacts.** The trained bundle, model card, labeled dataset,
metrics and figures are committed so the repository works immediately after
clone — CI re-trains from scratch to prove the artifacts are reproducible
rather than taking them on faith.

**Local MLflow.** Experiment tracking must not require an account; a file
store under `./mlruns` (git-ignored) with run IDs recorded in metrics.json
gives durable evidence without repository bloat.

**Playwright as the only frontend test layer.** The critical frontend risks
are integration-level (proxy, error surfacing, persistence, accessibility of
the review flow), so end-to-end browser tests cover the golden paths and
capture the screenshots the README shows. Type-checking and the production
build gate the rest.
