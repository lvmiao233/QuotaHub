#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def backend_package_version() -> str:
    source = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    project = re.search(r"(?ms)^\[project\]\s*$([\s\S]*?)(?=^\[|\Z)", source)
    if project is None:
        raise ValueError("backend/pyproject.toml 缺少 [project]")
    version = re.search(
        r'(?m)^version\s*=\s*["\']([^"\']+)["\']\s*$', project.group(1)
    )
    if version is None:
        raise ValueError("backend/pyproject.toml 缺少 project.version")
    return version.group(1)


def backend_application_version() -> str:
    source = (ROOT / "backend" / "app" / "version.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "APP_VERSION" for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise ValueError("backend/app/version.py 缺少字符串 APP_VERSION")


def frontend_package_version() -> str:
    payload = json.loads(
        (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    return str(payload["version"])


def normalized_tag(value: str) -> str:
    tag = value.strip()
    return tag[1:] if tag.startswith("v") else tag


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 QuotaHub 发布版本声明")
    parser.add_argument("tag", nargs="?", help="可选 Git tag，例如 v0.3.0")
    args = parser.parse_args()

    versions = {
        "backend/pyproject.toml": backend_package_version(),
        "backend/app/version.py": backend_application_version(),
        "frontend/package.json": frontend_package_version(),
    }
    distinct = set(versions.values())
    if len(distinct) != 1:
        for source, version in versions.items():
            print(f"{source}: {version}", file=sys.stderr)
        print("版本声明不一致", file=sys.stderr)
        return 1

    version = next(iter(distinct))
    if args.tag and normalized_tag(args.tag) != version:
        print(
            f"Git tag {args.tag!r} 与应用版本 {version!r} 不一致",
            file=sys.stderr,
        )
        return 1

    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
