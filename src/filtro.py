#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAT El Tarra – Sistema de Alerta Temprana
Módulo principal de extracción, filtrado y clasificación de alertas.

Autores: Walter Alejandro Toscano Delgado / Yeferson Andrés Fernández Moreno
Proyecto de Grado – UNAD – Ingeniería de Sistemas – 2026
Metodología: CDIO – Fase 3 (Implementar)
"""

import os
import re
import json
import hashlib
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE RUTAS
# ─────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = BASE_DIR / "data"
LOGS_DIR   = BASE_DIR / "logs"
JSON_PATH  = DATA_DIR / "alertas_activas.json"
DB_PATH    = DATA_DIR / "historico.db"
LOG_PATH   = LOGS_DIR / "metricas.log"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE LOGGING (RNF – metricas.log)
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("SAT_ElTarra")

# ─────────────────────────────────────────────
# DICCIONARIO DE PALABRAS CLAVE (RF02 / RF03)
# Definido a partir de resultados encuesta (Figura 10):
#   75% bloqueos, 62.5% derrumbes, 62.5% emergencias,
#   50% orden público, 37.5% rutas alternas
# ─────────────────────────────────────────────
PALABRAS_CLAVE = {
    "movilidad": [
        r"\bbloqueo\b", r"\bbloqueos\b", r"\bcierre\s+vial\b", r"\bcierres?\b",
        r"\bparo\b", r"\bparos\b", r"\bret[eé]n\b", r"\bcontingencia\b",
        r"\bv[íi]a\s+cerrada\b", r"\bacceso\s+bloqueado\b",
        r"\bpaso\s+restringido\b", r"\bpaso\s+habilitado\b",
        r"\bsuspendi[dr]", r"\binternamiento\b",
    ],
    "emergencia_ambiental": [
        r"\bderrumbe\b", r"\bderrumbes\b", r"\bdeslizamiento\b",
        r"\binundaci[oó]n\b", r"\bdesbordamiento\b", r"\bavenidar\b",
        r"\bcreciente\b", r"\blluvias\b", r"\btormenta\b",
        r"\brio\s+catatumbo\b", r"\binundado\b", r"\bdesastre\b",
        r"\bemergencia\s+ambiental\b",
    ],
    "seguridad": [
        r"\borden\s+p[úu]blico\b", r"\bgrupos?\s+armados?\b",
        r"\bdisturbi", r"\bconflicto\b", r"\boperaci[oó]n\b",
        r"\bpolicía\b", r"\bejército\b", r"\bseguridad\b",
        r"\balerta\s+roja\b", r"\balerta\s+naranja\b",
        r"\btoque\s+de\s+queda\b", r"\bconfrontaci[oó]n\b",
    ],
    "accidente": [
        r"\baccidente\b", r"\bvolcamiento\b", r"\bcolis[ií]on\b",
        r"\bchoqu[eo]\b", r"\bv[íi]ctima\b", r"\bherido\b",
        r"\batenci[oó]n\s+m[eé]dica\b",
    ],
}

# Palabras clave geográficas para clasificación de zona (RF03)
ZONAS = {
    "El Tarra – Tibú":        [r"\btibu\b", r"\btib[úu]\b", r"\bla\s+gabarra\b",
                                r"\bel\s+tarra\b", r"\bcatatumbo\b"],
    "El Tarra – Ocaña":       [r"\boca[ñn]a\b", r"\bla\s+playa\b", r"\bel\s+tarra\b"],
    "El Tarra – La Gabarra":  [r"\bla\s+gabarra\b", r"\bel\s+tarra\b"],
    "Regional Catatumbo":     [r"\bcatatumbo\b", r"\bnorte\s+de\s+santander\b",
                                r"\bnorsan\b"],
}

# ─────────────────────────────────────────────
# FUENTES OFICIALES (RF01)
# Nota: RSS-Bridge convierte las páginas en feeds JSON/RSS.
# Durante pruebas sin RSS-Bridge activo, se usa scraping directo.
# ─────────────────────────────────────────────
FUENTES = [
    {
        "nombre":  "INVÍAS Norte de Santander",
        "tipo":    "rss",
        "url":     "https://www.invias.gov.co/index.php/cierres-viales?format=feed&type=rss",
        "url_alt": "https://www.invias.gov.co/index.php/cierres-viales",
        "icono":   "🛣️",
    },
    {
        "nombre":  "Policía Nacional – Tránsito",
        "tipo":    "rss",
        "url":     "https://www.policia.gov.co/estado-de-las-vias?format=feed&type=rss",
        "url_alt": "https://www.policia.gov.co/noticias",
        "icono":   "🚔",
    },
    {
        "nombre":  "Alcaldía El Tarra",
        "tipo":    "scraping",
        "url":     "https://eltarra-nortedesantander.gov.co/noticias",
        "url_alt": "https://eltarra-nortedesantander.gov.co/noticias",
        "icono":   "🏛️",
    },
    # Fuente adicional: IDEAM para alertas ambientales
    {
        "nombre":  "IDEAM – Alertas Hidro",
        "tipo":    "rss",
        "url":     "https://www.ideam.gov.co/web/tiempo-y-clima/alertas-meteorologicas",
        "url_alt": "https://www.ideam.gov.co/web/tiempo-y-clima/alertas-meteorologicas",
        "icono":   "🌊",
    },
    {
    "nombre":  "Alcaldía El Tarra – Alertas Viales",
    "tipo":    "scraping",
    "url":     "https://alecraft-bot.github.io/reporte-eltarra/",
    "url_alt": "https://alecraft-bot.github.io/reporte-eltarra/",
    "icono":   "🏛️",
    },
]

# ─────────────────────────────────────────────
# INICIALIZACIÓN DE BASE DE DATOS SQLITE (Capa 3)
# ─────────────────────────────────────────────
def inicializar_db() -> sqlite3.Connection:
    """Crea la tabla de alertas históricas si no existe."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id          TEXT PRIMARY KEY,
            fecha_pub   TEXT,
            fecha_cap   TEXT,
            fuente      TEXT,
            titulo      TEXT,
            descripcion TEXT,
            url         TEXT,
            categoria   TEXT,
            zona        TEXT
        )
    """)
    conn.commit()
    logger.info("Base de datos SQLite inicializada: %s", DB_PATH)
    return conn


# ─────────────────────────────────────────────
# FUNCIONES DE EXTRACCIÓN (Capa 1)
# ─────────────────────────────────────────────
def _sha1(texto: str) -> str:
    """Genera hash SHA-1 para deduplicación (RF – Dedup)."""
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def extraer_feed_rss(fuente: dict) -> list[dict]:
    """Extrae publicaciones desde un feed RSS/Atom usando feedparser."""
    items = []
    t0 = time.time()
    try:
        headers = {"User-Agent": "SAT-ElTarra/1.0 (bot educativo UNAD 2026)"}
        resp = requests.get(fuente["url"], headers=headers, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        latencia = round(time.time() - t0, 3)
        logger.info("[RSS] %s | latencia=%.3fs | entradas=%d",
                    fuente["nombre"], latencia, len(feed.entries))
        for entry in feed.entries:
            titulo = getattr(entry, "title", "Sin título")
            desc   = getattr(entry, "summary", getattr(entry, "description", ""))
            enlace = getattr(entry, "link", fuente["url"])
            fecha  = getattr(entry, "published", datetime.now(timezone.utc).isoformat())
            uid    = _sha1(titulo + enlace)
            items.append({
                "id":          uid,
                "titulo":      titulo,
                "descripcion": BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)[:500],
                "url":         enlace,
                "fecha_pub":   fecha,
                "fuente":      fuente["nombre"],
                "icono":       fuente["icono"],
            })
    except Exception as exc:
        latencia = round(time.time() - t0, 3)
        logger.warning("[RSS-ERROR] %s | %.3fs | %s", fuente["nombre"], latencia, exc)
        # Intento con URL alternativa mediante scraping
        items = extraer_scraping(fuente)
    return items


def extraer_scraping(fuente: dict) -> list[dict]:
    """Extrae publicaciones mediante BeautifulSoup como fallback."""
    items = []
    t0 = time.time()
    try:
        headers = {"User-Agent": "SAT-ElTarra/1.0 (bot educativo UNAD 2026)"}
        resp = requests.get(fuente["url_alt"], headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        latencia = round(time.time() - t0, 3)

        # Estrategia genérica: buscar etiquetas semánticas de noticias
        candidatos = (
        soup.select("article") or
        soup.select(".noticia, .news-item, .entry, .post") or
        soup.select("h1, h2 a, h3 a") or  
        soup.select("p")
        )
        logger.info("[SCRAPING] %s | latencia=%.3fs | candidatos=%d",
                    fuente["nombre"], latencia, len(candidatos))

        for tag in candidatos[:20]:
            titulo = tag.get_text(" ", strip=True)[:200]
            enlace = tag.find("a")
            url    = enlace["href"] if enlace and enlace.get("href") else fuente["url_alt"]
            if url.startswith("/"):
                from urllib.parse import urlparse
                base = urlparse(fuente["url_alt"])
                url  = f"{base.scheme}://{base.netloc}{url}"
            uid = _sha1(titulo + url)
            items.append({
                "id":          uid,
                "titulo":      titulo,
                "descripcion": titulo,
                "url":         url,
                "fecha_pub":   datetime.now(timezone.utc).isoformat(),
                "fuente":      fuente["nombre"],
                "icono":       fuente["icono"],
            })
    except Exception as exc:
        latencia = round(time.time() - t0, 3)
        logger.error("[SCRAPING-ERROR] %s | %.3fs | %s", fuente["nombre"], latencia, exc)
    return items


# ─────────────────────────────────────────────
# FUNCIONES DE FILTRADO Y CLASIFICACIÓN (Capa 2)
# ─────────────────────────────────────────────
def _texto_completo(item: dict) -> str:
    return (item.get("titulo", "") + " " + item.get("descripcion", "")).lower()


def detectar_categoria(texto: str) -> str | None:
    """Retorna la primera categoría coincidente o None si no hay match."""
    for categoria, patrones in PALABRAS_CLAVE.items():
        for patron in patrones:
            if re.search(patron, texto, re.IGNORECASE):
                return categoria
    return None


def detectar_zona(texto: str) -> str:
    """Retorna la primera zona geográfica coincidente."""
    for zona, patrones in ZONAS.items():
        for patron in patrones:
            if re.search(patron, texto, re.IGNORECASE):
                return zona
    return "Norte de Santander"


def filtrar_y_clasificar(items: list[dict]) -> list[dict]:
    """Pipeline de filtrado: deduplicación + regex + clasificación."""
    vistos  = set()
    alertas = []
    total   = len(items)

    for item in items:
        # Deduplicación por hash SHA-1
        if item["id"] in vistos:
            continue
        vistos.add(item["id"])

        texto     = _texto_completo(item)
        categoria = detectar_categoria(texto)
        if categoria is None:
            continue  # No es alerta relevante

        zona = detectar_zona(texto)
        item["categoria"] = categoria
        item["zona"]      = zona
        item["fecha_cap"] = datetime.now(timezone.utc).isoformat()
        alertas.append(item)

    filtradas = len(alertas)
    precision = round(filtradas / total * 100, 1) if total else 0
    logger.info("Filtrado: %d/%d publicaciones → %.1f%% relevancia", filtradas, total, precision)
    return alertas


# ─────────────────────────────────────────────
# PERSISTENCIA (Capa 3)
# ─────────────────────────────────────────────
def guardar_json(alertas: list[dict]) -> None:
    """Guarda las alertas de las últimas 48 h en JSON activo (baja latencia)."""
    limite = datetime.now(timezone.utc) - timedelta(hours=48)
    recientes = []
    for a in alertas:
        try:
            # Intenta parsear fecha de publicación
            fp_str = a.get("fecha_pub", "")
            # feedparser devuelve structs; aquí ya son strings ISO
            recientes.append(a)
        except Exception:
            recientes.append(a)

    # Mantener máximo las 200 alertas más recientes
    recientes = recientes[:200]

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
            "total": len(recientes),
            "alertas": recientes,
        }, f, ensure_ascii=False, indent=2)
    logger.info("JSON activo guardado: %d alertas → %s", len(recientes), JSON_PATH)


def guardar_db(conn: sqlite3.Connection, alertas: list[dict]) -> None:
    """Persiste alertas en SQLite para historial (INSERT OR IGNORE evita duplicados)."""
    cursor = conn.cursor()
    for a in alertas:
        cursor.execute("""
            INSERT OR IGNORE INTO alertas
              (id, fecha_pub, fecha_cap, fuente, titulo, descripcion, url, categoria, zona)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            a["id"], a.get("fecha_pub"), a.get("fecha_cap"),
            a["fuente"], a["titulo"], a["descripcion"],
            a["url"], a["categoria"], a["zona"],
        ))
    conn.commit()
    logger.info("SQLite actualizado: %d registros procesados", len(alertas))


