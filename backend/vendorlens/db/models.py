"""SQLAlchemy database models for analysis sessions and review workflow.

The application uses PostgreSQL via Docker Compose (``DATABASE_URL``) with a
SQLite fallback for the local quick start and tests. Schema initialization is
reproducible via ``init_db()``; formal migrations are intentionally not used
for this narrow schema (see docs/ENGINEERING_DECISIONS.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AnalysisSession(Base):
    """One duplicate-detection run over a sample or uploaded CSV."""

    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(String(16))  # "sample" | "upload"
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    row_count: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="completed")

    records: Mapped[list["SupplierRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["MatchSuggestion"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SupplierRecord(Base):
    """One uploaded supplier row: original values plus normalized forms."""

    __tablename__ = "supplier_records"
    __table_args__ = (UniqueConstraint("analysis_id", "supplier_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id"))
    record_index: Mapped[int] = mapped_column(Integer)

    # Original (display/export) values.
    supplier_id: Mapped[str] = mapped_column(String(128))
    supplier_name: Mapped[str] = mapped_column(String(512))
    street_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Normalized comparison forms (see vendorlens/ml/normalization.py).
    normalized_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    normalized_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    normalized_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_postal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    normalized_website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    session: Mapped[AnalysisSession] = relationship(back_populates="records")


class MatchSuggestion(Base):
    """A scored candidate pair surfaced for human review."""

    __tablename__ = "match_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis_sessions.id"))
    left_record_id: Mapped[str] = mapped_column(ForeignKey("supplier_records.id"))
    right_record_id: Mapped[str] = mapped_column(ForeignKey("supplier_records.id"))
    score: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(16))  # likely/needs_review/unlikely
    signals: Mapped[str] = mapped_column(Text)  # JSON evidence blob
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped[AnalysisSession] = relationship(back_populates="suggestions")
    decision: Mapped["ReviewDecision | None"] = relationship(
        back_populates="suggestion", cascade="all, delete-orphan", uselist=False
    )


class ReviewDecision(Base):
    """A human decision attached to one suggestion (upserted via PATCH)."""

    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("match_suggestions.id"), unique=True
    )
    decision: Mapped[str] = mapped_column(String(16))
    # confirm_same | reject_match | needs_investigation
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    suggestion: Mapped[MatchSuggestion] = relationship(back_populates="decision")
