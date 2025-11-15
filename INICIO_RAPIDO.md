# 🚀 INICIO RÁPIDO - Sistema Biblioteca Distribuido

**Pontificia Universidad Javeriana**  
**Sistemas Distribuidos - Proyecto Entrega 2**  
**Equipo:** Thomas Arévalo, Santiago Mesa, Diego Castrillón

---

## 📋 Tabla de Contenidos

1. [Configuración Inicial](#configuración-inicial)
2. [Mapeo de Máquinas](#mapeo-de-máquinas)
3. [Inicio Automático (Recomendado)](#inicio-automático-scripts)
4. [Inicio Manual (Alternativo)](#inicio-manual-detallado)
5. [Demo Completa 3 Máquinas](#demo-completa-3-máquinas)
6. [Cambios desde Entrega 1](#cambios-desde-entrega-1)
7. [Verificación y Pruebas](#verificación-y-pruebas)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Configuración Inicial

### Pre-requisitos (todas las máquinas):
```bash
python3 --version  # 3.10+
pip install pyzmq psutil python-dotenv
```

### Clonar repositorios:

**M1 (Thomas) y M2 (Santiago):**
```bash
git clone https://github.com/SistemasDistribuidos2530/biblioteca-sistema.git
cd biblioteca-sistema
```

**M3 (Diego):**
```bash
git clone https://github.com/SistemasDistribuidos2530/biblioteca-clientes.git
cd biblioteca-clientes
```

---

## 🖥️ Mapeo de Máquinas

| Máquina | Propietario | IP | Rol | Repositorio |
|---------|------------|-----|-----|-------------|
| M1 | Thomas | 10.43.101.220 | Sede 1 Primary (GA+GC+Actores) | biblioteca-sistema |
| M2 | Santiago | 10.43.102.248 | Sede 2 Secondary (GA+GC+Actores) | biblioteca-sistema |
| M3 | Diego | 10.43.102.38 | Clientes (PS+Experimentos) | biblioteca-clientes |

---

## 🔥 Inicio Automático (Scripts)

### Paso 1: M1 - Arrancar Sede 1 Primary

```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
# o la ruta donde clonaste

# Configurar .env
cp .env.example .env
# (Verificar que GA_ROLE=primary)

# Arrancar todos los componentes
bash scripts/start_site1.sh

# Verificar puertos
ss -tnlp | grep -E ':5555|:5556|:6000'
```

**Esperado:** 3 líneas mostrando puertos 5555, 5556, 6000 en LISTEN

---

### Paso 2: M2 - Arrancar Sede 2 Secondary

```bash
cd ~/Desktop/DistribuidosProyecto/biblioteca-sistema
# o tu ruta

# Configurar .env
cp .env.example .env
sed -i 's/GA_ROLE=primary/GA_ROLE=secondary/' .env

# Arrancar todos los componentes
bash scripts/start_site2.sh

# Verificar puertos
ss -tnlp | grep -E ':5555|:5556|:6001'
```

**Esperado:** 3 líneas mostrando puertos 5555, 5556, 6001 en LISTEN

---

### Paso 3: M3 - Validar Conectividad

```bash
cd ~/biblioteca-clientes

# Configurar .env
cp .env.example .env
# (Verificar que GC_ADDR=tcp://10.43.101.220:5555)

# Probar conectividad
nc -vz 10.43.101.220 5555  # Debe decir "succeeded"
```

**Si falla:** Verificar firewall en M1: `sudo ufw allow 5555/tcp`

---

### Paso 4: M3 - Ejecutar Experimentos

```bash
cd ~/biblioteca-clientes

# Opción A: Experimentos automáticos (4, 6, 10 PS)
bash scripts/run_experiments.sh

# Verificar resultados
ls -lh experimentos/
cat experimentos/experimento_carga.md

# Opción B: Carga manual
bash scripts/start_clients.sh
head -n5 logs/metricas_ps.csv
```

---

### Paso 5: Detener Sistema

**M1:**
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
bash scripts/stop_all.sh
```

**M2:**
```bash
cd ~/Desktop/DistribuidosProyecto/biblioteca-sistema
bash scripts/stop_all.sh
```

---

## 🔧 Inicio Manual (Detallado)

Si prefieres control total, puedes lanzar cada componente individualmente:

### M1 - Sede 1 Primary

**Terminal 1 - GA Primary:**
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
export GA_ROLE=primary
export GA_PRIMARY_BIND=tcp://0.0.0.0:6000
python3 ga/ga.py
```

**Terminal 2 - GC:**
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
python3 gc/gc_multihilo.py
```

**Terminal 3 - Actor Renovación:**
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
python3 actores/actor_renovacion.py
```

**Terminal 4 - Actor Devolución:**
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
python3 actores/actor_devolucion.py
```

**Terminal 5 - Actor Préstamo:**
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
python3 actores/actor_prestamo.py
```

**Terminal 6 - Monitor Failover:**
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
python3 gc/monitor_failover.py
```

---

### M2 - Sede 2 Secondary

**Terminal 1 - GA Secondary:**
```bash
cd ~/Desktop/DistribuidosProyecto/biblioteca-sistema
export GA_ROLE=secondary
export GA_SECONDARY_BIND=tcp://0.0.0.0:6001
python3 ga/ga.py
```

**Terminal 2-6:** Repetir GC y actores (igual que M1)

---

### M3 - Clientes

**Terminal 1 - Generar y Enviar:**
```bash
cd ~/biblioteca-clientes
python3 ps/gen_solicitudes.py --n 100 --mix 50:50:0 --seed 42
python3 ps/ps.py
```

**Terminal 2 - Ver Métricas:**
```bash
cd ~/biblioteca-clientes
tail -f ps_logs.txt
```

---

## 🎬 Demo Completa 3 Máquinas

### Orden de ejecución (paso a paso):

#### 1️⃣ M1 - Arrancar Sede 1 (2 min)
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
bash scripts/start_site1.sh
ss -tnlp | grep -E ':5555|:5556|:6000'
```
**Esperado:** 3 líneas LISTEN en puertos 5555, 5556, 6000

#### 2️⃣ M2 - Arrancar Sede 2 (2 min)
```bash
cd ~/Desktop/DistribuidosProyecto/biblioteca-sistema
bash scripts/start_site2.sh
ss -tnlp | grep -E ':5555|:5556|:6001'
```
**Esperado:** 3 líneas LISTEN en puertos 5555, 5556, 6001

#### 3️⃣ M3 - Validar Conectividad (30 seg)
```bash
nc -vz 10.43.101.220 5555  # succeeded
nc -vz 10.43.102.248 5555  # succeeded
```

#### 4️⃣ M3 - Ejecutar Experimentos (3 min)
```bash
cd ~/biblioteca-clientes
bash scripts/run_experiments.sh
cat experimentos/experimento_carga.md
```

#### 5️⃣ M1+M3 - Prueba de Failover (2 min)
```bash
# M1:
pgrep -f ga/ga.py
pkill -f ga/ga.py
sleep 5
cat gc/ga_activo.txt  # Debe decir: secondary

# M3:
python3 pruebas/multi_ps.py --num-ps 2 --requests-per-ps 10
grep -c 'status=OK' ps_logs.txt  # Sistema sigue funcionando
```

#### 6️⃣ M1+M2 - Detener Sistema (1 min)
```bash
# M1:
bash scripts/stop_all.sh

# M2:
bash scripts/stop_all.sh
```

**Total: ~10 minutos de demo completa**

---

## 📊 Cambios desde Entrega 1

### 1️⃣ **Automatización con Scripts**

**Antes (Entrega 1):**
- 5-7 terminales manuales por sede
- Procesos foreground (bloqueaban terminal)
- Logs mezclados en pantalla
- Detener con Ctrl+C en cada terminal

**Ahora (Entrega 2):**
- 1 comando por sede: `bash scripts/start_site1.sh`
- Procesos background (operador `&`)
- Logs separados en archivos (`logs/*.log`)
- Detener con: `bash scripts/stop_all.sh`

---

### 2️⃣ **Gestión de PIDs**

**Nuevo:**
```bash
# Ver procesos corriendo
cat .pids/*.pid

# Detener proceso específico
pkill -f ga/ga.py

# Ver logs en tiempo real
tail -f logs/ga_primary.log
```

---

### 3️⃣ **Failover GA**

**Nuevo en Entrega 2:**
- GA Secondary en puerto 6001 (M2)
- Monitoreo automático con heartbeats
- Conmutación automática si GA primary cae
- Archivo `gc/ga_activo.txt` indica estado actual

**Prueba:**
```bash
# M1: Simular caída
pkill -f ga/ga.py
sleep 5
cat gc/ga_activo.txt  # Debe decir: secondary

# M3: Carga sigue funcionando
python3 pruebas/multi_ps.py --num-ps 2 --requests-per-ps 10
```

---

### 4️⃣ **Multi-PS Concurrentes**

**Nuevo:**
```bash
# Lanzar múltiples PS en paralelo
python3 pruebas/multi_ps.py --num-ps 10 --requests-per-ps 20 --mode concurrent

# Logs consolidados automáticamente
cat multi_ps_logs/ps_logs_consolidado.txt
```

---

### 5️⃣ **Experimentos Automatizados**

**Nuevo:**
```bash
# Ejecuta 3 escenarios (4, 6, 10 PS) automáticamente
bash scripts/run_experiments.sh

# Resultados consolidados
cat experimentos/experimento_carga.md
```

---

### 6️⃣ **Gitignore Completo**

**Archivos que ahora se ignoran automáticamente:**
- `logs/` - Logs de ejecución
- `multi_ps_logs/` - Logs de PS múltiples
- `experimentos/` - Resultados de pruebas
- `solicitudes*.bin` - Archivos temporales
- `.pids/` - PIDs de procesos background
- `gc/ga_db_*.pkl` - Bases de datos generadas
- `gc/ga_wal_*.log` - Write-ahead logs
- `pruebas/reporte_*.json` - Reportes de seguridad

**Beneficio:** No más conflictos git tras ejecutar experimentos

---

## ✅ Verificación y Pruebas

### 1. Verificar Sistema Levantado

**M1:**
```bash
ss -tnlp | grep -E ':5555|:5556|:6000'  # 3 líneas
pgrep -f python3  # Varios PIDs
ls -lh logs/  # Logs actualizándose
```

**M2:**
```bash
ss -tnlp | grep -E ':5555|:5556|:6001'  # 3 líneas
```

**M3:**
```bash
nc -vz 10.43.101.220 5555  # succeeded
nc -vz 10.43.102.248 5555  # succeeded
```

---

### 2. Prueba Rápida de Carga

**M3:**
```bash
cd ~/biblioteca-clientes
python3 ps/gen_solicitudes.py --n 10 --mix 50:50:0
python3 ps/ps.py
grep -c 'status=OK' ps_logs.txt  # Debe ser > 0
```

---

### 3. Prueba de Failover

**M1:**
```bash
pgrep -f ga/ga.py  # Anotar PID
pkill -f ga/ga.py
sleep 5
cat gc/ga_activo.txt  # Debe decir: secondary
```

**M3:**
```bash
python3 pruebas/multi_ps.py --num-ps 2 --requests-per-ps 5
grep -c 'status=OK' ps_logs.txt  # Sistema sigue funcionando
```

---

### 4. Experimentos Completos

**M3:**
```bash
bash scripts/run_experiments.sh
ls -1 experimentos/*.txt | wc -l  # Debe dar 3 (4ps, 6ps, 10ps)
cat experimentos/experimento_carga.md
```

---

## 🔎 Pre‑Check rápido (Sistema)

Validar que los puertos esperados estén en LISTEN tras arrancar:

### M1
```bash
ss -tnlp | grep -E ':5555|:5556|:6000' || echo "GC/GA no están arriba en M1"
```

### M2
```bash
ss -tnlp | grep -E ':5555|:5556|:6001' || echo "GC/GA no están arriba en M2"
```

---
## 🧹 Reset total (dejar en cero)

### M1 — Sede 1 (Primary)
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
bash scripts/stop_all.sh || true
pkill -f "python3 ga/ga.py" 2>/dev/null || true
pkill -f "python3 gc/gc.py" 2>/dev/null || true
pkill -f "python3 gc/gc_multihilo.py" 2>/dev/null || true
pkill -f "python3 actores/" 2>/dev/null || true
pkill -f "python3 gc/monitor_failover.py" 2>/dev/null || true
rm -rf .pids/* logs/* 2>/dev/null || true
ss -tnlp | grep -E ':5555|:5556|:6000' || echo "✓ Puertos liberados en M1"
```

### M2 — Sede 2 (Secondary)
```bash
cd ~/Desktop/DistribuidosProyecto/biblioteca-sistema
bash scripts/stop_all.sh || true
pkill -f "python3 ga/ga.py" 2>/dev/null || true
pkill -f "python3 gc/gc.py" 2>/dev/null || true
pkill -f "python3 gc/gc_multihilo.py" 2>/dev/null || true
pkill -f "python3 actores/" 2>/dev/null || true
pkill -f "python3 gc/monitor_failover.py" 2>/dev/null || true
rm -rf .pids/* logs/* 2>/dev/null || true
ss -tnlp | grep -E ':5555|:5556|:6001' || echo "✓ Puertos liberados en M2"
```

---
# ...existing code...
````
## 🚨 Troubleshooting
### Problema: Puerto ya en uso (Address already in use)
**Error:**
```
zmq.error.ZMQError: Address already in use (addr='tcp://0.0.0.0:6000')
```
**Causa:** Ya hay un proceso usando ese puerto (levantado por scripts o manualmente)
**Solución:**
```bash
# Ver qué proceso usa el puerto
ss -tnlp | grep ':6000'
# Opción 1: Parar todo ordenadamente (RECOMENDADO)
bash scripts/stop_all.sh
# Opción 2: Forzar liberación del puerto
fuser -k 6000/tcp 2>/dev/null || true
# Verificar que quedó libre
ss -tnlp | grep ':6000' || echo "✓ Puerto 6000 libre"
```
**Prevención:** Usa `stop_all.sh` antes de lanzar procesos manualmente
---
### Problema: Monitor failover no conecta al GA primary
**Síntomas:**
```
Timeout/recv error esperando pong: Resource temporarily unavailable
GA primario no responde. Usando secundario (tcp://localhost:6001)
```
**Causa:** Monitor usa `localhost` en lugar de IP de M1
**Solución:**
```bash
# M2: Exportar dirección correcta antes de lanzar monitor
export GA_PRIMARY_ADDR=tcp://10.43.101.220:6000
export GA_SECONDARY_ADDR=tcp://localhost:6001
python3 gc/monitor_failover.py
```
O mejor aún, usa el script de arranque que ya configura esto:
```bash
bash scripts/start_site2.sh
```
---
**Última actualización:** 15 noviembre 2025
---
## 🔍 Ver Monitor Failover en Vivo
Para ver el monitor en tiempo real (en lugar de background):
### M1 o M2:
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema  # o tu ruta en M2
bash scripts/run_monitor_interactive.sh
```
**Salida esperada (M1 activo):**
```
==========================================
  MONITOR FAILOVER - MODO INTERACTIVO
==========================================
Rol detectado: primary
Presiona Ctrl+C para detener
==========================================
📡 Monitoreando GA Primary local: tcp://localhost:6000
🔄 Fallback a GA Secondary en M2: tcp://10.43.102.248:6001
Iniciando monitor...
==========================================
[2025-11-15T...Z] GA primario activo (tcp://localhost:6000)
```
**Para simular failover en vivo:**
1. Abre otra terminal en M1
2. Ejecuta: `pkill -f ga/ga.py`
3. El monitor mostrará en tiempo real:
   ```
   [2025-11-15T...Z] GA primario no responde, conmutando a secundario
   [2025-11-15T...Z] Estado GA actualizado a 'secondary'
   ```
---
## 🗄️ Restaurar Base de Datos
Si borraste la BD, regenerarla con el script:
```bash
cd ~/ProyectoDistribuidos/biblioteca-sistema
python3 scripts/generate_db.py --seed 42 --num-libros 1000 --prestados-sede1 50 --prestados-sede2 150
# Verificar
ls -lh gc/ga_db_*.pkl gc/ga_wal_*.log
```
**Archivos generados:**
- `gc/ga_db_primary.pkl` (~63KB)
- `gc/ga_db_secondary.pkl` (~63KB)
- `gc/ga_wal_primary.log` (vacío inicial)
- `gc/ga_wal_secondary.log` (vacío inicial)
**Contenido de la BD:**
- 1000 libros totales
- 50 prestados en Sede 1
- 150 prestados en Sede 2
- Semilla 42 (reproducible)
---
