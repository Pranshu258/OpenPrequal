#!/bin/bash
# Run all Python unit tests using pytest

set -e

cd "$(dirname "$0")/.."

if ! command -v pytest >/dev/null 2>&1; then
  echo "pytest not found. Installing..."
  pip install pytest
fi

PYTHONPATH=src pytest tests "$@"
