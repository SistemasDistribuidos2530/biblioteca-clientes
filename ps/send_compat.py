# archivo: ps/send_compat.py
# Envío compatible con el GC de ellos (JSON como string).
# - Lee solicitudes.bin
# - Mapea: tipo(RENOVACION/DEVOLUCION)->operation(renovacion/devolucion)
#         book_id -> book_code="BOOK-<id>"
#         user_id -> user_id (str o int)
# - Envía por REQ con send_string(json.dumps(...))
# - Recibe string y normaliza OK/ERROR

import os, pickle, time, json, argparse
import zmq
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BIN_PATH = ROOT / "solicitudes.bin"

load_dotenv()
GC_ADDR = os.getenv("GC_ADDR", "tcp://127.0.0.1:5555")

def cargar_solicitudes(path=BIN_PATH):
    with open(path, "rb") as f:
        return pickle.load(f)

def to_json_string(req: dict) -> str:
    oper = str(req.get("tipo", "")).strip().lower()   # 'RENOVACION'->'renovacion'
    book_code = f"BOOK-{req.get('book_id')}"
    user_id = req.get("user_id")
    payload = {"operation": oper, "book_code": book_code, "user_id": user_id}
    return json.dumps(payload, ensure_ascii=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=2.0)
    args = ap.parse_args()

    ctx = zmq.Context()
    s = ctx.socket(zmq.REQ)
    s.connect(GC_ADDR)
    print(f"[compat] Conectado a {GC_ADDR}")

    batch = cargar_solicitudes()
    ok = fail = 0

    for req in batch:
        wire = to_json_string(req)          # JSON -> string
        s.send_string(wire)                 # su GC usa recv_string()

        if s.poll(int(args.timeout * 1000), zmq.POLLIN):
            raw = s.recv_string()           # su GC responde string JSON
            try:
                r = json.loads(raw)
            except Exception:
                r = {}
            # Su GC responde {"estado":"ok"} -> normalizamos a OK/ERROR
            status = r.get("status")
            if not status:
                estado = str(r.get("estado", "")).upper() if r else ""
                status = "OK" if estado == "OK" else "ERROR"
            print(f"RESP {status}")
            ok += int(status == "OK")
            fail += int(status != "OK")
        else:
            print("RESP TIMEOUT")
            fail += 1

    print(f"[compat] Resumen: OK={ok} FALLIDOS={fail}")

if __name__ == "__main__":
    main()
