# 📚 Sistema Biblioteca Distribuido - Lado Clientes

**Universidad:** Pontificia Universidad Javeriana  
**Materia:** Sistemas Distribuidos  
**Profesor:** Rafael Páez Méndez  
**Equipo:** Thomas Arévalo, Santiago Mesa, Diego Castrillón  
**Entrega:** 2 (14 noviembre 2025)

---

## 🎯 Descripción

Implementación del **lado cliente** del sistema de biblioteca distribuido:

- **PS (Procesos Solicitantes)**: Clientes REQ que envían solicitudes al GC
- **Experimentos**: Pruebas de carga (4, 6, 10 PS concurrentes)
- **Seguridad**: Validación HMAC, detección de ataques
- **Métricas**: Parser de logs, análisis de TPS y latencias

---

## 🖥️ Máquina del Cliente

| Máquina | Rol | IP | Conecta a | Componentes |
|---------|-----|-----|-----------|-------------|
| **M3 (Diego)** | Clientes | 10.43.102.38 | 10.43.101.220:5555 (GC en M1) | PS + Experimentos + Pruebas Seguridad |

---

## 🚀 Inicio Rápido

### Pre-requisito: Sistema levantado

Asegúrate de que M1 y M2 estén corriendo primero:

```bash
# Verificar conectividad desde M3
nc -vz 10.43.101.220 5555  # Debe decir "succeeded"
```

Si falla, ver **[INICIO_RAPIDO.md](./INICIO_RAPIDO.md)** → Troubleshooting

---

### Opción 1: Experimentos Automáticos (Recomendado)

```bash
cd ~/biblioteca-clientes

# Ejecutar 3 escenarios (4, 6, 10 PS)
bash scripts/run_experiments.sh

# Ver resultados
ls -lh experimentos/
cat experimentos/experimento_carga.md
```

---

### Opción 2: Carga Manual

```bash
cd ~/biblioteca-clientes

# Generar solicitudes
python3 ps/gen_solicitudes.py --n 100 --mix 50:50:0 --seed 42

# Enviar al GC
python3 ps/ps.py

# Ver métricas
grep -c 'status=OK' ps_logs.txt
python3 ps/log_parser.py --log ps_logs.txt
```

---

### Opción 3: Multi-PS Concurrentes

```bash
cd ~/biblioteca-clientes

# Lanzar 10 PS en paralelo
python3 pruebas/multi_ps.py --num-ps 10 --requests-per-ps 20 --mode concurrent

# Ver consolidado
cat multi_ps_logs/ps_logs_consolidado.txt
python3 ps/log_parser.py --log multi_ps_logs/ps_logs_consolidado.txt
```

---

## 📁 Estructura

```
biblioteca-clientes/
├── ps/                   # Proceso Solicitante
│   ├── ps.py            # Cliente REQ con reintentos
│   ├── gen_solicitudes.py  # Generador de solicitudes
│   ├── log_parser.py    # Analiza ps_logs.txt
│   ├── schema.py        # Validación HMAC
│   └── requirements.txt
├── pruebas/              # Tests y experimentos
│   ├── multi_ps.py      # Lanzador de múltiples PS
│   ├── consolidar_metricas.py
│   ├── test_seguridad.py
│   ├── test_injection.py
│   ├── test_corrupt.py
│   ├── test_replay.py
│   └── test_flood.py
├── scripts/             # Scripts de automatización
│   ├── start_clients.sh     # Carga básica
│   └── run_experiments.sh   # Experimentos 4/6/10 PS
├── .env.example         # Plantilla configuración
├── README.md           # Este archivo
├── INICIO_RAPIDO.md    # Guía de inicio rápido
└── PASO_A_PASO_MULTI_MAQUINA.md  # Guía detallada 3 PCs
```

---

## ⚙️ Configuración

### Variables Clave (.env)

