# Guía Paso a Paso Multi‑Máquina (FASE 6)

Este documento describe un flujo secuencial, terminal por terminal y máquina por máquina, para desplegar, probar carga, seguridad, fallos y failover del sistema distribuido de biblioteca en 3 máquinas (M1, M2, M3). Está pensado para una DEMO o verificación integral. No incluye LaTeX ni empaquetado final.

## Tabla de Referencia de Máquinas
| Alias | Propietario | Rol | Repo a clonar | IP |
|-------|------------|-----|---------------|----|
| M1 | Thomas (Computador 1) | Sede 1 — Primary (GA + GC + Actores) | https://github.com/SistemasDistribuidos2530/biblioteca-sistema | 10.43.101.220 |
| M2 | Santiago (Computador 2) | Sede 2 — Secondary (GA + GC + Actores) | https://github.com/SistemasDistribuidos2530/biblioteca-sistema | 10.43.102.248 |
| M3 | Diego (Computador 3) | Clientes (PS + Seguridad + Experimentos) | https://github.com/SistemasDistribuidos2530/biblioteca-clientes | 10.43.102.38 |

## Convenciones
- "T1", "T2" … indican terminales distintos simultáneos en la misma máquina.
- Comandos son copy & paste. Ajustar IPs si difieren.
- Usar entorno virtual opcional en cada máquina.
- Asegurar reloj sincronizado (NTP) para tolerancia de timestamp en HMAC.

---
## 0. Pre‑Flight Checklist (una sola vez)
Ejecutar en cada máquina antes de iniciar secuencia:
```bash
python3 --version           # Debe ser 3.10+ 
python3 -c "import zmq; print(zmq.__version__)"  # pyzmq instalado
ping -c1 10.43.101.220      # Desde M3 a M1 (Thomas)
ping -c1 10.43.102.248      # Desde M3 a M2 (Santiago)
```
Si falta pyzmq o psutil:
```bash
pip install pyzmq psutil python-dotenv
```

---
## 1. Clonar Repositorio (por máquina)
### M1 / T1 — Thomas (Sede 1 Primary)
```bash
git clone https://github.com/SistemasDistribuidos2530/biblioteca-sistema.git
cd biblioteca-sistema
```
### M2 / T1 — Santiago (Sede 2 Secondary)
```bash
git clone https://github.com/SistemasDistribuidos2530/biblioteca-sistema.git
cd biblioteca-sistema
```
### M3 / T1 — Diego (Clientes)
```bash
git clone https://github.com/SistemasDistribuidos2530/biblioteca-clientes.git
cd biblioteca-clientes
```

(Usar mismo commit/branch en las 3 máquinas para reproducibilidad.)

---
## 2. Configuración .env y Entorno
### M1 / T1 (biblioteca-sistema — Primary)
```bash
cp .env.example .env
# Confirmar/ajustar GA_ROLE=primary (por defecto) y binds si aplica
sed -n '1,40p' .env
```
### M2 / T1 (biblioteca-sistema — Secondary)
```bash
cp .env.example .env
# Cambiar rol a secundario
sed -i 's/GA_ROLE=primary/GA_ROLE=secondary/' .env
sed -n '1,40p' .env
```
### M3 / T1 (biblioteca-clientes — Clientes)
```bash
cp .env.example .env
# Asegurar que GC_ADDR apunte al GC de M1 (Thomas)
sed -i 's#GC_ADDR=tcp://10.43.101.220:5555#GC_ADDR=tcp://10.43.101.220:5555#' .env
sed -n '1,20p' .env
```
(Opcional: crear entorno virtual y activar en cada máquina.)

### Aclaración sobre variables .env (bind vs dirección remota)
Las variables actuales en `biblioteca-sistema/.env` usan `0.0.0.0` para BIND (escuchar en todas las interfaces de la máquina local). Esto está BIEN para procesos que se levantan en esa máquina.

Resumen de uso:
- GC_REP_BIND / GC_PUB_BIND / GA_PRIMARY_BIND / GA_SECONDARY_BIND / GA_REPL_PULL_BIND: valores de BIND (el proceso abre el puerto local). Se mantienen como `tcp://0.0.0.0:PUERTO`.
- GA_REPL_PUSH_ADDR: dirección REMOTA a la que el GA primario enviará (push) actualizaciones. Aquí sí conviene poner la IP de la otra sede.

