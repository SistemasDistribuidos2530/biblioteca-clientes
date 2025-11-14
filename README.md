# Biblioteca – Cliente (PS)

**Universidad:** Pontificia Universidad Javeriana  
**Materia:** Introducción a Sistemas Distribuidos  
**Profesor:** Rafael Páez Méndez  
**Integrantes:** Thomas Arévalo, Santiago Mesa, Diego Castrillón  
**Fecha:** 8 de octubre de 2025

## 🎯 Descripción

Este repositorio implementa el **Proceso Solicitante (PS)** de un sistema distribuido de biblioteca:

- Genera solicitudes de **RENOVACIÓN** o **DEVOLUCIÓN** (`ps/gen_solicitudes.py`).
- Envía solicitudes al **Gestor de Carga (GC)** por **ZeroMQ REQ/REP** (`ps/ps.py`).
- Recalcula **HMAC** antes de cada envío (`ps/schema.py`).
- Registra métricas en `ps_logs.txt` (TPS, latencias, estados), y permite analizarlas (`ps/log_parser.py`).

> **Topología final de integración**  
> PS (M3: `10.43.102.38`) → **REQ** → GC (M1: `10.43.101.220:5555`) → **PUB** → Actores (M1)

```
+---------------------+          REQ/REP                    +-----------------------------+      PUB/SUB                   +------------------------+
|  PS (M3)            |  ---> tcp://10.43.101.220:5555 ---> |  GC (M1)                    | ---> tcp://127.0.0.1:5556 ---> |  Actores (M1)          |
|  biblioteca-clientes|                                     |  biblioteca-sistema (gc.py) |                                |  Renovación/Devolución |
+---------------------+                                     +-----------------------------+                                +------------------------+
```

---

## 📦 Requisitos

- **SO** de referencia: Ubuntu 22.04.5 LTS (jammy)
- **Python**: 3.10.12
- **ZeroMQ**:
  - `pyzmq`: 27.1.0
  - `libzmq`: 4.3.5
- (Recomendado) **python-dotenv**: para cargar variables desde `.env`

> Si no instalas `python-dotenv`, el PS usará **defaults** embebidos en el código y/o variables de entorno exportadas por shell.

---

## 🗂️ Estructura del repo

```
biblioteca-clientes/
├── common/
│   └── security.py
├── .env                    # (local, NO versionar) configuración del PS
├── ps/
│   ├── gen_solicitudes.py  # genera solicitudes.bin
│   ├── log_parser.py       # métricas de ps_logs.txt (TPS/latencias)
│   ├── ps.py               # PS principal con reintentos y métricas
│   ├── requirements.txt    # dependencias del cliente
│   ├── schema.py           # HMAC y estructura de solicitud
│   └── send_compat.py      # sender simple compatible (sin métricas avanzadas)
├── README.md               # este archivo
├── solicitudes.bin         # (artefacto) lote generado para pruebas
├── ps_logs.txt             # (artefacto) métricas producidas por ps.py
└── .venv/                  # (local) entorno virtual
```

---

## ⚙️ Instalación (entorno local)

```bash
cd ~/biblioteca-clientes
python3 -m venv .venv
source .venv/bin/activate

# Instala dependencias (si no aparecen en requirements, instala directo)
pip install -r ps/requirements.txt || pip install pyzmq python-dotenv
```

---

## 🧩 Configuración (.env)

Archivo **`.env`** en la raíz del repo:

```env
# Dirección del Gestor de Carga (GC) en M1
GC_ADDR=tcp://10.43.101.220:5555

# Parámetros de envío del PS
PS_TIMEOUT=2.0
PS_BACKOFF=0.5,1,2,4

# Clave HMAC (NO subir la real al repo)
SECRET_KEY=clave-super-secreta
```

> Sube un **`.env.example`** al repo (sin secretos) y mantén `.env` en `.gitignore`.

---

## 🚀 Ejecución CON Makefile (atajos)

> Requiere el **Makefile_M3** incluido en este repo.

```bash
# 1) Preparar entorno
make setup

# 2) Generar lote (parámetros override con N, SEED, MIX)
make gen N=50 SEED=42 MIX=70:30

# 3) Enviar (override TIMEOUT/BACKOFF si quieres)
make send TIMEOUT=2 BACKOFF='0.5,1,2,4'

# 4) Métricas
make metrics          # global
make metrics-ok       # solo OK
make metrics-renov    # por tipo: renovacion
make metrics-devol    # por tipo: devolucion

# 5) Utilidades
make tail-logs        # tail -f ps_logs.txt
make clean            # borra solicitudes.bin y ps_logs.txt
```

---

## 🏃 Ejecución TRADICIONAL (SIN Makefile)

### 1) Preparar entorno e instalar
```bash
cd ~/biblioteca-clientes
python3 -m venv .venv
source .venv/bin/activate
pip install -r ps/requirements.txt || pip install pyzmq python-dotenv
```

