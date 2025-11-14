#!/usr/bin/env python3
# archivo: pruebas/consolidar_metricas.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 13 de noviembre de 2025
#
# Consolidador de métricas de múltiples ejecuciones.
# Agrega resultados de varios logs y genera reportes comparativos.

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
import statistics

# Añadir path para importar log_parser
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ps"))
from log_parser import load_lines, compute_metrics

def iso():
    """Retorna timestamp ISO-8601."""
    return datetime.utcnow().isoformat() + "Z"

def print_banner():
    """Imprime banner de inicio."""
    print("\n" + "=" * 72)
    print(" CONSOLIDADOR DE MÉTRICAS ".center(72, " "))
    print("-" * 72)
    print("  Universidad: Pontificia Universidad Javeriana")
    print("  Materia    : Sistemas Distribuidos")
    print("=" * 72 + "\n")

def descubrir_logs(directorio):
    """
    Descubre archivos de log en un directorio.
    Retorna lista de archivos encontrados.
    """
    dir_path = Path(directorio)

    if not dir_path.exists():
        return []

    # Buscar archivos ps_logs*.txt
    logs = list(dir_path.glob("ps_logs*.txt"))

    return sorted(logs)

def procesar_log(log_path):
    """
    Procesa un archivo de log y retorna métricas.
    """
    try:
        rows = list(load_lines(log_path))
        if not rows:
            return None

        metricas = compute_metrics(rows, only_ok=False)

        # Agregar desglose por operación
        operaciones = {}
        for row in rows:
            op = row["operation"]
            if op not in operaciones:
                operaciones[op] = []
            operaciones[op].append(row)

        metricas["por_operacion"] = {}
        for op, rows_op in operaciones.items():
            metricas["por_operacion"][op] = compute_metrics(rows_op, only_ok=False)

        return metricas

    except Exception as e:
        print(f"⚠️  Error procesando {log_path}: {e}")
        return None

def generar_tabla_markdown(escenarios):
    """
    Genera tabla markdown comparativa.
    """
    lineas = []

    lineas.append("# Comparación de Escenarios\n")
    lineas.append("| Escenario | Total | OK | ERROR | TIMEOUT | TPS | Lat Media (s) | Lat p95 (s) |")
    lineas.append("|-----------|-------|----|----|---------|-----|---------------|-------------|")

    for nombre, metricas in escenarios:
        if metricas:
            lineas.append(
                f"| {nombre} | {metricas['total']} | {metricas['ok']} | "
                f"{metricas['error']} | {metricas['timeout']} | "
                f"{metricas['tps']:.2f} | {metricas['lat_mean_s']:.3f} | "
                f"{metricas['lat_p95_s']:.3f} |"
            )

    return "\n".join(lineas)

def generar_csv(escenarios, output_path):
    """
    Genera CSV con métricas consolidadas.
    """
    with open(output_path, "w") as f:
        # Header
        f.write("escenario,total,ok,error,timeout,period_s,tps,lat_mean_s,lat_p50_s,lat_p95_s,lat_max_s\n")

        # Datos
        for nombre, metricas in escenarios:
            if metricas:
                f.write(
                    f"{nombre},{metricas['total']},{metricas['ok']},"
                    f"{metricas['error']},{metricas['timeout']},{metricas['period_s']:.3f},"
                    f"{metricas['tps']:.3f},{metricas['lat_mean_s']:.3f},"
                    f"{metricas['lat_p50_s']:.3f},{metricas['lat_p95_s']:.3f},"
                    f"{metricas['lat_max_s']:.3f}\n"
                )

