"""End-to-end training, evaluation and experiment-tracking pipeline.

Design guarantees (see docs/ML_METHODOLOGY.md for the full narrative):

* **Entity-disjoint splits.** Canonical supplier entities are partitioned into
  train / validation / test sets BEFORE any pairs are sampled. Aliases of one
  entity never appear in two splits, so the model cannot memorize entities.
* **Leakage-free representation fitting.** The TF-IDF + SVD name embedding used
  for candidate retrieval is fitted on TRAINING names only and applied to the
  validation and test splits.
* **Threshold discipline.** The classification threshold and the review bands
  are selected on the VALIDATION split only. The held-out TEST split is
  evaluated once with frozen thresholds.
* **Honest baselines.** A deterministic name-similarity rule is evaluated on
  exactly the same test pairs as the trained classifier.
* **Real MLflow runs.** One baseline run and one model run are logged to a
  local MLflow file store; run IDs are recorded in ``reports/metrics.json``.

All metrics in ``reports/metrics.json`` are computed from actual executed runs
on the generated benchmark dataset - they are NOT production accuracy claims.
"""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from vendorlens.config import MODEL_VERSION, repo_root
from vendorlens.data.generator import SEED
from vendorlens.ml.candidates import (
    FAISS_AVAILABLE,
    CandidateRecord,
    CandidateRetriever,
)
from vendorlens.ml.features import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    NormalizedPairView,
    feature_matrix,
)
from vendorlens.ml.normalization import normalize_name

TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15
# TEST_FRACTION is the remainder (0.15).

BASELINE_RULE_THRESHOLD = 0.85  # documented deterministic baseline rule


class DataValidationError(Exception):
    """Raised when the labeled dataset is missing or malformed."""


@dataclass
class LabeledRecord(CandidateRecord):
    canonical_entity_id: str = ""


@dataclass
class SplitData:
    name: str
    records: list[LabeledRecord]
    candidate_pairs: list[tuple[int, int]] = field(default_factory=list)
    extra_negatives: list[tuple[int, int]] = field(default_factory=list)

    @property
    def entities(self) -> set[str]:
        return {r.canonical_entity_id for r in self.records}


def load_labeled_dataset(path: Path) -> list[LabeledRecord]:
    """Read the generated labeled CSV into typed records."""
    import csv

    if not path.exists():
        raise DataValidationError(
            f"Labeled dataset not found at {path}. Run `make generate` "
            "(backend/scripts/generate_dataset.py) first."
        )
    records: list[LabeledRecord] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"supplier_id", "supplier_name", "canonical_entity_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise DataValidationError(
                f"Labeled dataset is missing columns: {sorted(missing)}"
            )
        for row in reader:
            records.append(
                LabeledRecord(
                    supplier_id=row["supplier_id"],
                    supplier_name=row["supplier_name"],
                    street_address=row.get("street_address") or None,
                    city=row.get("city") or None,
                    state=row.get("state") or None,
                    postal_code=row.get("postal_code") or None,
                    country=row.get("country") or None,
                    website=row.get("website") or None,
                    canonical_entity_id=row["canonical_entity_id"],
                )
            )
    if not records:
        raise DataValidationError("Labeled dataset is empty.")
    return records


def split_by_entity(
    records: list[LabeledRecord], seed: int
) -> dict[str, SplitData]:
    """Partition records by canonical entity into train/val/test splits."""
    entity_ids = sorted({r.canonical_entity_id for r in records})
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(entity_ids))
    n_train = int(round(len(entity_ids) * TRAIN_FRACTION))
    n_val = int(round(len(entity_ids) * VAL_FRACTION))
    train_entities = {entity_ids[i] for i in order[:n_train]}
    val_entities = {entity_ids[i] for i in order[n_train : n_train + n_val]}
    test_entities = {entity_ids[i] for i in order[n_train + n_val :]}

    splits: dict[str, SplitData] = {
        "train": SplitData("train", []),
        "val": SplitData("val", []),
        "test": SplitData("test", []),
    }
    for rec in records:
        if rec.canonical_entity_id in train_entities:
            splits["train"].records.append(rec)
        elif rec.canonical_entity_id in val_entities:
            splits["val"].records.append(rec)
        else:
            splits["test"].records.append(rec)

    # Guard: splits must be strictly entity-disjoint.
    assert not (train_entities & val_entities), "train/val entity leakage"
    assert not (train_entities & test_entities), "train/test entity leakage"
    assert not (val_entities & test_entities), "val/test entity leakage"
    return splits


