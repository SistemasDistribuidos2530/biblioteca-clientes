#!/usr/bin/env bash
# start_clients.sh - Genera solicitudes y lanza PS múltiples (wrapper)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

NUM_PS=${NUM_PS:-4}
REQ_PER_PS=${REQ_PER_PS:-25}
MIX=${MIX:-50:50:0}
SEED=${SEED:-100}
MODE=${MODE:-concurrent}

echo "== Iniciando clientes (multi-PS) =="
cd "$ROOT_DIR"

python3 pruebas/multi_ps.py --num-ps "$NUM_PS" --requests-per-ps "$REQ_PER_PS" \
  --mix "$MIX" --seed "$SEED" --mode "$MODE" > "$LOG_DIR/multi_ps_run.log" 2>&1

python3 ps/log_parser.py --log ps_logs.txt --csv "$LOG_DIR/metricas_ps.csv" > "$LOG_DIR/parser_out.log" 2>&1 || true

echo "Clientes finalizados. Métricas en $LOG_DIR"
