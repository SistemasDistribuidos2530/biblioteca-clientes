# Makefile — biblioteca-clientes (PS)
# Universidad: Pontificia Universidad Javeriana
# Materia: Introducción a Sistemas Distribuidos
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 8 de octubre de 2025
#
# Uso rápido:
#   make help
#   make setup
#   make gen N=50 SEED=42 MIX=70:30
#   make send TIMEOUT=2 BACKOFF='0.5,1,2,4'
#   make metrics
#   make metrics-renov
#   make metrics-devol
#   make clean
#
# Notas:
# - Si existe .venv/, se usa su python/pip automáticamente.
# - Los scripts leen .env (si python-dotenv está instalado) o variables de entorno.
# - Variables útiles: GC_ADDR, PS_TIMEOUT, PS_BACKOFF, SECRET_KEY (en .env).

SHELL := /bin/bash

# Detecta intérpretes preferidos (usa .venv si existe)
PY  := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else command -v python3; fi)
PIP := $(shell if [ -x .venv/bin/pip ]; then echo .venv/bin/pip; else command -v pip3 || echo pip; fi)

# Parámetros por defecto (puedes override: make gen N=100 SEED=1 MIX=80:20)
N      ?= 25
SEED   ?=
MIX    ?= 50:50

# PS runtime (override: make send TIMEOUT=3 BACKOFF='0.25,0.5,1,2')
TIMEOUT ?=
BACKOFF ?=

# Log parser (override: make metrics LOG=ps_logs.txt ONLY_OK=1 CSV=out.csv)
LOG      ?= ps_logs.txt
ONLY_OK  ?=
TIPO     ?=
CSV      ?=

# Construye args condicionales
GEN_ARGS      := --n $(N) --mix $(MIX) $(if $(SEED),--seed $(SEED),)
SEND_ARGS     := $(if $(TIMEOUT),--timeout $(TIMEOUT),) $(if $(BACKOFF),--backoff $(BACKOFF),)
METRICS_ARGS  := $(if $(LOG),--log $(LOG),) $(if $(ONLY_OK),--only-ok,) $(if $(TIPO),--tipo $(TIPO),) $(if $(CSV),--csv $(CSV),)

.PHONY: help setup gen send send-compat metrics metrics-ok metrics-renov metrics-devol tail-logs clean clean-logs clean-bin all

help:
	@echo ""
	@echo "========================== HELP — biblioteca-clientes =========================="
	@echo "make setup                         # crea .venv e instala dependencias"
	@echo "make gen N=50 SEED=42 MIX=70:30    # genera solicitudes.bin"
	@echo "make send TIMEOUT=2 BACKOFF='0.5,1,2,4'  # envia con ps.py (reintentos/metricas)"
	@echo "make send-compat                   # envia con send_compat.py (simple)"
	@echo "make metrics [ONLY_OK=1]           # parser de ps_logs.txt"
	@echo "make metrics-renov                 # parser filtrando renovacion"
	@echo "make metrics-devol                 # parser filtrando devolucion"
	@echo "make tail-logs                     # tail -f ps_logs.txt"
	@echo "make clean                         # limpia binarios y logs"
	@echo "==============================================================================="
	@echo ""

setup:
	@echo ">> Creando entorno virtual (.venv) si no existe..."
	@if [ ! -d .venv ]; then python3 -m venv .venv; fi
	@echo ">> Instalando dependencias..."
	@$(PIP) install --upgrade pip
	@($(PIP) install -r ps/requirements.txt) || ($(PIP) install pyzmq python-dotenv)
	@echo ">> Listo. Usa: source .venv/bin/activate"

gen:
	@echo ">> Generando solicitudes.bin (N=$(N), SEED=$(SEED), MIX=$(MIX))"
	@$(PY) ps/gen_solicitudes.py $(GEN_ARGS)

send:
	@echo ">> Enviando lote con ps/ps.py (TIMEOUT=$(TIMEOUT) BACKOFF=$(BACKOFF))"
	@$(PY) ps/ps.py $(SEND_ARGS)

send-compat:
	@echo ">> Enviando lote con ps/send_compat.py (simple)"
	@$(PY) ps/send_compat.py $(if $(TIMEOUT),--timeout $(TIMEOUT),)

metrics:
	@echo ">> Métricas del PS (LOG=$(LOG) ONLY_OK=$(ONLY_OK) CSV=$(CSV))"
	@$(PY) ps/log_parser.py $(METRICS_ARGS)

metrics-ok:
	@$(MAKE) metrics ONLY_OK=1

metrics-renov:
	@$(MAKE) metrics TIPO=renovacion

metrics-devol:
	@$(MAKE) metrics TIPO=devolucion

tail-logs:
	@echo ">> Tail de ps_logs.txt (Ctrl+C para salir)"
	@tail -f ps_logs.txt

clean: clean-bin clean-logs

clean-logs:
	@echo ">> Limpiando logs..."
	@rm -f ps_logs.txt

clean-bin:
	@echo ">> Limpiando binarios..."
	@rm -f solicitudes.bin

all: gen send metrics
