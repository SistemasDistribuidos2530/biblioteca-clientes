# archivo: ps/ps.py
# 
# Cliente del Proceso Solicitante (PS):
# - Lee 'solicitudes.bin' desde la RAÍZ.
# - Recalcula HMAC antes de enviar.
# - Envía por ZeroMQ (REQ) al GC y espera REP con timeout.
# - Reintenta usando backoff exponencial.
# - Registra métricas en 'ps_logs.txt' (en la RAÍZ) para TPS/latencias.

import os
import time
import pickle
import argparse
import zmq
import json
from pathlib import Path
from dotenv import load_dotenv
from schema import sign

load_dotenv()

GC_ADDR = os.getenv("GC_ADDR", "tcp://10.43.101.220:5555")

ROOT = Path(__file__).resolve().parents[1]     # Ruta base del repo
BIN_PATH = ROOT / "solicitudes.bin"            # Archivo de entrada
LOG_PATH = ROOT / "ps_logs.txt"                # Archivo de salida (métricas)

# Backoff por defecto (segundos)
BACKOFFS = [0.5, 1, 2, 4]
# Timeout por defecto (segundos)
TIMEOUT_S = 2.0


def build_gc_payload(req: dict) -> str:
    """
    Adapta la solicitud del PS al formato que espera el GC de ellos.
    Retorna un JSON SERIALIZADO EN STRING (el GC usa recv_string()) con:
      {
        "operation": "renovacion" | "devolucion",
        "book_code": "BOOK-<id>",
        "user_id": <id>
      }
    - 'tipo' (RENOVACION/DEVOLUCION) se pasa a minúsculas para 'operation'.
    - 'book_id' se mapea a 'book_code' con prefijo BOOK-.
    """
    oper = str(req.get("tipo", "")).strip().lower()
    payload = {
        "operation": oper,
        "book_code": f"BOOK-{req.get('book_id')}",
        "user_id": req.get("user_id"),
    }
    return json.dumps(payload, ensure_ascii=False)


def cargar_solicitudes(path=BIN_PATH):
    # Abre el archivo binario y devuelve la lista de solicitudes.
    # Si el archivo no existe, lanza un error claro.
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def log_line(text: str):
    # Escribe una línea en el archivo de log (append).
    # Cada línea representa una solicitud enviada y su resultado.
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def parse_runtime_args():
    # Lee timeout y backoff desde CLI o variables de entorno.
    # Permite cambiar parámetros sin modificar el código.

    parser = argparse.ArgumentParser(description="PS runtime params", add_help=False)
    parser.add_argument("--timeout", type=float, default=float(os.getenv("PS_TIMEOUT", TIMEOUT_S)),
                        help="Timeout de respuesta del GC en segundos")
    parser.add_argument("--backoff", type=str, default=os.getenv("PS_BACKOFF", ",".join(map(str, BACKOFFS))),
                        help="Secuencia de backoff en segundos, separada por comas")

    # Obtiene valores parseados, si hay error usa los valores por defecto
    try:
        args, _ = parser.parse_known_args()
    except SystemExit:
        return TIMEOUT_S, BACKOFFS

    # Convierte la cadena "0.5,1,2,4" a lista [0.5, 1, 2, 4]
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
    print(f"Conectado al Gestor de Carga: {GC_ADDR}")

    # Lee timeout/backoff de CLI o ENV
    timeout_s, backoffs = parse_runtime_args()

    try:
        solicitudes = cargar_solicitudes()
        ok, fail = 0, 0

        for req in solicitudes:
            # Recalcula la firma HMAC antes de enviar (por si cambió SECRET_KEY)
            req["hmac"] = sign(req)
            start = time.time()

            attempt = 0
            status = "TIMEOUT"

            # Envío con reintentos (backoff exponencial)
            while attempt <= len(backoffs):
                # ENVÍO en “dialecto GC”: JSON serializado como STRING (su GC hace recv_string)
                wire = build_gc_payload(req)
                sock.send_string(wire)

                # Espera respuesta del GC dentro del timeout
                if sock.poll(int(timeout_s * 1000), zmq.POLLIN):
                    # RECEPCIÓN como STRING y normalización de status
                    raw = sock.recv_string()
                    try:
                        resp = json.loads(raw)
                    except Exception:
                        resp = {}

                    # Ellos suelen usar {"estado": "ok"}; normalizamos a "OK"/"ERROR"
                    status = resp.get("status")
                    if not status:
                        estado = str(resp.get("estado", "")).upper() if resp else ""
                        status = "OK" if estado in ("OK", "OKAY", "SUCCESS") else "ERROR"

                    print(f"RESP {status} {resp}")
                    ok += int(status == "OK")
                    fail += int(status != "OK")
                    break
                else:
                    # Timeout: aplica backoff o falla definitivo
                    if attempt == len(backoffs):
                        print("Timeout definitivo (sin más reintentos)")
                        fail += 1
                        break
                    wait = backoffs[attempt]
                    print(f"Timeout, reintentando en {wait} s...")
                    time.sleep(wait)
                    attempt += 1

            end = time.time()

            # Guarda métricas por solicitud
            log_line(
                f"request_id={req['request_id']}|"
                f"tipo={req['tipo']}|"
                f"start={start:.6f}|end={end:.6f}|"
                f"status={status}|retries={attempt}"
            )

        # Resumen final
        print(f"Resumen PS: OK={ok} FALLIDOS={fail}")
        print(f"Log de métricas: {LOG_PATH}")

    finally:
        # Cierre ordenado de recursos
        try:
            sock.close(linger=0)
        finally:
            ctx.term()


if __name__ == "__main__":
    main()
