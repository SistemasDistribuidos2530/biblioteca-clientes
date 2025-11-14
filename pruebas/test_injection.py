#!/usr/bin/env python3
# archivo: pruebas/test_injection.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 13 de noviembre de 2025
#
# Prueba de seguridad: Inyección de Operaciones
# Intenta enviar operaciones no válidas para verificar validación del GC.

import os
import sys
import zmq
import json
from pathlib import Path
from datetime import datetime

# Configuración
GC_ADDR = os.getenv("GC_ADDR", "tcp://10.43.101.220:5555")

def iso():
    """Retorna timestamp ISO-8601."""
    return datetime.utcnow().isoformat() + "Z"

def print_banner():
    """Imprime banner de inicio."""
    print("\n" + "=" * 72)
    print(" TEST DE SEGURIDAD: INYECCIÓN DE OPERACIONES ".center(72, " "))
    print("-" * 72)
    print(f"  GC Target : {GC_ADDR}")
    print("=" * 72 + "\n")

def enviar_operacion(ctx, nombre_test, operacion, descripcion):
    """
    Envía una solicitud con una operación específica al GC.
    """
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, 3000)
    sock.setsockopt(zmq.SNDTIMEO, 3000)

    try:
        sock.connect(GC_ADDR)

        # Construir payload
        payload = {
            "operation": operacion,
            "book_code": "BOOK-999",
            "user_id": 99,
            "request_id": f"test-inject-{nombre_test}"
        }
        payload_str = json.dumps(payload)

        print(f"\n[{iso()}] Test: {nombre_test}")
        print(f"  Operación   : {operacion}")
        print(f"  Descripción : {descripcion}")

        sock.send_string(payload_str)

        try:
            respuesta = sock.recv_string()
            try:
                resp_obj = json.loads(respuesta)
                estado = resp_obj.get("estado", resp_obj.get("status", "UNKNOWN"))
                mensaje = resp_obj.get("mensaje", "")
            except:
                estado = "NO_JSON"
                mensaje = respuesta[:50]

            print(f"  Respuesta   : {estado}")
            if mensaje:
                print(f"  Mensaje     : {mensaje}")

            return estado, respuesta

        except zmq.ZMQError as e:
            print(f"  Respuesta   : TIMEOUT")
            return "TIMEOUT", None

    except Exception as e:
        print(f"  Error       : {e}")
        return "ERROR", str(e)
    finally:
        sock.close(linger=0)

