# syntax=docker/dockerfile:1.7

FROM node:24-alpine AS web
WORKDIR /build

RUN corepack enable && corepack prepare pnpm@10.33.0 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS runtime
WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1 \
    QUOTAHUB_DATA=/data \
    QUOTAHUB_LISTEN_HOST=0.0.0.0 \
    QUOTAHUB_LISTEN_PORT=8788

COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

COPY backend/app ./app
COPY --from=web /build/dist /app/frontend/dist

EXPOSE 8788

VOLUME ["/data"]

CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --app-dir . --host \"${QUOTAHUB_LISTEN_HOST:-0.0.0.0}\" --port \"${QUOTAHUB_LISTEN_PORT:-8788}\""]
