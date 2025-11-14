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
    print(f"  Mezcla          : {mix}  (RENOVACION:DEVOLUCION:PRESTAMO)")
    print("=" * 72 + "\n")


def banner_resumen(n: int, seed, a: int, b: int, c: int, c_ren: int, c_dev: int, c_pres: int):
    # Muestra un bloque de resumen final (conteo por tipo y parámetros efectivos).
    print("-" * 72)
    print(" RESUMEN DE GENERACIÓN ".center(72, " "))
    print("-" * 72)
    print(f"  Total generadas      : {n}")
    print(f"  RENOVACION (objetivo): {a:>3}   | Generadas: {c_ren}")
    print(f"  DEVOLUCION (objetivo): {b:>3}   | Generadas: {c_dev}")
    print(f"  PRESTAMO   (objetivo): {c:>3}   | Generadas: {c_pres}")
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
    p.add_argument("--mix", type=str, default="50:50:0",
                   help="Proporción RENOVACION:DEVOLUCION:PRESTAMO, ej. '40:40:20' (default '50:50:0')")
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


def parse_mix(mix_str: str) -> tuple[int, int, int]:
    # Convierte una cadena 'A:B:C' a tres enteros (A, B, C).
    # Soporta formato legacy 'A:B' (asume C=0).
    # Valida y normaliza proporciones (si A+B+C=0, usa 50:50:0).
    try:
        parts = mix_str.split(":")
        if len(parts) == 2:
            # Formato legacy: "70:30" → (70, 30, 0)
            a, b = int(parts[0]), int(parts[1])
            c = 0
        elif len(parts) == 3:
            # Formato completo: "40:40:20" → (40, 40, 20)
            a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            a, b, c = 50, 50, 0
    except Exception:
        a, b, c = 50, 50, 0  # Formato inválido → default

    if a < 0 or b < 0 or c < 0:
        a, b, c = 50, 50, 0
    if (a + b + c) == 0:
        a, b, c = 50, 50, 0
    return a, b, c


def pick_tipo(a: int, b: int, c: int) -> str:
    # Elige 'RENOVACION', 'DEVOLUCION' o 'PRESTAMO' según la proporción a:b:c.
    # Implementación: sorteo en el rango [1 .. a+b+c].
    total = a + b + c
    r = random.randint(1, total)
    if r <= a:
        return "RENOVACION"
    elif r <= a + b:
        return "DEVOLUCION"
    else:
        return "PRESTAMO"


def generar_solicitudes(n: int, seed: int | None, mix_str: str):
    # Genera n solicitudes con la mezcla indicada y, si se da, con semilla fija.
    # seed: si se especifica, setea random.seed(seed) para reproducibilidad.
    # mix_str: proporción 'RENOVACION:DEVOLUCION:PRESTAMO' (p. ej. 40:40:20).

    if seed is not None:
        # Fija la semilla para que la secuencia aleatoria sea determinista.
        random.seed(seed)

    a, b, c = parse_mix(mix_str)  # p.ej., "40:40:20" -> (40, 40, 20)
    banner_inicio(n, seed, f"{a}:{b}:{c}")

    batch = []
    c_ren = 0   # Conteo RENOVACION generado efectivamente
    c_dev = 0   # Conteo DEVOLUCION generado efectivamente
    c_pres = 0  # Conteo PRESTAMO generado efectivamente

    for _ in range(n):
        tipo = pick_tipo(a, b, c)
        # book_id y user_id en rangos sencillos (válidos para la entrega)
        book_id = random.randint(1, 1000)
        user_id = random.randint(1, 100)
        batch.append(make_request(tipo, book_id, user_id))
        if tipo == "RENOVACION":
            c_ren += 1
        elif tipo == "DEVOLUCION":
            c_dev += 1
        else:
            c_pres += 1

    # Serializa todo el lote en la RAÍZ del repo.
    with open(OUT, "wb") as f:
        pickle.dump(batch, f)

    # Mensaje final legible (bloque)
    banner_resumen(n, seed, a, b, c, c_ren, c_dev, c_pres)


if __name__ == "__main__":
    n, seed, mix_str = parse_args()
    generar_solicitudes(n, seed, mix_str)
