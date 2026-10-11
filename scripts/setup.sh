#!/usr/bin/env bash
# One-time local setup on Linux/macOS. Usage (from the repo root):  bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ required"'
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements-dev.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (local values only, git-ignored)."
fi
echo "Setup complete. Next:  docker compose up -d --build"
