#!/usr/bin/env python3
# archivo: ps/gen_solicitudes.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 8 de octubre de 2025
#
# Qué hace:
#   Genera 'solicitudes.bin' en la RAÍZ del repo (biblioteca-clientes/).
#   Permite configurar:
#     - N de solicitudes (CLI --n o ENV NUM_SOLICITUDES; default=25)
#     - Semilla (--seed) para reproducibilidad
#     - Mezcla RENOVACION:DEVOLUCION (--mix "70:30", default "50:50")
#
# Formato de cada elemento:
#   dict con: request_id, tipo ("RENOVACION"|"DEVOLUCION"), book_id, user_id, ts, hmac
#   (la HMAC igual se recalcula en el envío desde ps.py)
#
# Uso:
#   python ps/gen_solicitudes.py
#   python ps/gen_solicitudes.py --n 500 --seed 42 --mix 70:30
#   NUM_SOLICITUDES=1000 python ps/gen_solicitudes.py --seed 1
#
# Salida en consola:
#   Se imprime un bloque legible con ruta del binario, resumen por tipo y parámetros usados.

import os
import pickle               # Serialización binaria sencilla (estándar de Python)
import random
import argparse
from pathlib import Path    # Manejo de rutas (independiente del cwd)
from schema import make_request  # Construye la estructura y firma HMAC de cada solicitud

# Calcula la ruta de la RAÍZ del repo partiendo de este archivo (ps/)
# es decir: biblioteca-clientes/
ROOT = Path(__file__).resolve().parents[1]

# Ruta de salida FINAL: biblioteca-clientes/solicitudes.bin
OUT = ROOT / "solicitudes.bin"


def banner_inicio(n: int, seed, mix: str):
    # Imprime encabezado legible con los parámetros de generación.
    print("\n" + "=" * 72)
    print(" GENERADOR DE SOLICITUDES ".center(72, " "))
    print("-" * 72)
    print(f"  Archivo destino : {OUT}")
    print(f"  Cantidad (N)    : {n}")
    print(f"  Semilla (seed)  : {seed}")
    print(f"  Mezcla          : {mix}  (RENOVACION:DEVOLUCION)")
    print("=" * 72 + "\n")


def banner_resumen(n: int, seed, a: int, b: int, c_ren: int, c_dev: int):
    # Muestra un bloque de resumen final (conteo por tipo y parámetros efectivos).
    print("-" * 72)
    print(" RESUMEN DE GENERACIÓN ".center(72, " "))
    print("-" * 72)
    print(f"  Total generadas      : {n}")
    print(f"  RENOVACION (objetivo): {a:>3}   | Generadas: {c_ren}")
    print(f"  DEVOLUCION (objetivo): {b:>3}   | Generadas: {c_dev}")
    print(f"  Semilla usada        : {seed}")
    print(f"  Archivo              : {OUT}")
    print("-" * 72 + "\n")


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
    # es decir: cuando el usuario da una distribución como 70:30,
    # esto lo separa y asigna 70 para RENOVACION y 30 para DEVOLUCION.
    try:
        a_str, b_str = mix_str.split(":")
        a, b = int(a_str), int(b_str)
    except Exception:
        a, b = 50, 50  # Formato inválido → default
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

    if seed is not None:
        # Fija la semilla para que la secuencia aleatoria sea determinista
        # (mismo comando + misma semilla => mismo archivo generado).
        random.seed(seed)

    a, b = parse_mix(mix_str)  # p.ej., "70:30" -> (70, 30)
    banner_inicio(n, seed, f"{a}:{b}")

    batch = []
    c_ren = 0  # Conteo RENOVACION generado efectivamente
    c_dev = 0  # Conteo DEVOLUCION generado efectivamente

    for _ in range(n):
        tipo = pick_tipo(a, b)
        # book_id y user_id en rangos sencillos (válidos para la entrega)
        book_id = random.randint(1, 1000)
        user_id = random.randint(1, 100)
        batch.append(make_request(tipo, book_id, user_id))
        if tipo == "RENOVACION":
            c_ren += 1
        else:
            c_dev += 1

    # Serializa todo el lote en la RAÍZ del repo.
    with open(OUT, "wb") as f:
        pickle.dump(batch, f)

    # Mensaje final legible (bloque)
    banner_resumen(n, seed, a, b, c_ren, c_dev)


if __name__ == "__main__":
    n, seed, mix_str = parse_args()
    generar_solicitudes(n, seed, mix_str)