```bash
# Dirección del GC (M1)
GC_ADDR=tcp://10.43.101.220:5555

# Timeouts y reintentos
PS_TIMEOUT=2.0
PS_BACKOFF=0.5,1,2,4

# (Opcional) Clave HMAC
SECRET_KEY=tu_clave_secreta
```

---

## 🧪 Pruebas de Seguridad

### Suite completa

```bash
cd ~/biblioteca-clientes/pruebas
python3 test_seguridad.py --skip-slow
```

### Pruebas individuales

```bash
# Inyección de datos
python3 test_injection.py

# Datos corruptos
python3 test_corrupt.py

# Replay attack
python3 test_replay.py

# Flood (DoS)
python3 test_flood.py
```

**Ver resultados:** `pruebas/reporte_*.json`

---

## 📊 Análisis de Métricas

### Generar métricas de un log

```bash
python3 ps/log_parser.py --log ps_logs.txt --csv logs/metricas.csv
```

### Consolidar múltiples experimentos

```bash
cd experimentos
python3 ../pruebas/consolidar_metricas.py --dir . --output informe_final --formato all
ls -lh informe_final.*
```

**Formatos generados:**
- `informe_final.csv` - Tabla de métricas
- `informe_final.json` - Datos estructurados
- `informe_final.md` - Reporte legible

---

## 🔍 Verificación

### Ver logs generados

```bash
# Último log de PS
tail -n20 ps_logs.txt

# Logs de multi-PS
ls -lh multi_ps_logs/

# Métricas de experimentos
cat experimentos/experimento_carga.md
```

### Limpiar archivos generados

```bash
rm -rf logs/ multi_ps_logs/ experimentos/
rm -f solicitudes*.bin ps_logs.txt
```

**Nota:** Estos archivos están en `.gitignore` y no se trackean.

---

## 🆚 Cambios desde Entrega 1

| Aspecto | Entrega 1 | Entrega 2 |
|---------|-----------|-----------|
| **PS** | 1 a la vez manual | Múltiples (hasta 10) concurrentes |
| **Experimentos** | Manual | Automatizado (`run_experiments.sh`) |
| **Métricas** | ❌ No | ✅ Parser + CSV + consolidación |
| **Seguridad** | ❌ Básica | ✅ Suite completa (injection, replay, flood) |
| **Logs** | Pantalla | Archivos separados |
| **Consolidación** | ❌ No | ✅ Multi-PS logs consolidados |

---

## 📈 Métricas Esperadas

### Escenario: Carga Baja (4 PS)

| Métrica | Valor |
|---------|-------|
| Latencia media | 0.12-0.18 s |
| TPS | 22-28 req/s |
| OK% | 95%+ |

### Escenario: Carga Media (6 PS)

| Métrica | Valor |
|---------|-------|
| Latencia media | 0.13-0.20 s |
| TPS | 30-38 req/s |
| OK% | 95%+ |

### Escenario: Carga Alta (10 PS)

| Métrica | Valor |
|---------|-------|
| Latencia media | 0.15-0.24 s |
| TPS | 44-55 req/s |
| OK% | 93%+ |

---

## 📚 Documentación Completa

| Archivo | Descripción |
|---------|-------------|
| **[INICIO_RAPIDO.md](./INICIO_RAPIDO.md)** | Guía de inicio (automático y manual) |
| **[PASO_A_PASO_MULTI_MAQUINA.md](./PASO_A_PASO_MULTI_MAQUINA.md)** | Demo completa en 3 PCs |
| `README.md` | Este archivo |
| `ps/README.md` | Detalles del Proceso Solicitante |

---

## 🔗 Repositorio Relacionado

**Lado Sistema:** https://github.com/SistemasDistribuidos2530/biblioteca-sistema

---

## 📞 Contacto

- Thomas Arévalo - M1 (10.43.101.220) - Sistema
- Santiago Mesa - M2 (10.43.102.248) - Sistema
- Diego Castrillón - M3 (10.43.102.38) - Clientes

---

**Última actualización:** 14 noviembre 2025

