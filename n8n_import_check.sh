#!/usr/bin/env bash
# Optional: import the reborn workflows into a real (throwaway) n8n instance via the n8n CLI.
# Needs n8n installed (npm i n8n). Usage: ./n8n_import_check.sh [dir]
set -u
DIR="${1:-reborn}"; N8N="${N8N_BIN:-n8n}"
export N8N_USER_FOLDER="${N8N_USER_FOLDER:-$PWD/.n8n-scratch}" N8N_DIAGNOSTICS_ENABLED=false
mkdir -p logs; LOG="logs/n8n_import_$(date -u +%Y%m%dT%H%M%SZ).log"
{
  echo "# n8n $($N8N --version 2>/dev/null | tail -1) | user folder $N8N_USER_FOLDER"
  for f in $(ls "$DIR"/*.json | grep -v '\.plan\.json$'); do
    echo "\$ n8n import:workflow --input=$f"
    $N8N import:workflow --input="$f" 2>&1 | grep -E "Import|import|rror"
  done
  echo "\$ n8n list:workflow"
  $N8N list:workflow 2>&1 | grep -v "license SDK"
} 2>&1 | tee "$LOG"