def test_operaciones_injection():
    """
    Ejecuta pruebas de inyección de operaciones:
    - Operaciones administrativas peligrosas
    - Comandos del sistema
    - Operaciones SQL-like
    - Operaciones con caracteres especiales
    """
    print_banner()

    ctx = zmq.Context()
    resultados = []

    # Operaciones a probar (todas deben ser rechazadas)
    operaciones_maliciosas = [
        ("delete", "DELETE (simula DELETE SQL)"),
        ("drop", "DROP (simula DROP TABLE)"),
        ("truncate", "TRUNCATE (simula TRUNCATE)"),
        ("admin", "ADMIN (acceso administrativo)"),
        ("shutdown", "SHUTDOWN (apagar sistema)"),
        ("exec", "EXEC (ejecutar comando)"),
        ("system", "SYSTEM (comando de sistema)"),
        ("../../etc/passwd", "PATH TRAVERSAL (inyección de ruta)"),
        ("'; DROP TABLE--", "SQL INJECTION (comentario SQL)"),
        ("<script>alert(1)</script>", "XSS (cross-site scripting)"),
        ("$USER", "VARIABLE EXPANSION (expansión de variable)"),
        ("|ls -la", "COMMAND INJECTION (pipe a comando)"),
        ("renovacion; rm -rf /", "COMMAND CHAINING (encadenamiento)"),
        ("' OR '1'='1", "SQL BYPASS (inyección booleana)"),
        ("../../../", "DIRECTORY TRAVERSAL"),
        ("null", "NULL (valor nulo)"),
        ("undefined", "UNDEFINED (valor indefinido)"),
        ("", "EMPTY STRING (cadena vacía)"),
        (" ", "WHITESPACE (solo espacios)"),
        ("renovacion\x00delete", "NULL BYTE INJECTION"),
    ]

    print("Ejecutando pruebas de inyección...\n")

    for idx, (operacion, descripcion) in enumerate(operaciones_maliciosas, 1):
        print("=" * 72)
        print(f" PRUEBA {idx}/{len(operaciones_maliciosas)} ".center(72, " "))
        print("=" * 72)

        estado, _ = enviar_operacion(ctx, f"inject-{idx}", operacion, descripcion)
        resultados.append((operacion, descripcion, estado))

    # Análisis de resultados
    print("\n" + "=" * 72)
    print(" RESULTADOS CONSOLIDADOS ".center(72, " "))
    print("=" * 72)

    rechazados = 0
    aceptados = 0
    timeouts = 0

    print(f"\n{'Operación':<30} {'Descripción':<35} {'Estado':<10}")
    print("-" * 72)

    for operacion, descripcion, estado in resultados:
        op_display = operacion[:28] if len(operacion) <= 28 else operacion[:25] + "..."
        desc_display = descripcion[:33] if len(descripcion) <= 33 else descripcion[:30] + "..."
        print(f"{op_display:<30} {desc_display:<35} {estado:<10}")

        if estado in ("error", "ERROR"):
            rechazados += 1
        elif estado in ("ok", "OK", "OKAY"):
            aceptados += 1
        elif estado == "TIMEOUT":
            timeouts += 1

    total = len(resultados)

    print("\n" + "-" * 72)
    print(f"\n  Total de pruebas    : {total}")
    print(f"  Rechazados          : {rechazados} ({rechazados/total*100:.1f}%)")
    print(f"  Aceptados (¡MALO!)  : {aceptados} ({aceptados/total*100:.1f}%)")
    print(f"  Timeouts            : {timeouts} ({timeouts/total*100:.1f}%)")

    # Evaluación de seguridad
    print("\n" + "-" * 72)

    if aceptados == 0:
        print("\n✅ EXCELENTE: Todas las operaciones maliciosas fueron rechazadas")
        print("   El sistema tiene validación efectiva de operaciones")
        resultado_final = "SEGURO"
    elif aceptados <= 3:
        print(f"\n⚠️  ACEPTABLE: {aceptados} operaciones maliciosas fueron aceptadas")
        print("   Se recomienda revisar la validación")
        resultado_final = "ACEPTABLE"
    else:
        print(f"\n❌ VULNERABLE: {aceptados} operaciones maliciosas fueron aceptadas")
        print("   CRÍTICO: El sistema no valida adecuadamente las operaciones")
        resultado_final = "VULNERABLE"

    if aceptados > 0:
        print("\n  Operaciones aceptadas (revisar):")
        for op, desc, estado in resultados:
            if estado in ("ok", "OK", "OKAY"):
                print(f"    - {op}: {desc}")

    print("-" * 72)

    # Guardar reporte
    reporte = {
        "test": "operaciones_injection",
        "timestamp": iso(),
        "total_pruebas": total,
        "rechazados": rechazados,
        "aceptados": aceptados,
        "timeouts": timeouts,
        "resultado": resultado_final,
        "detalle": [
            {
                "operacion": op,
                "descripcion": desc,
                "estado": est
            }
            for op, desc, est in resultados
        ]
    }

    reporte_path = Path(__file__).parent / "reporte_injection.json"
    with open(reporte_path, "w") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n📄 Reporte guardado en: {reporte_path}\n")

    ctx.term()

    return aceptados == 0

if __name__ == "__main__":
    try:
        exito = test_operaciones_injection()
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrumpido por el usuario\n")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ ERROR INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

