#!/usr/bin/env python3
# archivo: ps/ps.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 8 de octubre de 2025
#
# Qué hace:
#   Cliente del Proceso Solicitante (PS):
#     - Lee 'solicitudes.bin' desde la RAÍZ del repo.
#     - Recalcula HMAC antes de cada envío.
#     - Envía por ZeroMQ (REQ) al GC y espera REP con timeout.
#     - Reintenta usando backoff exponencial configurable.
#     - Registra métricas en 'ps_logs.txt' (en la RAÍZ) para TPS/latencias.
#
# Entradas:
#   - .env:
#       GC_ADDR=tcp://10.43.101.220:5555
#       PS_TIMEOUT=2.0
#       PS_BACKOFF=0.5,1,2,4
#   - ps/ps.py CLI:
#       --timeout   (override de PS_TIMEOUT)
#       --backoff   (override de PS_BACKOFF, coma-separado)
#
# Salida en consola:
#   - Banner de conexión y parámetros efectivos.
#   - Un bloque legible por solicitud (envío/resp/reintentos).
#   - Resumen final (OK/FALLIDOS y ruta del log).

import os
import time
import pickle
import argparse
import zmq
import json
from pathlib import Path
from dotenv import load_dotenv
from schema import sign   # Firma HMAC de cada solicitud

# Carga variables del archivo .env (si existe)
load_dotenv()

# ---------- Configuración por defecto (M3 → conecta a M1) ----------
GC_ADDR = os.getenv("GC_ADDR", "tcp://10.43.101.220:5555")

# RAÍZ del repo (biblioteca-clientes/)
ROOT = Path(__file__).resolve().parents[1]
BIN_PATH = ROOT / "solicitudes.bin"       # Archivo de entrada (pickle con lista de dicts)
LOG_PATH = ROOT / "ps_logs.txt"           # Archivo de salida (métricas)

# Backoff y timeout por defecto (si no llegan por ENV/CLI)
BACKOFFS = [0.5, 1, 2, 4]
TIMEOUT_S = 2.0

# ---------- Utilidades de impresión (salida legible) ----------

def banner_inicio(gc_addr: str, timeout_s: float, backoffs: list[float], total: int | None):
    # Imprime un encabezado con parámetros efectivos y tamaño del lote (si se conoce).
    print("\n" + "=" * 72)
    print(" PROCESO SOLICITANTE (PS) — REQ/REP contra GC ".center(72, " "))
    print("-" * 72)
    print(f"  Conectando a  : {gc_addr}")
    print(f"  Timeout (s)   : {timeout_s}")
    print(f"  Backoff (s)   : {', '.join(str(b) for b in backoffs)}")
    if total is not None:
        print(f"  Lote a enviar : {total} solicitudes")
    print(f"  Log métricas  : {LOG_PATH}")
    print("=" * 72 + "\n")


def print_bloque_envio(i: int, total: int, req: dict, intento: int):
    # Muestra el envío con metadatos útiles.
    print("-" * 72)
    print(f" ENVÍO {i}/{total} (intento {intento + 1}) ".center(72, " "))
    print("-" * 72)
    print(f"  request_id : {req.get('request_id')}")
    print(f"  tipo       : {req.get('tipo')}")
    print(f"  book_id    : {req.get('book_id')}")
    print(f"  user_id    : {req.get('user_id')}")
    print("-" * 72 + "\n")


def print_bloque_respuesta(status: str, resp: dict):
    # Intenta mostrar respuesta normalizada.
    print("-" * 72)
    print(" RESPUESTA DEL GC ".center(72, " "))
    print("-" * 72)
    print(f"  status  : {status}")
    if resp:
        # Desglosa contenido de la respuesta (si es JSON válido)
        estado = resp.get("estado")
        mensaje = resp.get("mensaje")
        info = resp.get("info")
        ts = resp.get("ts")
        if estado is not None:
            print(f"  estado  : {estado}")
        if mensaje is not None:
            print(f"  mensaje : {mensaje}")
        if ts is not None:
            print(f"  ts      : {ts}")
        if info:
            print("  info    :")
            for k, v in info.items():
                print(f"    - {k}: {v}")
    print("-" * 72 + "\n")


def print_bloque_timeout(wait: float, agotado: bool):
    # Informa timeout y, si procede, el tiempo a esperar antes del siguiente intento.
    print("-" * 72)
    print(" TIMEOUT DE RESPUESTA ".center(72, " "))
    print("-" * 72)
    if agotado:
        print("  Tiempo agotado y no hay más reintentos disponibles.")
    else:
        print(f"  Reintentando luego de esperar {wait} s...")
    print("-" * 72 + "\n")


