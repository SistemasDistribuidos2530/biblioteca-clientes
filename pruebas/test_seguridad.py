#!/usr/bin/env python3
# archivo: pruebas/test_seguridad.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 13 de noviembre de 2025
#
# Script maestro de pruebas de seguridad.
# Ejecuta todos los tests de seguridad y genera reporte consolidado.

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

def iso():
    """Retorna timestamp ISO-8601."""
    return datetime.utcnow().isoformat() + "Z"

def print_banner():
    """Imprime banner de inicio."""
    print("\n" + "=" * 72)
    print(" SUITE DE PRUEBAS DE SEGURIDAD ".center(72, " "))
    print("-" * 72)
    print("  Universidad: Pontificia Universidad Javeriana")
    print("  Materia    : Sistemas Distribuidos")
    print("  Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón")
    print("=" * 72 + "\n")

def ejecutar_test(test_name, test_path):
    """
    Ejecuta un test individual y retorna el resultado.
    """
    print("\n" + "=" * 72)
    print(f" EJECUTANDO: {test_name} ".center(72, " "))
    print("=" * 72)

    start = datetime.utcnow()

    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=False,
            text=True,
            timeout=300  # 5 minutos máximo por test
        )

        end = datetime.utcnow()
        duracion = (end - start).total_seconds()

        exito = result.returncode == 0

        return {
            "test": test_name,
            "ejecutado": True,
            "exito": exito,
            "codigo_salida": result.returncode,
            "duracion_s": duracion,
            "timestamp": iso()
        }

    except subprocess.TimeoutExpired:
        print(f"\n⚠️  TIMEOUT: {test_name} excedió el tiempo límite\n")
        return {
            "test": test_name,
            "ejecutado": False,
            "exito": False,
            "error": "TIMEOUT",
            "timestamp": iso()
        }
    except Exception as e:
        print(f"\n❌ ERROR ejecutando {test_name}: {e}\n")
        return {
            "test": test_name,
            "ejecutado": False,
            "exito": False,
            "error": str(e),
            "timestamp": iso()
        }

