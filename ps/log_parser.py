#!/usr/bin/env python3
# archivo: ps/log_parser.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 8 de octubre de 2025
#
# Qué hace:
#   Analiza el log línea-a-línea generado por ps/ps.py (ps_logs.txt)
#
# Formato esperado por línea:
#   request_id=<id>|tipo=<tipo>|start=<epoch_f>|end=<epoch_f>|status=<OK|ERROR|TIMEOUT>|retries=<int>
#
# Calcula:
#   - Totales por estado (OK/ERROR/TIMEOUT)
#   - Latencias (end - start): media, p50, p95, máx
#   - TPS ≈ total / (t_ultima - t_primera), usando 'start' como referencia
#
# CLI:
#   --log RUTA        Ruta al log (default: ./ps_logs.txt)
#   --tipo T          Filtro por tipo (renovacion | devolucion) [case-insensitive]
#   --only-ok         Métricas de latencia sólo con status=OK
#   --csv SALIDA      Exporta métricas agregadas a CSV (append si existe)
#
# Uso:
#   python ps/log_parser.py
#   python ps/log_parser.py --tipo renovacion
#   python ps/log_parser.py --log otro_log.txt --only-ok --csv resultados.csv

import re
import argparse
import statistics
from pathlib import Path
import sys

# Regex para extraer campos de cada línea
LINE_RE = re.compile(
    r"request_id=(?P<id>[^|]+)\|"
    r"tipo=(?P<tipo>[^|]+)\|"
    r"start=(?P<start>[\d.]+)\|"
    r"end=(?P<end>[\d.]+)\|"
    r"status=(?P<status>\w+)"
    r"(?:\|retries=(?P<retries>\d+))?"
)

TIPOS_VALIDOS = {"renovacion", "devolucion"}

# ---------- Utilidades de impresión (salida legible) ----------

def banner_inicio(log_path: Path, tipo: str | None, only_ok: bool, csv_path: str | None):
    # Encabezado legible al iniciar el análisis.
    print("\n" + "=" * 72)
    print(" PARSER DE LOGS — MÉTRICAS PS ".center(72, " "))
    print("-" * 72)
    print(f"  Log      : {log_path}")
    print(f"  Filtro   : tipo={tipo or 'ALL'}")
    print(f"  only_ok  : {only_ok}")
    print(f"  CSV out  : {csv_path or '(no)'}")
    print("=" * 72 + "\n")

def print_metrics(title: str, m: dict):
    # Bloque multilínea con métricas formateadas.
    print("-" * 72)
    print(f" {title} ".center(72, " "))
    print("-" * 72)
    print(f"  Total           : {m['total']}")
    print(f"    OK            : {m['ok']}")
    print(f"    ERROR         : {m['error']}")
    print(f"    TIMEOUT       : {m['timeout']}")
    print(f"  Periodo [s]     : {m['period_s']:.3f}")
    print(f"  TPS (aprox)     : {m['tps']:.3f}")
    print(f"  Latencias [s]   : mean={m['lat_mean_s']:.3f}  p50={m['lat_p50_s']:.3f}  p95={m['lat_p95_s']:.3f}  max={m['lat_max_s']:.3f}")
    print("-" * 72 + "\n")

def print_error(msg: str):
    # Mensajes de error legibles (stderr).
    print("\n" + "!" * 72, file=sys.stderr)
    print(f" ERROR: {msg}", file=sys.stderr)
    print("!" * 72 + "\n", file=sys.stderr)

# ---------- Lógica principal ----------

def parse_args():
    p = argparse.ArgumentParser(description="Parser de logs del PS (TPS y latencias)")
    p.add_argument("--log", default=str(Path("ps_logs.txt")),
                   help="Ruta al archivo de log (default: ./ps_logs.txt)")
    # Permite case-insensitive; validamos manualmente
    p.add_argument("--tipo", type=str,
                   help="Filtrar por tipo de solicitud (renovacion|devolucion)")
    p.add_argument("--only-ok", action="store_true",
                   help="Considerar latencias sólo de status=OK")
    p.add_argument("--csv", help="Ruta de salida CSV para métricas agregadas (append)")
    return p.parse_args()

def normalize_tipo(t: str | None) -> str | None:
    # Normaliza el tipo a minúsculas y valida.
    if t is None:
        return None
    t_norm = t.strip().lower()
    if t_norm not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: {t!r}. Válidos: {', '.join(sorted(TIPOS_VALIDOS))}")
    return t_norm

