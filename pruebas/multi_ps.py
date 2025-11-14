#!/usr/bin/env python3
# archivo: pruebas/multi_ps.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 13 de noviembre de 2025
#
# Lanzador de múltiples Procesos Solicitantes (PS) en paralelo.
# Genera carga concurrente para medir rendimiento del sistema.

import os
import sys
import time
import subprocess
import argparse
import json
from pathlib import Path
from datetime import datetime

# Configuración
ROOT = Path(__file__).resolve().parents[1]
PS_SCRIPT = ROOT / "ps" / "ps.py"
GEN_SCRIPT = ROOT / "ps" / "gen_solicitudes.py"

def iso():
    """Retorna timestamp ISO-8601."""
    return datetime.utcnow().isoformat() + "Z"

def print_banner():
    """Imprime banner de inicio."""
    print("\n" + "=" * 72)
    print(" LANZADOR DE MÚLTIPLES PS CONCURRENTES ".center(72, " "))
    print("-" * 72)
    print("  Universidad: Pontificia Universidad Javeriana")
    print("  Materia    : Sistemas Distribuidos")
    print("=" * 72 + "\n")

def generar_solicitudes(num_ps, requests_per_ps, mix, seed_base):
    """
    Genera archivos de solicitudes para cada PS.
    Retorna lista de archivos generados.
    """
    print(f"\n[{iso()}] Generando solicitudes para {num_ps} PS...")
    print(f"  Solicitudes por PS: {requests_per_ps}")
    print(f"  Mix: {mix}")

    archivos = []

    for i in range(num_ps):
        # Archivo único por PS
        output_file = ROOT / f"solicitudes_ps{i+1}.bin"

        # Semilla única para cada PS (reproducible)
        seed = seed_base + i if seed_base else None

        # Comando de generación
        cmd = [
            sys.executable,
            str(GEN_SCRIPT),
            "--n", str(requests_per_ps),
            "--mix", mix
        ]

        if seed:
            cmd.extend(["--seed", str(seed)])

        # Redirigir salida a archivo específico
        env = os.environ.copy()
        env["NUM_SOLICITUDES"] = str(requests_per_ps)

        try:
            # Ejecutar generador
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(ROOT)
            )

            # Mover archivo generado
            default_output = ROOT / "solicitudes.bin"
            if default_output.exists():
                default_output.rename(output_file)
                archivos.append(output_file)
                print(f"  ✓ PS{i+1}: {output_file.name}")
            else:
                print(f"  ✗ PS{i+1}: No se generó el archivo")

        except Exception as e:
            print(f"  ✗ PS{i+1}: Error - {e}")

    print(f"\n[{iso()}] Archivos generados: {len(archivos)}/{num_ps}")
    return archivos

def lanzar_ps_paralelo(archivos, timeout, backoff, mode="concurrent"):
    """
    Lanza múltiples PS en paralelo.
    mode: 'concurrent' (todos al mismo tiempo) o 'staggered' (escalonado)
    Retorna lista de procesos.
    """
    print(f"\n[{iso()}] Lanzando {len(archivos)} PS en modo {mode}...")

    procesos = []
    logs_dir = ROOT / "multi_ps_logs"
    logs_dir.mkdir(exist_ok=True)

    for i, archivo in enumerate(archivos):
        ps_id = i + 1
        log_file = logs_dir / f"ps{ps_id}.log"
        metrics_file = logs_dir / f"ps{ps_id}_metrics.txt"

        # Preparar comando base para ps.py con log override
        cmd = [sys.executable, str(PS_SCRIPT), "--log-file", str(metrics_file)]

        if timeout:
            cmd.extend(["--timeout", str(timeout)])

        if backoff:
            cmd.extend(["--backoff", backoff])

        # Modificar temporalmente para que cada PS use su archivo
        # Copiamos el archivo al nombre estándar antes de ejecutar
        solicitudes_temp = ROOT / "solicitudes.bin"

        # Abrir archivo de log
        log_f = open(log_file, "w")

        # Crear script wrapper que copia y ejecuta
        wrapper_cmd = f"""
cd {ROOT}
cp {archivo} solicitudes.bin
{' '.join(cmd)}
"""

        # Lanzar proceso
        proc = subprocess.Popen(
            ["bash", "-c", wrapper_cmd],
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT)
        )

        procesos.append({
            "ps_id": ps_id,
            "proceso": proc,
            "log_file": log_file,
            "metrics_file": metrics_file,
            "log_handle": log_f,
            "archivo": archivo,
            "inicio": time.time()
        })

        print(f"  ✓ PS{ps_id} lanzado (PID: {proc.pid})")

        # Modo escalonado: esperar antes de lanzar el siguiente
        if mode == "staggered" and i < len(archivos) - 1:
            time.sleep(0.5)

    return procesos

