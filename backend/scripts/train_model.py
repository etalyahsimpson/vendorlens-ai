#!/usr/bin/env python3
"""Train, evaluate and export the supplier-matching model.

Runs the full pipeline: entity-disjoint splits, FAISS candidate retrieval,
pair features, baseline rule, logistic regression, threshold selection on
validation, held-out test evaluation, MLflow tracking, artifact bundle and
reports. Deterministic for a fixed dataset and seed.

Run from the repository root:  python backend/scripts/train_model.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from vendorlens.config import repo_root
from vendorlens.data.generator import SEED
from vendorlens.ml.training import run_training


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--labeled-csv",
        type=Path,
        default=None,
        help="Path to the labeled dataset (default: data/generated/suppliers_labeled.csv)",
    )
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--mlflow-dir", type=Path, default=None)
    args = parser.parse_args()

    root = args.output_root or repo_root()
    labeled = args.labeled_csv or root / "data" / "generated" / "suppliers_labeled.csv"
    if not labeled.exists():
        raise SystemExit(
            f"Labeled dataset missing at {labeled}. "
            "Run `python backend/scripts/generate_dataset.py` first."
        )

    result = run_training(
        labeled_csv=labeled,
        output_root=root,
        seed=args.seed,
        mlflow_tracking_dir=args.mlflow_dir,
    )
    m = result.model_metrics
    b = result.baseline_metrics
    print("Training complete.")
    print(f"  Model bundle:       {result.bundle_path}")
    print(f"  Metrics report:     {result.metrics_path}")
    print(f"  Evaluation report:  {result.evaluation_path}")
    print(f"  MLflow model run:   {result.model_run_id}")
    print(f"  MLflow baseline run: {result.baseline_run_id}")
    print("Held-out test (baseline rule):  ", {k: b[k] for k in ("precision", "recall", "f1")})
    print("Held-out test (trained model):  ", {k: m[k] for k in ("precision", "recall", "f1")})


if __name__ == "__main__":
    main()
