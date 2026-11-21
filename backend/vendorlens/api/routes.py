"""API routes for the VendorLens analysis, review and export workflow."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from vendorlens.api import schemas
from vendorlens.config import MAX_UPLOAD_BYTES, sample_csv_path
from vendorlens.data.validation import (
    CSVValidationError,
    load_sample_records,
    validate_csv_bytes,
)
from vendorlens.ml.inference import ModelNotTrainedError
from vendorlens.services.analysis import run_analysis, summarize_session
from vendorlens.services.export import neutralized_export_csv
from vendorlens.services.review import SuggestionNotFound, save_review_decision

router = APIRouter(prefix="/api/v1")


def _db(request: Request):
    return request.app.state.db_session()


def _scorer(request: Request):
    scorer = request.app.state.scorer
    if scorer is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "model_not_trained",
                    "message": (
                        "The trained model bundle is not available. "
                        "Run `make train` and restart the API."
                    ),
                }
            },
        )
    return scorer


def _error(status: int, code: str, message: str, details: list[str] | None = None):
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message, "details": details or []}},
    )


def _get_session_or_404(db, analysis_id: str):
    from vendorlens.db.models import AnalysisSession

    session = db.get(AnalysisSession, analysis_id)
    if session is None:
        raise _error(
            404,
            "analysis_not_found",
            f"No analysis session exists with id {analysis_id}.",
        )
    return session


# --------------------------------------------------------------------- health


@router.get("/health", response_model=schemas.HealthResponse)
def health(request: Request) -> schemas.HealthResponse:
    from sqlalchemy import text

    db_ok = "unknown"
    try:
        db = _db(request)
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = "ok"
    except Exception:  # pragma: no cover - connectivity failure path
        db_ok = "unavailable"

    scorer = request.app.state.scorer
    from vendorlens.ml.candidates import FAISS_AVAILABLE

    return schemas.HealthResponse(
        status="ok" if db_ok == "ok" else "degraded",
        model_loaded=scorer is not None,
        model_version=scorer.model_version if scorer else None,
        app_version=request.app.state.app_version,
        retrieval_engine="faiss" if FAISS_AVAILABLE else "numpy-fallback",
        database=db_ok,
    )


# ----------------------------------------------------------------------- demo


@router.get("/demo", response_model=schemas.DemoInfoResponse)
def demo_info(request: Request) -> schemas.DemoInfoResponse:
    path = sample_csv_path()
    available = path.exists()
    count = 0
    if available:
        try:
            validated = load_sample_records(path)
            count = len(validated.records)
        except CSVValidationError:  # pragma: no cover - corrupted sample
            available = False
    return schemas.DemoInfoResponse(
        available=available,
        record_count=count,
        description=(
            "Bundled sample supplier register with duplicates, lookalike "
            "companies and missing fields - enough to exercise every "
            "recommendation band."
        ),
        provenance=(
            "Synthetic sample data generated deterministically for this "
            "project (see docs/ML_METHODOLOGY.md); not real supplier data."
        ),
        sample_download_path="/api/v1/demo/sample",
    )


@router.get("/demo/sample")
def demo_sample(request: Request) -> Response:
    path = sample_csv_path()
    if not path.exists():  # pragma: no cover - packaging error path
        raise _error(404, "sample_unavailable", "The sample CSV is not bundled.")
    return Response(
        content=path.read_bytes(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="vendorlens_sample_suppliers.csv"'
        },
    )


@router.post("/analyses/demo", response_model=schemas.AnalysisSummary, status_code=201)
def create_demo_analysis(request: Request) -> schemas.AnalysisSummary:
    scorer = _scorer(request)
    path = sample_csv_path()
    if not path.exists():
        raise _error(404, "sample_unavailable", "The sample CSV is not bundled.")
    validated = load_sample_records(path)
    db = _db(request)
    try:
        session, counts = run_analysis(
            db, scorer, validated.records, "sample", "vendorlens_sample_suppliers.csv"
        )
        return _summary(db, session.id, validated.warnings)
    finally:
        db.close()


# --------------------------------------------------------------------- upload


@router.post("/analyses/upload", response_model=schemas.AnalysisSummary, status_code=201)
async def upload_analysis(
    request: Request, file: UploadFile = File(...)
) -> schemas.AnalysisSummary:
    scorer = _scorer(request)
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise _error(
            413,
            "file_too_large",
            "The uploaded file exceeds the 5 MB limit.",
        )
    try:
        validated = validate_csv_bytes(file.filename or "", content)
    except CSVValidationError as exc:
        raise _error(422, exc.code, exc.message, exc.details) from exc

    db = _db(request)
    try:
        session, counts = run_analysis(
            db, scorer, validated.records, "upload", file.filename
        )
        return _summary(db, session.id, validated.warnings)
    finally:
        db.close()


# ------------------------------------------------------------------- analyses


def _summary(db, analysis_id: str, warnings: list[str] | None = None) -> schemas.AnalysisSummary:
    from vendorlens.db.models import AnalysisSession

    session = db.get(AnalysisSession, analysis_id)
    counts = summarize_session(db, analysis_id)
    return schemas.AnalysisSummary(
        analysis_id=session.id,
        source_type=session.source_type,
        filename=session.filename,
        created_at=session.created_at,
        row_count=session.row_count,
        model_version=session.model_version,
        status=session.status,
        counts=schemas.AnalysisCountsModel(
            records=counts.records,
            suggestions=counts.suggestions,
            likely=counts.likely,
            needs_review=counts.needs_review,
            unlikely=counts.unlikely,
            reviewed=counts.reviewed,
            confirmed=counts.confirmed,
            rejected=counts.rejected,
            investigation=counts.investigation,
        ),
        warnings=warnings or [],
    )


@router.get("/analyses/{analysis_id}", response_model=schemas.AnalysisSummary)
def get_analysis(request: Request, analysis_id: str) -> schemas.AnalysisSummary:
    db = _db(request)
    try:
        _get_session_or_404(db, analysis_id)
        return _summary(db, analysis_id)
    finally:
        db.close()


@router.get("/analyses/{analysis_id}/matches", response_model=schemas.MatchesPage)
def list_matches(
    request: Request,
    analysis_id: str,
    band: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> schemas.MatchesPage:
    from sqlalchemy import select

    from vendorlens.db.models import MatchSuggestion, SupplierRecord

    db = _db(request)
    try:
        _get_session_or_404(db, analysis_id)

        stmt = (
            select(MatchSuggestion)
            .where(MatchSuggestion.analysis_id == analysis_id)
            .order_by(MatchSuggestion.score.desc(), MatchSuggestion.id)
        )
        suggestions = db.execute(stmt).scalars().all()

        records = {
            r.id: r
            for r in db.execute(
                select(SupplierRecord).where(SupplierRecord.analysis_id == analysis_id)
            ).scalars()
        }

        items: list[schemas.MatchSuggestionItem] = []
        for s in suggestions:
            if band and s.band != band:
                continue
            if decision:
                dec = s.decision.decision if s.decision else ""
                if dec != decision:
                    continue
            if q:
                left, right = records[s.left_record_id], records[s.right_record_id]
                hay = " ".join(
                    [
                        left.supplier_id,
                        left.supplier_name,
                        right.supplier_id,
                        right.supplier_name,
                    ]
                ).lower()
                if q.lower() not in hay:
                    continue

            left, right = records[s.left_record_id], records[s.right_record_id]
            try:
                signals = json.loads(s.signals)
            except (TypeError, ValueError):  # pragma: no cover
                signals = {}
            review = None
            if s.decision:
                review = schemas.ReviewDecisionModel(
                    decision=s.decision.decision,
                    notes=s.decision.notes,
                    reviewed_at=s.decision.reviewed_at,
                )
            items.append(
                schemas.MatchSuggestionItem(
                    suggestion_id=s.id,
                    score=s.score,
                    band=s.band,
                    signals=signals,
                    left=_brief(left),
                    right=_brief(right),
                    review_decision=review,
                )
            )
        total = len(items)
        return schemas.MatchesPage(total=total, items=items[offset : offset + limit])
    finally:
        db.close()


def _brief(record) -> schemas.RecordBrief:
    return schemas.RecordBrief(
        supplier_id=record.supplier_id,
        supplier_name=record.supplier_name,
        street_address=record.street_address,
        city=record.city,
        state=record.state,
        postal_code=record.postal_code,
        country=record.country,
        website=record.website,
        normalized_name=record.normalized_name,
    )


# --------------------------------------------------------------------- review


@router.patch(
    "/matches/{suggestion_id}/review", response_model=schemas.MatchSuggestionItem
)
def review_match(
    request: Request, suggestion_id: str, body: schemas.ReviewDecisionRequest
) -> schemas.MatchSuggestionItem:
    from vendorlens.db.models import SupplierRecord

    db = _db(request)
    try:
        try:
            suggestion = save_review_decision(
                db, suggestion_id, body.decision, body.notes
            )
        except SuggestionNotFound as exc:
            raise _error(
                404,
                "suggestion_not_found",
                f"No match suggestion exists with id {suggestion_id}.",
            ) from exc

        left = db.get(SupplierRecord, suggestion.left_record_id)
        right = db.get(SupplierRecord, suggestion.right_record_id)
        try:
            signals = json.loads(suggestion.signals)
        except (TypeError, ValueError):  # pragma: no cover
            signals = {}
        review = None
        if suggestion.decision:
            review = schemas.ReviewDecisionModel(
                decision=suggestion.decision.decision,
                notes=suggestion.decision.notes,
                reviewed_at=suggestion.decision.reviewed_at,
            )
        return schemas.MatchSuggestionItem(
            suggestion_id=suggestion.id,
            score=suggestion.score,
            band=suggestion.band,
            signals=signals,
            left=_brief(left),
            right=_brief(right),
            review_decision=review,
        )
    finally:
        db.close()


# --------------------------------------------------------------------- export


@router.get("/analyses/{analysis_id}/export")
def export_analysis(request: Request, analysis_id: str) -> Response:
    db = _db(request)
    try:
        _get_session_or_404(db, analysis_id)
        csv_text = neutralized_export_csv(db, analysis_id)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="vendorlens_findings_{analysis_id}.csv"'
                )
            },
        )
    finally:
        db.close()


# ---------------------------------------------------------------- model metrics


@router.get("/model/metrics", response_model=schemas.ModelMetricsResponse)
def model_metrics(request: Request) -> Any:
    from vendorlens.config import metrics_path

    path = metrics_path()
    if not path.exists():
        raise _error(
            503,
            "metrics_unavailable",
            "Model evaluation metrics have not been generated. Run `make train`.",
        )
    return json.loads(path.read_text(encoding="utf-8"))
