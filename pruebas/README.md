# Pruebas de Seguridad - Sistema de Biblioteca

**Universidad:** Pontificia Universidad Javeriana  
**Materia:** Sistemas Distribuidos  
**Integrantes:** Thomas Arévalo, Santiago Mesa, Diego Castrillón

---

## 📋 Descripción

Suite de pruebas automatizadas para validar el modelo de seguridad del sistema distribuido de biblioteca.

---

## 🧪 Tests Disponibles

### 1. **test_replay.py** - Ataque de Replay
Verifica que el sistema rechace solicitudes con timestamps fuera de la ventana válida.

**Escenario:**
1. Envía solicitud válida
2. Espera 65 segundos (fuera de ventana de 60s)
3. Reenvía la MISMA solicitud
4. Espera rechazo por timestamp expirado

**Uso:**
```bash
python pruebas/test_replay.py
```

**Configuración:**
- `GC_ADDR`: Dirección del GC (default: tcp://10.43.101.220:5555)
- `REPLAY_DELAY`: Segundos a esperar (default: 65)

---

### 2. **test_corrupt.py** - Entrada Corrupta
Envía datos malformados para verificar validación del GC.

**Casos probados:**
- HMAC inválido
- JSON malformado
- Campos faltantes (operation, book_code, user_id)
- Tipos de datos incorrectos
- Operaciones inválidas

**Uso:**
```bash
python pruebas/test_corrupt.py
```

**Métricas:**
- % de solicitudes rechazadas
- % de solicitudes aceptadas (vulnerabilidad)

---

### 3. **test_flood.py** - Ataque DoS por Flood
Envía ráfaga masiva de solicitudes para medir resistencia a sobrecarga.

**Métricas:**
- TPS alcanzado
- % de timeouts
- Latencias (min, mean, p50, p95, max)

**Uso:**
```bash
python pruebas/test_flood.py

# Con configuración personalizada
FLOOD_NUM=200 FLOOD_THREADS=10 python pruebas/test_flood.py
```

**Variables:**
- `FLOOD_NUM`: Número de solicitudes (default: 100)
- `FLOOD_THREADS`: Threads concurrentes (default: 5)

---

### 4. **test_injection.py** - Inyección de Operaciones
Intenta enviar operaciones maliciosas no válidas.

**Operaciones probadas:**
- Comandos administrativos (delete, drop, shutdown)
- SQL injection
- Command injection
- Path traversal
- XSS
- Null byte injection

**Uso:**
```bash
python pruebas/test_injection.py
```

---

### 5. **test_seguridad.py** - Script Maestro
Ejecuta todos los tests y genera reporte consolidado.

**Uso:**
```bash
# Ejecutar todos los tests
python pruebas/test_seguridad.py

# Ejecutar test específico
python pruebas/test_seguridad.py --test replay
python pruebas/test_seguridad.py --test corrupt
python pruebas/test_seguridad.py --test flood
python pruebas/test_seguridad.py --test injection

# Omitir tests lentos (replay, flood)
python pruebas/test_seguridad.py --skip-slow
```

---

## 📊 Reportes Generados

Cada test genera un reporte JSON individual:
- `reporte_replay.json`
- `reporte_corrupt.json`
- `reporte_flood.json`
- `reporte_injection.json`

El script maestro genera:
- `reporte_seguridad_consolidado.json` (JSON completo)
- `reporte_seguridad.txt` (resumen legible)

---

## 🎯 Interpretación de Resultados

### Estado por Test

- **SEGURO / PROTEGIDO / RESISTENTE**: ✅ Test pasó
- **ACEPTABLE / DEGRADADO**: ⚠️ Advertencia
- **VULNERABLE**: ❌ Vulnerabilidad crítica

### Puntuación General

- **≥ 80%**: EXCELENTE ✅
- **60-79%**: ACEPTABLE ⚠️
- **< 60%**: INSUFICIENTE ❌

---

## 🔧 Requisitos

```bash
# Dependencias (ya instaladas con biblioteca-clientes)
pip install pyzmq python-dotenv
```

---

## 📝 Ejemplo de Ejecución Completa

```bash
# 1. Asegurarse de que GC esté corriendo
cd ~/biblioteca-sistema
python gc/gc.py &

# 2. Ejecutar suite completa
cd ~/biblioteca-clientes
python pruebas/test_seguridad.py

# 3. Ver reportes
cat pruebas/reporte_seguridad.txt
```

---

## ⚠️ Notas Importantes

1. **GC debe estar corriendo** antes de ejecutar las pruebas
2. **test_replay.py** tarda ~65 segundos (espera deliberada)
3. **test_flood.py** puede saturar el GC temporalmente
4. Los reportes se sobrescriben en cada ejecución

---

## 🚀 Integración con Makefile

```bash
# Añadir al Makefile de biblioteca-clientes
test-security:
	@python pruebas/test_seguridad.py

test-security-fast:
	@python pruebas/test_seguridad.py --skip-slow
```

---
