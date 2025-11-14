#!/usr/bin/env python3
# archivo: pruebas/test_flood.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 13 de noviembre de 2025
#
# Prueba de seguridad: Ataque DoS por Flood
# Envía una ráfaga masiva de solicitudes para medir resistencia a sobrecarga.

import os
import sys
import time
import zmq
import json
from pathlib import Path
from datetime import datetime
import threading
from queue import Queue

# Añadir path para importar módulos del PS
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ps"))
from schema import make_request

# Configuración
GC_ADDR = os.getenv("GC_ADDR", "tcp://10.43.101.220:5555")
NUM_SOLICITUDES = int(os.getenv("FLOOD_NUM", "100"))
NUM_THREADS = int(os.getenv("FLOOD_THREADS", "5"))
TIMEOUT_MS = 2000

def iso():
    """Retorna timestamp ISO-8601."""
    return datetime.utcnow().isoformat() + "Z"

def print_banner():
    """Imprime banner de inicio."""
    print("\n" + "=" * 72)
    print(" TEST DE SEGURIDAD: ATAQUE FLOOD (DoS) ".center(72, " "))
    print("-" * 72)
    print(f"  GC Target       : {GC_ADDR}")
    print(f"  Total Solicitudes: {NUM_SOLICITUDES}")
    print(f"  Threads Concurrentes: {NUM_THREADS}")
    print(f"  Timeout         : {TIMEOUT_MS}ms")
    print("=" * 72 + "\n")

def worker_flood(thread_id, cola_trabajo, cola_resultados):
    """
    Worker que envía solicitudes en ráfaga desde la cola de trabajo.
    """
    ctx = zmq.Context()

    while True:
        try:
            item = cola_trabajo.get(timeout=0.1)
            if item is None:  # Señal de terminación
                break

            idx, solicitud = item

            sock = ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.RCVTIMEO, TIMEOUT_MS)
            sock.setsockopt(zmq.SNDTIMEO, TIMEOUT_MS)

            start = time.time()
            estado = "ERROR"

            try:
                sock.connect(GC_ADDR)
                payload = json.dumps(solicitud)
                sock.send_string(payload)

                try:
                    respuesta = sock.recv_string()
                    resp_obj = json.loads(respuesta)
                    estado = resp_obj.get("estado", resp_obj.get("status", "UNKNOWN"))
                    if estado.upper() in ("OK", "OKAY"):
                        estado = "OK"
                except zmq.ZMQError:
                    estado = "TIMEOUT"

            except Exception as e:
                estado = "ERROR"
            finally:
                sock.close(linger=0)

            end = time.time()
            latencia = end - start

            cola_resultados.put({
                "idx": idx,
                "thread": thread_id,
                "estado": estado,
                "latencia_s": latencia
            })

        except:
            break

    ctx.term()

