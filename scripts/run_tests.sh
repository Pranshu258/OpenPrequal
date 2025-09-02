#!/bin/bash
# Run Go unit tests for the repository. Optionally run Python tests if --python is passed.

set -euo pipefail

ROOT_DIR="$(dirname "$0")/.."
cd "$ROOT_DIR"

if ! command -v go >/dev/null 2>&1; then
  echo "go not found. Please install Go to run tests."
  exit 1
fi

echo "Running go test ./... (from go/ module)"
cd go
go test ./...
cd - >/dev/null

if [ "${1-}" = "--python" ]; then
  if ! command -v pytest >/dev/null 2>&1; then
    echo "pytest not found. Installing..."
    pip install pytest
  fi
  PYTHONPATH=src pytest tests
fi
