#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

windows_path() {
  if command -v cygpath >/dev/null; then cygpath -w "$1"
  elif command -v wslpath >/dev/null; then wslpath -w "$1"
  else printf '%s\n' "$1"; fi
}

PYTHON="$ROOT/.venv-rl/Scripts/python.exe"
OUT="$(windows_path "$ROOT/models/train-smoke")"
MLFLOW="$(windows_path "$ROOT/runs/train-smoke")"
RESULTS="$(windows_path "$ROOT/experiments/results")"
RESULT="$(windows_path "$ROOT/results/train-smoke-evaluation.json")"

cd "$ROOT/backend"
"$PYTHON" -m research.training.cli train --scenario normal --seed-count 3 --timesteps 65 --max-episodes 1 --threads 1 --output-dir "$OUT" --results-dir "$RESULTS" --mlflow-dir "$MLFLOW"
CHECKPOINT="$("$PYTHON" -c "import json, sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['runs'][0]['checkpoint'])" "$OUT\\training-manifest.json" | tr -d '\r')"
"$PYTHON" -m research.training.cli evaluate --scenario normal --seed-count 1 --checkpoint "$CHECKPOINT" --output "$RESULT"
