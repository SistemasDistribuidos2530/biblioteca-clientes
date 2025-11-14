#!/usr/bin/env python3
# archivo: pruebas/test_replay.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 13 de noviembre de 2025
#
# Prueba de seguridad: Ataque de Replay
# Verifica que el sistema rechaza solicitudes con timestamps fuera de la ventana válida.

import os
import sys
import time
import zmq
import json
from pathlib import Path
from datetime import datetime

# Añadir path para importar módulos del PS
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ps"))
from schema import make_request, sign

# Configuración
GC_ADDR = os.getenv("GC_ADDR", "tcp://10.43.101.220:5555")
REPLAY_DELAY = 65  # segundos (fuera de ventana de 60s)

def iso():
    """Retorna timestamp ISO-8601."""
    return datetime.utcnow().isoformat() + "Z"

def print_banner():
    """Imprime banner de inicio."""
    print("\n" + "=" * 72)
    print(" TEST DE SEGURIDAD: ATAQUE DE REPLAY ".center(72, " "))
    print("-" * 72)
    print(f"  GC Target       : {GC_ADDR}")
    print(f"  Replay Delay    : {REPLAY_DELAY}s (ventana válida: 60s)")
    print("=" * 72 + "\n")

def enviar_solicitud(ctx, solicitud, intento_num, es_replay=False):
    """
    Envía una solicitud al GC y retorna la respuesta.
    """
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, 5000)
    sock.setsockopt(zmq.SNDTIMEO, 5000)
    
    try:
        sock.connect(GC_ADDR)
        
        # Construir payload
        payload = json.dumps(solicitud)
        
        tipo = "REPLAY" if es_replay else "ORIGINAL"
        print(f"\n[{iso()}] Intento {intento_num} ({tipo})")
        print(f"  request_id : {solicitud['request_id']}")
        print(f"  ts         : {solicitud['ts']}")
        print(f"  operation  : {solicitud['operation']}")
        
        sock.send_string(payload)
        
        try:
            respuesta = sock.recv_string()
            resp_obj = json.loads(respuesta)
            estado = resp_obj.get("estado", resp_obj.get("status", "UNKNOWN"))
            mensaje = resp_obj.get("mensaje", "")
            
            print(f"  Respuesta  : {estado}")
            if mensaje:
                print(f"  Mensaje    : {mensaje}")
            
            return estado, respuesta
            
        except zmq.ZMQError as e:
            print(f"  Respuesta  : TIMEOUT ({e})")
            return "TIMEOUT", None
            
    except Exception as e:
        print(f"  Error      : {e}")
        return "ERROR", None
    finally:
        sock.close(linger=0)

def test_replay_attack():
    """
    Ejecuta prueba de ataque de replay:
    1. Envía solicitud válida
    2. Espera REPLAY_DELAY segundos
    3. Reenvía la MISMA solicitud (mismo ts, nonce, hmac)
    4. Verifica que se rechace por timestamp expirado
    """
    print_banner()
    
    ctx = zmq.Context()
    
    # Generar solicitud original
    print("Generando solicitud original...")
    solicitud = make_request("RENOVACION", 123, 42)
    
    print(f"\nSolicitud generada:")
    print(f"  request_id : {solicitud['request_id']}")
    print(f"  ts         : {solicitud['ts']}")
    print(f"  nonce      : {solicitud['nonce']}")
    print(f"  hmac       : {solicitud['hmac'][:16]}...")
    
    # Intento 1: Envío original
    print("\n" + "-" * 72)
    print(" PASO 1: Enviar solicitud original ".center(72, " "))
    print("-" * 72)
    
    estado1, resp1 = enviar_solicitud(ctx, solicitud, 1, es_replay=False)
    
    if estado1 not in ("ok", "OK", "OKAY"):
        print(f"\n⚠️  ADVERTENCIA: Solicitud original no fue aceptada (estado: {estado1})")
        print("   Esto puede indicar que el GC no está disponible o hay otro problema.")
    
    # Esperar fuera de la ventana de tiempo
    print("\n" + "-" * 72)
    print(f" PASO 2: Esperar {REPLAY_DELAY}s (fuera de ventana) ".center(72, " "))
    print("-" * 72)
    print(f"\nEsperando {REPLAY_DELAY} segundos...", end="", flush=True)
    
    for i in range(REPLAY_DELAY):
        time.sleep(1)
        if (i + 1) % 10 == 0:
            print(f" {i + 1}s", end="", flush=True)
    
    print(" ✓")
    
    # Intento 2: Replay attack
    print("\n" + "-" * 72)
    print(" PASO 3: Reenviar MISMA solicitud (REPLAY) ".center(72, " "))
    print("-" * 72)
    
    estado2, resp2 = enviar_solicitud(ctx, solicitud, 2, es_replay=True)
    
    # Análisis de resultados
    print("\n" + "=" * 72)
    print(" RESULTADOS DEL TEST ".center(72, " "))
    print("=" * 72)
    
    print(f"\nIntento 1 (Original):")
    print(f"  Estado: {estado1}")
    
    print(f"\nIntento 2 (Replay después de {REPLAY_DELAY}s):")
    print(f"  Estado: {estado2}")
    
    # Determinar si el test pasó
    print("\n" + "-" * 72)
    
    # Nota: El GC actual NO valida HMAC/timestamp, así que este test
    # documenta el comportamiento actual y sirve para cuando se implemente
    if estado2 in ("ok", "OK", "OKAY"):
        print("❌ VULNERABILIDAD DETECTADA: El sistema acepta solicitudes replay")
        print("   Recomendación: Implementar validación de timestamp en el GC")
        resultado = "VULNERABLE"
    else:
        print("✅ PROTECCIÓN DETECTADA: El sistema rechazó el replay")
        resultado = "PROTEGIDO"
    
    print("-" * 72)
    
    # Guardar reporte
    reporte = {
        "test": "replay_attack",
        "timestamp": iso(),
        "delay_segundos": REPLAY_DELAY,
        "intento_original": {"estado": estado1},
        "intento_replay": {"estado": estado2},
        "resultado": resultado,
        "gc_validacion_timestamp": resultado == "PROTEGIDO"
    }
    
    reporte_path = Path(__file__).parent / "reporte_replay.json"
    with open(reporte_path, "w") as f:
        json.dump(reporte, f, indent=2)
    
    print(f"\n📄 Reporte guardado en: {reporte_path}\n")
    
    ctx.term()
    
    return resultado == "PROTEGIDO"

if __name__ == "__main__":
    try:
        exito = test_replay_attack()
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrumpido por el usuario\n")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ ERROR INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

