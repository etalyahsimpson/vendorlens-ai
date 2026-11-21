"""Central configuration and path resolution for VendorLens AI.

All settings can be overridden with environment variables (see `.env.example`
at the repository root). The application is local demonstration software and
requires no secrets or external services.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "VendorLens AI"
APP_VERSION = "1.0.0"
MODEL_VERSION = "vendorlens-match-v1"

# Hard operational limits (documented in docs/SECURITY_AND_LIMITATIONS.md).
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 2000  # maximum supplier rows per analysis
MAX_CANDIDATE_PAIRS = 6000  # bound on generated candidate pairs per analysis
TOP_K = 8  # FAISS nearest neighbours retrieved per record
MAX_BLOCK_SIZE = 30  # deterministic blocks larger than this are skipped


class Settings(BaseSettings):
    """Runtime settings resolved from the environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./vendorlens.db"
    sample_csv: str = ""  # resolved against repository root when empty
    model_path: str = ""  # resolved against repository root when empty
    metrics_path: str = ""  # resolved against repository root when empty
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:3000,http://localhost:8080"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def repo_root() -> Path:
    """Locate the repository root by walking up from this file.

    Works for source checkouts, ``pip install -e`` runs and the Docker image
    (where the repo layout is reproduced under /app). Falls back to the
    current working directory.
    """
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "data" / "sample_suppliers.csv").exists():
            return parent
        if (parent / "backend" / "pyproject.toml").exists() and (parent / "data").is_dir():
            return parent
    return Path.cwd()


def resolve_path(setting_value: str, default: Path) -> Path:
    """Resolve a configured path: absolute, or relative to the repository root."""
    if not setting_value:
        return default
    p = Path(setting_value)
    return p if p.is_absolute() else (repo_root() / p)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def sample_csv_path() -> Path:
    return resolve_path(get_settings().sample_csv, repo_root() / "data" / "sample_suppliers.csv")


def model_path() -> Path:
    return resolve_path(get_settings().model_path, repo_root() / "artifacts" / "model_bundle.joblib")


def metrics_path() -> Path:
    return resolve_path(get_settings().metrics_path, repo_root() / "reports" / "metrics.json")
