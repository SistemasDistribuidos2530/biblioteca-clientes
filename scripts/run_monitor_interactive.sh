#!/usr/bin/env bash
# run_monitor_interactive.sh - Ejecuta monitor_failover en modo interactivo (foreground)
# Muestra salida en tiempo real para debugging/demostración
# Uso: bash scripts/run_monitor_interactive.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Determinar si estamos en M1 o M2 según el .env
ROLE=$(grep -E '^GA_ROLE=' .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "primary")

echo "=========================================="
echo "  MONITOR FAILOVER - MODO INTERACTIVO"
echo "=========================================="
echo "Rol detectado: $ROLE"
echo "Presiona Ctrl+C para detener"
echo "=========================================="
echo

# Configurar direcciones según rol
if [[ "$ROLE" == "secondary" ]]; then
  # M2: Monitorear M1 (primary) y usar local como fallback
  export GA_PRIMARY_ADDR=${GA_PRIMARY_ADDR:-tcp://10.43.101.220:6000}
  export GA_SECONDARY_ADDR=${GA_SECONDARY_ADDR:-tcp://localhost:6001}
  echo "📡 Monitoreando GA Primary en M1: $GA_PRIMARY_ADDR"
  echo "🔄 Fallback a GA Secondary local: $GA_SECONDARY_ADDR"
else
  # M1: Monitorear local primary (localhost:6000)
  export GA_PRIMARY_ADDR=${GA_PRIMARY_ADDR:-tcp://localhost:6000}
  export GA_SECONDARY_ADDR=${GA_SECONDARY_ADDR:-tcp://10.43.102.248:6001}
  echo "📡 Monitoreando GA Primary local: $GA_PRIMARY_ADDR"
  echo "🔄 Fallback a GA Secondary en M2: $GA_SECONDARY_ADDR"
fi

echo
echo "Iniciando monitor..."
echo "=========================================="
echo

# Ejecutar en foreground (sin redirigir a archivo)
python3 gc/monitor_failover.py

