# Portfolio Integration

Reusable metadata for including VendorLens AI on the reserved personal
portfolio root, **https://etalyahsimpson.github.io/**. That site is not
launched yet and must not be created or modified as part of this repository —
this page only prepares the material for later inclusion.

## Card summary (one sentence)

VendorLens AI — an end-to-end supplier identity-resolution product: FAISS
candidate retrieval, an entity-disjoint trained classifier, human review
workflow, and reproducible MLflow-tracked evaluation.

## Quick facts

| Field | Value |
|---|---|
| Title | VendorLens AI |
| Subtitle | Intelligent Supplier Identity Resolution & Duplicate Detection |
| Classification | Independent ML engineering portfolio project |
| Repository | https://github.com/etalyahsimpson/vendorlens-ai |
| Live app | None (local demonstration software; no hosted deployment claimed) |
| Role framing | Machine Learning Engineer skill set (see docs/SKILLS_EVIDENCE.md) |
| Primary stack | Python · scikit-learn · FAISS · MLflow · FastAPI · PostgreSQL · React · TypeScript · Tailwind · Playwright · Docker |

## Card artwork

- Landscape card image (1200×675): [`assets/portfolio-card.png`](../assets/portfolio-card.png)
- Banner (1200×400 SVG): [`assets/banner.svg`](../assets/banner.svg)
- Social preview (1280×640): [`assets/social-preview.png`](../assets/social-preview.png)

Use relative paths from the repository when embedding; do not hotlink forks.

## Suggested portfolio card copy

> **VendorLens AI** — Supplier identity resolution & duplicate detection.
> Imports messy supplier registers, retrieves candidate duplicates with FAISS
> similarity search, scores them with a trained classifier over 19
> interpretable features, and routes uncertain matches to a human review
> workspace with evidence, decisions, and CSV export. Measured on a seeded
> synthetic benchmark with entity-disjoint splits: F1 0.964 vs 0.855 baseline.
> FastAPI · React · PostgreSQL · MLflow · Docker · CI-verified.

## Application screenshots (current, authentic)

| View | Path |
|---|---|
| Overview (desktop) | `assets/screenshots/overview.png` |
| Review workspace | `assets/screenshots/review-matches.png` |
| Comparison drawer & decision | `assets/screenshots/comparison-review.png` |
| Model performance | `assets/screenshots/model-performance.png` |
| Overview (mobile 390px) | `assets/screenshots/overview-mobile.png` |

All images are captured from the running application by the Playwright suite
and re-captured whenever the UI changes.

## Linking rules

- Link the label **"Official Portfolio"** to the exact root
  `https://etalyahsimpson.github.io/` (no subpath, no project page).
- Do not describe the portfolio site as live or verified — it is reserved for
  future launch.
- Do not create or modify the `etalyahsimpson.github.io` repository from this
  project; do not enable a project-specific GitHub Pages site for
  `vendorlens-ai`.
