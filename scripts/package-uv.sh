#!/usr/bin/env bash
set -euo pipefail

version="${1:?用法: package-uv.sh <version> <output-dir>}"
output_dir="${2:?用法: package-uv.sh <version> <output-dir>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pkg_name="quotahub-${version}"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT

if [[ ! -d "$root/frontend/dist" ]]; then
  echo "frontend/dist 不存在，请先构建前端" >&2
  exit 1
fi

mkdir -p "$staging/$pkg_name/backend" "$staging/$pkg_name/frontend" "$staging/$pkg_name/scripts"

cp -r "$root/backend/app" "$root/backend/pyproject.toml" "$root/backend/uv.lock" "$staging/$pkg_name/backend/"
cp -r "$root/frontend/dist" "$staging/$pkg_name/frontend/"
cp "$root/scripts/start.sh" "$root/scripts/start.bat" "$staging/$pkg_name/scripts/"
cp "$root/README.md" "$root/.env.example" "$root/config.json.example" "$staging/$pkg_name/"
echo "$version" > "$staging/$pkg_name/VERSION"

chmod +x "$staging/$pkg_name/scripts/start.sh"

mkdir -p "$output_dir"
output_abs="$(cd "$output_dir" && pwd)/${pkg_name}-uv.zip"
( cd "$staging" && zip -rq "$output_abs" "$pkg_name" \
  -x '*/__pycache__/*' '*.py[co]' '*/.DS_Store' )
echo "已生成: $output_abs"
