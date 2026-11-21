"""Candidate generation: TF-IDF/SVD name embeddings + FAISS top-k retrieval.

Pipeline (documented in docs/ML_METHODOLOGY.md):

1. Character n-gram TF-IDF over normalized supplier names.
2. ``TruncatedSVD`` projection to a compact dense embedding (<= 64 dims).
3. ``float32`` + L2 normalization so inner product == cosine similarity.
4. ``faiss.IndexFlatIP`` exact top-k retrieval, self excluded.
5. Union with deterministic blocking candidates (shared website domain, or
   shared city+postal combination).
6. Deduplicated, deterministically ordered pair list with hard bounds.

FAISS is genuinely used on the standard supported path. A pure-NumPy exact
fallback exists only for environments where ``faiss-cpu`` cannot be installed;
it is clearly flagged and never reported as FAISS validation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:  # pragma: no cover - exercised implicitly on supported platforms
    import faiss

    FAISS_AVAILABLE = True
except ImportError:  # pragma: no cover - only on unsupported platforms
    faiss = None
    FAISS_AVAILABLE = False

from vendorlens.config import MAX_BLOCK_SIZE, MAX_CANDIDATE_PAIRS, TOP_K
from vendorlens.ml.normalization import normalize_name


class CandidateLimitExceeded(Exception):
    """Raised when generated candidates exceed configured hard bounds."""


@dataclass
class CandidateRecord:
    """Minimal record shape needed for candidate generation and features."""

    supplier_id: str
    supplier_name: str
    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    website: str | None = None


class _NumpyIndex:
    """Exact top-k inner-product fallback used only when FAISS is absent."""

    def __init__(self, vectors: np.ndarray):
        self._vectors = np.ascontiguousarray(vectors, dtype=np.float32)

    def search(self, queries: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        sims = queries @ self._vectors.T  # (nq, n)
        k = min(k, self._vectors.shape[0])
        idx = np.argsort(-sims, axis=1, kind="stable")[:, :k]
        scores = np.take_along_axis(sims, idx, axis=1)
        return scores.astype(np.float32), idx.astype(np.int64)


class CandidateRetriever:
    """Fits the name representation and retrieves bounded candidate pairs."""

    def __init__(self, top_k: int = TOP_K, max_pairs: int = MAX_CANDIDATE_PAIRS):
        self.top_k = top_k
        self.max_pairs = max_pairs
        self.vectorizer = None
        self.svd = None
        self.engine = "faiss" if FAISS_AVAILABLE else "numpy"

    # ------------------------------------------------------------------ fit
    def fit(self, names: list[str]) -> "CandidateRetriever":
        """Fit the char n-gram TF-IDF + TruncatedSVD representation on names."""
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize

        corpus = [n if n else "unknown" for n in names]
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            min_df=1,
            lowercase=False,
            sublinear_tf=True,
        )
        X = self.vectorizer.fit_transform(corpus)
        n_components = int(min(48, X.shape[0], X.shape[1] - 1))
        if n_components < 1:
            n_components = 1
        self.svd = TruncatedSVD(n_components=n_components, random_state=42)
        Xd = self.svd.fit_transform(X)
        Xd = normalize(Xd).astype(np.float32)
        self._reference_matrix = np.ascontiguousarray(Xd)
        return self

    def transform(self, names: list[str]) -> np.ndarray:
        """Apply the fitted representation; returns L2-normalized float32."""
        from sklearn.preprocessing import normalize

        if self.vectorizer is None or self.svd is None:
            raise RuntimeError("CandidateRetriever.fit() must run before transform()")
        corpus = [n if n else "unknown" for n in names]
        X = self.vectorizer.transform(corpus)
        Xd = self.svd.transform(X)
        if Xd.shape[1] == 1:  # degenerate 1-dim SVD output
            Xd = np.hstack([Xd, np.zeros((Xd.shape[0], 1), dtype=Xd.dtype)])
        return np.ascontiguousarray(
            normalize(Xd).astype(np.float32), dtype=np.float32
        )

    def build_index(self, vectors: np.ndarray):
        """Build a FAISS IndexFlatIP (exact) or the documented NumPy fallback."""
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if FAISS_AVAILABLE:
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            return index
        return _NumpyIndex(vectors)

    # ------------------------------------------------------------- retrieval
    def _faiss_candidates(self, vectors: np.ndarray) -> set[tuple[int, int]]:
        index = self.build_index(vectors)
        k = min(self.top_k + 1, vectors.shape[0])
        _, neighbours = index.search(vectors, k)
        pairs: set[tuple[int, int]] = set()
        for i in range(vectors.shape[0]):
            for j in neighbours[i]:
                j = int(j)
                if j < 0 or j == i:
                    continue
                pairs.add((min(i, j), max(i, j)))
        return pairs

    @staticmethod
    def _blocking_candidates(
        records: list[CandidateRecord],
        normalized: list[str | None],
    ) -> tuple[set[tuple[int, int]], int]:
        """Deterministic blocks: shared website domain or city+postal code."""
        from vendorlens.ml.normalization import (
            normalize_city,
            normalize_postal,
            normalize_website,
        )

        pairs: set[tuple[int, int]] = set()
        skipped_blocks = 0

        groups: dict[str, list[int]] = {}
        for i, rec in enumerate(records):
            domain = normalize_website(rec.website)
            if domain:
                groups.setdefault(f"w:{domain}", []).append(i)
        for i, rec in enumerate(records):
            city = normalize_city(rec.city)
            postal = normalize_postal(rec.postal_code)
            if city and postal:
                groups.setdefault(f"p:{postal}|{city}", []).append(i)

        for key in sorted(groups):
            members = groups[key]
            if len(members) < 2:
                continue
            if len(members) > MAX_BLOCK_SIZE:
                skipped_blocks += 1  # bounded behaviour on degenerate inputs
                continue
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    i, j = members[a], members[b]
                    pairs.add((min(i, j), max(i, j)))
        return pairs, skipped_blocks

    def candidate_pairs(
        self, records: list[CandidateRecord]
    ) -> tuple[list[tuple[int, int]], dict]:
        """Return deduplicated candidate pairs (i < j) plus retrieval stats."""
        if len(records) < 2:
            return [], {"pairs": 0, "faiss_pairs": 0, "blocking_pairs": 0,
                        "skipped_blocks": 0, "engine": self.engine}

        normalized = [normalize_name(r.supplier_name) for r in records]
        if self.vectorizer is None:
            self.fit(normalized)
        vectors = self.transform(normalized)

        faiss_pairs = self._faiss_candidates(vectors)
        blocking_pairs, skipped = self._blocking_candidates(records, normalized)

        all_pairs = sorted(faiss_pairs | blocking_pairs)
        if len(all_pairs) > self.max_pairs:
            raise CandidateLimitExceeded(
                f"Candidate generation produced {len(all_pairs)} pairs, which "
                f"exceeds the configured limit of {self.max_pairs}. Reduce the "
                "number of supplier records or contact the administrator to "
                "raise the limit."
            )
        stats = {
            "pairs": len(all_pairs),
            "faiss_pairs": len(faiss_pairs),
            "blocking_pairs": len(blocking_pairs),
            "skipped_blocks": skipped,
            "engine": self.engine,
        }
        return all_pairs, stats
