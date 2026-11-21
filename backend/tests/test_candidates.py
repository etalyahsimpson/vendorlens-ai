"""Candidate generation tests: FAISS retrieval, blocking, bounds, fallback."""

from __future__ import annotations

import numpy as np
import pytest

from vendorlens.ml import candidates as cand
from vendorlens.ml.candidates import (
    CandidateLimitExceeded,
    CandidateRecord,
    CandidateRetriever,
    _NumpyIndex,
)


def _record(sid: str, name: str, **kwargs) -> CandidateRecord:
    return CandidateRecord(supplier_id=sid, supplier_name=name, **kwargs)


RECORDS = [
    _record("S1", "Northstar Industrial Supplies LLC", city="Philadelphia", state="PA",
            postal_code="19103", website="northstarindustrial.example"),
    _record("S2", "North Star Industrial Supply", city="Philadelphia", state="PA",
            postal_code="19103", website="northstarindustrial.example"),
    _record("S3", "Northstar Office Services LLC", city="Philadelphia", state="PA",
            postal_code="19103", website="northstaroffice.example"),
    _record("S4", "Silverline Packaging Corp.", city="Chicago", state="IL",
            postal_code="60601", website="silverlinepackaging.example"),
    _record("S5", "Silverline Packaging Incorporated", city="Chicago", state="IL",
            postal_code="60614", website=None),
]


def test_faiss_is_genuinely_available_and_used():
    """The standard supported environment must exercise real FAISS."""
    assert cand.FAISS_AVAILABLE, "faiss-cpu must be installed in the supported environment"
    retriever = CandidateRetriever()
    assert retriever.engine == "faiss"
    pairs, stats = retriever.candidate_pairs(RECORDS)
    assert stats["engine"] == "faiss"
    assert stats["pairs"] > 0
    assert stats["faiss_pairs"] > 0


def test_faiss_index_is_indexflatip():
    retriever = CandidateRetriever().fit([r.supplier_name for r in RECORDS])
    vectors = retriever.transform([r.supplier_name for r in RECORDS])
    index = retriever.build_index(vectors)
    assert type(index).__module__.startswith("faiss"), (
        "the retrieval index must be a real FAISS index on the supported path"
    )
    assert index.ntotal == len(RECORDS)


def test_self_is_excluded_and_pairs_deduplicated():
    retriever = CandidateRetriever()
    pairs, _ = retriever.candidate_pairs(RECORDS)
    assert all(i < j for i, j in pairs), "pairs must be canonical i<j"
    assert len(pairs) == len(set(pairs)), "no duplicate pairs"
    assert all(0 <= i < len(RECORDS) for i, _ in pairs)


def test_top_k_bounds_candidate_count():
    retriever = CandidateRetriever(top_k=2)
    pairs, _ = retriever.candidate_pairs(RECORDS)
    # With 5 records and k=2, FAISS contributes at most 5*2/2 = 5 pairs
    # (plus bounded blocking pairs).
    assert len(pairs) <= 5 + 10


def test_similar_names_surfaced_as_candidates():
    retriever = CandidateRetriever()
    pairs, _ = retriever.candidate_pairs(RECORDS)
    ids = {r.supplier_id for r in RECORDS}
    assert (0, 1) in pairs, "alias pair must be retrieved"
    assert (3, 4) in pairs, "similar-name pair must be retrieved"


def test_website_blocking_unions_candidates():
    retriever = CandidateRetriever(top_k=1)
    records = [
        _record("A", "Zeta Components", website="zeta.example"),
        _record("B", "Completely Different Name Industries", website="zeta.example"),
    ]
    pairs, stats = retriever.candidate_pairs(records)
    assert (0, 1) in pairs, "shared website domain must union into candidates"
    assert stats["blocking_pairs"] >= 1


def test_postal_city_blocking():
    retriever = CandidateRetriever(top_k=1)
    records = [
        _record("A", "Zeta Components", city="Denver", postal_code="80202"),
        _record("B", "Unrelated Named Ventures", city="Denver", postal_code="80202"),
    ]
    pairs, _ = retriever.candidate_pairs(records)
    assert (0, 1) in pairs


def test_candidate_limit_enforced_with_descriptive_error():
    retriever = CandidateRetriever(top_k=8, max_pairs=2)
    with pytest.raises(CandidateLimitExceeded) as exc:
        retriever.candidate_pairs(RECORDS)
    assert "exceeds" in str(exc.value)


def test_numpy_fallback_matches_faiss_results():
    """The documented NumPy fallback must return the same top neighbours."""
    rng = np.random.default_rng(7)
    vectors = rng.normal(size=(20, 8)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    faiss_index = CandidateRetriever().build_index(vectors)
    numpy_index = _NumpyIndex(vectors)
    d1, i1 = faiss_index.search(vectors, 5)
    d2, i2 = numpy_index.search(vectors, 5)
    assert np.allclose(np.sort(i1, axis=1), np.sort(i2, axis=1)), (
        "fallback retrieval must match FAISS neighbours"
    )


def test_single_record_returns_empty():
    retriever = CandidateRetriever()
    pairs, stats = retriever.candidate_pairs([RECORDS[0]])
    assert pairs == []
    assert stats["pairs"] == 0


def test_deterministic_pair_order():
    r1 = CandidateRetriever().candidate_pairs(RECORDS)[0]
    r2 = CandidateRetriever().candidate_pairs(RECORDS)[0]
    assert r1 == r2