def main():
    parser = argparse.ArgumentParser(description="Consolidador de métricas")
    parser.add_argument("--dir", default=".",
                       help="Directorio con logs a consolidar (default: .)")
    parser.add_argument("--output", default="metricas_consolidadas",
                       help="Prefijo para archivos de salida (default: metricas_consolidadas)")
    parser.add_argument("--formato", choices=["csv", "json", "markdown", "all"],
                       default="all",
                       help="Formato de salida (default: all)")

    args = parser.parse_args()

    print_banner()

    print(f"Configuración:")
    print(f"  Directorio : {args.dir}")
    print(f"  Formato    : {args.formato}")

    # Descubrir logs
    print(f"\n[{iso()}] Buscando archivos de log en {args.dir}...")
    logs = descubrir_logs(args.dir)

    if not logs:
        print(f"⚠️  No se encontraron archivos de log")
        return 1

    print(f"✓ Encontrados {len(logs)} archivos:")
    for log in logs:
        print(f"  - {log.name}")

    # Procesar cada log
    print(f"\n[{iso()}] Procesando logs...")
    escenarios = []

    for log_path in logs:
        nombre = log_path.stem  # Nombre sin extensión
        print(f"\n  Procesando {nombre}...")

        metricas = procesar_log(log_path)

        if metricas:
            escenarios.append((nombre, metricas))
            print(f"    ✓ Total: {metricas['total']}, OK: {metricas['ok']}, TPS: {metricas['tps']:.2f}")
        else:
            print(f"    ✗ Sin datos válidos")

    if not escenarios:
        print(f"\n❌ No se obtuvieron métricas válidas")
        return 1

    # Generar reportes
    print(f"\n[{iso()}] Generando reportes...")

    output_dir = Path(args.dir)

    # JSON
    if args.formato in ("json", "all"):
        json_path = output_dir / f"{args.output}.json"
        reporte_json = {
            "timestamp": iso(),
            "num_escenarios": len(escenarios),
            "escenarios": [
                {
                    "nombre": nombre,
                    "metricas": metricas
                }
                for nombre, metricas in escenarios
            ]
        }

        with open(json_path, "w") as f:
            json.dump(reporte_json, f, indent=2)

        print(f"  ✓ JSON: {json_path}")

    # CSV
    if args.formato in ("csv", "all"):
        csv_path = output_dir / f"{args.output}.csv"
        generar_csv(escenarios, csv_path)
        print(f"  ✓ CSV: {csv_path}")

    # Markdown
    if args.formato in ("markdown", "all"):
        md_path = output_dir / f"{args.output}.md"
        tabla_md = generar_tabla_markdown(escenarios)

        with open(md_path, "w") as f:
            f.write(tabla_md)

        print(f"  ✓ Markdown: {md_path}")

    # Resumen en consola
    print("\n" + "=" * 72)
    print(" RESUMEN CONSOLIDADO ".center(72, " "))
    print("=" * 72)

    print(f"\n{'Escenario':<30} {'Total':<8} {'OK':<8} {'TPS':<10} {'Lat p95':<10}")
    print("-" * 72)

    for nombre, metricas in escenarios:
        print(f"{nombre:<30} {metricas['total']:<8} {metricas['ok']:<8} "
              f"{metricas['tps']:<10.2f} {metricas['lat_p95_s']:<10.3f}")

    # Comparación
    if len(escenarios) > 1:
        print("\n" + "-" * 72)
        print(" COMPARACIÓN ".center(72, " "))
        print("-" * 72)

        tps_values = [m['tps'] for _, m in escenarios]
        lat_values = [m['lat_mean_s'] for _, m in escenarios]

        mejor_tps_idx = tps_values.index(max(tps_values))
        mejor_lat_idx = lat_values.index(min(lat_values))

        print(f"\n  Mejor TPS      : {escenarios[mejor_tps_idx][0]} ({max(tps_values):.2f})")
        print(f"  Mejor Latencia : {escenarios[mejor_lat_idx][0]} ({min(lat_values):.3f}s)")

        if len(escenarios) == 2:
            # Comparación directa
            mejora_tps = ((tps_values[1] - tps_values[0]) / tps_values[0]) * 100
            mejora_lat = ((lat_values[0] - lat_values[1]) / lat_values[0]) * 100

            print(f"\n  Diferencia TPS      : {mejora_tps:+.1f}%")
            print(f"  Diferencia Latencia : {mejora_lat:+.1f}%")

    print("\n" + "=" * 72 + "\n")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por el usuario\n")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ ERROR INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

