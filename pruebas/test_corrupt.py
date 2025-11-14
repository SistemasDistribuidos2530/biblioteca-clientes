#!/usr/bin/env python3
# archivo: pruebas/test_corrupt.py
#
# Universidad: Pontificia Universidad Javeriana
# Materia: INTRODUCCIÓN A SISTEMAS DISTRIBUIDOS
# Profesor: Rafael Páez Méndez
# Integrantes: Thomas Arévalo, Santiago Mesa, Diego Castrillón
# Fecha: 13 de noviembre de 2025
#
# Prueba de seguridad: Entrada Corrupta
# Verifica que el sistema maneja correctamente datos malformados o inválidos.

import os
import sys
import zmq
import json
from pathlib import Path
from datetime import datetime

# Añadir path para importar módulos del PS
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ps"))
from schema import make_request

# Configuración
GC_ADDR = os.getenv("GC_ADDR", "tcp://10.43.101.220:5555")

def iso():
    """Retorna timestamp ISO-8601."""
    return datetime.utcnow().isoformat() + "Z"

def print_banner():
    """Imprime banner de inicio."""
    print("\n" + "=" * 72)
    print(" TEST DE SEGURIDAD: ENTRADA CORRUPTA ".center(72, " "))
    print("-" * 72)
    print(f"  GC Target : {GC_ADDR}")
    print("=" * 72 + "\n")

def enviar_payload(ctx, nombre_test, payload_str, descripcion):
    """
    Envía un payload al GC y retorna el resultado.
    """
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, 3000)
    sock.setsockopt(zmq.SNDTIMEO, 3000)
    
    try:
        sock.connect(GC_ADDR)
        
        print(f"\n[{iso()}] Test: {nombre_test}")
        print(f"  Descripción : {descripcion}")
        print(f"  Payload     : {payload_str[:100]}..." if len(payload_str) > 100 else f"  Payload     : {payload_str}")
        
        sock.send_string(payload_str)
        
        try:
            respuesta = sock.recv_string()
            try:
                resp_obj = json.loads(respuesta)
                estado = resp_obj.get("estado", resp_obj.get("status", "UNKNOWN"))
            except:
                estado = "NO_JSON"
            
            print(f"  Respuesta   : {estado}")
            return estado, respuesta
            
        except zmq.ZMQError as e:
            print(f"  Respuesta   : TIMEOUT")
            return "TIMEOUT", None
            
    except Exception as e:
        print(f"  Error       : {e}")
        return "ERROR", str(e)
    finally:
        sock.close(linger=0)

