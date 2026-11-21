"""Human review decisions: persistence for the review workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from vendorlens.db.models import MatchSuggestion, ReviewDecision

VALID_DECISIONS = ("confirm_same", "reject_match", "needs_investigation")


class SuggestionNotFound(Exception):
    """Raised when the target suggestion does not exist."""


def save_review_decision(
    db: Session, suggestion_id: str, decision: str, notes: str | None
) -> MatchSuggestion:
    """Create or update the human decision for one suggestion (upsert)."""
    suggestion = db.get(MatchSuggestion, suggestion_id)
    if suggestion is None:
        raise SuggestionNotFound(suggestion_id)

    existing = db.execute(
        select(ReviewDecision).where(ReviewDecision.suggestion_id == suggestion_id)
    ).scalar_one_or_none()

    if existing is None:
        existing = ReviewDecision(
            suggestion_id=suggestion_id, decision=decision, notes=notes
        )
        db.add(existing)
    else:
        existing.decision = decision
        existing.notes = notes
        existing.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(suggestion)
    return suggestion