def load_lines(path: Path):
    # Itera líneas del log, produciendo dicts normalizados.
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el log en: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = LINE_RE.search(line)
            if not m:
                # Línea que no cumple el formato: se ignora.
                continue
            try:
                tipo = (m.group("tipo") or "").strip().lower()   # normaliza tipo
                status = (m.group("status") or "").strip().upper()
                start_f = float(m.group("start"))
                end_f = float(m.group("end"))
                retries_i = int(m.group("retries") or 0)
            except Exception:
                # Si algo no se puede convertir, se ignora la línea.
                continue

            yield {
                "id": m.group("id"),
                "tipo": tipo,            # 'renovacion' | 'devolucion' (minúsculas)
                "start": start_f,
                "end": end_f,
                "status": status,        # 'OK' | 'ERROR' | 'TIMEOUT' (mayúsculas)
                "retries": retries_i,
            }

def compute_metrics(rows, only_ok=False):
    """
    rows: iterable de dicts con keys [id, tipo, start, end, status, retries]
    only_ok: si True, las métricas de latencia se calculan sólo con status=OK
    """
    rows = list(rows)
    if not rows:
        return None

    # Tiempos para TPS (usamos los 'start' como aproximación al inicio de la ventana)
    starts = [r["start"] for r in rows]
    t0, t1 = min(starts), max(starts)
    period = max(t1 - t0, 1e-6)  # evita división por cero

    # Conteos por status
    total = len(rows)
    ok = sum(r["status"] == "OK" for r in rows)
    err = sum(r["status"] == "ERROR" for r in rows)
    to  = sum(r["status"] == "TIMEOUT" for r in rows)

    # Latencias
    used = [r for r in rows if (r["status"] == "OK" or not only_ok)]
    latencies = [(r["end"] - r["start"]) for r in used] or [0.0]
    lat_mean = statistics.mean(latencies)
    lat_p50  = statistics.median(latencies)
    # p95 robusto: si hay pocos datos, usar el max como aproximación
    try:
        lat_p95 = statistics.quantiles(latencies, n=100)[94]
    except Exception:
        lat_p95 = max(latencies)
    lat_max  = max(latencies)

    # TPS estimado
    tps = total / period

    return {
        "total": total,
        "ok": ok,
        "error": err,
        "timeout": to,
        "period_s": period,
        "tps": tps,
        "lat_mean_s": lat_mean,
        "lat_p50_s": lat_p50,
        "lat_p95_s": lat_p95,
        "lat_max_s": lat_max,
    }

def append_csv(path: Path, title: str, m: dict):
    # Agrega (append) una fila CSV con las métricas agregadas.
    header = ("escenario,total,ok,error,timeout,period_s,tps,lat_mean_s,lat_p50_s,lat_p95_s,lat_max_s\n")
    row = (f"{title},{m['total']},{m['ok']},{m['error']},{m['timeout']},"
           f"{m['period_s']:.3f},{m['tps']:.3f},{m['lat_mean_s']:.3f},"
           f"{m['lat_p50_s']:.3f},{m['lat_p95_s']:.3f},{m['lat_max_s']:.3f}\n")
    exists = path.exists()
    with path.open("a", encoding="utf-8") as f:
        if not exists:
            f.write(header)
        f.write(row)

def main():
    try:
        args = parse_args()
        log_path = Path(args.log)
        tipo_norm = normalize_tipo(args.tipo) if args.tipo else None

        banner_inicio(log_path, tipo_norm, args.only_ok, args.csv)

        # Carga completo y calcula métricas
        all_rows = list(load_lines(log_path))
        if not all_rows:
            print_error("No hay datos válidos en el log.")
            return

        if tipo_norm:
            filtered = [r for r in all_rows if r["tipo"] == tipo_norm]
            if not filtered:
                print_error(f"No hay datos para tipo={tipo_norm}")
                return
            title = f"{log_path.name}-tipo={tipo_norm}-onlyOK={args.only_ok}"
            m = compute_metrics(filtered, only_ok=args.only_ok)
            print_metrics(title, m)
            if args.csv:
                append_csv(Path(args.csv), title, m)
        else:
            # Global
            title_all = f"{log_path.name}-ALL-onlyOK={args.only_ok}"
            m_all = compute_metrics(all_rows, only_ok=args.only_ok)
            print_metrics(title_all, m_all)
            if args.csv:
                append_csv(Path(args.csv), title_all, m_all)

            # Por tipo
            for t in ("renovacion", "devolucion"):
                sub = [r for r in all_rows if r["tipo"] == t]
                if not sub:
                    continue
                title_t = f"{log_path.name}-{t}-onlyOK={args.only_ok}"
                m_t = compute_metrics(sub, only_ok=args.only_ok)
                print_metrics(title_t, m_t)
                if args.csv:
                    append_csv(Path(args.csv), title_t, m_t)

    except Exception as e:
        print_error(str(e))

if __name__ == "__main__":
    main()
