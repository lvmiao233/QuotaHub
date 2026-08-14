#!/usr/bin/env bash
set -euo pipefail

version="${1:?用法: package-source.sh <version> <output-dir>}"
output_dir="${2:?用法: package-source.sh <version> <output-dir>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pkg_name="quotahub-${version}"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT

mkdir -p "$staging/$pkg_name"

copy_tree() {
  local src="$1"
  local dest="$2"
  if [[ -d "$src" ]]; then
    mkdir -p "$dest"
    cp -r "$src/." "$dest/"
  fi
}

mkdir -p "$staging/$pkg_name/backend" "$staging/$pkg_name/frontend"

copy_tree "$root/backend/app" "$staging/$pkg_name/backend/app"
copy_tree "$root/backend/tests" "$staging/$pkg_name/backend/tests"
cp "$root/backend/pyproject.toml" "$root/backend/uv.lock" "$staging/$pkg_name/backend/"

for item in package.json pnpm-lock.yaml index.html postcss.config.js tailwind.config.js tsconfig.json tsconfig.node.json vite.config.ts components.json; do
  if [[ -f "$root/frontend/$item" ]]; then
    cp "$root/frontend/$item" "$staging/$pkg_name/frontend/"
  fi
done
copy_tree "$root/frontend/src" "$staging/$pkg_name/frontend/src"
copy_tree "$root/frontend/public" "$staging/$pkg_name/frontend/public"
if [[ -d "$root/frontend/dist" ]]; then
  copy_tree "$root/frontend/dist" "$staging/$pkg_name/frontend/dist"
fi

copy_tree "$root/scripts" "$staging/$pkg_name/scripts"
cp "$root/README.md" "$root/.env.example" "$root/Dockerfile" "$root/config.json.example" "$root/docker-compose.yml.example" "$staging/$pkg_name/"
echo "$version" > "$staging/$pkg_name/VERSION"

mkdir -p "$output_dir"
output_abs="$(cd "$output_dir" && pwd)/${pkg_name}-source.zip"
( cd "$staging" && zip -rq "$output_abs" "$pkg_name" \
  -x '*/__pycache__/*' '*.py[co]' '*/.DS_Store' )
echo "已生成: $output_abs"
