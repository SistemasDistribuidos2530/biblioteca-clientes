# common/security.py (mínimo)
import hmac, hashlib, json, os, time

SECRET_KEY = os.environ.get("SECRET_KEY","demo-key").encode()

def now_ts() -> int:
    return int(time.time())

def sign(payload: dict) -> str:
    data = {k:v for k,v in payload.items() if k != "hmac"}
    raw = json.dumps(data, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, raw, hashlib.sha256).hexdigest()

def verify(payload: dict, window=60) -> bool:
    try:
        mac = payload.get("hmac","")
        ts  = int(payload.get("ts",0))
        if abs(now_ts() - ts) > window:
            return False
        return hmac.compare_digest(mac, sign(payload))
    except Exception:
        return False
