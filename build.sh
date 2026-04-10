#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/web" || exit

export PATH="$HOME/.local/bin:$PATH"

PYTHON=$HOME/.local/share/uv/python/cpython-3.13.11-linux-x86_64-gnu/bin/python3.13

echo "Setting up Python environment..."
uv venv --relocatable --python "$PYTHON"
uv sync --frozen --no-install-project
