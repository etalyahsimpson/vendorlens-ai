# VendorLens AI backend image.
# Build from the REPOSITORY ROOT so bundled data, artifacts and reports are
# available to the application inside the container:
#   docker build -f backend/Dockerfile -t vendorlens-backend .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/README.md ./README.md
RUN pip install .

# Application package plus the bundled sample data, trained model artifacts
# and evaluation reports (all committed, reproducible inputs).
COPY backend/vendorlens ./vendorlens
COPY data ./data
COPY artifacts ./artifacts
COPY reports ./reports

# Non-root runtime user.
RUN useradd --create-home --shell /usr/sbin/nologin vendorlens \
    && chown -R vendorlens:vendorlens /app
USER vendorlens

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)" || exit 1

CMD ["uvicorn", "vendorlens.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
