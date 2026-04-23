#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAT El Tarra – Programador de tareas
Ejecuta el ciclo de extracción cada 15 minutos (RF01: ≤ 15 min).

Uso:
  python src/scheduler.py            # Bucle infinito (producción)
  python src/scheduler.py --once     # Una sola ejecución (prueba)

Autores: Walter A. Toscano Delgado / Yeferson A. Fernández Moreno
UNAD – Ingeniería de Sistemas – 2026
"""

import sys
import time
import logging
import threading
from datetime import datetime
from pathlib import Path

# Asegurar que src/ esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from filtro import ciclo_extraccion, cargar_o_generar_demo, inicializar_db

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
INTERVALO_SEGUNDOS = 15 * 60  # 15 minutos = 900 segundos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | [SCHEDULER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SAT_Scheduler")


# ─────────────────────────────────────────────
# TAREA PROGRAMADA
# ─────────────────────────────────────────────
def ejecutar_con_retry(intentos: int = 3) -> None:
    """Ejecuta el ciclo con reintentos en caso de fallo."""
    for intento in range(1, intentos + 1):
        try:
            logger.info("Ejecutando ciclo de extracción (intento %d/%d)...", intento, intentos)
            ciclo_extraccion()
            logger.info("Ciclo completado exitosamente.")
            return
        except Exception as exc:
            logger.error("Error en ciclo (intento %d): %s", intento, exc)
            if intento < intentos:
                time.sleep(30)  # Espera 30s antes del reintento
    logger.critical("Todos los reintentos fallaron en este ciclo.")


def loop_continuo() -> None:
    """Bucle infinito: ejecuta ciclo cada INTERVALO_SEGUNDOS."""
    logger.info("SAT El Tarra – Scheduler iniciado")
    logger.info("Intervalo de extracción: %d segundos (%.0f min)", 
                INTERVALO_SEGUNDOS, INTERVALO_SEGUNDOS / 60)

    # Inicializar con demo si no hay datos
    cargar_o_generar_demo()

    # Primera ejecución inmediata
    ejecutar_con_retry()

    while True:
        proxima = datetime.now()
        logger.info("Próxima extracción en %d minutos.", INTERVALO_SEGUNDOS // 60)
        time.sleep(INTERVALO_SEGUNDOS)
        ejecutar_con_retry()


# ─────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if "--once" in sys.argv:
        logger.info("Modo: ejecución única")
        cargar_o_generar_demo()
        ejecutar_con_retry()
    else:
        loop_continuo()