def print_resumen(ok: int, fail: int):
    # Reporte final del PS.
    print("\n" + "=" * 72)
    print(" RESUMEN PS ".center(72, " "))
    print("-" * 72)
    print(f"  OK        : {ok}")
    print(f"  FALLIDOS  : {fail}")
    print(f"  Log       : {LOG_PATH}")
    print("=" * 72 + "\n")


# ---------- Lógica de negocio ----------

def build_gc_payload(req: dict) -> str:
    # Adapta la solicitud del PS al formato que espera el GC (ellos leen JSON string).
    #   {
    #     "operation": "renovacion" | "devolucion",
    #     "book_code": "BOOK-<id>",
    #     "user_id": <id>
    #   }
    oper = str(req.get("tipo", "")).strip().lower()  # RENOVACION/DEVOLUCION → minus
    payload = {
        "operation": oper,
        "book_code": f"BOOK-{req.get('book_id')}",
        "user_id": req.get("user_id"),
    }
    return json.dumps(payload, ensure_ascii=False)


def cargar_solicitudes(path=BIN_PATH):
    # Abre el archivo binario y devuelve la lista de solicitudes (dicts).
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def log_line(text: str):
    # Escribe una línea en el archivo de log (append).
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def parse_runtime_args():
    # Lee timeout y backoff desde CLI y/o ENV.
    parser = argparse.ArgumentParser(description="PS runtime params", add_help=False)
    parser.add_argument("--timeout", type=float,
                        default=float(os.getenv("PS_TIMEOUT", TIMEOUT_S)),
                        help="Timeout de respuesta del GC en segundos")
    parser.add_argument("--backoff", type=str,
                        default=os.getenv("PS_BACKOFF", ",".join(map(str, BACKOFFS))),
                        help="Secuencia de backoff en segundos, separada por comas")
    try:
        args, _ = parser.parse_known_args()
    except SystemExit:
        return TIMEOUT_S, BACKOFFS

    # Convierte "0.5,1,2,4" → [0.5, 1, 2, 4]
    try:
        backoffs = [float(x) for x in args.backoff.split(",") if x.strip()]
        if not backoffs:
            backoffs = BACKOFFS
    except Exception:
        backoffs = BACKOFFS

    return args.timeout, backoffs


def main():
    # Crea contexto y socket REQ; conecta al GC usando GC_ADDR (.env o default)
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.connect(GC_ADDR)

    # Lee timeout/backoff efectivos (CLI/ENV)
    timeout_s, backoffs = parse_runtime_args()

    try:
        solicitudes = cargar_solicitudes()
        total = len(solicitudes)
        banner_inicio(GC_ADDR, timeout_s, backoffs, total)

        ok, fail = 0, 0

        for i, req in enumerate(solicitudes, start=1):
            # Recalcula la firma HMAC antes de enviar (por si cambió SECRET_KEY)
            req["hmac"] = sign(req)

            start = time.time()
            attempt = 0
            status = "TIMEOUT"

            # Envío con reintentos (backoff exponencial)
            while attempt <= len(backoffs):
                # Bloque de envío legible
                print_bloque_envio(i, total, req, attempt)

                # ENVÍO en “dialecto GC”: JSON serializado como STRING (su GC hace recv_string())
                wire = build_gc_payload(req)
                sock.send_string(wire)

                # Espera respuesta del GC dentro del timeout (poll en ms)
                if sock.poll(int(timeout_s * 1000), zmq.POLLIN):
                    # RECEPCIÓN como STRING y normalización de status
                    raw = sock.recv_string()
                    try:
                        resp = json.loads(raw)
                    except Exception:
                        resp = {}

                    # Ellos suelen usar {"estado":"ok"}; normalizamos a "OK"/"ERROR"
                    status = resp.get("status")
                    if not status:
                        estado = str(resp.get("estado", "")).upper() if resp else ""
                        status = "OK" if estado in ("OK", "OKAY", "SUCCESS") else "ERROR"

                    print_bloque_respuesta(status, resp)

                    ok += int(status == "OK")
                    fail += int(status != "OK")
                    break

                else:
                    # Timeout: aplica backoff o falla definitivo
                    if attempt == len(backoffs):
                        print_bloque_timeout(wait=0.0, agotado=True)
                        fail += 1
                        break
                    wait = backoffs[attempt]
                    print_bloque_timeout(wait=wait, agotado=False)
                    time.sleep(wait)
                    attempt += 1

            end = time.time()

            # Guarda métricas por solicitud (formato estable para el parser)
            log_line(
                f"request_id={req['request_id']}|"
                f"tipo={req['tipo'].lower()}|"
                f"start={start:.6f}|end={end:.6f}|"
                f"status={status}|retries={attempt}"
            )

        # Resumen final legible
        print_resumen(ok, fail)

    finally:
        # Cierre ordenado de recursos
        try:
            sock.close(linger=0)
        finally:
            ctx.term()


if __name__ == "__main__":
    main()
