#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/web" || exit

export PATH="$HOME/.local/bin:$PATH"

PYTHON=$HOME/.local/share/uv/python/cpython-3.13.11-linux-x86_64-gnu/bin/python3.13

echo "Setting up Python environment..."
uv venv --relocatable --python "$PYTHON"
uv sync --frozen --no-install-project --group dev

echo "Running type checks..."
uv run mypy server.py

echo "Running dr2server e2e replay tests..."
cd "$SCRIPT_DIR"
uv sync --frozen --group dev
uv run pytest tests/ -v
