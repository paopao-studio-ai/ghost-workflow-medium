#!/usr/bin/env bash
# Run the full seance on the sample ghosts and keep a timestamped log.
# Usage: ./run_demo.sh [model] [outdir]
set -u
MODEL="${1:-gemma3:1b}"; OUT="${2:-reborn}"
mkdir -p logs "$OUT"
LOG="logs/run_$(date -u +%Y%m%dT%H%M%SZ)_${MODEL//[:\/]/-}.log"
{
  echo "# run started $(date -u -Is) | $(nproc) CPU cores, no GPU | model=$MODEL"
  echo "# $(ollama --version 2>/dev/null | tail -1)"
  echo "\$ python3 medium.py ghosts/* --model $MODEL --out $OUT"
  python3 -u medium.py ghosts/* --model "$MODEL" --out "$OUT"
  echo
  echo "\$ python3 validate.py $OUT/*[!n].json"
  python3 validate.py $(ls "$OUT"/*.json | grep -v '\.plan\.json$')
  echo "# run ended $(date -u -Is)"
} 2>&1 | tee "$LOG"
echo "log: $LOG"
