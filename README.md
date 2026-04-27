# SAT El Tarra 🛡️
### Sistema Automatizado de Monitoreo y Centralización de Alertas de Movilidad y Seguridad

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-green)](https://flask.palletsprojects.com)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow)](LICENSE)
[![UNAD](https://img.shields.io/badge/UNAD-Ingeniería%20de%20Sistemas-blue)](https://unad.edu.co)

---

## ¿Qué es SAT El Tarra?

SAT El Tarra es un sistema de alerta temprana de código abierto diseñado para el municipio de **El Tarra, Norte de Santander (Colombia)**, que centraliza, filtra y presenta alertas de movilidad y seguridad vial extrayendo datos en tiempo real de fuentes oficiales y estables (como **INVÍAS Noticias Viales**, la **Gobernación de Norte de Santander** y **Google News**).

**Problema que resuelve:** Los habitantes de El Tarra no tienen acceso centralizado a información veraz y oportuna sobre el estado de las vías y el orden público. Dependen de grupos de WhatsApp con información fragmentada.

**Solución:** Web Scraping automatizado + Filtrado inteligente + Interfaz dual (Alertas/Noticias) optimizada para redes 3G, con carga inferior a 5 segundos y peso de página inferior a 50 KB.

---

## Arquitectura del sistema (Versión 4.2)

```
CAPA 1 – Extracción    │ INVÍAS · Gobernación · Google News (RSS)
(Requests/BS4)         │ → búsqueda avanzada (El Tarra + Catatumbo)
                        │
CAPA 2 – Procesamiento │ filtro.py → Deduplicación SHA-1
(Python 3.12)          │ → Lógica de expiración inteligente (7 vs 30 días)
                        │ → Clasificador semántico Alertas vs Noticias
                        │
CAPA 3 – Persistencia  │ alertas_activas.json (Caché de baja latencia)
(JSON + SQLite)        │ historico.db (SQLite, registro permanente)
                        │
CAPA 4 – Presentación  │ Flask + HTML/CSS puro (Optimizado 3G)
(Flask 3.1)            │ /alertas (Viales) · /noticias (Orden Público)
                        │
CAPA 5 – Usuarios      │ Campesinos · Transportadores · Habitantes
(Navegador básico)     │ Interfaz en hora local Colombia (UTC-5)
```

---

## Nuevas Funcionalidades (Abril 2026)

*   **Pestañas Separadas:** Interfaz dividida en "Alertas Viales" (movilidad, accidentes) y "Noticias Catatumbo" (orden público, seguridad).
*   **Expiración Inteligente:** Las alertas de mantenimiento y seguridad crítica se mantienen por **30 días**, mientras que alertas menores caducan a los **7 días**.
*   **Búsqueda Ampliada:** El bot ahora rastrea información de toda la región del **Catatumbo** y términos de seguridad (ataques, drones, enfrentamientos).
*   **Hora Local:** Toda la interfaz muestra la "Última revisión del sistema" en hora de Colombia (UTC-5).

---

## Palabras clave de filtrado (RF02/RF03)

| Categoría | Palabras clave principales |
|---|---|
| **Movilidad** | bloqueo, cierre vial, mantenimiento, pavimentación, obras, arreglo, paro... |
| **Seguridad** | ataque, drones, atentado, enfrentamiento, combate, orden público, grupos armados... |
| **Emergencia** | derrumbe, deslizamiento, inundación, lluvias, creciente río catatumbo... |
| **Accidente** | accidente, volcamiento, colisión, choque, heridos... |

---

## Instalación local

```bash
# 1. Clonar el repositorio
git clone https://github.com/ALECRAFT-BOT/ProyectoDeGrado-SistemaDeAlertas.git
cd ProyectoDeGrado-SistemaDeAlertas

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar Servidor Web
python src/app.py

# 5. Ejecutar Programador (Scheduler) en otra terminal
python src/scheduler.py
```

---

## Requerimientos funcionales y no funcionales

| ID | Descripción | Estado |
|---|---|---|
| RF01 | Extracción automática ≤ 15 min | ✅ |
| RF02 | Filtrado inteligente por palabras clave | ✅ |
| RF03 | Clasificación Alertas vs Noticias | ✅ |
| RF06 | Log de métricas y auditoría | ✅ |
| RNF01 | Carga < 5 s en redes 3G | ✅ |
| RNF02 | Peso de página < 50 KB | ✅ |
| RNF03 | Precisión de filtrado ≥ 85% | ✅ |

---

## Licencia

MIT License – Proyecto de grado UNAD 2026. Walter Toscano & Yeferson Fernández.
ales de Colombia y América Latina.

---

## Alineación con ODS y política pública

- **ODS 11:** Ciudades y Comunidades Sostenibles
- **Agenda Colombia Digital 2022-2026** (MinTIC, 2023)
- **CONPES 3975 de 2019** – Transformación Digital
- **Ley 1712 de 2014** – Transparencia y acceso a información pública
