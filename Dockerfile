# syntax=docker/dockerfile:1
FROM python:3.12-slim

ARG VERSION=0.1.5

LABEL org.opencontainers.image.title="Provena Server" \
      org.opencontainers.image.description="Evidence-backed memory service for AI agents" \
      org.opencontainers.image.source="https://github.com/admiralpunk/Provena" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ".[server]" \
    && addgroup --system provena \
    && adduser --system --ingroup provena --home /app provena

COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

USER provena

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn provena.api:app --host 0.0.0.0 --port 8000"]
