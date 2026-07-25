#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  python3.11 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit MySQL credentials before running migrations."
fi

echo "B.S. Portal development environment prepared."