def _pair_label(
    records: list[LabeledRecord], i: int, j: int
) -> int:
    return int(records[i].canonical_entity_id == records[j].canonical_entity_id)


def build_split_pairs(
    split: SplitData, retriever: CandidateRetriever, seed: int
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Candidate pairs + labels + sampled easy negatives for one split.

    Pairs never cross split boundaries because candidate generation runs on
    the split's own records (retrieval representation is fitted on training
    names only and applied here).
    """
    pairs, stats = retriever.candidate_pairs(split.records)
    split.candidate_pairs = pairs

    rng = np.random.default_rng(seed + len(split.records))
    n = len(split.records)
    existing = set(pairs)
    extra_neg: list[tuple[int, int]] = []
    target_extra = max(8, int(0.15 * len(pairs)))
    guard = 0
    while len(extra_neg) < target_extra and guard < target_extra * 20 and n >= 2:
        guard += 1
        i, j = int(rng.integers(0, n)), int(rng.integers(0, n))
        if i == j:
            continue
        key = (min(i, j), max(i, j))
        if key in existing:
            continue
        if _pair_label(split.records, *key) == 1:
            continue  # only negatives are added here
        existing.add(key)
        extra_neg.append(key)
    split.extra_negatives = extra_neg

    all_pairs = pairs + extra_neg
    X = feature_matrix(
        [(split.records[i], split.records[j]) for i, j in all_pairs]
    )
    y = np.array(
        [_pair_label(split.records, i, j) for i, j in all_pairs], dtype=np.int64
    )
    stats = dict(stats)
    stats["extra_negatives"] = len(extra_neg)
    stats["positives"] = int(y.sum())
    stats["negatives"] = int(len(y) - y.sum())
    return X, y, stats


def candidate_recall(split: SplitData) -> float:
    """Fraction of all same-entity pairs in the split that candidates cover."""
    by_entity: dict[str, list[int]] = {}
    for idx, rec in enumerate(split.records):
        by_entity.setdefault(rec.canonical_entity_id, []).append(idx)
    total = sum(len(v) * (len(v) - 1) // 2 for v in by_entity.values())
    if total == 0:
        return 0.0
    found = sum(
        1 for i, j in split.candidate_pairs if _pair_label(split.records, i, j) == 1
    )
    return found / total


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Precision / recall / F1 / confusion counts for a binary prediction."""
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "false_positives": fp,
        "false_negatives": fn,
        "support": {"positive": int(y_true.sum()), "negative": int(len(y_true) - y_true.sum())},
    }


def baseline_predict(X: np.ndarray) -> np.ndarray:
    """Deterministic baseline: name character similarity >= 0.85."""
    name_sim = X[:, FEATURE_NAMES.index("name_char_similarity")]
    return (name_sim >= BASELINE_RULE_THRESHOLD).astype(np.int64)


