#!/usr/bin/env bash
set -euo pipefail

# Stages the single-source makemoney core package into this Actor directory,
# pushes to Apify, and cleans up the temporary copy so zero code is duplicated in git.
ACTOR_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${ACTOR_DIR}/../../.." && pwd)"

cleanup() {
  rm -rf "${ACTOR_DIR}/src" "${ACTOR_DIR}/pyproject.toml"
}
trap cleanup EXIT

mkdir -p "${ACTOR_DIR}/src/makemoney"
cp "${ROOT_DIR}/src/makemoney/__init__.py" "${ACTOR_DIR}/src/makemoney/__init__.py"
cp -R "${ROOT_DIR}/src/makemoney/compliance_guard" "${ACTOR_DIR}/src/makemoney/compliance_guard"
cp "${ROOT_DIR}/pyproject.toml" "${ACTOR_DIR}/pyproject.toml"

cd "${ACTOR_DIR}"
apify push "$@"