def esperar_procesos(procesos):
    """
    Espera a que todos los procesos terminen.
    Retorna métricas de ejecución.
    """
    print(f"\n[{iso()}] Esperando a que {len(procesos)} PS terminen...")

    inicio_espera = time.time()
    completados = 0

    while completados < len(procesos):
        time.sleep(1)

        for ps_info in procesos:
            if ps_info["proceso"].poll() is not None and "fin" not in ps_info:
                ps_info["fin"] = time.time()
                ps_info["duracion"] = ps_info["fin"] - ps_info["inicio"]
                ps_info["codigo_salida"] = ps_info["proceso"].returncode
                completados += 1

                print(f"  ✓ PS{ps_info['ps_id']} terminado ({ps_info['duracion']:.2f}s, exit={ps_info['codigo_salida']})")

    fin_espera = time.time()
    duracion_total = fin_espera - inicio_espera

    print(f"\n[{iso()}] Todos los PS terminaron en {duracion_total:.2f}s")

    # Cerrar handles de log
    for ps_info in procesos:
        ps_info["log_handle"].close()

    return procesos

def consolidar_logs(procesos):
    """
    Consolida los logs de ps_logs.txt de cada PS.
    """
    print(f"\n[{iso()}] Consolidando logs...")

    log_consolidado = ROOT / "multi_ps_logs" / "ps_logs_consolidado.txt"

    count = 0
    with open(log_consolidado, "w") as out:
        for ps_info in procesos:
            metrics_path = ps_info.get("metrics_file")
            if metrics_path and Path(metrics_path).exists():
                with open(metrics_path, "r") as mf:
                    for linea in mf:
                        linea = linea.strip()
                        if not linea:
                            continue
                        if "request_id=" in linea and "|" in linea:
                            out.write(f"PS{ps_info['ps_id']}|{linea}\n")
                            count += 1

    # Copiar consolidado a ps_logs.txt para compatibilidad
    target = ROOT / "ps_logs.txt"
    try:
        if log_consolidado.exists():
            log_consolidado.write_text(log_consolidado.read_text())
            # (Mantener mismo contenido; ya creado)
    except Exception:
        pass

    print(f"  ✓ Log consolidado: {log_consolidado}")
    print(f"  ✓ Líneas de métricas: {count}")

    return log_consolidado

def parse_consolidado(log_path):
    try:
        from ps.log_parser import load_lines, compute_metrics
    except Exception:
        return None
    if not log_path.exists():
        return None
    # Adaptar líneas añadiendo operación y demás; el prefijo PSx| se debe retirar
    filas = []
    with open(log_path, "r") as f:
        for linea in f:
            # Remover prefijo PSx|
            if linea.startswith("PS"):
                linea = "|".join(linea.split("|", 1)[1:])
            # Reutilizar regex del parser si disponible
            filas.append(linea)
    # Simple conteo
    total = len(filas)
    return total

def generar_reporte(procesos, num_ps, requests_per_ps, mode, mix):
    """
    Genera reporte JSON con resultados.
    """
    duraciones = [p["duracion"] for p in procesos if "duracion" in p]
    codigos = [p["codigo_salida"] for p in procesos if "codigo_salida" in p]

    exitosos = sum(1 for c in codigos if c == 0)
    fallidos = len(codigos) - exitosos

    reporte = {
        "test": "multi_ps_concurrent",
        "timestamp": iso(),
        "configuracion": {
            "num_ps": num_ps,
            "requests_per_ps": requests_per_ps,
            "total_requests": num_ps * requests_per_ps,
            "mode": mode,
            "mix": mix
        },
        "resultados": {
            "ps_exitosos": exitosos,
            "ps_fallidos": fallidos,
            "duracion_min_s": min(duraciones) if duraciones else 0,
            "duracion_max_s": max(duraciones) if duraciones else 0,
            "duracion_mean_s": sum(duraciones) / len(duraciones) if duraciones else 0
        },
        "procesos": [
            {
                "ps_id": p["ps_id"],
                "pid": p["proceso"].pid,
                "duracion_s": p.get("duracion", 0),
                "codigo_salida": p.get("codigo_salida", -1),
                "log_file": str(p["log_file"])
            }
            for p in procesos
        ]
    }

    reporte_path = ROOT / "multi_ps_logs" / "reporte_multi_ps.json"
    with open(reporte_path, "w") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n📄 Reporte guardado en: {reporte_path}")

    return reporte

