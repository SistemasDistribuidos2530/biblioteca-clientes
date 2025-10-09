# SistemasDistribuidos - Proceso Solicitante (PS)

Proyecto académico en Python para la materia **Sistemas Distribuidos**.  
Simula el comportamiento de un **Proceso Solicitante (PS)** que genera, firma y envía solicitudes a un **Gestor de Carga (GC)** mediante **ZeroMQ**, midiendo tiempos, fallos y rendimiento.

---

## 📦 Descripción general

El sistema implementa el flujo completo de pruebas de carga y tolerancia a fallos del **PS**:
1. **Generación de solicitudes** (`gen_solicitudes.py`)  
   Crea un archivo binario con solicitudes firmadas digitalmente.
2. **Envío al GC** (`ps.py`)  
   Lee el binario, recalcula firmas HMAC, reintenta con backoff y mide tiempos.
3. **Análisis de resultados** (`log_parser.py`)  
   Procesa los logs y calcula métricas como TPS, latencia promedio, reintentos, etc.
4. **Simulación de GC** (`make mock-gc`)  
   Permite probar localmente el envío sin depender de un servidor real.

---

## 🚀 Instalación y ejecución

### 1. Clonar y entrar al proyecto
```bash
git clone <repo-url>
cd SistemasDistribuidos
