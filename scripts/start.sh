#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export QUOTAHUB_DATA="${QUOTAHUB_DATA:-$ROOT/data}"
mkdir -p "$QUOTAHUB_DATA"

export QUOTAHUB_LISTEN_HOST="${QUOTAHUB_LISTEN_HOST:-127.0.0.1}"
export QUOTAHUB_LISTEN_PORT="${QUOTAHUB_LISTEN_PORT:-8788}"

if ! command -v uv >/dev/null 2>&1; then
  echo "未找到 uv，请先安装: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

cd "$ROOT/backend"
uv sync --no-dev --frozen
exec .venv/bin/uvicorn app.main:app \
  --host "$QUOTAHUB_LISTEN_HOST" \
  --port "$QUOTAHUB_LISTEN_PORT"