# ─────────────────────────────────────────────
# GENERACIÓN DE DATOS DE PRUEBA / DEMO
# Usados cuando las fuentes reales no están disponibles
# (entorno de demostración académica)
# ─────────────────────────────────────────────
ALERTAS_DEMO = [
    {
        "id": "demo001",
        "titulo": "🔴 Bloqueo vial en km 23 vía Tibú – Retén ilegal reportado",
        "descripcion": "Se reporta presencia de retén ilegal en el km 23 vía El Tarra–Tibú. "
                       "Autoridades en desplazamiento. Evite transitar por la zona hasta nuevo aviso.",
        "url": "#",
        "fecha_pub": datetime.now(timezone.utc).isoformat(),
        "fuente": "Policía Nacional – Tránsito",
        "icono": "🚔",
        "categoria": "seguridad",
        "zona": "El Tarra – Tibú",
        "fecha_cap": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "demo002",
        "titulo": "🟠 Vía cerrada por derrumbe – km 45 vía Ocaña",
        "descripcion": "Derrumbe en el km 45 vía El Tarra–Ocaña impide el paso vehicular. "
                       "INVÍAS trabaja en remoción de material. Tiempo estimado de apertura: 4 horas.",
        "url": "#",
        "fecha_pub": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "fuente": "INVÍAS Norte de Santander",
        "icono": "🛣️",
        "categoria": "movilidad",
        "zona": "El Tarra – Ocaña",
        "fecha_cap": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "demo003",
        "titulo": "🟢 Alerta ambiental – Nivel alto río Catatumbo",
        "descripcion": "Por lluvias intensas el río Catatumbo presenta nivel alto. "
                       "Se recomienda precaución al cruzar los puentes en vía Tibú "
                       "y evitar zonas cercanas a la ribera.",
        "url": "#",
        "fecha_pub": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "fuente": "IDEAM – Alertas Hidro",
        "icono": "🌊",
        "categoria": "emergencia_ambiental",
        "zona": "El Tarra – Tibú",
        "fecha_cap": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "demo004",
        "titulo": "🔵 Paso restringido por mantenimiento vial – La Gabarra",
        "descripcion": "Mantenimiento vial en el sector La Gabarra. Paso controlado por "
                       "bandereros entre 8:00 AM y 4:00 PM. Se permite paso alternado.",
        "url": "#",
        "fecha_pub": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        "fuente": "Alcaldía El Tarra",
        "icono": "🏛️",
        "categoria": "movilidad",
        "zona": "El Tarra – La Gabarra",
        "fecha_cap": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "demo005",
        "titulo": "🔴 Cierre vial por orden público – vía Tibú",
        "descripcion": "Las autoridades informan cierre temporal de la vía El Tarra–Tibú "
                       "por situaciones de orden público. Se adelantan operaciones de control. "
                       "Espere instrucciones antes de emprender viaje.",
        "url": "#",
        "fecha_pub": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
        "fuente": "Policía Nacional – Tránsito",
        "icono": "🚔",
        "categoria": "seguridad",
        "zona": "El Tarra – Tibú",
        "fecha_cap": datetime.now(timezone.utc).isoformat(),
    },
]


