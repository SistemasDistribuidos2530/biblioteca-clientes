# ✅ CHECKLIST DEMO 3 MÁQUINAS - Sistema Biblioteca

**Fecha:** 14 noviembre 2025  
**Equipo:** Thomas (M1), Santiago (M2), Diego (M3)

---
## 📋 Pre-Demo (5 min)

### M1 (Thomas - 10.43.101.220)
```bash
cd ~/biblioteca-sistema
git pull
grep GA_ROLE= .env    # ✓ primary
python3 --version     # ✓ 3.10+
python3 -c "import zmq; print(zmq.__version__)"  # ✓ instalado
```

### M2 (Santiago - 10.43.102.248)
```bash
cd ~/biblioteca-sistema
git pull
grep GA_ROLE= .env    # ✓ secondary
python3 --version
python3 -c "import zmq; print(zmq.__version__)"
```

### M3 (Diego - 10.43.102.38)
```bash
cd ~/biblioteca-clientes
git pull
grep GC_ADDR= .env    # ✓ tcp://10.43.101.220:5555
python3 --version
python3 -c "import zmq; print(zmq.__version__)"
```

---
## 🚀 INICIO DEMO (Orden exacto)

### 1️⃣ M1: Arranque Sede 1 Primary
```bash
cd ~/biblioteca-sistema
bash scripts/start_site1.sh
ss -tnlp | grep -E ':5555|:5556|:6000'
```
**✓ Esperado:** 3 líneas con LISTEN en puertos 5555, 5556, 6000

---

### 2️⃣ M2: Arranque Sede 2 Secondary
```bash
cd ~/biblioteca-sistema
bash scripts/start_site2.sh
ss -tnlp | grep -E ':5555|:5556|:6001'
```
**✓ Esperado:** 3 líneas con LISTEN en puertos 5555, 5556, 6001

---

### 3️⃣ M3: Validar conectividad
```bash
nc -vz 10.43.101.220 5555   # ✓ succeeded
nc -vz 10.43.102.248 5555   # ✓ succeeded (opcional)
```
**Si falla:** Revisar firewall en M1/M2 (`sudo ufw allow 5555/tcp`)

---

### 4️⃣ M3: Experimentos de Carga
```bash
cd ~/biblioteca-clientes
bash scripts/run_experiments.sh
ls -1 experimentos/*ps.txt | wc -l     # ✓ 3 archivos
grep -c request_id= experimentos/ps_logs_4ps.txt   # ✓ > 0
```
**✓ Esperado:** 3 escenarios (4, 6, 10 PS) completados con métricas

---

### 5️⃣ M3: Seguridad (DEMO rápida)
```bash
cd ~/biblioteca-clientes/pruebas
python3 test_injection.py
python3 test_corrupt.py
ls -lh reporte_injection.json reporte_corrupt.json
```
**✓ Esperado:** 2 archivos JSON generados

---

### 6️⃣ M1+M3: FAILOVER GA (⭐ Momento clave)
#### M1:
```bash
pgrep -f ga/ga.py         # Anotar PID
pkill -f ga/ga.py         # Simular caída
sleep 5
cat gc/ga_activo.txt      # ✓ Debe decir: secondary
```
#### M3 (inmediatamente después):
```bash
cd ~/biblioteca-clientes
python3 pruebas/multi_ps.py --num-ps 2 --requests-per-ps 10 --mix 50:50:0 --seed 999 --allow-fail
grep -c 'status=OK' ps_logs.txt
grep -c 'status=TIMEOUT' ps_logs.txt
```
**✓ Esperado:** Sistema continúa procesando (algunos OK/TIMEOUT durante transición)

---

### 7️⃣ M3: Consolidar Métricas Finales
```bash
cd ~/biblioteca-clientes/experimentos
python3 ../pruebas/consolidar_metricas.py --dir . --output informe_final --formato all
ls -lh informe_final.{csv,json,md}
head -n10 informe_final.md
```
**✓ Esperado:** 3 archivos generados con comparativa

