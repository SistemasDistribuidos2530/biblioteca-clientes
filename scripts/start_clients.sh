#!/usr/bin/env bash
# start_clients.sh - Genera solicitudes y lanza PS múltiples (wrapper)
set -euo pipefail
set -x

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

echo "[DEBUG] Directorio raíz: $ROOT_DIR"
echo "[DEBUG] Ejecutando multi_ps (NUM_PS=$NUM_PS REQ_PER_PS=$REQ_PER_PS MIX=$MIX MODE=$MODE SEED=$SEED)"

python3 pruebas/multi_ps.py --num-ps "$NUM_PS" --requests-per-ps "$REQ_PER_PS" \
  --mix "$MIX" --seed "$SEED" --mode "$MODE" > "$LOG_DIR/multi_ps_run.log" 2>&1 || {
    echo "[ERROR] Falló multi_ps.py (ver $LOG_DIR/multi_ps_run.log)"; exit 1; }

# After multi_ps run, use consolidated log instead of expecting ps_logs.txt
CONSOLIDADO="$ROOT_DIR/multi_ps_logs/ps_logs_consolidado.txt"
echo "[DEBUG] Buscando consolidado en: $CONSOLIDADO"
if [ -f "$CONSOLIDADO" ]; then
  cp "$CONSOLIDADO" "$ROOT_DIR/ps_logs.txt"
  echo "[INFO] Consolidado encontrado: $(wc -l < "$CONSOLIDADO") líneas" | tee -a "$LOG_DIR/multi_ps_run.log"
  python3 ps/log_parser.py --log "$ROOT_DIR/ps_logs.txt" --csv "$LOG_DIR/metricas_ps.csv" > "$LOG_DIR/parser_out.log" 2>&1 || echo "[WARN] Falló parser (ver parser_out.log)" | tee -a "$LOG_DIR/multi_ps_run.log"
else
  ls -lh "$ROOT_DIR/multi_ps_logs" || echo "[DEBUG] multi_ps_logs no listado"
  echo "[ERROR] No se encontró $CONSOLIDADO; no se generará metricas_ps.csv" | tee -a "$LOG_DIR/multi_ps_run.log"
fi

echo "Clientes finalizados. Métricas en $LOG_DIR"
