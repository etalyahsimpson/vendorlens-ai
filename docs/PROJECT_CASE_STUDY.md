# Project Case Study

**Product:** VendorLens AI — Intelligent Supplier Identity Resolution &
Duplicate Detection
**Classification:** Independent machine-learning engineering portfolio project
(procurement data quality). Not built for, endorsed by, or affiliated with any
employer.

## 1. The business problem

Procurement, finance and operations teams maintain supplier master data
imported from divisions, ERPs and spreadsheets. The same vendor reappears
under abbreviations, punctuation variants, old addresses and inconsistent
legal suffixes; meanwhile, similar names often belong to *different* legal
entities. Exact-string matching over-merges and under-finds; manual deduplication
doesn't scale; and silent duplicates leak into spend analysis, payments and
vendor risk.

```
SUP-0107  Northstar Industrial Supplies LLC   Philadelphia PA  northstarindustrial.example
SUP-0320  North Star Industrial Supply        Philadelphia PA  northstarindustrial.example   ← possibly the same
SUP-0458  Northstar Office Services LLC       Philadelphia PA  northstaroffice.example       ← different company
```

## 2. Requirements

1. Import supplier registers (CSV) or open a bundled sample; validate against
   a documented schema with hard limits.
2. Surface *candidate* duplicate pairs with per-field evidence — never merge
   automatically.
3. Score candidates with a genuinely trained, reproducible model; compare
   against a deterministic baseline on held-out data.
4. Route uncertain pairs to human review; persist decisions and export a full
   findings report.
5. Run locally end-to-end (Docker Compose or quick start), with CI proving
   tests, training, Playwright flows and packaging.

## 3. Solution architecture

| Layer | Choice | Why |
|---|---|---|
| Candidate retrieval | char n-gram TF-IDF → SVD → **FAISS** top-8 + website/city+postal blocking | Avoids O(n²); 100% candidate recall on the benchmark |
| Pair model | `StandardScaler + LogisticRegression(class_weight="balanced")` on 19 interpretable features | Small data, explainable, deterministic |
| Evaluation | canonical-entity-disjoint splits (204/44/44 entities); thresholds from validation only | Prevents identity leakage; honest generalization |
| Tracking | MLflow local file store, baseline + model runs with artifacts | Reproducible evidence, no external accounts |
| Serving | FastAPI + Pydantic + SQLAlchemy; PostgreSQL (Compose) with SQLite quick start | Typed contracts, quick evaluation |
| Review UI | React + Vite + TypeScript + Tailwind with Axios | Responsive, accessible review workspace |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full component map and
[ML_METHODOLOGY.md](ML_METHODOLOGY.md) for the pipeline narrative.

## 4. Working interface

- **Overview** — problem framing, live counts from the active analysis, and
  one-click *Explore Sample Data* / *Upload Supplier CSV*.
- **Review workspace** — ranked suggestions with score bars, evidence chips
  (name/website/city/postal/suffix), band badges, filters and search, an
  expandable side-by-side comparison drawer, and decision controls
  (confirm / reject / investigate) persisted server-side.
- **Model evidence** — held-out precision/recall/F1, confusion matrix,
  baseline comparison, thresholds, feature definitions and links to the full
  methodology.
- **Export** — CSV report with model output and human decisions, formula
  neutralization applied.

All screenshots in the README are captured from the running application by
the Playwright suite (`assets/screenshots/`).

## 5. Verified outcomes (measured, not asserted)

Held-out test split (44 unseen entities, 128 records, 135 positive / 591
negative pairs; seed 42):

| Approach | Precision | Recall | F1 |
|---|---|---|---|
| Deterministic baseline rule | 0.9381 | 0.7852 | 0.8548 |
| Trained model | 0.9310 | 1.0000 | **0.9643** |

- Candidate retrieval recall: **1.000** (validation) / **1.000** (test).
- 29 true duplicates recovered that the baseline misses (FN 29 → 0), for 3
  additional false positives — the right trade when a missed duplicate stays
  hidden while a false positive costs one analyst review.
- 82 backend tests, 9 Playwright end-to-end flows, production frontend build,
  and Docker packaging all pass in CI on the final commit.

*Metrics are measured on the included synthetic benchmark dataset and are not
estimates of real-world accuracy.*

## 6. Key engineering decisions

- **Entity-disjoint splits before pair sampling** — the model is evaluated on
  suppliers it has never seen.
- **19 interpretable features** computed by identical code in training and
  serving; missing fields become missingness indicators, never false evidence.
- **Human-in-the-loop by API design** — there is no merge endpoint; decisions
  are stored facts and appear in exports.
- **Determinism as a feature** — seed 42, byte-identical dataset regeneration,
  pinned dependencies, reproducible metrics.
- Further rationale: [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md).

## 7. Risks and next steps

- **Generalization:** the benchmark encodes generated corruption patterns;
  real registers add OCR noise, transliteration and M&A history. Next step:
  plug in a real (anonymized) register and recalibrate bands.
- **Model upgrades:** gradient-boosted trees or a lightweight text-embedding
  siamese model behind the same feature/evidence contract.
- **Scale:** ANN indexes (IVF/HNSW), blocking on phonetic keys, and incremental
  analysis for registers beyond 2,000 rows.
- **Operations:** authentication, audit logs and role separation before any
  multi-user deployment.

## 8. Professional context

This project demonstrates the supplier entity-resolution skill set — Python
ML engineering with scikit-learn/Pandas/NumPy, FAISS similarity search,
MLflow experiment tracking, quantitative evaluation, and FastAPI serving —
developed in the spirit of independent portfolio work aligned with a
**Machine Learning Engineer** background (Altana AI, May 2024 – Feb 2026,
per the current CV). VendorLens AI itself is an independent project; no
employer data, customers, or proprietary systems were used.