---

### 8️⃣ M1+M2: Parada Ordenada
#### M1:
```bash
cd ~/biblioteca-sistema
bash scripts/stop_all.sh
ss -tnlp | grep -E ':5555|:5556|:6000' || echo "✓ Puertos liberados"
```
#### M2:
```bash
cd ~/biblioteca-sistema
bash scripts/stop_all.sh
ss -tnlp | grep -E ':5555|:5556|:6001' || echo "✓ Puertos liberados"
```

---

### 9️⃣ Recolectar Evidencias
```bash
# M3
cd ~
mkdir -p demo_evidencias
cp biblioteca-clientes/experimentos/*.{csv,json,md} demo_evidencias/ 2>/dev/null
cp biblioteca-clientes/pruebas/reporte_*.json demo_evidencias/ 2>/dev/null
ls -lh demo_evidencias/
tar -czf demo_evidencias_$(date +%Y%m%d_%H%M).tar.gz demo_evidencias/
```

---

## 🎯 PUNTOS CLAVE PARA MOSTRAR

| # | Qué mostrar | Dónde | Duración |
|---|-------------|-------|----------|
| 1 | Arquitectura (diagrama) | Slides | 2 min |
| 2 | Arranque M1/M2 (logs y puertos) | Terminales | 1 min |
| 3 | Conectividad M3→M1 (`nc`) | M3 | 30 seg |
| 4 | Experimentos (4/6/10 PS) | M3 logs | 2 min |
| 5 | Métricas comparativas (CSV/MD) | M3 | 1 min |
| 6 | **FAILOVER GA** | M1+M3 | 3 min ⭐ |
| 7 | Continuidad post-failover | M3 logs | 1 min |
| 8 | Seguridad (injection bloqueada) | M3 JSON | 1 min |

**Total estimado:** 12 minutos (margen para preguntas)

---

## 🔴 TROUBLESHOOTING RÁPIDO

| Problema | Solución inmediata |
|----------|--------------------|
| Puerto 5555 no escucha | `bash scripts/start_site1.sh` en M1 |
| M3 no conecta a M1 | `sudo ufw allow 5555/tcp` en M1 |
| `nc` falla | Verificar IP M1 en `.env` de M3 |
| Experimentos sin CSV | Revisar `logs/multi_ps_run.log` |
| Failover no cambia | Verificar `logs/monitor_failover.log` |
| Puertos colgados | `lsof -i :5555` y `kill -9 <PID>` |

---

## 📊 MÉTRICAS ESPERADAS (Referencia)

| Escenario | PS | Latencia media | TPS aprox | OK% |
|-----------|----|----|-------|-----|
| Carga baja | 4 | 0.12-0.18s | 22-28 | 95%+ |
| Carga media | 6 | 0.13-0.20s | 30-38 | 95%+ |
| Carga alta | 10 | 0.15-0.24s | 44-55 | 93%+ |

| Métrica Failover | Valor esperado |
|------------------|----------------|
| MTTD (detección) | < 10s |
| MTTR (recuperación) | < 5s |
| Continuidad | ≥80% solicitudes OK post-failover |

---

## ✅ CHECKLIST FINAL PRE-DEMO

- [ ] Git pull en las 3 máquinas
- [ ] .env configurados correctamente
- [ ] Dependencias instaladas (zmq, psutil)
- [ ] Conectividad validada (ping, nc)
- [ ] Scripts ejecutables (chmod +x)
- [ ] Logs limpios (opcional: `rm -rf logs/*`)
- [ ] Browser/editor abierto para mostrar código
- [ ] Diagrama de arquitectura preparado
- [ ] Timer/cronómetro visible

---

**Éxito:** Sistema levantado → Carga → Failover → Métricas → Parada  
**Documentado en:** `PASO_A_PASO_MULTI_MAQUINA.md` (idéntico en ambos repos)