def select_thresholds(y_val: np.ndarray, p_val: np.ndarray) -> dict:
    """Choose decision/review thresholds on validation data only.

    The classifier's scores are strongly bimodal, so a single F1-maximizing
    cut would collapse all three recommendation bands onto one point. Bands
    are therefore derived from two complementary criteria, both computed on
    the validation split:

    * ``decision``: threshold maximizing F1 on validation.
    * ``likely``: the STRICTER of (a) the smallest threshold whose validation
      precision is >= 0.97 and (b) the 5th percentile of validation scores of
      true matches (the region containing 95% of known duplicates).
    * ``review_lower``: the STRICTER of (a) the largest threshold whose
      validation recall is >= 0.98 and (b) the 95th percentile of validation
      scores of true non-matches - scores below it are confidently distinct.

    Both band edges are clamped around the decision threshold; a documented
    symmetric fallback applies if the edges would cross.
    """
    thresholds = np.round(np.arange(0.05, 0.96, 0.01), 2)
    best_t, best_f1 = 0.5, -1.0
    for t in thresholds:
        m = classification_metrics(y_val, (p_val >= t).astype(np.int64))
        if m["f1"] > best_f1:
            best_f1, best_t = m["f1"], float(t)

    pos_scores = p_val[y_val == 1]
    neg_scores = p_val[y_val == 0]
    pos_p05 = float(np.percentile(pos_scores, 5)) if pos_scores.size else 0.9
    neg_p95 = float(np.percentile(neg_scores, 95)) if neg_scores.size else 0.1

    t_prec97 = None
    for t in thresholds:
        if t < best_t:
            continue
        m = classification_metrics(y_val, (p_val >= t).astype(np.int64))
        if m["precision"] >= 0.97:
            t_prec97 = float(t)
            break
    if t_prec97 is None:
        t_prec97 = max(0.90, best_t)

    t_rec98 = None
    for t in thresholds[::-1]:
        if t > best_t:
            continue
        m = classification_metrics(y_val, (p_val >= t).astype(np.int64))
        if m["recall"] >= 0.98:
            t_rec98 = float(t)
            break
    if t_rec98 is None:
        t_rec98 = min(0.30, best_t)

    likely = max(t_prec97, pos_p05)
    review_lower = min(t_rec98, neg_p95)
    likely = float(np.clip(likely, best_t, 0.98))
    review_lower = float(np.clip(review_lower, 0.02, best_t))

    if review_lower >= likely:  # degenerate separation -> symmetric fallback
        likely = float(min(0.98, best_t + 0.15))
        review_lower = float(max(0.02, best_t - 0.15))

    return {
        "decision": round(best_t, 2),
        "likely": round(likely, 2),
        "review_lower": round(review_lower, 2),
        "selection_basis": (
            "validation split (entity-disjoint from test); F1-max decision "
            "threshold, likely band = stricter of precision>=0.97 threshold "
            "and 5th percentile of true-match scores, review lower bound = "
            "stricter of recall>=0.98 threshold and 95th percentile of "
            "true-non-match scores"
        ),
    }


def _difficult_cases(
    split: SplitData,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    p: np.ndarray,
    kind: str,
    limit: int = 5,
) -> list[dict]:
    """Most informative FP (kind='fp') or FN (kind='fn') pairs on a split."""
    pairs = split.candidate_pairs + split.extra_negatives
    mask = (y_pred == 1) & (y_true == 0) if kind == "fp" else (y_pred == 0) & (y_true == 1)
    candidates = np.where(mask)[0]
    if kind == "fp":
        order = candidates[np.argsort(-p[candidates])]
    else:
        order = candidates[np.argsort(p[candidates])]
    cases = []
    for idx in order[:limit]:
        i, j = pairs[int(idx)]
        left, right = split.records[i], split.records[j]
        cases.append(
            {
                "left": f"{left.supplier_id} {left.supplier_name}",
                "right": f"{right.supplier_id} {right.supplier_name}",
                "score": round(float(p[idx]), 3),
            }
        )
    return cases