def leer_reporte_json(reporte_path):
    """Lee un archivo de reporte JSON si existe."""
    try:
        if reporte_path.exists():
            with open(reporte_path, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️  No se pudo leer {reporte_path}: {e}")
    return None

def main():
    parser = argparse.ArgumentParser(description="Suite de pruebas de seguridad")
    parser.add_argument("--test", choices=["replay", "corrupt", "flood", "injection", "all"],
                       default="all", help="Test a ejecutar (default: all)")
    parser.add_argument("--skip-slow", action="store_true",
                       help="Omitir tests lentos (replay, flood)")
    args = parser.parse_args()

    print_banner()

    # Directorio de pruebas
    pruebas_dir = Path(__file__).parent

    # Tests disponibles
    tests_disponibles = {
        "replay": ("Ataque de Replay", pruebas_dir / "test_replay.py", "reporte_replay.json"),
        "corrupt": ("Entrada Corrupta", pruebas_dir / "test_corrupt.py", "reporte_corrupt.json"),
        "flood": ("Ataque Flood (DoS)", pruebas_dir / "test_flood.py", "reporte_flood.json"),
        "injection": ("Inyección de Operaciones", pruebas_dir / "test_injection.py", "reporte_injection.json"),
    }

    # Determinar qué tests ejecutar
    if args.test == "all":
        tests_a_ejecutar = list(tests_disponibles.keys())
        if args.skip_slow:
            tests_a_ejecutar = [t for t in tests_a_ejecutar if t not in ("replay", "flood")]
    else:
        tests_a_ejecutar = [args.test]

    print(f"Tests a ejecutar: {', '.join(tests_a_ejecutar)}\n")

    # Ejecutar tests
    resultados_ejecucion = []

    for test_key in tests_a_ejecutar:
        if test_key not in tests_disponibles:
            print(f"⚠️  Test desconocido: {test_key}")
            continue

        test_name, test_path, reporte_file = tests_disponibles[test_key]

        if not test_path.exists():
            print(f"⚠️  Test no encontrado: {test_path}")
            continue

        resultado = ejecutar_test(test_name, test_path)
        resultados_ejecucion.append(resultado)

    # Recolectar reportes individuales
    print("\n" + "=" * 72)
    print(" RECOLECTANDO REPORTES ".center(72, " "))
    print("=" * 72 + "\n")

    reportes_individuales = {}
    for test_key in tests_a_ejecutar:
        if test_key in tests_disponibles:
            _, _, reporte_file = tests_disponibles[test_key]
            reporte_path = pruebas_dir / reporte_file
            reporte = leer_reporte_json(reporte_path)
            if reporte:
                reportes_individuales[test_key] = reporte
                print(f"✓ {test_key}: reporte cargado")
            else:
                print(f"✗ {test_key}: reporte no disponible")

    # Generar reporte consolidado
    print("\n" + "=" * 72)
    print(" REPORTE CONSOLIDADO ".center(72, " "))
    print("=" * 72)

    total_tests = len(resultados_ejecucion)
    tests_exitosos = sum(1 for r in resultados_ejecucion if r.get("exito", False))
    tests_fallidos = total_tests - tests_exitosos

    print(f"\n  Total de tests      : {total_tests}")
    print(f"  Exitosos            : {tests_exitosos}")
    print(f"  Fallidos            : {tests_fallidos}")

    print("\n  Detalle por test:")
    for res in resultados_ejecucion:
        estado = "✅ PASS" if res.get("exito") else "❌ FAIL"
        duracion = f"{res.get('duracion_s', 0):.2f}s" if "duracion_s" in res else "N/A"
        print(f"    {res['test']:25} : {estado:10} ({duracion})")

    # Evaluación de seguridad global
    print("\n" + "-" * 72)
    print(" EVALUACIÓN DE SEGURIDAD ".center(72, " "))
    print("-" * 72)

    vulnerabilidades = []
    fortalezas = []

    for test_key, reporte in reportes_individuales.items():
        resultado = reporte.get("resultado", "UNKNOWN")
        if resultado in ("VULNERABLE", "DEGRADADO"):
            vulnerabilidades.append(f"{test_key}: {resultado}")
        elif resultado in ("SEGURO", "PROTEGIDO", "RESISTENTE"):
            fortalezas.append(f"{test_key}: {resultado}")

    if vulnerabilidades:
        print("\n⚠️  VULNERABILIDADES DETECTADAS:")
        for vuln in vulnerabilidades:
            print(f"    - {vuln}")
    else:
        print("\n✅ NO SE DETECTARON VULNERABILIDADES CRÍTICAS")

    if fortalezas:
        print("\n✅ FORTALEZAS:")
        for fort in fortalezas:
            print(f"    - {fort}")

    print("\n" + "-" * 72)

    # Puntuación general
    if len(reportes_individuales) > 0:
        score = (len(fortalezas) / len(reportes_individuales)) * 100
        print(f"\n  Puntuación de Seguridad: {score:.1f}%")

        if score >= 80:
            print("  Calificación: EXCELENTE ✅")
        elif score >= 60:
            print("  Calificación: ACEPTABLE ⚠️")
        else:
            print("  Calificación: INSUFICIENTE ❌")

    # Guardar reporte consolidado
    reporte_consolidado = {
        "timestamp": iso(),
        "tests_ejecutados": tests_a_ejecutar,
        "total": total_tests,
        "exitosos": tests_exitosos,
        "fallidos": tests_fallidos,
        "ejecuciones": resultados_ejecucion,
        "reportes": reportes_individuales,
        "vulnerabilidades": vulnerabilidades,
        "fortalezas": fortalezas
    }

    reporte_path = pruebas_dir / "reporte_seguridad_consolidado.json"
    with open(reporte_path, "w") as f:
        json.dump(reporte_consolidado, f, indent=2)

    print(f"\n📄 Reporte consolidado guardado en: {reporte_path}")

    # Generar reporte de texto
    txt_path = pruebas_dir / "reporte_seguridad.txt"
    with open(txt_path, "w") as f:
        f.write("=" * 72 + "\n")
        f.write(" REPORTE DE PRUEBAS DE SEGURIDAD ".center(72) + "\n")
        f.write("=" * 72 + "\n\n")
        f.write(f"Fecha: {iso()}\n")
        f.write(f"Tests ejecutados: {', '.join(tests_a_ejecutar)}\n\n")

        f.write(f"RESUMEN:\n")
        f.write(f"  Total: {total_tests}\n")
        f.write(f"  Exitosos: {tests_exitosos}\n")
        f.write(f"  Fallidos: {tests_fallidos}\n\n")

        if vulnerabilidades:
            f.write("VULNERABILIDADES:\n")
            for vuln in vulnerabilidades:
                f.write(f"  - {vuln}\n")
            f.write("\n")

        if fortalezas:
            f.write("FORTALEZAS:\n")
            for fort in fortalezas:
                f.write(f"  - {fort}\n")
            f.write("\n")

        f.write("=" * 72 + "\n")

    print(f"📄 Reporte de texto guardado en: {txt_path}\n")

    # Código de salida
    sys.exit(0 if tests_fallidos == 0 else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Suite interrumpida por el usuario\n")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ ERROR INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

