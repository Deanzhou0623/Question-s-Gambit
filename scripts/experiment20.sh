#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
python3 scripts/run_experiment20.py "${1:?Usage: bash scripts/experiment20.sh smoke|remaining}"
