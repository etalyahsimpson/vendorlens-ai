# Data Dictionary

## Input CSV schema (uploads and bundled sample)

| Column | Required | Type | Rules | Example |
|---|---|---|---|---|
| `supplier_id` | yes | string | Nonempty; **unique within the file**; control characters stripped | `SUP-0107` |
| `supplier_name` | yes | string | Nonempty; compared after normalization; original preserved | `Northstar Industrial Supplies LLC` |
| `street_address` | no | string | Missing → `address_missing` feature, never a match/mismatch | `1200 Market St` |
| `city` | no | string | Compared case-insensitively | `Philadelphia` |
| `state` | no | string | Compared uppercased | `PA` |
| `postal_code` | no | string | Compared with whitespace removed | `19103` |
| `country` | no | string | Stored, not currently a matching feature | `USA` |
| `website` | no | string | Reduced to bare domain for comparison (scheme/`www.`/path stripped) | `https://www.acme.example/about` |

**Limits:** `.csv` files only · ≤ 5 MB · ≤ 2,000 data rows · UTF-8 (BOM
accepted). Unknown columns are ignored and reported as warnings. Duplicate
`supplier_id`s, missing required headers/values, empty files and undecodable
content fail with structured validation errors (see
[API_REFERENCE.md](API_REFERENCE.md)).

## Bundled sample dataset

`data/sample_suppliers.csv` (78 records) is a deterministic subset of the
generated register: ordinary duplicate clusters, hard-negative lookalike
sibling pairs, and namesake companies, with realistic missing fields. It is
**the same shape as an upload** — it contains no labels. Provenance: generated
by `backend/vendorlens/data/generator.py` (seed 42); all records fictional.

## Labeled benchmark dataset (pipeline only)

`data/generated/suppliers_labeled.csv` adds one column used exclusively by the
training/evaluation pipeline:

| Column | Type | Meaning |
|---|---|---|
| `canonical_entity_id` | string | Ground-truth entity identity (`ENT-0001`…). **Never** a model feature, never exported by the API, never included in the sample CSV. |

## Recommendation bands

| Band | Score range (current bundle) | Meaning |
|---|---|---|
| `likely_match` | ≥ 0.93 | High-confidence duplicate — still requires human confirmation |
| `needs_review` | 0.02 – 0.93 | Mixed evidence — human judgment required |
| `unlikely_match` | < 0.02 | Distinct records |

Thresholds are selected on validation data by the training pipeline and stored
in the model bundle (see [ML_METHODOLOGY.md](ML_METHODOLOGY.md)).

## Review decisions

| Value | UI label |
|---|---|
| `confirm_same` | Confirm same entity |
| `reject_match` | Not the same entity |
| `needs_investigation` | Needs investigation |

Decisions are persisted per suggestion (one per suggestion, upsertable) with
optional notes (≤ 500 chars) and a review timestamp.

## Export report columns

`GET /api/v1/analyses/{id}/export` produces CSV with columns:

```
pair_id, analysis_id,
left_supplier_id, left_supplier_name, left_city, left_state, left_website,
right_supplier_id, right_supplier_name, right_city, right_state, right_website,
model_score, recommendation_band,
name_similarity, website_evidence, city_evidence, postal_evidence,
review_decision, review_notes, reviewed_at
```

- `model_score` — classifier probability for the pair (0–1).
- `recommendation_band` — `Likely match` / `Needs review` / `Unlikely match`.
- Evidence columns reproduce the values shown in the review workspace
  (`same` / `different` / `missing`, name similarity 0–1).
- `review_decision` is empty until a human decides; otherwise the decision
  label. Original supplier identifiers and field values are preserved.
- **Formula neutralization:** any cell beginning with `=`, `+`, `-`, `@`, tab
  or CR is prefixed with `'` so spreadsheet applications render it as text.
  This transformation is applied to every exported cell and is asserted by
  `tests/test_api.py::test_export_neutralizes_formula_injection`.

## Matching signals (per suggestion)

`signals` JSON returned by the matches endpoint:

| Key | Values |
|---|---|
| `name_similarity` | 0–1 normalized-name character similarity |
| `name_evidence` | `strong` (≥0.85) / `moderate` (≥0.6) / `weak` |
| `token_jaccard` | 0–1 shared-word overlap |
| `legal_suffix` | `same` / `different` / `missing` |
| `city`, `state`, `postal_code`, `website` | `same` / `different` / `missing` |
| `address_similarity` | 0–1 or `missing` |