Recomendación mínima para replicación:
- En M1 (primary):
  - GA_PRIMARY_BIND=tcp://0.0.0.0:6000
  - GA_SECONDARY_BIND=tcp://10.43.102.248:6001   (opcional si algún proceso necesita conocer el secundario por IP)
  - GA_REPL_PUSH_ADDR=tcp://10.43.102.248:7001   (push hacia secondary)
  - GA_REPL_PULL_BIND=tcp://0.0.0.0:7001         (si el primary también acepta pull interno, se puede dejar; sino ignorar)
- En M2 (secondary):
  - GA_PRIMARY_BIND=tcp://10.43.101.220:6000     (si procesos locales deben contactar al primary)
  - GA_SECONDARY_BIND=tcp://0.0.0.0:6001
  - GA_REPL_PULL_BIND=tcp://0.0.0.0:7001         (bind para recibir push del primary)
  - GA_REPL_PUSH_ADDR (puede omitirse si la replicación es solo primaria→secundaria)

Si aún no implementan el flujo de replicación, pueden dejar todos en `0.0.0.0` sin romper la demo básica. Ajustar IPs sólo cuando prueben failover/replicación real.

---
## 3. Generar Base de Datos Inicial (Primary)
### M1 / T1
```bash
python3 scripts/generate_db.py --seed 42 --num-libros 1000 --prestados-sede1 50 --prestados-sede2 150
ls -lh gc/ga_db_primary.pkl gc/ga_db_secondary.pkl gc/ga_wal_primary.log gc/ga_wal_secondary.log
```

---
## 4. Arranque de Componentes – Sede 1 (Primary)
### M1 / T1 (GA + GC + Actores + Monitor) 
```bash
bash scripts/start_site1.sh
```
Verificar puertos:
```bash
ss -tnlp | grep -E ':5555|:5556|:6000'
```
### M1 / T2 (Tail de logs opcional)
```bash
cd logs
tail -f ga_primary.log gc_multihilo.log actor_renovacion.log | sed -u 's/^/[M1-T2] /'
```

---
## 5. Arranque de Componentes – Sede 2 (Secondary)
### M2 / T1
```bash
bash scripts/start_site2.sh
ss -tnlp | grep -E ':6001'
```
### M2 / T2 (Logs)
```bash
cd logs
tail -f ga_secondary.log | sed -u 's/^/[M2-T2] /'
```

---
## 6. Lanzar Carga Inicial – Clientes (después de Sistema)
Antes de lanzar clientes, valida conectividad desde M3 hacia M1:
```bash
nc -vz 10.43.101.220 5555   # Debe mostrar 'succeeded'
```
Si falla:
- Revisar que en M1 esté activo `bash scripts/start_site1.sh`.
- Ver firewall: `sudo ufw allow 5555/tcp && sudo ufw allow 5556/tcp`.

### M3 / T1
```bash
bash scripts/start_clients.sh
ls -lh logs/
head -n5 logs/metricas_ps.csv
```
### M3 / T2 (Tail métricas en vivo – opcional)
```bash
watch -n2 "grep -c request_id= ps_logs.txt; tail -n3 ps_logs.txt"
```

---
## 7. Experimentos de Escenarios (4, 6, 10 PS)
Verifica nuevamente que el puerto 5555 está abierto antes de iniciar:
```bash
nc -vz 10.43.101.220 5555
```
Si un escenario no produce CSV, inspecciona `experimentos/parser_*ps.log` y `experimentos/escenario_*ps_run.log`.

### M3 / T1
```bash
bash scripts/run_experiments.sh
ls -lh experimentos/
cat experimentos/experimento_carga.md
```
### M3 / T2 (Consolidación adicional)
```bash
cd biblioteca-clientes/experimentos
python3 ../pruebas/consolidar_metricas.py --dir . --output comparativa --formato all
ls -lh comparativa.*
```

---
## 8. Pruebas de Seguridad (rápido)
### M3 / T1
```bash
cd biblioteca-clientes/pruebas
python3 test_injection.py
python3 test_corrupt.py
python3 test_seguridad.py --skip-slow
ls -lh reporte_*seguridad*.json || ls -lh reporte_injection.json
```
(Omitir replay/flood si el tiempo es limitado; ejecutar luego.)

---
## 9. Pruebas de Fallos – Caída de Actor
### M1 / T3 (nuevo terminal)
```bash
cd biblioteca-sistema/pruebas
python3 test_actor_failure.py --actor renovacion
ls -lh reporte_actor_failure_renovacion.json
```
(Interpretar resultado: RECUPERADO vs CAIDO)