def _make_figures(y_test, p_test, base_metrics, model_metrics, out_dir: Path) -> list[str]:
    """Render evaluation figures from the actual measured results."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    # 1. Confusion matrix heatmaps (baseline vs model, test split).
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, (title, m) in zip(
        axes,
        [("Baseline (rule)", base_metrics), ("Trained model", model_metrics)],
    ):
        cm = m["confusion_matrix"]
        grid = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
        ax.imshow(grid, cmap="Blues")
        for (r, c), val in np.ndenumerate(grid):
            ax.text(c, r, f"{val}", ha="center", va="center", color="#10233C", fontsize=12)
        ax.set_xticks([0, 1], ["Pred non-match", "Pred match"])
        ax.set_yticks([0, 1], ["Actual non-match", "Actual match"])
        ax.set_title(f"{title} - held-out test")
    fig.suptitle("Confusion matrices on the held-out test split")
    fig.tight_layout()
    path = out_dir / "confusion_matrix.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    written.append(str(path.name))

    # 2. Score distribution by true class (test split).
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(p_test[y_test == 0], bins=30, alpha=0.7, label="Non-match pairs", color="#94A3B8")
    ax.hist(p_test[y_test == 1], bins=30, alpha=0.7, label="Match pairs", color="#0D9488")
    ax.set_xlabel("Model match score")
    ax.set_ylabel("Pair count")
    ax.set_title("Model score distribution - held-out test pairs")
    ax.legend()
    fig.tight_layout()
    path = out_dir / "score_distribution.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    written.append(str(path.name))

    # 3. Baseline vs model P/R/F1 bars.
    fig, ax = plt.subplots(figsize=(7, 4))
    metrics = ("precision", "recall", "f1")
    x = np.arange(len(metrics))
    width = 0.35
    ax.bar(x - width / 2, [base_metrics[m] for m in metrics], width, label="Baseline rule", color="#94A3B8")
    ax.bar(x + width / 2, [model_metrics[m] for m in metrics], width, label="Logistic regression", color="#0D9488")
    ax.set_xticks(x, [m.capitalize() for m in metrics])
    ax.set_ylim(0, 1.05)
    ax.set_title("Baseline vs trained model - held-out test split")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend()
    fig.tight_layout()
    path = out_dir / "baseline_comparison.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    written.append(str(path.name))
    return written


@dataclass
class TrainingResult:
    bundle_path: Path
    metrics_path: Path
    evaluation_path: Path
    model_run_id: str
    baseline_run_id: str
    model_metrics: dict
    baseline_metrics: dict


def run_training(
    labeled_csv: Path | None = None,
    output_root: Path | None = None,
    seed: int = SEED,
    mlflow_tracking_dir: Path | None = None,
) -> TrainingResult:
    """Train, evaluate, track and persist the full model pipeline."""
    root = output_root or repo_root()
    labeled_csv = labeled_csv or root / "data" / "generated" / "suppliers_labeled.csv"
    artifacts_dir = root / "artifacts"
    reports_dir = root / "reports"
    figures_dir = reports_dir / "figures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    records = load_labeled_dataset(labeled_csv)
    splits = split_by_entity(records, seed)

    # --- Candidate retrieval: fit representation on TRAIN names only.
    retriever = CandidateRetriever()
    retriever.fit([normalize_name(r.supplier_name) or "" for r in splits["train"].records])

    data: dict[str, tuple[np.ndarray, np.ndarray, dict]] = {}
    for name, split in splits.items():
        data[name] = build_split_pairs(split, retriever, seed)

    X_train, y_train, train_stats = data["train"]
    X_val, y_val, val_stats = data["val"]
    X_test, y_test, test_stats = data["test"]

    # --- Baseline rule -----------------------------------------------------
    base_val = classification_metrics(y_val, baseline_predict(X_val))
    base_test = classification_metrics(y_test, baseline_predict(X_test))

    # --- Trained model -----------------------------------------------------
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced", max_iter=1000, random_state=seed
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)
    p_val = model.predict_proba(X_val)[:, 1]
    p_test = model.predict_proba(X_test)[:, 1]

    thresholds = select_thresholds(y_val, p_val)
    y_pred_val = (p_val >= thresholds["decision"]).astype(np.int64)
    y_pred_test = (p_test >= thresholds["decision"]).astype(np.int64)
    model_val = classification_metrics(y_val, y_pred_val)
    model_test = classification_metrics(y_test, y_pred_test)

    # --- Candidate-generation recall (retrieval quality, separate metric) --
    cand_recall = {
        "val": round(candidate_recall(splits["val"]), 4),
        "test": round(candidate_recall(splits["test"]), 4),
    }

    # --- MLflow tracking (local file store, real runs) ----------------------
    import mlflow

    tracking_dir = mlflow_tracking_dir or (root / "mlruns")
    tracking_dir.mkdir(parents=True, exist_ok=True)
    tracking_uri = tracking_dir.resolve().as_uri()
    mlflow.set_tracking_uri(tracking_uri)
    if mlflow.active_run() is not None:  # defensive: never inherit stale state
        mlflow.end_run()
    mlflow.set_experiment("vendorlens-supplier-matching")

    common_params = {
        "seed": seed,
        "dataset": "data/generated/suppliers_labeled.csv",
        "dataset_provenance": "synthetic, deterministically generated (docs/ML_METHODOLOGY.md)",
        "n_records": len(records),
        "n_entities": len({r.canonical_entity_id for r in records}),
        "train_entities": len(splits["train"].entities),
        "val_entities": len(splits["val"].entities),
        "test_entities": len(splits["test"].entities),
        "train_records": len(splits["train"].records),
        "val_records": len(splits["val"].records),
        "test_records": len(splits["test"].records),
        "feature_count": len(FEATURE_NAMES),
        "retrieval_engine": "faiss" if FAISS_AVAILABLE else "numpy-fallback",
    }
    with mlflow.start_run(run_name="baseline-name-similarity-rule") as run:
        mlflow.log_params({**common_params, "rule": "name_char_similarity >= 0.85"})
        mlflow.log_metrics(
            {
                "val_precision": base_val["precision"],
                "val_recall": base_val["recall"],
                "val_f1": base_val["f1"],
                "test_precision": base_test["precision"],
                "test_recall": base_test["recall"],
                "test_f1": base_test["f1"],
            }
        )
        baseline_run_id = run.info.run_id

    # Persist the artifact bundle while the model run is active so the
    # bundle is a genuine MLflow artifact of the evaluated run.
    bundle_path = artifacts_dir / "model_bundle.joblib"
    bundle = {
        "model_version": MODEL_VERSION,
        "model": model,
        "vectorizer": retriever.vectorizer,
        "svd": retriever.svd,
        "feature_names": list(FEATURE_NAMES),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "thresholds": thresholds,
        "seed": seed,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sklearn_version": sklearn.__version__,
        "numpy_version": np.__version__,
        "faiss_available": FAISS_AVAILABLE,
        "training_run_id": "pending",
    }
    with mlflow.start_run(run_name="logistic-regression") as run:
        mlflow.log_params(
            {
                **common_params,
                "model": "LogisticRegression(class_weight=balanced)",
                "decision_threshold": thresholds["decision"],
                "likely_threshold": thresholds["likely"],
                "review_lower_threshold": thresholds["review_lower"],
            }
        )
        mlflow.log_metrics(
            {
                "val_precision": model_val["precision"],
                "val_recall": model_val["recall"],
                "val_f1": model_val["f1"],
                "test_precision": model_test["precision"],
                "test_recall": model_test["recall"],
                "test_f1": model_test["f1"],
                "candidate_recall_val": cand_recall["val"],
                "candidate_recall_test": cand_recall["test"],
            }
        )
        bundle["training_run_id"] = run.info.run_id
        joblib.dump(bundle, bundle_path)
        mlflow.log_artifact(str(bundle_path), artifact_path="model")
        model_run_id = run.info.run_id

    # --- reports/metrics.json ------------------------------------------------
    metrics_report = {
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "provenance": (
                "Synthetic benchmark generated by backend/vendorlens/data/generator.py "
                "with fixed seed; all records fictional. See docs/ML_METHODOLOGY.md."
            ),
            "seed": seed,
            "records": len(records),
            "entities": len({r.canonical_entity_id for r in records}),
            "path": "data/generated/suppliers_labeled.csv",
        },
        "splits": {
            "strategy": "canonical-entity-disjoint (no entity crosses splits)",
            "train": {"entities": len(splits["train"].entities), "records": len(splits["train"].records)},
            "val": {"entities": len(splits["val"].entities), "records": len(splits["val"].records)},
            "test": {"entities": len(splits["test"].entities), "records": len(splits["test"].records)},
        },
        "baseline": {
            "rule": f"normalized-name character similarity >= {BASELINE_RULE_THRESHOLD}",
            "val": base_val,
            "test": base_test,
        },
        "model": {
            "type": "StandardScaler + LogisticRegression(class_weight='balanced')",
            "feature_names": list(FEATURE_NAMES),
            "val": model_val,
            "test": model_test,
        },
        "thresholds": thresholds,
        "candidate_generation": {
            "engine": "faiss.IndexFlatIP" if FAISS_AVAILABLE else "numpy-exact-fallback",
            "top_k": retriever.top_k,
            "blocking": "shared website domain OR shared city+postal code",
            "candidate_recall": cand_recall,
            "pair_stats": {
                "train": train_stats,
                "val": val_stats,
                "test": test_stats,
            },
        },
        "difficult_cases": {
            "false_positives": _difficult_cases(
                splits["test"], y_test, y_pred_test, p_test, "fp"
            ),
            "false_negatives": _difficult_cases(
                splits["test"], y_test, y_pred_test, p_test, "fn"
            ),
        },
        "mlflow": {
            "tracking_uri": "local file store (./mlruns) - see Makefile target `mlflow-ui`",
            "experiment": "vendorlens-supplier-matching",
            "baseline_run_id": baseline_run_id,
            "model_run_id": model_run_id,
        },
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "faiss": "installed (faiss-cpu)" if FAISS_AVAILABLE else "not installed (numpy fallback)",
            "platform": platform.platform(),
        },
        "reproduce": "make train  (or: python backend/scripts/train_model.py)",
        "qualification": (
            "Metrics are measured on the included synthetic benchmark dataset and "
            "are not estimates of real-world or production accuracy."
        ),
    }
    metrics_path = reports_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics_report, indent=2) + "\n", encoding="utf-8")

    # --- Figures from actual results ---------------------------------------
    figures = _make_figures(
        y_test, p_test, base_test, model_test, figures_dir
    )
    metrics_report["figures"] = figures
    metrics_path.write_text(json.dumps(metrics_report, indent=2) + "\n", encoding="utf-8")

    # Attach the finished reports to the model run via the client API
    # (the fluent "active run" has already ended at this point).
    tracking_client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
    tracking_client.log_artifact(model_run_id, str(metrics_path), artifact_path="reports")

    # --- reports/model_evaluation.md ---------------------------------------
    evaluation_path = reports_dir / "model_evaluation.md"
    evaluation_path.write_text(
        _render_evaluation_md(metrics_report), encoding="utf-8"
    )

    # --- artifacts/model_card.json ------------------------------------------
    model_card = {
        "model_version": MODEL_VERSION,
        "task": "supplier duplicate pair classification (recommendation only)",
        "model": "StandardScaler + LogisticRegression(class_weight='balanced')",
        "features": list(FEATURE_NAMES),
        "thresholds": thresholds,
        "seed": seed,
        "trained_at": bundle["trained_at"],
        "training_run_id": model_run_id,
        "baseline_run_id": baseline_run_id,
        "input_schema": "see docs/DATA_DICTIONARY.md",
        "limitations": "Synthetic benchmark only; human review required before any merge.",
    }
    (artifacts_dir / "model_card.json").write_text(
        json.dumps(model_card, indent=2) + "\n", encoding="utf-8"
    )

    return TrainingResult(
        bundle_path=bundle_path,
        metrics_path=metrics_path,
        evaluation_path=evaluation_path,
        model_run_id=model_run_id,
        baseline_run_id=baseline_run_id,
        model_metrics=model_test,
        baseline_metrics=base_test,
    )


def _render_evaluation_md(m: dict) -> str:
    """Human-readable evaluation report rendered from measured metrics."""
    model_test = m["model"]["test"]
    base_test = m["baseline"]["test"]
    cm = model_test["confusion_matrix"]
    s = m["splits"]

    def table(rows: list[list], headers: list[str]) -> str:
        head = "| " + " | ".join(headers) + " |"
        sep = "| " + " | ".join("---" for _ in headers) + " |"
        body = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
        return "\n".join([head, sep, body])

    lines = [
        "# Model Evaluation Report",
        "",
        f"**Model version:** `{m['model_version']}`  ",
        f"**Generated at:** {m['generated_at']}  ",
        f"**Reproduce with:** `{m['reproduce']}`",
        "",
        "## Dataset provenance",
        "",
        m["dataset"]["provenance"],
        "",
        table(
            [
                ["Records", m["dataset"]["records"]],
                ["Canonical entities", m["dataset"]["entities"]],
                ["Generation seed", m["dataset"]["seed"]],
                ["Train (entities / records)", f"{s['train']['entities']} / {s['train']['records']}"],
                ["Validation (entities / records)", f"{s['val']['entities']} / {s['val']['records']}"],
                ["Test (entities / records)", f"{s['test']['entities']} / {s['test']['records']}"],
            ],
            ["Item", "Value"],
        ),
        "",
        "Splits are **canonical-entity-disjoint**: no supplier entity appears in",
        "more than one split, so the model cannot memorize entities it was",
        "trained on. The TF-IDF/SVD name representation is fitted on training",
        "names only. Thresholds are selected on the validation split; the test",
        "split is scored once with frozen thresholds.",
        "",
        "## Held-out test results",
        "",
        table(
            [
                ["Baseline rule", base_test["precision"], base_test["recall"], base_test["f1"]],
                ["Trained model", model_test["precision"], model_test["recall"], model_test["f1"]],
            ],
            ["Approach", "Precision", "Recall", "F1"],
        ),
        "",
        "Confusion matrix (trained model, held-out test):",
        "",
        table(
            [
                ["Actual non-match", cm["tn"], cm["fp"]],
                ["Actual match", cm["fn"], cm["tp"]],
            ],
            ["", "Predicted non-match", "Predicted match"],
        ),
        "",
        f"False positives: **{model_test['false_positives']}** - "
        f"false negatives: **{model_test['false_negatives']}** "
        f"(test support: {model_test['support']['positive']} positive / "
        f"{model_test['support']['negative']} negative pairs).",
        "",
        "## Candidate generation (retrieval) quality",
        "",
        "Candidate recall is measured separately from classifier quality: of",
        "all same-entity pairs that exist in each split, the fraction surfaced",
        "by FAISS top-k retrieval plus deterministic blocking.",
        "",
        table(
            [
                ["Validation", m["candidate_generation"]["candidate_recall"]["val"]],
                ["Test", m["candidate_generation"]["candidate_recall"]["test"]],
            ],
            ["Split", "Candidate pair recall"],
        ),
        "",
        "## Decision thresholds",
        "",
        table(
            [
                ["Decision threshold", m["thresholds"]["decision"]],
                ["Likely-match band (>=)", m["thresholds"]["likely"]],
                ["Review band lower bound", m["thresholds"]["review_lower"]],
            ],
            ["Threshold", "Value"],
        ),
        "",
        "Selected on the validation split only (F1-maximizing decision",
        "threshold; precision >= 0.97 for the likely band; recall >= 0.98 for",
        "the review lower bound). Bands are review recommendations, not",
        "verified business rules.",
        "",
        "## Difficult pair cases (held-out test)",
        "",
        "Most confident false positives:",
        "",
        table(
            [[c["left"], c["right"], c["score"]] for c in m["difficult_cases"]["false_positives"]]
            or [["(none)", "", ""]],
            ["Left record", "Right record", "Score"],
        ),
        "",
        "Most confident false negatives:",
        "",
        table(
            [[c["left"], c["right"], c["score"]] for c in m["difficult_cases"]["false_negatives"]]
            or [["(none)", "", ""]],
            ["Left record", "Right record", "Score"],
        ),
        "",
        "## MLflow experiment tracking",
        "",
        f"* Experiment: `{m['mlflow']['experiment']}` (local file store `./mlruns`)",
        f"* Baseline run: `{m['mlflow']['baseline_run_id']}`",
        f"* Model run: `{m['mlflow']['model_run_id']}`",
        "* Inspect locally with `make mlflow-ui` (opens the MLflow UI).",
        "",
        "## Qualification",
        "",
        m["qualification"],
        "",
    ]
    return "\n".join(lines) + "\n"