def test_flood_attack():
    """
    Ejecuta ataque de flood:
    1. Genera NUM_SOLICITUDES solicitudes válidas
    2. Las envía en ráfaga con NUM_THREADS threads concurrentes
    3. Mide: TPS, % timeouts, latencias
    """
    print_banner()

    # Generar solicitudes
    print(f"[{iso()}] Generando {NUM_SOLICITUDES} solicitudes...")
    solicitudes = []
    for i in range(NUM_SOLICITUDES):
        sol = make_request("RENOVACION", i % 1000 + 1, i % 100 + 1)
        solicitudes.append((i, sol))

    print(f"[{iso()}] Solicitudes generadas: {len(solicitudes)}\n")

    # Crear colas
    cola_trabajo = Queue()
    cola_resultados = Queue()

    # Llenar cola de trabajo
    for item in solicitudes:
        cola_trabajo.put(item)

    # Añadir señales de terminación
    for _ in range(NUM_THREADS):
        cola_trabajo.put(None)

    # Iniciar workers
    print(f"[{iso()}] Iniciando {NUM_THREADS} threads de ataque...")
    workers = []
    for i in range(NUM_THREADS):
        t = threading.Thread(target=worker_flood, args=(i+1, cola_trabajo, cola_resultados))
        t.start()
        workers.append(t)

    # Monitorear progreso
    inicio = time.time()
    print(f"[{iso()}] Flood iniciado...\n")

    procesadas = 0
    while procesadas < NUM_SOLICITUDES:
        try:
            cola_resultados.get(timeout=0.5)
            procesadas += 1
            if procesadas % 20 == 0 or procesadas == NUM_SOLICITUDES:
                elapsed = time.time() - inicio
                tps_actual = procesadas / elapsed if elapsed > 0 else 0
                print(f"  Procesadas: {procesadas}/{NUM_SOLICITUDES} | TPS: {tps_actual:.2f}")
        except:
            pass

    fin = time.time()
    duracion = fin - inicio

    # Esperar a que terminen todos los workers
    for t in workers:
        t.join(timeout=2)

    # Recolectar resultados
    resultados = []
    while not cola_resultados.empty():
        try:
            resultados.append(cola_resultados.get_nowait())
        except:
            break

    # Análisis de resultados
    print("\n" + "=" * 72)
    print(" RESULTADOS DEL FLOOD ".center(72, " "))
    print("=" * 72)

    ok = sum(1 for r in resultados if r["estado"] == "OK")
    timeouts = sum(1 for r in resultados if r["estado"] == "TIMEOUT")
    errores = sum(1 for r in resultados if r["estado"] == "ERROR")
    total = len(resultados)

    latencias = [r["latencia_s"] for r in resultados if r["estado"] == "OK"]

    if latencias:
        lat_min = min(latencias)
        lat_max = max(latencias)
        lat_mean = sum(latencias) / len(latencias)
        latencias_sorted = sorted(latencias)
        lat_p50 = latencias_sorted[len(latencias_sorted) // 2]
        lat_p95 = latencias_sorted[int(len(latencias_sorted) * 0.95)] if len(latencias_sorted) > 20 else lat_max
    else:
        lat_min = lat_max = lat_mean = lat_p50 = lat_p95 = 0

    tps = total / duracion if duracion > 0 else 0

    print(f"\n  Solicitudes enviadas : {NUM_SOLICITUDES}")
    print(f"  Procesadas           : {total}")
    print(f"  Duración             : {duracion:.2f}s")
    print(f"  TPS (promedio)       : {tps:.2f}")

    print(f"\n  Resultados:")
    print(f"    OK                 : {ok} ({ok/total*100:.1f}%)")
    print(f"    TIMEOUT            : {timeouts} ({timeouts/total*100:.1f}%)")
    print(f"    ERROR              : {errores} ({errores/total*100:.1f}%)")

    print(f"\n  Latencias (solo OK):")
    print(f"    Mínima             : {lat_min:.3f}s")
    print(f"    Media              : {lat_mean:.3f}s")
    print(f"    p50                : {lat_p50:.3f}s")
    print(f"    p95                : {lat_p95:.3f}s")
    print(f"    Máxima             : {lat_max:.3f}s")

    # Evaluación
    print("\n" + "-" * 72)

    if timeouts > total * 0.5:
        print(f"\n❌ VULNERABLE A DoS: {timeouts/total*100:.1f}% de timeouts")
        print("   El sistema colapsó bajo carga de flood")
        resultado = "VULNERABLE"
    elif timeouts > total * 0.2:
        print(f"\n⚠️  SATURACIÓN PARCIAL: {timeouts/total*100:.1f}% de timeouts")
        print("   El sistema mostró degradación bajo carga")
        resultado = "DEGRADADO"
    else:
        print(f"\n✅ RESISTENTE: Solo {timeouts/total*100:.1f}% de timeouts")
        print(f"   TPS alcanzado: {tps:.2f}")
        resultado = "RESISTENTE"

    print("-" * 72)

    # Guardar reporte
    reporte = {
        "test": "flood_attack",
        "timestamp": iso(),
        "configuracion": {
            "num_solicitudes": NUM_SOLICITUDES,
            "num_threads": NUM_THREADS,
            "timeout_ms": TIMEOUT_MS
        },
        "metricas": {
            "duracion_s": duracion,
            "tps": tps,
            "ok": ok,
            "timeouts": timeouts,
            "errores": errores,
            "latencia_min_s": lat_min,
            "latencia_mean_s": lat_mean,
            "latencia_p50_s": lat_p50,
            "latencia_p95_s": lat_p95,
            "latencia_max_s": lat_max
        },
        "resultado": resultado
    }

    reporte_path = Path(__file__).parent / "reporte_flood.json"
    with open(reporte_path, "w") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n📄 Reporte guardado en: {reporte_path}\n")

    return resultado == "RESISTENTE"

if __name__ == "__main__":
    try:
        exito = test_flood_attack()
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrumpido por el usuario\n")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ ERROR INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

