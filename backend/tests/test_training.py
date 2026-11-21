"""Training pipeline tests: leakage-free splits, evaluation, MLflow, artifacts."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from vendorlens.data.generator import SEED
from vendorlens.ml.candidates import CandidateRetriever
from vendorlens.ml.features import NormalizedPairView
from vendorlens.ml.normalization import normalize_name
from vendorlens.ml.training import (
    LabeledRecord,
    baseline_predict,
    build_split_pairs,
    candidate_recall,
    classification_metrics,
    load_labeled_dataset,
    run_training,
    select_thresholds,
    split_by_entity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_splits_are_entity_disjoint(labeled_csv):
    records = load_labeled_dataset(labeled_csv)
    splits = split_by_entity(records, SEED)
    train_entities = splits["train"].entities
    val_entities = splits["val"].entities
    test_entities = splits["test"].entities
    assert not (train_entities & val_entities)
    assert not (train_entities & test_entities)
    assert not (val_entities & test_entities)
    # Every record lands in exactly one split.
    total = sum(len(s.records) for s in splits.values())
    assert total == len(records)


def test_pairs_never_cross_split_boundaries(labeled_csv):
    records = load_labeled_dataset(labeled_csv)
    splits = split_by_entity(records, SEED)
    retriever = CandidateRetriever()
    retriever.fit([normalize_name(r.supplier_name) or "" for r in splits["train"].records])
    for split in splits.values():
        _X, y, _stats = build_split_pairs(split, retriever, SEED)
        # All pair members belong to this split by construction; verify labels
        # agree with canonical identity within the split.
        for (i, j), label in zip(split.candidate_pairs + split.extra_negatives, y):
            same = split.records[i].canonical_entity_id == split.records[j].canonical_entity_id
            assert int(same) == label


def test_candidate_recall_computed_on_labeled_pairs(labeled_csv):
    records = load_labeled_dataset(labeled_csv)
    splits = split_by_entity(records, SEED)
    retriever = CandidateRetriever()
    retriever.fit([normalize_name(r.supplier_name) or "" for r in splits["train"].records])
    build_split_pairs(splits["test"], retriever, SEED)
    recall = candidate_recall(splits["test"])
    assert 0.0 <= recall <= 1.0
    assert recall > 0.5, "retrieval must surface the large majority of true pairs"


def test_thresholds_selected_without_touching_test():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, size=400)
    p = np.clip(y * 0.9 + rng.normal(0, 0.08, 400), 0, 1)
    thresholds = select_thresholds(y, p)
    assert 0.0 < thresholds["decision"] < 1.0
    assert thresholds["review_lower"] < thresholds["likely"], (
        "review band must sit strictly between the unlikely and likely bands"
    )


def test_classification_metrics_math():
    y_true = np.array([1, 1, 0, 0, 1, 0])
    y_pred = np.array([1, 0, 0, 1, 1, 0])
    m = classification_metrics(y_true, y_pred)
    assert m["confusion_matrix"] == {"tp": 2, "fp": 1, "tn": 2, "fn": 1}
    assert m["precision"] == round(2 / 3, 4)
    assert m["recall"] == round(2 / 3, 4)
    assert m["f1"] == round(2 / 3, 4)


def test_baseline_is_deterministic_rule():
    from vendorlens.ml.features import FEATURE_NAMES

    X = np.zeros((3, len(FEATURE_NAMES)))
    name_idx = FEATURE_NAMES.index("name_char_similarity")
    X[0, name_idx] = 0.99
    X[1, name_idx] = 0.5
    X[2, name_idx] = 0.85
    assert list(baseline_predict(X)) == [1, 0, 1]


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    """Run the real training once for this module (isolated output)."""
    out = tmp_path_factory.mktemp("training")
    mlflow_dir = out / "mlruns"
    result = run_training(
        labeled_csv=REPO_ROOT / "data" / "generated" / "suppliers_labeled.csv",
        output_root=out,
        seed=SEED,
        mlflow_tracking_dir=mlflow_dir,
    )
    return out, mlflow_dir, result


def test_training_produces_artifacts_and_reports(trained):
    out, _mlflow_dir, result = trained
    assert (out / "artifacts" / "model_bundle.joblib").exists()
    assert (out / "artifacts" / "model_card.json").exists()
    assert (out / "reports" / "metrics.json").exists()
    assert (out / "reports" / "model_evaluation.md").exists()
    assert (out / "reports" / "figures" / "confusion_matrix.png").exists()
    assert (out / "reports" / "figures" / "score_distribution.png").exists()
    assert (out / "reports" / "figures" / "baseline_comparison.png").exists()


def test_metrics_report_contains_required_measurements(trained):
    out, _mlflow_dir, _result = trained
    report = json.loads((out / "reports" / "metrics.json").read_text())
    for approach in ("baseline", "model"):
        for split in ("val", "test"):
            m = report[approach][split]
            for key in ("precision", "recall", "f1"):
                assert 0.0 <= m[key] <= 1.0
            assert set(m["confusion_matrix"]) == {"tp", "fp", "tn", "fn"}
    assert "candidate_recall" in report["candidate_generation"]
    assert report["thresholds"]["decision"] > 0
    assert report["model"]["test"]["f1"] > report["baseline"]["test"]["f1"], (
        "trained model should beat the deterministic baseline on F1"
    )
    assert "synthetic" in report["dataset"]["provenance"].lower()
    assert "not estimates of real-world" in report["qualification"]


def test_mlflow_runs_actually_logged(trained):
    _out, mlflow_dir, result = trained
    import mlflow

    mlflow.set_tracking_uri(mlflow_dir.resolve().as_uri())
    client = mlflow.tracking.MlflowClient()
    exp = client.get_experiment_by_name("vendorlens-supplier-matching")
    assert exp is not None
    runs = client.search_runs([exp.experiment_id])
    assert len(runs) >= 2
    names = {r.data.tags.get("mlflow.runName") for r in runs}
    assert "baseline-name-similarity-rule" in names
    assert "logistic-regression" in names

    model_run = client.get_run(result.model_run_id)
    assert model_run.info.status == "FINISHED"
    assert "test_f1" in model_run.data.metrics
    assert model_run.data.metrics["test_f1"] > 0
    artifacts = [a.path for a in client.list_artifacts(result.model_run_id, "model")]
    assert any("model_bundle" in a for a in artifacts), (
        "the trained bundle must be logged as a real MLflow artifact"
    )


def test_training_is_reproducible(trained, tmp_path):
    """Same seed + same data must yield identical held-out metrics."""
    out, _mlflow_dir, first = trained
    second_out = tmp_path / "rerun"
    second = run_training(
        labeled_csv=REPO_ROOT / "data" / "generated" / "suppliers_labeled.csv",
        output_root=second_out,
        seed=SEED,
        mlflow_tracking_dir=second_out / "mlruns",
    )
    assert second.model_metrics == first.model_metrics
    assert second.baseline_metrics == first.baseline_metrics


def test_bundle_reloads_and_scores_consistently(trained):
    from vendorlens.ml.inference import MatchScorer

    out, _mlflow_dir, _result = trained
    scorer = MatchScorer.load(out / "artifacts" / "model_bundle.joblib")
    from vendorlens.ml.candidates import CandidateRecord

    records = [
        CandidateRecord(supplier_id="S1", supplier_name="Northstar Industrial Supplies LLC",
                        city="Philadelphia", state="PA", postal_code="19103",
                        website="northstarindustrial.example"),
        CandidateRecord(supplier_id="S2", supplier_name="North Star Industrial Supply",
                        city="Philadelphia", state="PA", postal_code="19103",
                        website="northstarindustrial.example"),
    ]
    r1 = scorer.analyze(records)
    r2 = scorer.analyze(records)
    assert r1.pairs[0].score == r2.pairs[0].score, "fixed input/model must score identically"
    assert r1.pairs[0].band in {"likely_match", "needs_review", "unlikely_match"}


def test_labeled_record_shape_has_no_label_leak_into_features():
    import inspect

    fields = LabeledRecord.__dataclass_fields__
    assert "canonical_entity_id" in fields  # exists on the training record
    view_params = list(inspect.signature(NormalizedPairView.__init__).parameters)
    assert "canonical_entity_id" not in view_params, (
        "the label must not be accepted by the feature view used at serving time"
    )
