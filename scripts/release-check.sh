#!/usr/bin/env bash
set -euo pipefail

# Repo-specific: path to package __init__.py relative to repo root
PKG_INIT="context_bridge/__init__.py"

PYPROJECT_VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/' | tr -d '\r')
INIT_VERSION=$(grep '__version__' "$PKG_INIT" | head -1 | sed 's/__version__ = "\(.*\)"/\1/' | tr -d '\r')

if [ "$PYPROJECT_VERSION" != "$INIT_VERSION" ]; then
  echo "FAIL: version mismatch — pyproject.toml=$PYPROJECT_VERSION, $PKG_INIT=$INIT_VERSION"
  exit 1
fi

if ! grep -q "## \[$PYPROJECT_VERSION\]" CHANGELOG.md; then
  echo "FAIL: CHANGELOG.md missing entry for version $PYPROJECT_VERSION"
  exit 1
fi

uv run pytest -m "not integration and not e2e" -q

echo "PASS: release check passed for version $PYPROJECT_VERSION"
