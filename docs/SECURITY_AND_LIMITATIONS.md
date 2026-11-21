# Security and Limitations

VendorLens AI is **local demonstration software** built as an independent
engineering portfolio project. This page documents its security posture and
the boundaries of what it claims to do.

## Untrusted input handling

Uploads are treated as untrusted **data**, never code:

- **CSV only.** Non-`.csv` extensions are rejected before parsing.
- **Size and row limits.** 5 MB / 2,000 rows, enforced with descriptive
  validation errors rather than silent truncation.
- **Encoding.** Only UTF-8 (with BOM tolerance) is accepted; undecodable
  files are rejected with a helpful message, never a traceback.
- **Control characters** (C0/C1) are stripped from every field before
  storage or display.
- **React renders all supplier text as text nodes** — no `dangerouslySetInnerHTML`
  anywhere in the codebase, so uploaded content cannot inject HTML/scripts.
- **No formula execution.** Nothing uploaded is evaluated as a spreadsheet
  formula, macro, script or Python expression. On export, any cell beginning
  with `=`, `+`, `-`, `@`, tab or CR is prefixed with a single quote
  (documented transformation; covered by an explicit injection test).
- **Ground-truth labels cannot leak.** Canonical-entity IDs exist only inside
  the training pipeline; the sample CSV, every API response and the feature
  computation path have no access to them.

## Application boundaries

- **No authentication / multi-tenancy.** The API is designed to bind to
  localhost for individual evaluation. Do not expose it to the open internet
  as-is: an unauthenticated upload endpoint would let anyone create analyses
  on your machine.
- **CORS** is a narrow allowlist of localhost development origins
  (configurable via `VENDORLENS_CORS_ORIGINS`).
- **No data leaves the machine.** No third-party AI services, no external
  model APIs, no telemetry. MLflow tracking is a local file store.
- **Never publish real uploaded files.** Only the generated sample data ships
  in this repository. Real supplier registers may contain personal or
  commercially sensitive data.

## Model and product limitations

- The model is a **recommendation engine**, not a legal-identity verifier.
  Identical names can be different businesses; different names can be one
  business.
- **No automatic merges or deletions.** Every consolidation requires an
  explicit human decision; nothing in the system mutates or removes source
  records.
- Metrics come from the **included synthetic benchmark** (seed 42). They are
  not estimates of real-world accuracy. See
  [ML_METHODOLOGY.md](ML_METHODOLOGY.md).
- Recommendation bands are **demonstration defaults** calibrated on validation
  data — not universal business rules.
- No production SLA, uptime guarantee, audit logging, or role-based access.

## Data retention

- Analyses, records, suggestions and decisions are stored in the configured
  database (PostgreSQL in Docker Compose, SQLite in the quick start) on your
  machine only.
- Uploaded file bytes are parsed and discarded; only validated fields are
  persisted.
- Clearing the database (or the SQLite file) removes all analysis data.

## Reporting

This project has no known unresolved security issues. If you find one, please
open a GitHub issue at
https://github.com/etalyahsimpson/vendorlens-ai/issues.
