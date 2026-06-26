# Multi-stage: small, reproducible image for the FastAPI quoting hot path.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Non-root user — least privilege, no shell.
RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000
# Default provider is the offline mock, so the container boots with zero secrets.
ENV COPILOT_PROVIDER=mock
CMD ["uvicorn", "copilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
