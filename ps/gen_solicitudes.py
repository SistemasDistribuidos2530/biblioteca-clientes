# archivo: ps/gen_solicitudes.py
# 
# Qué hace:
#   Genera 'solicitudes.bin' en la RAÍZ del repo (SistemasDistribuidos/).
#   Permite configurar:
#     - N de solicitudes (CLI --n o ENV NUM_SOLICITUDES; default=25)
#     - Semilla (--seed) para reproducibilidad
#     - Mezcla RENOVACION:DEVOLUCION (--mix "70:30", default "50:50")
#
# Formato de cada elemento:
#   dict con request_id, tipo, book_id, user_id, ts, hmac
#   (la HMAC igual se recalcula en el envío desde ps.py)
#
# Uso:
#   python ps/gen_solicitudes.py
#   python ps/gen_solicitudes.py --n 500 --seed 42 --mix 70:30
#   NUM_SOLICITUDES=1000 python ps/gen_solicitudes.py --seed 1

import os
import pickle               # Serialización binaria sencilla (estándar de Python)
import random
import argparse
from pathlib import Path    # Manejo de rutas (independiente del cwd)
from schema import make_request  # Construye la estructura y firma HMAC de cada solicitud

# Calcula la ruta de la RAÍZ del repo partiendo de este archivo (ps/)
# es decir: SistemasDistribuidos/
ROOT = Path(__file__).resolve().parents[1]

# Ruta de salida FINAL: SistemasDistribuidos/solicitudes.bin
OUT = ROOT / "solicitudes.bin"

def parse_args():
    
    # Lee la configuración desde CLI y ENV.
    # Prioridad N: CLI (--n) > ENV (NUM_SOLICITUDES) > DEFAULT (25).

    p = argparse.ArgumentParser(description="Genera solicitudes.bin con N solicitudes")
    p.add_argument("--n", type=int, default=None,
                   help="Cantidad de solicitudes a generar (override por CLI)")
    p.add_argument("--seed", type=int, default=None,
                   help="Semilla para reproducibilidad (mismas solicitudes)")
    p.add_argument("--mix", type=str, default="50:50",
                   help="Proporción RENOVACION:DEVOLUCION, ej. '70:30' (default '50:50')")
    args = p.parse_args()

    # N desde ENV si no viene por CLI
    n_env = os.getenv("NUM_SOLICITUDES")
    if args.n is not None:
        n = args.n
    elif n_env is not None and n_env.isdigit():
        n = int(n_env)
    else:
        n = 25

    return n, args.seed, args.mix


def parse_mix(mix_str: str) -> tuple[int, int]:
    
    # Convierte una cadena 'A:B' a dos enteros (A, B).
    # Valida y normaliza proporciones (si A+B=0, 50:50).
    # es decir: cuando se da el comando de entrada y hay una distribucion de cargas dadas por el usuario
    # como 70:30 esto lo separa y asigna 70 para renovacion y 30 para devolucion
    
    try:
        a_str, b_str = mix_str.split(":")
        a, b = int(a_str), int(b_str)
    except Exception:
        # Si el formato no es válido, usar 50:50
        a, b = 50, 50

    if a < 0 or b < 0:
        a, b = 50, 50
    if (a + b) == 0:
        a, b = 50, 50
    return a, b


def pick_tipo(a: int, b: int) -> str:
    
    # Elige 'RENOVACION' o 'DEVOLUCION' según la proporción a:b.
    # Implementación: sorteo en el rango [1 .. a+b].
    
    r = random.randint(1, a + b)
    return "RENOVACION" if r <= a else "DEVOLUCION"


def generar_solicitudes(n: int, seed: int | None, mix_str: str):
    
    # Genera n solicitudes con la mezcla indicada y, si se da, con semilla fija.
    # seed: si se especifica, setea random.seed(seed) para reproducibilidad.
    # mix_str: proporción 'RENOVACION:DEVOLUCION' (p. ej. 70:30).

    # es decir: Cuando se fija una semilla, se le dice al programa:
    # así, el resultado será idéntico si se ejecuta el mismo comando con la misma semilla.
    # y eso ayuda a las pruebas para comparar bien los resultados

    
    if seed is not None:
        # Fija la semilla para que la secuencia aleatoria sea determinista
        random.seed(seed)

    a, b = parse_mix(mix_str)  # p.ej., "70:30" -> (70, 30)

    batch = []
    for _ in range(n):
        tipo = pick_tipo(a, b)
        # book_id y user_id en rangos sencillos (válidos para la entrega)
        book_id = random.randint(1, 1000)
        user_id = random.randint(1, 100)
        batch.append(make_request(tipo, book_id, user_id))

    # Serializa todo el lote en la RAÍZ del repo
    with open(OUT, "wb") as f:
        pickle.dump(batch, f)

    print(f"'{OUT.name}' generado en: {OUT} (N={n}, seed={seed}, mix={a}:{b})")


if __name__ == "__main__":
    n, seed, mix_str = parse_args()
    generar_solicitudes(n, seed, mix_str)
