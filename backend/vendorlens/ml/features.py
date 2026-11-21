"""Pair feature engineering shared by training and inference.

Every feature is explicit, interpretable and computed identically at training
and serving time. Ground-truth ``canonical_entity_id`` labels, split
identifiers or any other answer keys are never accepted by this module -
see tests/test_features.py for the leakage guards.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from vendorlens.ml.candidates import CandidateRecord
from vendorlens.ml.normalization import (
    char_similarity,
    normalize_address,
    normalize_city,
    normalize_name,
    normalize_postal,
    normalize_state,
    normalize_website,
    token_containment,
    token_jaccard,
)

FEATURE_NAMES: list[str] = [
    "name_char_similarity",
    "name_token_jaccard",
    "name_token_containment",
    "suffix_both_present_same",
    "suffix_both_present_different",
    "city_both_present_equal",
    "city_both_present_different",
    "city_missing",
    "state_both_present_equal",
    "state_both_present_different",
    "state_missing",
    "postal_both_present_equal",
    "postal_both_present_different",
    "postal_missing",
    "website_both_present_equal",
    "website_both_present_different",
    "website_missing",
    "address_char_similarity",
    "address_missing",
]

FEATURE_SCHEMA_VERSION = "1"


class NormalizedPairView:
    """Precomputes normalized comparison fields for one record pair."""

    def __init__(self, left: CandidateRecord, right: CandidateRecord):
        self.left_name = normalize_name(left.supplier_name)
        self.right_name = normalize_name(right.supplier_name)
        self.left_suffix = _suffix(left.supplier_name)
        self.right_suffix = _suffix(right.supplier_name)
        self.left_city = normalize_city(left.city)
        self.right_city = normalize_city(right.city)
        self.left_state = normalize_state(left.state)
        self.right_state = normalize_state(right.state)
        self.left_postal = normalize_postal(left.postal_code)
        self.right_postal = normalize_postal(right.postal_code)
        self.left_website = normalize_website(left.website)
        self.right_website = normalize_website(right.website)
        self.left_address = normalize_address(left.street_address)
        self.right_address = normalize_address(right.street_address)


def _suffix(name: str | None) -> str | None:
    from vendorlens.ml.normalization import extract_legal_suffix

    if name is None:
        return None
    suffix = extract_legal_suffix(name)
    return suffix.lower().rstrip(".") if suffix else None


def _tri_state(
    left: str | None,
    right: str | None,
) -> tuple[float, float, float]:
    """(both_present_equal, both_present_different, missing) indicators."""
    if left is None or right is None:
        return 0.0, 0.0, 1.0
    return (1.0, 0.0, 0.0) if left == right else (0.0, 1.0, 0.0)


def compute_pair_features(view: NormalizedPairView) -> np.ndarray:
    """Return the ordered feature vector for one candidate pair."""
    name_sim = char_similarity(view.left_name, view.right_name)
    name_jac = token_jaccard(view.left_name, view.right_name)
    name_cont = token_containment(view.left_name, view.right_name)

    s_eq, s_diff, _ = _tri_state(view.left_suffix, view.right_suffix)
    c_eq, c_diff, c_miss = _tri_state(view.left_city, view.right_city)
    st_eq, st_diff, st_miss = _tri_state(view.left_state, view.right_state)
    p_eq, p_diff, p_miss = _tri_state(view.left_postal, view.right_postal)
    w_eq, w_diff, w_miss = _tri_state(view.left_website, view.right_website)

    if view.left_address is None or view.right_address is None:
        addr_sim, addr_missing = 0.0, 1.0
    else:
        addr_sim = char_similarity(view.left_address, view.right_address)
        addr_missing = 0.0

    return np.array(
        [
            name_sim,
            name_jac,
            name_cont,
            s_eq,
            s_diff,
            c_eq,
            c_diff,
            c_miss,
            st_eq,
            st_diff,
            st_miss,
            p_eq,
            p_diff,
            p_miss,
            w_eq,
            w_diff,
            w_miss,
            addr_sim,
            addr_missing,
        ],
        dtype=np.float64,
    )


def build_pair_signals(view: NormalizedPairView, score: float) -> dict[str, Any]:
    """Human-readable matching evidence shown in the review workspace."""
    name_sim = char_similarity(view.left_name, view.right_name)
    if name_sim >= 0.85:
        name_evidence = "strong"
    elif name_sim >= 0.6:
        name_evidence = "moderate"
    else:
        name_evidence = "weak"

    website_signal = _describe_pair(view.left_website, view.right_website, "domain")
    city_signal = _describe_pair(view.left_city, view.right_city, "city")
    state_signal = _describe_pair(view.left_state, view.right_state, "state")
    postal_signal = _describe_pair(view.left_postal, view.right_postal, "postal code")

    if view.left_suffix is None or view.right_suffix is None:
        suffix_signal = "missing"
    elif view.left_suffix == view.right_suffix:
        suffix_signal = "same"
    else:
        suffix_signal = "different"

    if view.left_address is None or view.right_address is None:
        address_signal: str | float = "missing"
    else:
        address_signal = round(char_similarity(view.left_address, view.right_address), 3)

    return {
        "name_similarity": round(name_sim, 3),
        "name_evidence": name_evidence,
        "token_jaccard": round(token_jaccard(view.left_name, view.right_name), 3),
        "legal_suffix": suffix_signal,
        "city": city_signal,
        "state": state_signal,
        "postal_code": postal_signal,
        "website": website_signal,
        "address_similarity": address_signal,
    }


def _describe_pair(left: str | None, right: str | None, label: str) -> str:
    if left is None or right is None:
        return "missing"
    if left == right:
        return "same"
    return "different"


def feature_matrix(pairs: list[tuple[CandidateRecord, CandidateRecord]]) -> np.ndarray:
    """Feature matrix for a list of record pairs (row order preserved)."""
    if not pairs:
        return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float64)
    return np.vstack(
        [compute_pair_features(NormalizedPairView(l, r)) for l, r in pairs]
    )
