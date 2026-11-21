"""Model inference: load the trained bundle and score an analysis.

The serving path reuses exactly the same normalization, TF-IDF/SVD name
representation, candidate retrieval and pair-feature computation as training.
The saved vectorizer/SVD are applied (never refit) so the retrieval space
matches the one the pipeline was validated in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import joblib

from vendorlens.config import MODEL_VERSION
from vendorlens.ml.candidates import CandidateRecord, CandidateRetriever
from vendorlens.ml.features import (
    FEATURE_NAMES,
    NormalizedPairView,
    build_pair_signals,
    compute_pair_features,
)
from vendorlens.ml.normalization import normalize_name

BAND_LIKELY = "likely_match"
BAND_REVIEW = "needs_review"
BAND_UNLIKELY = "unlikely_match"


class ModelNotTrainedError(Exception):
    """Raised when the trained model bundle is unavailable."""


@dataclass
class ScoredPair:
    left_index: int
    right_index: int
    score: float
    band: str
    signals: dict[str, Any]


@dataclass
class AnalysisResult:
    pairs: list[ScoredPair] = field(default_factory=list)
    retrieval_stats: dict[str, Any] = field(default_factory=dict)


class MatchScorer:
    """Loads the versioned model bundle and scores candidate pairs."""

    def __init__(self, bundle: dict):
        required = {"model", "vectorizer", "svd", "feature_names", "thresholds"}
        missing = required - set(bundle)
        if missing:
            raise ValueError(f"Model bundle is missing keys: {sorted(missing)}")
        if list(bundle["feature_names"]) != list(FEATURE_NAMES):
            raise ValueError(
                "Model bundle feature schema does not match the running "
                "feature engineering version."
            )
        self.bundle = bundle
        self.model = bundle["model"]
        self.thresholds = bundle["thresholds"]
        self.model_version: str = bundle.get("model_version", MODEL_VERSION)

    @classmethod
    def load(cls, path) -> "MatchScorer":
        try:
            bundle = joblib.load(path)
        except FileNotFoundError as exc:
            raise ModelNotTrainedError(
                "Trained model bundle not found. Run `make train` "
                "(backend/scripts/train_model.py) before starting the API."
            ) from exc
        return cls(bundle)

    def _band(self, score: float) -> str:
        if score >= self.thresholds["likely"]:
            return BAND_LIKELY
        if score >= self.thresholds["review_lower"]:
            return BAND_REVIEW
        return BAND_UNLIKELY

    def analyze(self, records: list[CandidateRecord]) -> AnalysisResult:
        """Run candidate generation + scoring over an analysis's records."""
        retriever = CandidateRetriever()
        # Apply the training-fitted representation (never refit at serving).
        retriever.vectorizer = self.bundle["vectorizer"]
        retriever.svd = self.bundle["svd"]

        pairs, stats = retriever.candidate_pairs(records)

        scored: list[ScoredPair] = []
        for i, j in pairs:
            view = NormalizedPairView(records[i], records[j])
            x = compute_pair_features(view).reshape(1, -1)
            score = float(self.model.predict_proba(x)[0, 1])
            scored.append(
                ScoredPair(
                    left_index=i,
                    right_index=j,
                    score=round(score, 4),
                    band=self._band(score),
                    signals=build_pair_signals(view, score),
                )
            )
        # Deterministic order: score desc, then stable pair order.
        scored.sort(key=lambda s: (-s.score, s.left_index, s.right_index))
        stats["engine"] = retriever.engine
        return AnalysisResult(pairs=scored, retrieval_stats=stats)