---
## 10. Pruebas de Fallos – Corrupción de DB (WAL)
### M1 / T3
```bash
python3 test_db_corruption.py --role primary
cat reporte_db_corruption_primary.json | sed -n '1,40p'
```
(No requiere detener el GA si sólo evalúa archivos; para prueba profunda detener GA antes.)

---
## 11. Latencia Artificial
### M1 / T3
```bash
python3 test_latency.py
cat reporte_latency.json | sed -n '1,60p'
```

---
## 12. Simular Failover GA
### M1 / T4 (nuevo terminal)
```bash
pgrep -f ga/ga.py    # Ver PID primario
pkill -f ga/ga.py    # Caída del GA primario
sleep 4
```
### M1 / T2 (viendo monitor_failover.log)
Observar cambio a secondary:
```bash
grep -i 'secondary' logs/monitor_failover.log | tail -n3
cat gc/ga_activo.txt   # Debe decir: secondary
```
### M3 / T1 (Enviar carga tras failover)
```bash
python3 pruebas/multi_ps.py --num-ps 4 --requests-per-ps 20 --mix 50:50:0 --seed 999
grep -c 'status=OK' ps_logs.txt
```
(Evaluar continuidad de servicio.)

---
## 13. Consolidar Métricas Finales
### M3 / T1
```bash
cd biblioteca-clientes/experimentos
python3 ../pruebas/consolidar_metricas.py --dir . --output informe_final --formato all
ls -lh informe_final.*
```

---
## 14. Verificación Global Pre‑Empaquetado
### Cualquier máquina / T1
```bash
bash scripts/verify_submission.sh
```
Salida esperada:
```
RESULTADO: ✅ Todo lo esencial está presente
```
Nota: este verificador existe cuando se usa el repositorio consolidado con ambos módulos. Si trabajas con repos separados por máquina, este paso es opcional.

---
## 15. Parada Ordenada
### M1 / T1
```bash
cd biblioteca-sistema
bash scripts/stop_all.sh
```
### M2 / T1
```bash
cd biblioteca-sistema
bash scripts/stop_all.sh
```
(No se requiere stop en clientes; procesos efímeros.)

---
## 16. Recolectar Artefactos para Informe
- Métricas: `biblioteca-clientes/experimentos/*.json|csv|md`
- Seguridad: `biblioteca-clientes/pruebas/reporte_*.json`
- Fallos: `biblioteca-sistema/pruebas/reporte_*.json`
- Failover: `biblioteca-sistema/logs/monitor_failover.log`
- BD inicial: `biblioteca-sistema/gc/ga_db_primary.pkl`

Copiar a carpeta `deliverables/` (crear si falta).
```bash
mkdir -p deliverables
cp biblioteca-clientes/experimentos/*.{json,csv,md} deliverables/ 2>/dev/null || true
cp biblioteca-clientes/pruebas/reporte_*.json deliverables/ 2>/dev/null || true
cp biblioteca-sistema/pruebas/reporte_*.json deliverables/ 2>/dev/null || true
cp biblioteca-sistema/logs/monitor_failover.log deliverables/ 2>/dev/null || true
cp biblioteca-sistema/gc/ga_db_primary.pkl deliverables/ 2>/dev/null || true
```

---
## 17. Referencias Rápidas
| Objetivo | Comando Clave |
|----------|---------------|
| Validar GC activo (M3→M1) | `nc -vz 10.43.101.220 5555` |
| Carga multi‑PS | `python3 pruebas/multi_ps.py --num-ps N --requests-per-ps M` |
| Métricas consolidadas | `python3 ps/log_parser.py --log ps_logs.txt --csv logs/metricas_ps.csv` |
| Failover GA | `pkill -f ga/ga.py` + revisar `gc/ga_activo.txt` |
| Actor caída | `python3 test_actor_failure.py --actor devolucion` |
| Seguridad suite | `python3 test_seguridad.py --skip-slow` |
| Verificación estructura | `bash scripts/verify_submission.sh` |

---
## 18. Notas y Buenas Prácticas
- Montar primero Sistema (M1 y M2), luego Clientes (M3); evita correr carga sin GC.
- Para pruebas rápidas locales usar localhost en `.env` del cliente.
- TIMEOUT se registra y es analizable; no indica fallo del cliente sino ausencia de respuesta GC.
- Mantener secreto HMAC fuera del repo final.
- Documentar ventana de inconsistencia por replicación asíncrona en informe.
- Usar mismas semillas para escenarios repetibles.
- Si puerto queda colgado tras fallo: `lsof -i :5555` y `kill -9 <PID>`.
