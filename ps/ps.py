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
# Permite override del path del log vía ENV o CLI
ENV_LOG_PATH = os.getenv("PS_LOG_PATH")


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
    print(f"  operation  : {req.get('operation')}")
    print(f"  book_code  : {req.get('book_code')}")
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
    # Construye el payload JSON que se envía al GC.
    # El payload incluye todos los campos de seguridad (request_id, ts, nonce, hmac)
    # además de los campos de negocio estandarizados.
    payload = {
        "operation": req.get("operation"),
        "book_code": req.get("book_code"),
        "user_id": req.get("user_id"),
        "request_id": req.get("request_id"),
        "ts": req.get("ts"),
        "nonce": req.get("nonce"),
        "hmac": req.get("hmac"),
    }
    return json.dumps(payload, ensure_ascii=False)


def cargar_solicitudes(path=BIN_PATH):
    # Abre el archivo binario y devuelve la lista de solicitudes (dicts).
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def log_line(text: str):
    # Escribe una línea en el archivo de log (append) usando LOG_PATH actual (puede ser override).
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def parse_runtime_args():
    # Lee timeout, backoff y log file desde CLI y/o ENV.
    parser = argparse.ArgumentParser(description="PS runtime params", add_help=False)
    parser.add_argument("--timeout", type=float,
                        default=float(os.getenv("PS_TIMEOUT", TIMEOUT_S)),
                        help="Timeout de respuesta del GC en segundos")
    parser.add_argument("--backoff", type=str,
                        default=os.getenv("PS_BACKOFF", ",".join(map(str, BACKOFFS))),
                        help="Secuencia de backoff en segundos, separada por comas")
    parser.add_argument("--log-file", type=str,
                        default=ENV_LOG_PATH or str(LOG_PATH),
                        help="Ruta de archivo de log (override). Por defecto ps_logs.txt en raíz.")
    try:
        args, _ = parser.parse_known_args()
    except SystemExit:
        return TIMEOUT_S, BACKOFFS, str(LOG_PATH)

    try:
        backoffs = [float(x) for x in args.backoff.split(",") if x.strip()]
        if not backoffs:
            backoffs = BACKOFFS
    except Exception:
        backoffs = BACKOFFS

    return args.timeout, backoffs, args.log_file


def main():
    global LOG_PATH  # permitirá cambiar el path del log si se pasa por CLI/ENV
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(GC_ADDR)

    # Lee timeout/backoff y log_path efectivos (CLI/ENV)
    timeout_s, backoffs, log_path_override = parse_runtime_args()
    LOG_PATH = Path(log_path_override)  # aplica override

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

                wire = build_gc_payload(req)
                try:
                    sock.send_string(wire)
                except zmq.ZMQError:
                    # Estado REQ inválido, recrear socket y reintentar en el próximo ciclo
                    try:
                        sock.close(linger=0)
                    except Exception:
                        pass
                    sock = ctx.socket(zmq.REQ)
                    sock.setsockopt(zmq.LINGER, 0)
                    sock.connect(GC_ADDR)
                    # espera mínima antes de próxima iteración
                    time.sleep(0.01)

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
                    # Timeout: aplica backoff o falla definitivo. Reparar socket antes de próximo send
                    if attempt == len(backoffs):
                        print_bloque_timeout(wait=0.0, agotado=True)
                        fail += 1
                        break
                    wait = backoffs[attempt]
                    print_bloque_timeout(wait=wait, agotado=False)
                    # Cerrar y recrear socket para evitar estado REQ bloqueado
                    try:
                        sock.close(linger=0)
                    except Exception:
                        pass
                    sock = ctx.socket(zmq.REQ)
                    sock.setsockopt(zmq.LINGER, 0)
                    sock.connect(GC_ADDR)
                    time.sleep(wait)
                    attempt += 1

            end = time.time()

            # Guarda métricas por solicitud (formato estable para el parser)
            log_line(
                f"request_id={req['request_id']}|"
                f"operation={req['operation']}|"
                f"start={start:.6f}|end={end:.6f}|"
                f"status={status}|retries={attempt}"
            )

            if status == "TIMEOUT" and attempt == len(backoffs):
                # Asegurar que operación exista y request_id para parser
                if not req.get("operation"):
                    req["operation"] = "renovacion"
                if not req.get("request_id"):
                    req["request_id"] = f"synthetic_{i}"

                # Guarda línea sintética en el log (para que el parser no falle)
                log_line(
                    f"request_id={req['request_id']}|"
                    f"operation={req['operation']}|"
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
