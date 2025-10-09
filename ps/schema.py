# archivo: ps/schema.py
# 
# Firma y verificación de mensajes del PS:
# - Campos: request_id, tipo, book_id, user_id, ts, nonce, hmac
# - HMAC-SHA256 sobre el payload sin 'hmac'
# - Validación de tipo y ventana de tiempo

import os, hmac, hashlib, json, time, uuid, secrets

# Lee la clave de entorno; usa bytes siempre
SECRET_KEY = os.environ.get("SECRET_KEY", "demo-key")
if isinstance(SECRET_KEY, str):
    SECRET_KEY = SECRET_KEY.encode()

# Tipos permitidos (según tu uso actual)
ALLOWED_TIPOS = {"RENOVACION", "DEVOLUCION"}

def timestamp() -> int:
    # Epoch en segundos (entero)
    return int(time.time())

def _canonical_payload(data: dict) -> bytes:
    # JSON estable (ordenado) para firmar/verificar
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

def sign(msg: dict) -> str:
    # Calcula HMAC-SHA256 ignorando el campo 'hmac'
    payload = {k: v for k, v in msg.items() if k != "hmac"}
    raw = _canonical_payload(payload)
    return hmac.new(SECRET_KEY, raw, hashlib.sha256).hexdigest()

def verify(msg: dict, window: int = 60) -> bool:
    # Verifica HMAC y ventana de tiempo (±window segundos)
    try:
        mac = msg.get("hmac", "")
        payload = {k: v for k, v in msg.items() if k != "hmac"}
        raw = _canonical_payload(payload)
        good_mac = hmac.compare_digest(
            mac, hmac.new(SECRET_KEY, raw, hashlib.sha256).hexdigest()
        )
        ts = int(msg.get("ts", 0))
        good_ts = abs(timestamp() - ts) <= window
        return bool(good_mac and good_ts)
    except Exception:
        return False

def make_request(tipo: str, book_id: int, user_id: int) -> dict:
    # Crea una solicitud válida y firmada
    # es decir: valida tipo, arma payload con ts y nonce, y añade hmac
    if tipo not in ALLOWED_TIPOS:
        raise ValueError(f"tipo inválido: {tipo}")

    data = {
        "request_id": uuid.uuid4().hex,   # identificador único
        "tipo": tipo,                     # operación
        "book_id": int(book_id),          # normaliza a int
        "user_id": int(user_id),          # normaliza a int
        "ts": timestamp(),                # marca de tiempo (seguridad)
        "nonce": secrets.token_hex(8),    # aleatorio; evita replay por duplicado exacto
    }
    data["hmac"] = sign(data)
    return data
