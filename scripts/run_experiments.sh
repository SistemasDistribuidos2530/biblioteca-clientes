#!/usr/bin/env bash
# run_experiments.sh - Ejecuta escenarios de carga (4,6,10 PS) y consolida métricas
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT_DIR/experimentos"
mkdir -p "$RESULTS_DIR"

SCENARIOS="4 6 10"
REQ_PER_PS=${REQ_PER_PS:-25}
MIX=${MIX:-50:50:0}
SEED_BASE=${SEED_BASE:-200}
MODE=${MODE:-concurrent}

cd "$ROOT_DIR"

echo "== Ejecutando experimentos de carga =="
for N in $SCENARIOS; do
  echo "-- Escenario: ${N} PS --"
  python3 pruebas/multi_ps.py --num-ps "$N" --requests-per-ps "$REQ_PER_PS" \
    --mix "$MIX" --seed "$((SEED_BASE + N))" --mode "$MODE" > "$RESULTS_DIR/escenario_${N}ps_run.log" 2>&1
  # Copiar log base
  cp ps_logs.txt "$RESULTS_DIR/ps_logs_${N}ps.txt" || true
  # Parsear métricas
  python3 ps/log_parser.py --log ps_logs.txt --csv "$RESULTS_DIR/metricas_${N}ps.csv" > "$RESULTS_DIR/parser_${N}ps.log" 2>&1 || true
  echo "Escenario ${N}ps completado"
  echo
  sleep 2
done

echo "== Consolidando métricas =="
python3 pruebas/consolidar_metricas.py --dir "$RESULTS_DIR" --output experimento_carga --formato all > "$RESULTS_DIR/consolidacion.log" 2>&1 || true

echo "Listo. Resultados en $RESULTS_DIR"
