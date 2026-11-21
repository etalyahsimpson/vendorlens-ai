"""Pydantic request/response contracts for the VendorLens API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ReviewDecisionValue = Literal["confirm_same", "reject_match", "needs_investigation"]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str | None = None
    app_version: str
    retrieval_engine: str
    database: str


class DemoInfoResponse(BaseModel):
    available: bool
    record_count: int
    description: str
    provenance: str
    sample_download_path: str


class AnalysisCountsModel(BaseModel):
    records: int
    suggestions: int
    likely: int
    needs_review: int
    unlikely: int
    reviewed: int
    confirmed: int
    rejected: int
    investigation: int


class AnalysisSummary(BaseModel):
    analysis_id: str
    source_type: str
    filename: str | None
    created_at: datetime
    row_count: int
    model_version: str
    status: str
    counts: AnalysisCountsModel
    warnings: list[str] = Field(default_factory=list)


class RecordBrief(BaseModel):
    supplier_id: str
    supplier_name: str
    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    website: str | None = None
    normalized_name: str | None = None


class ReviewDecisionModel(BaseModel):
    decision: ReviewDecisionValue
    notes: str | None = None
    reviewed_at: datetime | None = None


class MatchSuggestionItem(BaseModel):
    suggestion_id: str
    score: float
    band: str
    signals: dict[str, Any]
    left: RecordBrief
    right: RecordBrief
    review_decision: ReviewDecisionModel | None = None


class MatchesPage(BaseModel):
    total: int
    items: list[MatchSuggestionItem]


class ReviewDecisionRequest(BaseModel):
    decision: ReviewDecisionValue
    notes: str | None = Field(default=None, max_length=500)


class ModelMetricsResponse(BaseModel):
    """ passthrough of the measured metrics report (reports/metrics.json)."""

    model_config = {"protected_namespaces": ()}

    model_version: str
    generated_at: str
    dataset: dict[str, Any]
    splits: dict[str, Any]
    baseline: dict[str, Any]
    model: dict[str, Any]
    thresholds: dict[str, Any]
    candidate_generation: dict[str, Any]
    difficult_cases: dict[str, Any]
    mlflow: dict[str, Any]
    environment: dict[str, Any]
    qualification: str
    figures: list[str] = Field(default_factory=list)