### 2) Configurar `.env` (o exportar variables equivalentes)
```bash
cat > .env << 'EOF'
GC_ADDR=tcp://10.43.101.220:5555
PS_TIMEOUT=2.0
PS_BACKOFF=0.5,1,2,4
SECRET_KEY=clave-super-secreta
EOF
```

### 3) Generar solicitudes
```bash
python3 ps/gen_solicitudes.py --n 50 --seed 42 --mix 70:30
```

### 4) Enviar con el PS principal (reintentos + métricas)
```bash
python3 ps/ps.py
# overrides directos (sin .env):
# PS_TIMEOUT=3 PS_BACKOFF="0.25,0.5,1,2" GC_ADDR=tcp://10.43.101.220:5555 python3 ps/ps.py
```

### 5) Alternativa simple (compat)
```bash
python3 ps/send_compat.py --timeout 2
```

### 6) Métricas / análisis del log
```bash
# Global
python3 ps/log_parser.py

# Solo latencias de OK
python3 ps/log_parser.py --only-ok

# Por tipo
python3 ps/log_parser.py --tipo renovacion --only-ok
python3 ps/log_parser.py --tipo devolucion --only-ok

# Export a CSV (append)
python3 ps/log_parser.py --csv resultados.csv
```

**Ejemplo real de tu entorno (M3):**
```
PARSER DE LOGS — MÉTRICAS PS
  Total: 25 (OK=25  ERROR=0  TIMEOUT=0)
  Periodo [s]: 0.037   TPS≈ 671.609
  Latencias [s]: mean=0.001  p50=0.001  p95=0.002  max=0.002
```

---

## 🧱 Arquitectura Resumida
**Rol del PS:** Fuente de solicitudes hacia el Gestor de Carga (GC). Cada solicitud contiene `operation`, `book_code`, `user_id`, metadatos de seguridad (HMAC, nonce, ts).

Flujo lógico:
1. PS lee/genera lote (`gen_solicitudes.py`).
2. Recalcula HMAC y envía por REQ al GC (`ps.py`).
3. GC valida operación y responde (OK/ERROR/TIMEOUT).
4. Para renovacion/devolucion publica por PUB/SUB a actores.
5. Log consolidado en `ps_logs.txt` -> analizado por `log_parser.py`.

**Operaciones soportadas:** `renovacion`, `devolucion`, `prestamo` (esta última vía actor síncrono especial).

---
## 🔐 Modelo de Seguridad (Resumen)
| Elemento | Control | Riesgo mitigado |
|----------|---------|-----------------|
| Archivo de entrada | Validación de formato y mezcla | Inyección de datos malformados |
| Mensaje PS→GC | HMAC + nonce + timestamp | Replay / integridad |
| Reintentos | Backoff exponencial configurable | Flood accidental |
| request_id | Idempotencia básica | Duplicados en reintentos |
| Logs | Formato estructurado (línea por solicitud) | Auditoría / métricas |

Pruebas disponibles en `pruebas/`:
- `test_corrupt.py` (entradas corruptas)
- `test_injection.py` (operaciones maliciosas)
- `test_flood.py` (DoS por volumen)
- `test_replay.py` (replay timestamp) – lenta
- `test_seguridad.py` (suite consolidada)

---
## ⚠️ Modelo de Fallos (Perspectiva PS)
| Falla | Efecto | Manejo |
|-------|--------|--------|
| Timeout GC | Latencia > límite | Reintento/backoff |
| GC caído | Respuestas inexistentes | Reintentos hasta agotar backoff (documentar) |
| Failover GA (indirecto) | Breve período de ERROR/TIMEOUT | Reintentos continúan hasta estabilizar |
| Archivo inválido | Solicitudes descartadas | Conteo en logs y continuar |

---
## 📊 Métricas & Formatos
Formato de línea en `ps_logs.txt` (parseado por regex):
```
request_id=<hex> | operation=<op> | start=<epoch_float> | end=<epoch_float> | status=<OK|ERROR|TIMEOUT> | retries=<n>
```
`log_parser.py` produce:
- Latencias (mean, p50, p95, max)
- TPS calculado (ventana entre primer y último start)
- Conteos estado

---
## 🧪 Escenarios de Rendimiento (Ejemplo)
Comandos (desde raíz cliente):
```bash
python3 pruebas/multi_ps.py --num-ps 4 --requests-per-ps 25 --mix 50:50:0 --seed 101
python3 pruebas/multi_ps.py --num-ps 6 --requests-per-ps 25 --mix 50:50:0 --seed 102
python3 pruebas/multi_ps.py --num-ps 10 --requests-per-ps 25 --mix 50:50:0 --seed 103
python3 pruebas/consolidar_metricas.py --dir . --output comparativa --formato all
```
Resultados esperados (orientativo – ajustar al entorno):
| PS | OK% ≈ | Lat media (s) | p95 (s) | TPS (aprox) |
|----|-------|---------------|---------|-------------|
| 4  | 95–100% | 0.12–0.18 | 0.20 | 22–28 |
| 6  | 95–100% | 0.13–0.20 | 0.22 | 30–38 |
| 10 | 93–98%  | 0.15–0.24 | 0.26 | 44–55 |

