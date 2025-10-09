#!/usr/bin/env python3
# archivo: ps/send_compat.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 8 de octubre de 2025
#
# Qué hace:
#   Envío "compatible" con el GC de ellos (JSON como string).
#   - Lee solicitudes.bin (lista de dicts generados por gen_solicitudes.py)
#   - Mapea:  tipo (RENOVACION/DEVOLUCION) → operation (renovacion/devolucion)
#             book_id → book_code="BOOK-<id>"
#             user_id → user_id (str o int)
#   - Envía por REQ usando send_string(json.dumps(...))
#   - Recibe string y normaliza OK/ERROR para reporte
#
# Uso:
#   python ps/send_compat.py
#   python ps/send_compat.py --timeout 2.5
#   GC_ADDR=tcp://10.43.101.220:5555 python ps/send_compat.py
#
# Salida en consola:
#   - Banner con parámetros efectivos
#   - Bloques legibles por solicitud (envío/resp/timeout)
#   - Resumen final

import os
import pickle
import time
import json
import argparse
from pathlib import Path

import zmq
from dotenv import load_dotenv

# ---------- Rutas ----------
ROOT = Path(__file__).resolve().parents[1]
BIN_PATH = ROOT / "solicitudes.bin"

# ---------- Config ----------
load_dotenv()
# M3 → por defecto apunta al GC en M1:
GC_ADDR = os.getenv("GC_ADDR", "tcp://10.43.101.220:5555")

# ---------- Utilidades de impresión (salida legible) ----------

def banner_inicio(gc_addr: str, timeout_s: float, total: int | None):
    # Encabezado de inicio con parámetros efectivos.
    print("\n" + "=" * 72)
    print(" PS COMPAT — REQ/REP (JSON string) ".center(72, " "))
    print("-" * 72)
    print(f"  Conectando a  : {gc_addr}")
    print(f"  Timeout (s)   : {timeout_s}")
    if total is not None:
        print(f"  Lote a enviar : {total} solicitudes")
    print(f"  Fuente        : {BIN_PATH}")
    print("=" * 72 + "\n")


def print_bloque_envio(i: int, total: int, req: dict):
    # Muestra los campos relevantes que se mapearán a JSON.
    print("-" * 72)
    print(f" ENVÍO {i}/{total} ".center(72, " "))
    print("-" * 72)
    print(f"  request_id : {req.get('request_id')}")
    print(f"  tipo       : {req.get('tipo')}")
    print(f"  book_id    : {req.get('book_id')}")
    print(f"  user_id    : {req.get('user_id')}")
    print("-" * 72 + "\n")


def print_bloque_respuesta(status: str, resp: dict | None):
    # Bloque legible con la respuesta del GC (si es parseable).
    print("-" * 72)
    print(" RESPUESTA DEL GC ".center(72, " "))
    print("-" * 72)
    print(f"  status  : {status}")
    if isinstance(resp, dict) and resp:
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


def print_bloque_timeout(timeout_s: float):
    # Informa un timeout de respuesta para la solicitud actual.
    print("-" * 72)
    print(" TIMEOUT DE RESPUESTA ".center(72, " "))
    print("-" * 72)
    print(f"  No se recibió respuesta en {timeout_s} s.")
    print("-" * 72 + "\n")


def print_resumen(ok: int, fail: int):
    # Resumen del envío de todo el lote.
    print("\n" + "=" * 72)
    print(" RESUMEN PS COMPAT ".center(72, " "))
    print("-" * 72)
    print(f"  OK        : {ok}")
    print(f"  FALLIDOS  : {fail}")
    print("=" * 72 + "\n")


# ---------- Lógica ----------

def cargar_solicitudes(path=BIN_PATH):
    # Lee el archivo binario y retorna una lista de dicts.
    if not path.exists():
        raise FileNotFoundError(f"No se encontró {path}. Genere primero con ps/gen_solicitudes.py")
    with open(path, "rb") as f:
        return pickle.load(f)

def to_json_string(req: dict) -> str:
    # Mapea el payload interno del PS al "dialecto GC" (JSON → string).
    oper = str(req.get("tipo", "")).strip().lower()   # 'RENOVACION' → 'renovacion'
    book_code = f"BOOK-{req.get('book_id')}"
    user_id = req.get("user_id")
    payload = {"operation": oper, "book_code": book_code, "user_id": user_id}
    return json.dumps(payload, ensure_ascii=False)

def parse_args():
    ap = argparse.ArgumentParser(description="Sender compatible (JSON string) hacia GC")
    ap.add_argument("--timeout", type=float, default=float(os.getenv("PS_TIMEOUT", 2.0)),
                    help="Timeout de espera de respuesta (segundos)")
    return ap.parse_args()

def main():
    args = parse_args()

    # Carga solicitudes
    batch = cargar_solicitudes()
    total = len(batch)

    # ZMQ: REQ → GC
    ctx = zmq.Context()
    s = ctx.socket(zmq.REQ)
    s.connect(GC_ADDR)

    banner_inicio(GC_ADDR, args.timeout, total)

    ok = 0
    fail = 0

    try:
        for i, req in enumerate(batch, start=1):
            print_bloque_envio(i, total, req)

            wire = to_json_string(req)     # JSON → string
            s.send_string(wire)            # su GC usa recv_string()

            if s.poll(int(args.timeout * 1000), zmq.POLLIN):
                raw = s.recv_string()      # su GC responde string JSON
                try:
                    r = json.loads(raw)
                except Exception:
                    r = {}
                # Su GC responde {"estado":"ok"} → normalizamos a OK/ERROR
                status = r.get("status")
                if not status:
                    estado = str(r.get("estado", "")).upper() if r else ""
                    status = "OK" if estado in ("OK", "OKAY", "SUCCESS") else "ERROR"
                print_bloque_respuesta(status, r)
                ok += int(status == "OK")
                fail += int(status != "OK")
            else:
                print_bloque_timeout(args.timeout)
                fail += 1

        print_resumen(ok, fail)

    finally:
        try:
            s.close(linger=0)
        finally:
            ctx.term()

if __name__ == "__main__":
    main()