def test_entrada_corrupta():
    """
    Ejecuta múltiples pruebas con entradas corruptas:
    1. HMAC inválido (modificado)
    2. JSON malformado (sintaxis rota)
    3. Campos faltantes
    4. Tipos de datos incorrectos
    5. Valores extremos
    """
    print_banner()
    
    ctx = zmq.Context()
    resultados = []
    
    # Generar solicitud válida base
    solicitud_base = make_request("RENOVACION", 123, 42)
    
    # TEST 1: HMAC inválido
    print("\n" + "=" * 72)
    print(" TEST 1: HMAC INVÁLIDO ".center(72, " "))
    print("=" * 72)
    
    solicitud_hmac = solicitud_base.copy()
    solicitud_hmac["hmac"] = "0" * 64  # HMAC falso
    payload1 = json.dumps(solicitud_hmac)
    
    estado1, _ = enviar_payload(ctx, "HMAC Inválido", payload1, 
                                 "HMAC modificado (64 ceros)")
    resultados.append(("HMAC_invalido", estado1))
    
    # TEST 2: JSON malformado
    print("\n" + "=" * 72)
    print(" TEST 2: JSON MALFORMADO ".center(72, " "))
    print("=" * 72)
    
    payload2 = '{"operation":"renovacion", "book_code":"BOOK-123", "user_id":42'  # falta cierre
    
    estado2, _ = enviar_payload(ctx, "JSON Malformado", payload2,
                                 "JSON sin cerrar llave")
    resultados.append(("JSON_malformado", estado2))
    
    # TEST 3: Campo 'operation' faltante
    print("\n" + "=" * 72)
    print(" TEST 3: CAMPO OPERATION FALTANTE ".center(72, " "))
    print("=" * 72)
    
    solicitud_sin_op = {
        "book_code": "BOOK-123",
        "user_id": 42,
        "request_id": "test-missing-op",
        "ts": int(datetime.utcnow().timestamp()),
        "nonce": "testnonce"
    }
    payload3 = json.dumps(solicitud_sin_op)
    
    estado3, _ = enviar_payload(ctx, "Sin Operation", payload3,
                                 "Falta campo 'operation'")
    resultados.append(("Sin_operation", estado3))
    
    # TEST 4: Campo 'book_code' faltante
    print("\n" + "=" * 72)
    print(" TEST 4: CAMPO BOOK_CODE FALTANTE ".center(72, " "))
    print("=" * 72)
    
    solicitud_sin_book = {
        "operation": "renovacion",
        "user_id": 42,
        "request_id": "test-missing-book"
    }
    payload4 = json.dumps(solicitud_sin_book)
    
    estado4, _ = enviar_payload(ctx, "Sin Book Code", payload4,
                                 "Falta campo 'book_code'")
    resultados.append(("Sin_book_code", estado4))
    
    # TEST 5: user_id como string (tipo incorrecto)
    print("\n" + "=" * 72)
    print(" TEST 5: TIPO DE DATO INCORRECTO ".center(72, " "))
    print("=" * 72)
    
    solicitud_tipo = {
        "operation": "renovacion",
        "book_code": "BOOK-123",
        "user_id": "cuarenta y dos",  # string en lugar de int
        "request_id": "test-wrong-type"
    }
    payload5 = json.dumps(solicitud_tipo)
    
    estado5, _ = enviar_payload(ctx, "user_id String", payload5,
                                 "user_id es string en lugar de int")
    resultados.append(("Tipo_incorrecto", estado5))
    
    # TEST 6: operation como número (tipo incorrecto)
    print("\n" + "=" * 72)
    print(" TEST 6: OPERATION COMO NÚMERO ".center(72, " "))
    print("=" * 72)
    
    solicitud_op_num = {
        "operation": 123,  # número en lugar de string
        "book_code": "BOOK-123",
        "user_id": 42
    }
    payload6 = json.dumps(solicitud_op_num)
    
    estado6, _ = enviar_payload(ctx, "Operation Número", payload6,
                                 "operation es número en lugar de string")
    resultados.append(("Operation_numero", estado6))
    
    # TEST 7: Cadena vacía como JSON
    print("\n" + "=" * 72)
    print(" TEST 7: CADENA VACÍA ".center(72, " "))
    print("=" * 72)
    
    payload7 = ""
    
    estado7, _ = enviar_payload(ctx, "Cadena Vacía", payload7,
                                 "Payload vacío")
    resultados.append(("Cadena_vacia", estado7))
    
    # TEST 8: JSON válido pero operación inválida
    print("\n" + "=" * 72)
    print(" TEST 8: OPERACIÓN INVÁLIDA ".center(72, " "))
    print("=" * 72)
    
    solicitud_op_inv = {
        "operation": "delete_all",  # operación no soportada
        "book_code": "BOOK-123",
        "user_id": 42
    }
    payload8 = json.dumps(solicitud_op_inv)
    
    estado8, _ = enviar_payload(ctx, "Operación Inválida", payload8,
                                 "operation='delete_all' no soportada")
    resultados.append(("Operacion_invalida", estado8))
    
    # Análisis de resultados
    print("\n" + "=" * 72)
    print(" RESULTADOS CONSOLIDADOS ".center(72, " "))
    print("=" * 72)
    
    rechazados = 0
    aceptados = 0
    timeouts = 0
    errores = 0
    
    for nombre, estado in resultados:
        print(f"\n  {nombre:20} : {estado}")
        if estado in ("error", "ERROR"):
            rechazados += 1
        elif estado in ("ok", "OK", "OKAY"):
            aceptados += 1
        elif estado == "TIMEOUT":
            timeouts += 1
        else:
            errores += 1
    
    total = len(resultados)
    
    print("\n" + "-" * 72)
    print(f"\n  Total de pruebas : {total}")
    print(f"  Rechazados       : {rechazados} ({rechazados/total*100:.1f}%)")
    print(f"  Aceptados        : {aceptados} ({aceptados/total*100:.1f}%)")
    print(f"  Timeouts         : {timeouts} ({timeouts/total*100:.1f}%)")
    print(f"  Otros            : {errores}")
    
    # Evaluación de seguridad
    print("\n" + "-" * 72)
    
    if aceptados == 0:
        print("\n✅ EXCELENTE: El sistema rechazó todas las entradas corruptas")
        resultado_final = "SEGURO"
    elif aceptados <= total * 0.2:
        print(f"\n⚠️  ACEPTABLE: El sistema rechazó {rechazados}/{total} entradas corruptas")
        print("   Algunas entradas inválidas fueron aceptadas")
        resultado_final = "ACEPTABLE"
    else:
        print(f"\n❌ VULNERABLE: El sistema aceptó {aceptados}/{total} entradas corruptas")
        print("   Se recomienda implementar validación más estricta")
        resultado_final = "VULNERABLE"
    
    print("-" * 72)
    
    # Guardar reporte
    reporte = {
        "test": "entrada_corrupta",
        "timestamp": iso(),
        "total_pruebas": total,
        "rechazados": rechazados,
        "aceptados": aceptados,
        "timeouts": timeouts,
        "resultado": resultado_final,
        "detalle": [{"test": n, "estado": e} for n, e in resultados]
    }
    
    reporte_path = Path(__file__).parent / "reporte_corrupt.json"
    with open(reporte_path, "w") as f:
        json.dump(reporte, f, indent=2)
    
    print(f"\n📄 Reporte guardado en: {reporte_path}\n")
    
    ctx.term()
    
    return aceptados == 0

if __name__ == "__main__":
    try:
        exito = test_entrada_corrupta()
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrumpido por el usuario\n")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ ERROR INESPERADO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

