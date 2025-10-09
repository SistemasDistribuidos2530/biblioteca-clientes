#!/usr/bin/env python3
# archivo: ps/schema.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 8 de octubre de 2025
#
# Qué hace:
#   Firma y verificación de mensajes del PS (HMAC-SHA256).
#   Estructura base de cada solicitud y utilidades de validación.
#
# Campos esperados en cada solicitud:
#   request_id, tipo, book_id, user_id, ts, nonce, hmac
#
# Notas:
#   - La firma HMAC se calcula sobre el JSON canónico SIN el campo 'hmac'.
#   - La verificación incluye ventana de tiempo (ts) para mitigar replay.
#   - Se acepta el 'tipo' en cualquier casing; se normaliza a MAYÚSCULAS.

import os
import hmac
import hashlib
import json
import time
import uuid
import secrets

# Intenta cargar variables desde .env si está disponible (robusto ante orden de imports).
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Tipos permitidos en el sistema (normalizados a MAYÚSCULAS).
ALLOWED_TIPOS = {"RENOVACION", "DEVOLUCION"}


# ---------- Utilidades internas ----------

def _timestamp() -> int:
    # Epoch en segundos (entero)
    return int(time.time())


def _canonical_payload(data: dict) -> bytes:
    # JSON estable (ordenado) para firmar/verificar
    # sort_keys=True: ordena claves → canónico
    # separators=(",", ":"): evita espacios → canónico
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def _get_secret_key() -> bytes:
    # Obtiene SECRET_KEY desde entorno, siempre como bytes.
    # Se lee en cada llamada para soportar cambios de .env antes de ejecución.
    key = os.environ.get("SECRET_KEY", "demo-key")
    return key.encode() if isinstance(key, str) else key


def _normalize_tipo(tipo: str) -> str:
    # Normaliza 'tipo' a MAYÚSCULAS y valida que esté permitido.
    t = str(tipo).strip().upper()
    if t not in ALLOWED_TIPOS:
        raise ValueError(f"tipo inválido: {tipo!r} (válidos: {', '.join(sorted(ALLOWED_TIPOS))})")
    return t


# ---------- API pública ----------

def sign(msg: dict) -> str:
    # Calcula HMAC-SHA256 ignorando el campo 'hmac'
    payload = {k: v for k, v in msg.items() if k != "hmac"}
    raw = _canonical_payload(payload)
    return hmac.new(_get_secret_key(), raw, hashlib.sha256).hexdigest()


def verify(msg: dict, window: int = 60) -> bool:
    # Verifica HMAC y ventana de tiempo (±window segundos)
    try:
        mac = msg.get("hmac", "")
        payload = {k: v for k, v in msg.items() if k != "hmac"}
        raw = _canonical_payload(payload)

        good_mac = hmac.compare_digest(
            mac,
            hmac.new(_get_secret_key(), raw, hashlib.sha256).hexdigest()
        )

        ts = int(msg.get("ts", 0))
        good_ts = abs(_timestamp() - ts) <= window

        return bool(good_mac and good_ts)
    except Exception:
        return False


def make_request(tipo: str, book_id: int, user_id: int) -> dict:
    # Crea una solicitud válida y firmada:
    #   - Valida/normaliza 'tipo'
    #   - Normaliza 'book_id' y 'user_id' a int
    #   - Añade 'ts' (epoch) y 'nonce' aleatorio
    #   - Calcula 'hmac' sobre el payload canónico
    tipo_norm = _normalize_tipo(tipo)

    data = {
        "request_id": uuid.uuid4().hex,    # identificador único
        "tipo": tipo_norm,                  # RENOVACION | DEVOLUCION (MAYÚSCULAS)
        "book_id": int(book_id),            # normaliza a int
        "user_id": int(user_id),            # normaliza a int
        "ts": _timestamp(),                 # marca de tiempo (seguridad)
        "nonce": secrets.token_hex(8),      # aleatorio; desalienta replay exacto
    }
    data["hmac"] = sign(data)
    return data
