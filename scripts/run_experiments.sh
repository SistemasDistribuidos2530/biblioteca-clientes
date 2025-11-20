#!/usr/bin/env bash
# run_experiments.sh - Ejecuta escenarios de carga (4,6,10 PS) y consolida métricas
# Ahora valida presencia de operaciones 'prestamo' cuando la mezcla lo incluye.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT_DIR/experimentos"
mkdir -p "$RESULTS_DIR"

SCENARIOS="4 6 10"
REQ_PER_PS=${REQ_PER_PS:-25}
# Mezcla RENOVACION:DEVOLUCION:PRESTAMO. Mantiene default anterior pero se recomienda export MIX=40:40:20
MIX=${MIX:-50:50:0}
SEED_BASE=${SEED_BASE:-200}
MODE=${MODE:-concurrent}
SCEN_TIMEOUT=${SCEN_TIMEOUT:-180}

parse_mix() {
  local mix_str="$1"
  IFS=':' read -r a b c <<<"$mix_str"
  a=${a:-50}; b=${b:-50}; c=${c:-0}
  # Formato corto A:B -> asigna restante a C si >0
  if [[ -z "$c" ]]; then
    local sum=$((a + b))
    local rest=$((100 - sum))
    c=$(( rest > 0 ? rest : 0 ))
  fi
  echo "$a:$b:$c"
}

NORMALIZED_MIX=$(parse_mix "$MIX")
REN_PCT=${NORMALIZED_MIX%%:*}
TMP=${NORMALIZED_MIX#*:}; DEV_PCT=${TMP%%:*}; PRE_PCT=${NORMALIZED_MIX##*:}

echo "[INFO] Mezcla normalizada RENOVACION:DEVOLUCION:PRESTAMO = $REN_PCT:$DEV_PCT:$PRE_PCT"
if [[ "$PRE_PCT" -gt 0 && "$MIX" == *":0" ]]; then
  echo "[AVISO] Se expandió formato corto. Para generar préstamos use explícitamente MIX=40:40:20 (ejemplo)."
fi
if [[ "$PRE_PCT" -eq 0 ]]; then
  echo "[ADVERTENCIA] MIX tiene 0% PRESTAMO. No se medirán operaciones de préstamo."
fi

cd "$ROOT_DIR"

# Pre‑check de conectividad al GC
GC_ADDR_DEF="tcp://10.43.101.220:5555"
if [[ -f .env ]]; then
  SRC_ADDR=$(grep -E '^GC_ADDR=' .env | tail -n1 | cut -d'=' -f2- | tr -d '"' | tr -d "'")
  GC_ADDR=${SRC_ADDR:-$GC_ADDR_DEF}
else
  GC_ADDR=$GC_ADDR_DEF
fi
GC_HOSTPORT=${GC_ADDR#tcp://}
GC_HOST=${GC_HOSTPORT%:*}
GC_PORT=${GC_HOSTPORT##*:}
if command -v nc >/dev/null 2>&1; then
  if ! nc -vz "$GC_HOST" "$GC_PORT" >/dev/null 2>&1; then
    echo "[WARN] No hay conectividad al GC ($GC_ADDR). Revisa M1 o .env. Continuando de todas formas..."
  else
    echo "[OK] Conectividad al GC ($GC_ADDR) verificada."
  fi
fi

echo "== Ejecutando experimentos de carga =="
for N in $SCENARIOS; do
  echo "-- Escenario: ${N} PS --"
  echo "[INFO] Registro en: $RESULTS_DIR/escenario_${N}ps_run.log"
  if command -v stdbuf >/dev/null 2>&1; then CMD_PREFIX=(stdbuf -oL -eL); else CMD_PREFIX=(); fi
  if command -v timeout >/dev/null 2>&1; then TIMEOUT_PREFIX=(timeout "${SCEN_TIMEOUT}s"); else TIMEOUT_PREFIX=(); fi
  { "${TIMEOUT_PREFIX[@]}" "${CMD_PREFIX[@]}" python3 pruebas/multi_ps.py \
      --num-ps "$N" --requests-per-ps "$REQ_PER_PS" \
      --mix "$MIX" --seed "$((SEED_BASE + N))" --mode "$MODE" \
    | tee "$RESULTS_DIR/escenario_${N}ps_run.log"; } || echo "[WARN] Escenario ${N}ps terminó con código distinto de 0 (continuando)"

  if [[ -f ps_logs.txt ]]; then
    cp ps_logs.txt "$RESULTS_DIR/ps_logs_${N}ps.txt" || true
  elif [[ -f multi_ps_logs/ps_logs_consolidado.txt ]]; then
    cp multi_ps_logs/ps_logs_consolidado.txt "$RESULTS_DIR/ps_logs_${N}ps.txt" || true
  fi

  if [[ -f ps/log_parser.py && -f "$RESULTS_DIR/ps_logs_${N}ps.txt" ]]; then
    python3 ps/log_parser.py --log "$RESULTS_DIR/ps_logs_${N}ps.txt" --csv "$RESULTS_DIR/metricas_${N}ps.csv" \
      > "$RESULTS_DIR/parser_${N}ps.log" 2>&1 || true
  fi

  # Conteo de préstamos si corresponde
  if [[ "$PRE_PCT" -gt 0 && -f "$RESULTS_DIR/ps_logs_${N}ps.txt" ]]; then
    PRES_CT=$(grep -c 'operation=prestamo' "$RESULTS_DIR/ps_logs_${N}ps.txt" || true)
    echo "[INFO] Escenario ${N}ps - operaciones prestamo: $PRES_CT" | tee -a "$RESULTS_DIR/escenario_${N}ps_run.log"
    if [[ "$PRES_CT" -eq 0 ]]; then
      echo "[WARN] No se observaron operaciones de préstamo en escenario ${N}ps pese a MIX con componente >0" | tee -a "$RESULTS_DIR/escenario_${N}ps_run.log"
    fi
  fi

  echo "Escenario ${N}ps completado"; echo; sleep 1
done

echo "== Consolidando métricas =="
if [[ -f pruebas/consolidar_metricas.py ]]; then
  python3 pruebas/consolidar_metricas.py --dir "$RESULTS_DIR" --output experimento_carga --formato all \
    > "$RESULTS_DIR/consolidacion.log" 2>&1 || true
fi

ls -lh "$RESULTS_DIR" || true

echo "Listo. Resultados en $RESULTS_DIR"