---
## 🔄 Failover (Impacto en PS)
Durante caída del GA primario pueden observarse:
- Breve aumento de `status=ERROR` / `TIMEOUT`.
- Recuperación tras actualizar `ga_activo.txt` a `secondary` (visto por GC → transparente para PS).
Post-failover: latencia ligeramente mayor si réplica está atrasada.

---
## 🧭 Multi-Máquina (Resumen rápido)
| Paso | M1 | M2 | M3 |
|------|----|----|----|
| BD inicial | generate_db.py | – | – |
| Arranque sede | start_site1.sh | start_site2.sh | – |
| Carga | – | – | start_clients.sh / run_experiments.sh |
| Failover | kill GA primario | standby | enviar nuevo lote |
| Métricas | monitor_failover.log | – | ps_logs / experimentos |

Guía completa: ver `PASO_A_PASO_MULTI_MAQUINA.md` y `EJECUCION.md`.

---
## ✅ Validación Rápida
```bash
# Smoke
bash scripts/e2e_smoke.sh  # (ejecutar en raíz del repo si todo está en una máquina de prueba)
# Seguridad parcial
python3 pruebas/test_seguridad.py --skip-slow
# Rendimiento multi-PS
python3 pruebas/multi_ps.py --num-ps 6 --requests-per-ps 30 --mix 40:40:20 --seed 500
```

Esperar ≥90% OK y latencia media <0.25s en condiciones normales.

---
## 📦 Entregables Usando Este Cliente
- `ps_logs.txt` + CSV consolidado
- Reportes seguridad (`reporte_*.json`)
- Métricas rendimiento (`comparativa.csv`, `.md`)
- Evidencia failover (post-failover lote OK)

---
## 📝 Notas Finales
- Ajustar `PS_TIMEOUT` y `PS_BACKOFF` en `.env` para ambientes lentos.
- Evitar ejecutar `test_flood.py` simultáneamente con experimentos de rendimiento.
- Mantener sincronizadas versiones de repos en las 3 máquinas.

---
## 🔐 Formato de datos

### Solicitud interna (PS)
Campos: `request_id, tipo, book_id, user_id, ts, nonce, hmac`  
La **HMAC-SHA256** se calcula sobre el JSON **canónico** sin el campo `hmac`.

### Payload hacia GC (JSON string)
```json
{
  "operation": "renovacion",
  "book_code": "BOOK-123",
  "user_id": 45
}
```
<!-- Operaciones posibles: renovacion, devolucion, prestamo; user_id entero -->

---

## ✅ Verificación end-to-end

1. En **M1** (GC y Actores):
   - `gc/gc.py` **bind**: `tcp://0.0.0.0:5555` (REP) y `tcp://0.0.0.0:5556` (PUB)
   - Actores **connect**: `tcp://127.0.0.1:5556`
   - Comprobar puertos abiertos:
     ```
     ss -tulpen | grep -E ':5555|:5556'
     ```
2. En **M3** (PS):
   - `.env` con `GC_ADDR=tcp://10.43.101.220:5555`
   - Conectividad:
     ```
     ping -c 1 10.43.101.220
     nc -vz 10.43.101.220 5555
     ```
   - Generar lote y `python3 ps/ps.py`

**Señales de éxito**:
- En M1/Actores, aparecen bloques “DEVOLUCIÓN/RENOVACIÓN PROCESADA” y crecen logs.
- En M3, `ps_logs.txt` crece y el parser reporta OKs, TPS y latencias.

---

## 🩺 Troubleshooting

- **No conecta desde M3 a M1**  
  - Verifica IP y puerto: `nc -vz 10.43.101.220 5555`
  - Asegura que GC está corriendo y bind en `0.0.0.0`.
  - Revisa firewall en M1:  
    `sudo ufw allow 5555/tcp && sudo ufw allow 5556/tcp`

- **El .env no se lee**  
  - Instala `python-dotenv` y verifica:  
    `python3 - <<'PY'
from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('GC_ADDR'))
PY`
  - O exporta variables en shell antes de correr.

- **REQ/REP bloqueado**  
  - Respeta el patrón **send → poll/recv** (el PS ya lo hace).  
  - No llames `send` dos veces seguidas en REQ.

- **Dudas de red (127.0.0.1 vs IP LAN)**  
  - `127.0.0.1` = loopback, **solo** misma máquina.  
  - Conexión remota → usar IP LAN del servidor (p. ej., `10.43.101.220`).

---

## 📝 Notas de implementación

- Los scripts imprimen **bloques legibles** (banners, separadores y campos alineados).
- `ps/ps.py` soporta **reintentos** con **backoff** y **timeout** por CLI/ENV.
- `ps/log_parser.py` exporta CSV con `--csv salida.csv`.

---

## 📄 Licencia y créditos

Uso académico – curso de **Introducción a Sistemas Distribuidos** (PUJ).  
Autores: **Thomas Arévalo, Santiago Mesa, Diego Castrillón**.  
Profesor: **Rafael Páez Méndez**.  
Año: **2025**.