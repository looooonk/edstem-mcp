#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
.venv/bin/python scripts/check_secrets.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
