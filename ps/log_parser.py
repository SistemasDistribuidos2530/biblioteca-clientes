# archivo: tools/log_parser.py
# 
# Analiza el log línea-a-línea generado por ps/ps.py (ps_logs.txt)
# Formato esperado por línea:
#   request_id=<id>|tipo=<tipo>|start=<epoch_f>|end=<epoch_f>|status=<OK|ERROR|TIMEOUT>|retries=<int>
#
# Qué calcula:
# - Total de solicitudes, OK/ERROR/TIMEOUT
# - Latencia (end - start): media, p50, p95, máx
# - TPS ≈ total / (t_ultima - t_primera)  [según timestamps del log]
# Opciones:
#   --log RUTA        Ruta al log (default: ./ps_logs.txt)
#   --tipo T          Filtra por tipo (RENOVACION o DEVOLUCION); si no, toma todas
#   --only-ok         Considera sólo líneas con status=OK para métricas de latencia
#   --csv SALIDA      Exporta métricas agregadas a CSV (append si existe)
#
# Uso:
#   python tools/log_parser.py
#   python tools/log_parser.py --tipo RENOVACION
#   python tools/log_parser.py --log otro_log.txt --only-ok --csv resultados.csv
#

import re
import argparse
import statistics
from pathlib import Path

# Regex para extraer campos de cada línea
LINE_RE = re.compile(
    r"request_id=(?P<id>[^|]+)\|"
    r"tipo=(?P<tipo>[^|]+)\|"
    r"start=(?P<start>[\d.]+)\|"
    r"end=(?P<end>[\d.]+)\|"
    r"status=(?P<status>\w+)"
    r"(?:\|retries=(?P<retries>\d+))?"
)

def parse_args():
    p = argparse.ArgumentParser(description="Parser de logs del PS (TPS y latencias)")
    p.add_argument("--log", default=str(Path("ps_logs.txt")), help="Ruta al archivo de log (default: ./ps_logs.txt)")
    p.add_argument("--tipo", choices=["renovacion", "devolucion"], help="Filtrar por tipo de solicitud")
    p.add_argument("--only-ok", action="store_true", help="Considerar latencias sólo de status=OK")
    p.add_argument("--csv", help="Ruta de salida CSV para métricas agregadas (append)")
    return p.parse_args()

def load_lines(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el log en: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = LINE_RE.search(line)
            if m:
                yield {
                    "id": m.group("id"),
                    "tipo": m.group("tipo"),
                    "start": float(m.group("start")),
                    "end": float(m.group("end")),
                    "status": m.group("status"),
                    "retries": int(m.group("retries") or 0),
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
    period = max(t1 - t0, 1e-6)  # evitar división por cero

    # Conteos por status
    total = len(rows)
    ok = sum(r["status"] == "OK" for r in rows)
    err = sum(r["status"] == "ERROR" for r in rows)
    to  = sum(r["status"] == "TIMEOUT" for r in rows)

    # Latencias
    if only_ok:
        used = [r for r in rows if r["status"] == "OK"]
    else:
        used = rows

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

def print_metrics(title: str, m: dict):
    print(f"\n== {title} ==")
    print(f"Total:   {m['total']}  (OK={m['ok']}  ERROR={m['error']}  TIMEOUT={m['timeout']})")
    print(f"Periodo: {m['period_s']:.2f}s   TPS≈ {m['tps']:.2f}")
    print(f"Latencias [s]: mean={m['lat_mean_s']:.3f}  p50={m['lat_p50_s']:.3f}  p95={m['lat_p95_s']:.3f}  max={m['lat_max_s']:.3f}")

def append_csv(path: Path, title: str, m: dict):
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
    args = parse_args()
    log_path = Path(args.log)

    # Carga completo y calcula "global"
    all_rows = list(load_lines(log_path))
    if not all_rows:
        print("No hay datos en el log.")
        return

    # Si pidieron filtrar por tipo, separamos
    if args.tipo:
        filtered = [r for r in all_rows if r["tipo"] == args.tipo]
        title = f"{log_path.name}-tipo={args.tipo}-onlyOK={args.only_ok}"
        m = compute_metrics(filtered, only_ok=args.only_ok)
        if not m:
            print(f"No hay datos para tipo={args.tipo}")
            return
        print_metrics(title, m)
        if args.csv:
            append_csv(Path(args.csv), title, m)
    else:
        # Métricas globales (todas las líneas)
        title_all = f"{log_path.name}-ALL-onlyOK={args.only_ok}"
        m_all = compute_metrics(all_rows, only_ok=args.only_ok)
        print_metrics(title_all, m_all)
        if args.csv:
            append_csv(Path(args.csv), title_all, m_all)

        # Métricas por tipo
        for t in ("renovacion", "devolucion"):
            sub = [r for r in all_rows if r["tipo"] == t]
            if not sub:
                continue
            title_t = f"{log_path.name}-{t}-onlyOK={args.only_ok}"
            m_t = compute_metrics(sub, only_ok=args.only_ok)
            print_metrics(title_t, m_t)
            if args.csv:
                append_csv(Path(args.csv), title_t, m_t)

if __name__ == "__main__":
    main()