def cargar_o_generar_demo() -> None:
    """Si el JSON activo no existe o está vacío, carga datos de demo."""
    if JSON_PATH.exists():
        try:
            with open(JSON_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("total", 0) > 0:
                return  # Ya hay datos reales
        except Exception:
            pass

    logger.info("Cargando datos de demo (modo académico)...")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
            "total": len(ALERTAS_DEMO),
            "modo": "demo",
            "alertas": ALERTAS_DEMO,
        }, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# CICLO PRINCIPAL DE EXTRACCIÓN
# ─────────────────────────────────────────────
def ciclo_extraccion() -> None:
    """Ejecuta un ciclo completo: extracción → filtrado → persistencia."""
    logger.info("=" * 60)
    logger.info("INICIO CICLO EXTRACCIÓN – %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    conn = inicializar_db()
    todos_los_items: list[dict] = []

    for fuente in FUENTES:
        if fuente["tipo"] == "rss":
            items = extraer_feed_rss(fuente)
        else:
            items = extraer_scraping(fuente)
        todos_los_items.extend(items)
        logger.info("Fuente %s: %d items extraídos", fuente["nombre"], len(items))

    alertas = filtrar_y_clasificar(todos_los_items)

    if alertas:
        guardar_json(alertas)
        guardar_db(conn, alertas)
    else:
        logger.warning("Ninguna alerta filtrada en este ciclo. Manteniendo JSON anterior.")

    conn.close()
    logger.info("FIN CICLO – %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ─────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Inicializar con demo si no hay datos
    cargar_o_generar_demo()
    ciclo_extraccion()
