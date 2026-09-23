#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

mkdir -p data

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add the Discord and Google credentials before starting the bot."
fi

python -m pytest -q

echo "Codespaces setup complete."
