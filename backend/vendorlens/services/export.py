"""CSV report export with spreadsheet formula-injection neutralization.

Every cell that could be interpreted as a formula by spreadsheet applications
(leading ``=``, ``+``, ``-``, ``@`` or leading tab/carriage-return control
characters) is prefixed with a single quote so it renders as literal text.
The transformation is applied cell-by-cell and documented in
docs/SECURITY_AND_LIMITATIONS.md; original supplier identifiers and field
values are otherwise preserved exactly as reviewed.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from vendorlens.db.models import AnalysisSession, MatchSuggestion, ReviewDecision, SupplierRecord

EXPORT_COLUMNS = [
    "pair_id",
    "analysis_id",
    "left_supplier_id",
    "left_supplier_name",
    "left_city",
    "left_state",
    "left_website",
    "right_supplier_id",
    "right_supplier_name",
    "right_city",
    "right_state",
    "right_website",
    "model_score",
    "recommendation_band",
    "name_similarity",
    "website_evidence",
    "city_evidence",
    "postal_evidence",
    "review_decision",
    "review_notes",
    "reviewed_at",
]

_BAND_LABELS = {
    "likely_match": "Likely match",
    "needs_review": "Needs review",
    "unlikely_match": "Unlikely match",
}
_DECISION_LABELS = {
    "confirm_same": "Confirmed same entity",
    "reject_match": "Not the same entity",
    "needs_investigation": "Needs investigation",
}

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize_formula(value) -> str:
    """Prefix cells that spreadsheet apps could evaluate as formulas."""
    if value is None:
        return ""
    text = str(value)
    if text[:1] in _FORMULA_PREFIXES:
        return "'" + text
    return text


def build_export_csv(db: Session, analysis_id: str) -> str:
    """Render the full findings + decisions report for one analysis."""
    session = db.get(AnalysisSession, analysis_id)
    if session is None:
        raise KeyError(analysis_id)

    records = {
        r.id: r
        for r in db.execute(
            select(SupplierRecord).where(SupplierRecord.analysis_id == analysis_id)
        ).scalars()
    }
    suggestions = db.execute(
        select(MatchSuggestion)
        .where(MatchSuggestion.analysis_id == analysis_id)
        .order_by(MatchSuggestion.score.desc())
    ).scalars().all()

    import json

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for s in suggestions:
        left = records[s.left_record_id]
        right = records[s.right_record_id]
        try:
            signals = json.loads(s.signals)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            signals = {}
        decision: ReviewDecision | None = s.decision
        writer.writerow(
            {
                "pair_id": s.id,
                "analysis_id": analysis_id,
                "left_supplier_id": left.supplier_id,
                "left_supplier_name": left.supplier_name,
                "left_city": left.city,
                "left_state": left.state,
                "left_website": left.website,
                "right_supplier_id": right.supplier_id,
                "right_supplier_name": right.supplier_name,
                "right_city": right.city,
                "right_state": right.state,
                "right_website": right.website,
                "model_score": s.score,
                "recommendation_band": _BAND_LABELS.get(s.band, s.band),
                "name_similarity": signals.get("name_similarity", ""),
                "website_evidence": signals.get("website", ""),
                "city_evidence": signals.get("city", ""),
                "postal_evidence": signals.get("postal_code", ""),
                "review_decision": (
                    _DECISION_LABELS.get(decision.decision, decision.decision)
                    if decision
                    else ""
                ),
                "review_notes": decision.notes if decision else "",
                "reviewed_at": (
                    decision.reviewed_at.isoformat() if decision else ""
                ),
            }
        )
    return buf.getvalue()


def neutralized_export_csv(db: Session, analysis_id: str) -> str:
    """Export with every cell passed through formula neutralization."""
    raw = build_export_csv(db, analysis_id)
    reader = csv.reader(io.StringIO(raw))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for row in reader:
        writer.writerow([neutralize_formula(cell) for cell in row])
    return out.getvalue()
