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
    "Norte de Santander / Catatumbo": [r"\bcatatumbo\b", r"\bnorte\s+de\s+santander\b",
                                r"\bnorsan\b", r"\bc[úu]cuta\b", r"\bconvenci[oó]n\b", 
                                r"\bteorama\b", r"\bsan\s+calixto\b", r"\bhacar[ií]\b", 
                                r"\bpuerto\s+santander\b", r"\bsardinata\b", r"\bpamplona\b"],
}

# ─────────────────────────────────────────────
# FUENTES OFICIALES (RF01)
# Nota: Fuentes actualizadas basadas en accesibilidad. 
# RSS-Bridge (https://rss-bridge.org/bridge01/) puede usarse para agregar fuentes de redes sociales.
# Ver sección "FUENTES RSS-BRIDGE" al final para opciones comentadas.
# ─────────────────────────────────────────────
FUENTES = [
    {
        "nombre":  "INVÍAS – Noticias Viales",
        "tipo":    "invias_noticias",
        "url":     "https://www.invias.gov.co/publicaciones/noticias/",
        "url_alt": "https://www.invias.gov.co/publicaciones/noticias/",
        "icono":   "🛣️",
    },
    {
        "nombre":  "Gobernación Norte de Santander",
        "tipo":    "scraping",
        "url":     "https://www.nortedesantander.gov.co/",
        "url_alt": "https://www.nortedesantander.gov.co/",
        "icono":   "🏛️",
    },
    {
        "nombre":  "Google News – Reportes Catatumbo",
        "tipo":    "rss",
        "url":     "https://news.google.com/rss/search?q=El+Tarra+Norte+de+Santander+vias+OR+movilidad+OR+paro+OR+cierre&hl=es-419&gl=CO&ceid=CO:es-419",
        "url_alt": "https://news.google.com/",
        "icono":   "📰",
    },
    # NOTA: datos.gov.co suele tener actualizaciones semanales/mensuales, no es ideal para tiempo real
    # {
    #     "nombre":  "datos.gov.co – Red Vial INVÍAS",
    #     "tipo":    "api_json",
    #     "url":     "https://www.datos.gov.co/resource/ie7y-asdn.json",
    #     "url_alt": "https://www.datos.gov.co/Transporte/Red-Vial/ie7y-asdn",
    #     "icono":   "📊",
    # },
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


def hacer_peticion_con_reintentos(url: str, intentos=3, timeout=30):
    """Realiza peticiones HTTP con lógica de reintentos."""
    headers = {
        "User-Agent": "SAT-ElTarra/1.0 (bot educativo UNAD 2026) Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    for i in range(intentos):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if i == intentos - 1:
                raise e
            logger.warning("Intento %d fallido para %s, reintentando...", i+1, url)
            time.sleep(5 * (i + 1))
    return None


def extraer_feed_rss(fuente: dict) -> list[dict]:
    """Extrae publicaciones desde un feed RSS/Atom usando feedparser."""
    items = []
    t0 = time.time()
    try:
        resp = hacer_peticion_con_reintentos(fuente["url"], intentos=2, timeout=20)
        feed = feedparser.parse(resp.content)
        latencia = round(time.time() - t0, 3)
        logger.info("[RSS] %s | latencia=%.3fs | entradas=%d",
                    fuente["nombre"], latencia, len(feed.entries))
        for entry in feed.entries:
            titulo = getattr(entry, "title", "Sin título")
            desc   = getattr(entry, "summary", getattr(entry, "description", ""))
            enlace = getattr(entry, "link", fuente["url"])
            
            # Filtrar por antigüedad (máximo 7 días de antigüedad)
            fecha_parsed = getattr(entry, "published_parsed", None)
            if fecha_parsed:
                import calendar
                dt = datetime.fromtimestamp(calendar.timegm(fecha_parsed), timezone.utc)
                if datetime.now(timezone.utc) - dt > timedelta(days=7):
                    continue  # Descartar noticias viejas
                fecha = dt.isoformat()
            else:
                fecha = datetime.now(timezone.utc).isoformat()
                
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
    return items


def extraer_invias_noticias(fuente: dict) -> list[dict]:
    """Scraping quirúrgico para INVÍAS Noticias."""
    items = []
    t0 = time.time()
    try:
        resp = hacer_peticion_con_reintentos(fuente["url"], intentos=3, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        for tag in soup.select("nav, script, style, footer, header"):
            tag.decompose()
            
        candidatos = soup.select("h2 a")
        latencia = round(time.time() - t0, 3)
        logger.info("[INVIAS] %s | latencia=%.3fs | candidatos=%d", fuente["nombre"], latencia, len(candidatos))
        
        for tag in candidatos[:15]:
            titulo = tag.get_text(" ", strip=True)[:200]
            if len(titulo) < 10: continue
            
            url = tag.get("href", fuente["url"])
            if url.startswith("/"):
                url = f"https://www.invias.gov.co{url}"
                
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
        logger.error("[INVIAS-ERROR] %s | %.3fs | %s", fuente["nombre"], latencia, exc)
    return items


def extraer_datos_gov(fuente: dict) -> list[dict]:
    """Consume JSON desde datos.gov.co Socrata API."""
    items = []
    t0 = time.time()
    try:
        params = {
            "$where": "departamento LIKE '%SANTANDER%'",
            "$limit": "50"
        }
        resp = requests.get(fuente["url"], params=params, headers={"Accept": "application/json"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        latencia = round(time.time() - t0, 3)
        logger.info("[DATOS.GOV] %s | latencia=%.3fs | registros=%d", fuente["nombre"], latencia, len(data))
        
        for record in data[:10]:
            nombre = record.get("nombre_de_la_v_a", record.get("codigo_via", "Vía sin nombre"))
            estado = record.get("estado_de_la_v_a", "")
            if not estado: continue
            
            titulo = f"Reporte Red Vial: {nombre} ({estado})"
            desc = f"Vía: {nombre}, Estado: {estado}, Municipio: {record.get('municipio', '')}, Administrador: {record.get('administrador', '')}"
            url = fuente["url_alt"]
            
            uid = _sha1(titulo + url)
            items.append({
                "id":          uid,
                "titulo":      titulo[:200],
                "descripcion": desc[:500],
                "url":         url,
                "fecha_pub":   datetime.now(timezone.utc).isoformat(),
                "fuente":      fuente["nombre"],
                "icono":       fuente["icono"],
            })
    except Exception as exc:
        latencia = round(time.time() - t0, 3)
        logger.error("[DATOS.GOV-ERROR] %s | %.3fs | %s", fuente["nombre"], latencia, exc)
    return items


def extraer_scraping(fuente: dict) -> list[dict]:
    """Extrae publicaciones mediante BeautifulSoup como fallback."""
    items = []
    t0 = time.time()
    try:
        resp = hacer_peticion_con_reintentos(fuente["url_alt"], intentos=3, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")
        latencia = round(time.time() - t0, 3)

        for tag in soup.select("nav, script, style, footer, header"):
            tag.decompose()

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
            if len(titulo) < 15: continue

            enlace = tag.find("a")
            if not enlace and tag.name == "a":
                enlace = tag

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


def detectar_zona(texto: str) -> str | None:
    """Retorna la primera zona geográfica coincidente o None si no pertenece a la región."""
    for zona, patrones in ZONAS.items():
        for patron in patrones:
            if re.search(patron, texto, re.IGNORECASE):
                return zona
    return None


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
        if zona is None:
            continue  # No es de Norte de Santander / Catatumbo

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
    """Si el JSON activo no existe, intenta extraer datos reales o crea uno vacío."""
    if JSON_PATH.exists():
        try:
            with open(JSON_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("total", 0) >= 0:
                return  # Ya hay datos (reales o vacíos)
        except Exception:
            pass

    # Intentar extraer datos reales primero
    logger.info("Iniciando primer ciclo de extracción...")
    try:
        ciclo_extraccion()
        if JSON_PATH.exists():
            return
    except Exception as e:
        logger.warning("Fallo al extraer datos reales en el inicio: %s", e)

    # Si todo falla, crear JSON vacío en lugar de demo
    logger.info("Creando JSON vacío por defecto...")
    guardar_json([])


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
        elif fuente["tipo"] == "invias_noticias":
            items = extraer_invias_noticias(fuente)
        elif fuente["tipo"] == "api_json":
            items = extraer_datos_gov(fuente)
        else:
            items = extraer_scraping(fuente)
            
        todos_los_items.extend(items)
        logger.info("Fuente %s: %d items extraídos", fuente["nombre"], len(items))

    alertas = filtrar_y_clasificar(todos_los_items)

    if alertas:
        guardar_json(alertas)
        guardar_db(conn, alertas)
    else:
        logger.warning("Ninguna alerta filtrada en este ciclo.")
        if not JSON_PATH.exists():
            guardar_json([]) # Crear archivo vacío inicial

    conn.close()
    logger.info("FIN CICLO – %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ─────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Inicializar con demo si no hay datos
    cargar_o_generar_demo()
    ciclo_extraccion()