def main():
    parser = argparse.ArgumentParser(description="Lanzador de múltiples PS concurrentes")
    parser.add_argument("--num-ps", type=int, default=5,
                       help="Número de PS a lanzar (default: 5)")
    parser.add_argument("--requests-per-ps", type=int, default=20,
                       help="Solicitudes por PS (default: 20)")
    parser.add_argument("--mode", choices=["concurrent", "staggered"],
                       default="concurrent",
                       help="Modo de lanzamiento (default: concurrent)")
    parser.add_argument("--mix", default="50:50:0",
                       help="Mix de operaciones (default: 50:50:0)")
    parser.add_argument("--seed", type=int,
                       help="Semilla base para generación (opcional)")
    parser.add_argument("--timeout", type=float,
                       help="Timeout para cada PS en segundos")
    parser.add_argument("--backoff", type=str,
                       help="Secuencia de backoff (ej: 0.5,1,2,4)")
    parser.add_argument("--allow-fail", action="store_true", help="Forzar exit code 0 aunque existan PS fallidos")

    args = parser.parse_args()

    print_banner()

    print(f"Configuración:")
    print(f"  Número de PS        : {args.num_ps}")
    print(f"  Solicitudes por PS  : {args.requests_per_ps}")
    print(f"  Total solicitudes   : {args.num_ps * args.requests_per_ps}")
    print(f"  Modo de lanzamiento : {args.mode}")
    print(f"  Mix                 : {args.mix}")

    inicio_total = time.time()

    # Paso 1: Generar solicitudes
    archivos = generar_solicitudes(
        args.num_ps,
        args.requests_per_ps,
        args.mix,
        args.seed
    )

    if not archivos:
        print("\n❌ No se generaron archivos de solicitudes")
        return 1

    # Paso 2: Lanzar PS en paralelo
    procesos = lanzar_ps_paralelo(
        archivos,
        args.timeout,
        args.backoff,
        args.mode
    )

    # Paso 3: Esperar a que terminen
    procesos = esperar_procesos(procesos)

    # Paso 4: Consolidar logs
    consolidar_logs(procesos)

    # Paso 5: Generar reporte
    reporte = generar_reporte(
        procesos,
        args.num_ps,
        args.requests_per_ps,
        args.mode,
        args.mix
    )

    # Intentar generar métricas CSV si hay líneas
    consolidado_path = ROOT / "multi_ps_logs" / "ps_logs_consolidado.txt"
    if consolidado_path.exists():
        try:
            from ps.log_parser import load_lines, compute_metrics
            rows = list(load_lines(consolidado_path))
            if rows:
                metrics = compute_metrics(rows, only_ok=False)
                csv_path = ROOT / "multi_ps_logs" / "multi_ps_metrics.csv"
                with open(csv_path, "w") as cf:
                    cf.write("total,ok,error,timeout,period_s,tps,lat_mean_s,lat_p50_s,lat_p95_s,lat_max_s\n")
                    cf.write(f"{metrics['total']},{metrics['ok']},{metrics['error']},{metrics['timeout']},{metrics['period_s']:.6f},{metrics['tps']:.6f},{metrics['lat_mean_s']:.6f},{metrics['lat_p50_s']:.6f},{metrics['lat_p95_s']:.6f},{metrics['lat_max_s']:.6f}\n")
                print(f"📊 Métricas agregadas CSV: {csv_path}")
        except Exception as e:
            print(f"⚠️  No se pudieron calcular métricas agregadas: {e}")

    fin_total = time.time()
    duracion_total = fin_total - inicio_total

    # Resumen
    print("\n" + "=" * 72)
    print(" RESUMEN ".center(72, " "))
    print("=" * 72)
    print(f"\n  PS lanzados         : {len(procesos)}")
    print(f"  PS exitosos         : {reporte['resultados']['ps_exitosos']}")
    print(f"  PS fallidos         : {reporte['resultados']['ps_fallidos']}")
    print(f"  Duración total      : {duracion_total:.2f}s")
    print(f"  Duración promedio/PS: {reporte['resultados']['duracion_mean_s']:.2f}s")
    print("=" * 72 + "\n")

    exit_code = 0 if args.allow_fail else (0 if reporte['resultados']['ps_fallidos'] == 0 else 1)
    return exit_code

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
