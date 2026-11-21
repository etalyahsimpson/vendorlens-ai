"""Pair feature engineering tests, including leakage guards."""

from __future__ import annotations

import inspect

import numpy as np

from vendorlens.ml.candidates import CandidateRecord
from vendorlens.ml.features import (
    FEATURE_NAMES,
    NormalizedPairView,
    build_pair_signals,
    compute_pair_features,
    feature_matrix,
)


def _rec(sid, name, **kw) -> CandidateRecord:
    return CandidateRecord(supplier_id=sid, supplier_name=name, **kw)


def test_feature_schema_is_stable_and_documented():
    assert len(FEATURE_NAMES) == 19
    assert FEATURE_NAMES[0] == "name_char_similarity"
    assert "website_both_present_equal" in FEATURE_NAMES
    assert "missing" in " ".join(FEATURE_NAMES)


def test_identical_records_produce_maximal_features():
    rec = _rec(
        "S1", "Northstar Industrial Supplies LLC", city="Philadelphia",
        state="PA", postal_code="19103", website="northstarindustrial.example",
        street_address="100 Market St",
    )
    f = compute_pair_features(NormalizedPairView(rec, rec))
    assert f[FEATURE_NAMES.index("name_char_similarity")] == 1.0
    assert f[FEATURE_NAMES.index("website_both_present_equal")] == 1.0
    assert f[FEATURE_NAMES.index("city_both_present_equal")] == 1.0
    assert f[FEATURE_NAMES.index("website_missing")] == 0.0


def test_missing_fields_yield_missing_indicators_not_mismatches():
    left = _rec("S1", "Alpha Supply")
    right = _rec("S2", "Alpha Supply", city="Philadelphia", state="PA",
                 postal_code="19103", website="alpha.example")
    f = compute_pair_features(NormalizedPairView(left, right))
    # Missing website on one side: missing indicator set, NOT a difference.
    assert f[FEATURE_NAMES.index("website_missing")] == 1.0
    assert f[FEATURE_NAMES.index("website_both_present_different")] == 0.0
    assert f[FEATURE_NAMES.index("city_missing")] == 1.0
    assert f[FEATURE_NAMES.index("city_both_present_different")] == 0.0


def test_different_websites_are_explicit_differences():
    left = _rec("S1", "Alpha Supply", website="alpha.example", city="Philadelphia")
    right = _rec("S2", "Alpha Supply", website="alphagroup.example", city="Philadelphia")
    f = compute_pair_features(NormalizedPairView(left, right))
    assert f[FEATURE_NAMES.index("website_both_present_different")] == 1.0
    assert f[FEATURE_NAMES.index("website_both_present_equal")] == 0.0


def test_no_ground_truth_inputs_accepted_by_feature_computation():
    """Leakage guard: the feature API accepts only field-level records."""
    signature = inspect.signature(NormalizedPairView.__init__)
    params = list(signature.parameters)
    forbidden = {"canonical_entity_id", "label", "y", "split", "is_match"}
    assert not (set(params) & forbidden), (
        "ground-truth labels must never be accepted by feature engineering"
    )
    assert not hasattr(CandidateRecord, "canonical_entity_id")


def test_signals_are_human_readable():
    left = _rec("S1", "Northstar Industrial Supplies LLC", city="Philadelphia",
                state="PA", website="northstarindustrial.example")
    right = _rec("S2", "North Star Industrial Supply", city="Philadelphia",
                 state="PA", website="northstarindustrial.example")
    signals = build_pair_signals(NormalizedPairView(left, right), 0.97)
    assert signals["name_evidence"] in {"strong", "moderate", "weak"}
    assert signals["website"] == "same"
    assert signals["city"] == "same"
    assert 0.0 <= signals["name_similarity"] <= 1.0


def test_feature_matrix_row_order_preserved():
    left = _rec("S1", "Alpha Supply")
    right = _rec("S2", "Beta Supply")
    X = feature_matrix([(left, right), (left, left)])
    assert X.shape == (2, len(FEATURE_NAMES))
    assert X[1][FEATURE_NAMES.index("name_char_similarity")] == 1.0
    assert np.isfinite(X).all()
