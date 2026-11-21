"""Analysis orchestration: persist records, run the scorer, store suggestions."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from vendorlens.db.models import AnalysisSession, MatchSuggestion, SupplierRecord
from vendorlens.ml.inference import MatchScorer
from vendorlens.ml.normalization import (
    normalize_city,
    normalize_name,
    normalize_postal,
    normalize_state,
    normalize_website,
)


@dataclass
class AnalysisCounts:
    records: int
    suggestions: int
    likely: int
    needs_review: int
    unlikely: int
    reviewed: int
    confirmed: int
    rejected: int
    investigation: int


def run_analysis(
    db: Session,
    scorer: MatchScorer,
    records,
    source_type: str,
    filename: str | None,
    warnings: list[str] | None = None,
) -> tuple[AnalysisSession, AnalysisCounts]:
    """Persist a session + records and score candidate pairs with the model."""
    session = AnalysisSession(
        source_type=source_type,
        filename=filename,
        row_count=len(records),
        model_version=scorer.model_version,
        status="completed",
    )
    db.add(session)
    db.flush()

    db_records: list[SupplierRecord] = []
    for idx, rec in enumerate(records):
        db_rec = SupplierRecord(
            analysis_id=session.id,
            record_index=idx,
            supplier_id=rec.supplier_id,
            supplier_name=rec.supplier_name,
            street_address=rec.street_address,
            city=rec.city,
            state=rec.state,
            postal_code=rec.postal_code,
            country=rec.country,
            website=rec.website,
            normalized_name=normalize_name(rec.supplier_name),
            normalized_city=normalize_city(rec.city),
            normalized_state=normalize_state(rec.state),
            normalized_postal=normalize_postal(rec.postal_code),
            normalized_website=normalize_website(rec.website),
        )
        db_records.append(db_rec)
    db.add_all(db_records)
    db.flush()

    result = scorer.analyze(records)

    for scored in result.pairs:
        left, right = db_records[scored.left_index], db_records[scored.right_index]
        suggestion = MatchSuggestion(
            analysis_id=session.id,
            left_record_id=left.id,
            right_record_id=right.id,
            score=scored.score,
            band=scored.band,
            signals=json.dumps(scored.signals, separators=(",", ":")),
        )
        db.add(suggestion)

    db.commit()
    db.refresh(session)
    counts = summarize_session(db, session.id)
    return session, counts


def summarize_session(db: Session, analysis_id: str) -> AnalysisCounts:
    """Aggregate band and review-decision counts for one analysis."""
    suggestions = (
        db.query(MatchSuggestion)
        .filter(MatchSuggestion.analysis_id == analysis_id)
        .all()
    )
    band_counts = {"likely_match": 0, "needs_review": 0, "unlikely_match": 0}
    decision_counts = {"confirm_same": 0, "reject_match": 0, "needs_investigation": 0}
    for s in suggestions:
        if s.band in band_counts:
            band_counts[s.band] += 1
        if s.decision is not None:
            if s.decision.decision in decision_counts:
                decision_counts[s.decision.decision] += 1
    return AnalysisCounts(
        records=db.get(AnalysisSession, analysis_id).row_count,
        suggestions=len(suggestions),
        likely=band_counts["likely_match"],
        needs_review=band_counts["needs_review"],
        unlikely=band_counts["unlikely_match"],
        reviewed=sum(decision_counts.values()),
        confirmed=decision_counts["confirm_same"],
        rejected=decision_counts["reject_match"],
        investigation=decision_counts["needs_investigation"],
    )
