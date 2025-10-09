# Makefile - Proyecto SistemasDistribuidos
# ------------------------------------------------------------
# Ubicación: raíz del repositorio
# Requiere: make, Python 3.x y pyzmq
# Permite ejecutar tareas comunes del Proceso Solicitante (PS)

# ------------------------------------------------------------
# Variables configurables desde CLI (ejemplo):
#   make gen N=500 MIX=70:30 SEED=42
#   make send TIMEOUT=3 BACKOFF=1,2,4
# ------------------------------------------------------------

# Parámetros de generación de solicitudes
N ?= 25
MIX ?= 50:50
SEED ?=

# Parámetros de envío
TIMEOUT ?= 2.0
BACKOFF ?= 0.5,1,2,4

# Rutas del proyecto
PS_DIR := ps
LOG_FILE := ps_logs.txt
BIN_FILE := solicitudes.bin

# Intérprete de Python
PY := python

# Ejecutar cada receta en una única shell
.ONESHELL:

# Tareas principales
.PHONY: help setup gen send mock-gc metrics metrics-ok metrics-renov metrics-devol clean-logs clean-bin all

help:
	@echo "Tareas disponibles:"
	@echo "  make setup               -> instala dependencias del PS"
	@echo "  make gen [N=.. MIX=.. SEED=..] -> genera '$(BIN_FILE)' en la raíz"
	@echo "  make send [TIMEOUT=.. BACKOFF=..] -> envía lote al GC y actualiza '$(LOG_FILE)'"
	@echo "  make mock-gc             -> levanta un GC simulado"
	@echo "  make metrics             -> muestra métricas globales"
	@echo "  make metrics-ok          -> métricas considerando sólo OK"
	@echo "  make metrics-renov       -> métricas filtradas por RENOVACION"
	@echo "  make metrics-devol       -> métricas filtradas por DEVOLUCION"
	@echo "  make clean-logs          -> borra '$(LOG_FILE)'"
	@echo "  make clean-bin           -> borra '$(BIN_FILE)'"
	@echo "  make all                 -> instala, genera, envía y analiza métricas"

# Instala dependencias del PS
setup:
	$(PY) -m pip install -r $(PS_DIR)/requirements.txt
	@echo "Dependencias instaladas."

# Genera solicitudes.bin con parámetros
gen:
	@if [ -n "$(SEED)" ]; then \
		echo "Generando con N=$(N) MIX=$(MIX) SEED=$(SEED)"; \
		$(PY) $(PS_DIR)/gen_solicitudes.py --n $(N) --mix $(MIX) --seed $(SEED); \
	else \
		echo "Generando con N=$(N) MIX=$(MIX)"; \
		$(PY) $(PS_DIR)/gen_solicitudes.py --n $(N) --mix $(MIX); \
	fi

# Envía las solicitudes al GC y registra resultados
send:
	@echo "Ejecutando PS (timeout=$(TIMEOUT), backoff=$(BACKOFF))..."
	$(PY) $(PS_DIR)/ps.py --timeout $(TIMEOUT) --backoff $(BACKOFF)

# GC simulado para pruebas locales
mock-gc:
	@echo "GC mock escuchando en tcp://0.0.0.0:5555 (Ctrl+C para detener)"
	$(PY) - <<-'PYCODE'
	import os, zmq, time, hmac, hashlib, json
	SECRET_KEY=os.environ.get("SECRET_KEY","clave123").encode()
	def ok(msg):
	    mac=msg.get("hmac",""); data={k:v for k,v in msg.items() if k!="hmac"}
	    raw=json.dumps(data,sort_keys=True).encode()
	    good_mac=hmac.new(SECRET_KEY,raw,hashlib.sha256).hexdigest()==mac
	    good_ts=abs(int(time.time())-int(msg.get("ts",0)))<=60
	    return good_mac and good_ts
	ctx=zmq.Context.instance(); s=ctx.socket(zmq.REP); s.bind("tcp://0.0.0.0:5555")
	print("GC mock listo.")
	while True:
	    m=s.recv_json()
	    s.send_json({"status":"OK" if ok(m) else "ERROR","request_id":m.get("request_id"),"tipo":m.get("tipo")})
	PYCODE

# Métricas (usa ps/log_parser.py)
metrics:
	$(PY) $(PS_DIR)/log_parser.py --log $(LOG_FILE)

metrics-ok:
	$(PY) $(PS_DIR)/log_parser.py --log $(LOG_FILE) --only-ok

metrics-renov:
	$(PY) $(PS_DIR)/log_parser.py --log $(LOG_FILE) --tipo RENOVACION

metrics-devol:
	$(PY) $(PS_DIR)/log_parser.py --log $(LOG_FILE) --tipo DEVOLUCION

# Limpieza de archivos
clean-logs:
	rm -f $(LOG_FILE)
	@echo "Archivo de log eliminado."

clean-bin:
	rm -f $(BIN_FILE)
	@echo "Archivo binario eliminado."

# Ejecuta toda la secuencia completa
all: setup gen send metrics
