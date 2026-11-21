"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vendorlens import __version__
from vendorlens.api.routes import router
from vendorlens.config import APP_NAME, get_settings, model_path
from vendorlens.db.session import build_engine, init_db, session_factory
from vendorlens.ml.inference import MatchScorer, ModelNotTrainedError


def create_app() -> FastAPI:
    """Build the API application with database + model lifecycle management."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = build_engine(settings.database_url)
        init_db(engine)
        app.state.engine = engine
        app.state.db_session = session_factory(engine)
        app.state.app_version = __version__
        try:
            app.state.scorer = MatchScorer.load(model_path())
        except ModelNotTrainedError:
            app.state.scorer = None
        yield
        engine.dispose()

    app = FastAPI(
        title=f"{APP_NAME} API",
        version=__version__,
        description=(
            "Supplier identity resolution & duplicate detection. Local "
            "demonstration software for an independent engineering portfolio "
            "project - not a production service."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": str(exc),
                    "details": [],
                }
            },
        )

    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        """Normalize errors to {"error": {code, message, details}}."""
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            content = detail
        elif isinstance(detail, str):
            content = {
                "error": {"code": _slug(exc.detail), "message": detail, "details": []}
            }
        else:
            content = {
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": "Request failed.",
                    "details": [str(detail)],
                }
            }
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.get("/", include_in_schema=False)
    def root():
        return {
            "name": APP_NAME,
            "version": __version__,
            "docs": "/docs",
            "api_prefix": "/api/v1",
        }

    return app


def _slug(message: str) -> str:
    return message.lower().replace(" ", "_")[:60]


app = create_app()
