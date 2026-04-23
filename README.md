# SAT El Tarra 🛡️
### Sistema Automatizado de Monitoreo y Centralización de Alertas de Movilidad y Seguridad

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-green)](https://flask.palletsprojects.com)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow)](LICENSE)
[![UNAD](https://img.shields.io/badge/UNAD-Ingeniería%20de%20Sistemas-blue)](https://unad.edu.co)

---

## ¿Qué es SAT El Tarra?

SAT El Tarra es un sistema de alerta temprana de código abierto diseñado para el municipio de **El Tarra, Norte de Santander (Colombia)**, que centraliza, filtra y presenta alertas de movilidad y seguridad vial desde fuentes oficiales (INVÍAS, Policía Nacional, Alcaldía de El Tarra e IDEAM).

**Problema que resuelve:** Los habitantes de El Tarra no tienen acceso centralizado a información veraz y oportuna sobre el estado de las vías. Dependen de grupos de WhatsApp y Facebook con información fragmentada e inverificable.

**Solución:** Web Scraping automatizado + filtrado por palabras clave en Python + interfaz web minimalista optimizada para redes 3G, con carga inferior a 5 segundos y peso de página inferior a 50 KB.

---

## Autores

- **Walter Alejandro Toscano Delgado** – C.C. 1004821628 – CEAD Ocaña
- **Yeferson Andrés Fernández Moreno** – C.C. 1094285938 – CEAD Pamplona

**Tutor:** Daniel Andrés Guzmán Arévalo  
**Curso:** Proyecto de Grado – 202016907 – UNAD  
**Metodología:** CDIO (Concebir, Diseñar, Implementar y Operar) – Fase 4  
**Año:** 2026

---

## Arquitectura del sistema

```
CAPA 1 – Extracción    │ INVÍAS · Policía · Alcaldía · IDEAM
(RSS-Bridge/Requests)  │ → feeds JSON cada 15 min (cron/scheduler)
                        │
CAPA 2 – Procesamiento │ filtro.py → feedparser → SHA-1 dedup
(Python 3.12)          │ → regex keywords → clasificador zona/tipo
                        │
CAPA 3 – Persistencia  │ alertas_activas.json (48 h, baja latencia)
(JSON + SQLite)        │ historico.db (SQLite, registro permanente)
                        │
CAPA 4 – Presentación  │ Flask + HTML/CSS puro (sin frameworks)
(Flask 3.1)            │ /alertas · /historial · /metricas · /api/alertas
                        │
CAPA 5 – Usuarios      │ Campesinos · Transportadores · Habitantes
(Navegador básico)     │ Dispositivos 2G/3G
```

---

## Requisitos técnicos

- Python 3.12+
- pip
- ~50 MB de disco

---

## Instalación local

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/sat-eltarra.git
cd sat-eltarra

# 2. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar el servidor web
python src/app.py

# 5. En otra terminal, ejecutar el scheduler (extracción cada 15 min)
python src/scheduler.py

# 6. Abrir en navegador
# http://localhost:5000
```

---

## Estructura del proyecto

```
sat-eltarra/
├── src/
│   ├── app.py          # Servidor Flask (Capa 4 presentación)
│   ├── filtro.py       # Extracción + filtrado + persistencia (Capas 1-3)
│   └── scheduler.py    # Programador de ciclos cada 15 min
├── templates/
│   ├── alertas.html    # Página principal
│   ├── historial.html  # Historial SQLite
│   └── metricas.html   # Métricas técnicas
├── static/
│   └── css/
│       └── main.css    # Estilos HTML/CSS puro (sin frameworks)
├── data/               # generado en ejecución
│   ├── alertas_activas.json
│   └── historico.db
├── logs/               # generado en ejecución
│   └── metricas.log
├── requirements.txt
├── Procfile            # Railway.app / Render.com
├── railway.json        # Config Railway
├── render.yaml         # Config Render
├── runtime.txt         # Versión Python
└── README.md
```

---

## Palabras clave de filtrado (RF02)

| Categoría | Palabras clave |
|---|---|
| Movilidad | bloqueo, cierre vial, paro, retén, contingencia, paso restringido... |
| Emergencia Ambiental | derrumbe, deslizamiento, inundación, desbordamiento, creciente... |
| Seguridad | orden público, grupos armados, operación, alerta roja, toque de queda... |
| Accidente | accidente, volcamiento, colisión, víctima, herido... |

---

## Requerimientos funcionales y no funcionales

| ID | Descripción | Estado |
|---|---|---|
| RF01 | Extracción automática ≤ 15 min | ✅ |
| RF02 | Filtrado por palabras clave | ✅ |
| RF03 | Clasificación por zona y categoría | ✅ |
| RF04 | Orden cronológico descendente | ✅ |
| RF05 | Accesible sin instalación adicional | ✅ |
| RF06 | Log de métricas por ciclo | ✅ |
| RNF01 | Carga < 5 s en 3G | ✅ |
| RNF02 | Peso de página < 50 KB | ✅ |
| RNF03 | Precisión filtrado ≥ 85% | ✅ |
| RNF04 | Software 100% libre | ✅ |
| RNF05 | Plan gratuito Railway/Render | ✅ |
| RNF06 | Repositorio GitHub público | ✅ |

---

## Licencia

MIT License – Código abierto, replicable en otros municipios del Catatumbo y contextos rurales de Colombia y América Latina.

---

## Alineación con ODS y política pública

- **ODS 11:** Ciudades y Comunidades Sostenibles
- **Agenda Colombia Digital 2022-2026** (MinTIC, 2023)
- **CONPES 3975 de 2019** – Transformación Digital
- **Ley 1712 de 2014** – Transparencia y acceso a información pública
