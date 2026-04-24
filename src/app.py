#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAT El Tarra – Servidor Web Flask
Capa 4 de presentación: renderiza alertas desde JSON activo y SQLite.

Rutas:
  GET /            → Redirección a /alertas
  GET /alertas     → Página principal con alertas recientes (JSON activo)
  GET /historial   → Consulta histórica SQLite
  GET /api/alertas → JSON puro (para integraciones futuras)
  GET /api/status  → Estado del sistema (métricas)

Autores: Walter A. Toscano Delgado / Yeferson A. Fernández Moreno
UNAD – Ingeniería de Sistemas – 2026
"""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, render_template, jsonify, request, redirect, url_for

# Importar función de demo (absoluto para compatibilidad)
try:
    from .filtro import cargar_o_generar_demo
except ImportError:
    from filtro import cargar_o_generar_demo

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE RUTAS
# ─────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent.parent
DATA_DIR       = BASE_DIR / "data"
LOGS_DIR       = BASE_DIR / "logs"
JSON_PATH      = DATA_DIR / "alertas_activas.json"
DB_PATH        = DATA_DIR / "historico.db"
TEMPLATES_DIR  = BASE_DIR / "templates"
STATIC_DIR     = BASE_DIR / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
)
app.config["JSON_AS_ASCII"] = False


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
ETIQUETAS_CATEGORIA = {
    "movilidad":            ("Movilidad",           "#e65100", "🛣️"),
    "seguridad":            ("Seguridad",            "#b71c1c", "🚔"),
    "emergencia_ambiental": ("Emergencia Ambiental", "#1b5e20", "🌊"),
    "accidente":            ("Accidente",            "#f57f17", "🚑"),
}

def _leer_json() -> dict:
    """Lee el archivo JSON activo; genera demo si no existe."""
    if not JSON_PATH.exists():
        cargar_o_generar_demo()
    try:
        with open(JSON_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"ultima_actualizacion": None, "total": 0, "alertas": [], "modo": "sin_datos"}
    except json.JSONDecodeError:
        return {"ultima_actualizacion": None, "total": 0, "alertas": [], "modo": "error_json"}


def _enriquecer(alertas: list) -> list:
    """Agrega metadatos visuales a cada alerta."""
    for a in alertas:
        cat = a.get("categoria", "movilidad")
        etq = ETIQUETAS_CATEGORIA.get(cat, ("Alerta", "#1a237e", "📢"))
        a["etiqueta_texto"] = etq[0]
        a["etiqueta_color"] = etq[1]
        a["etiqueta_icono"] = etq[2]
        # Formatear fecha
        fp = a.get("fecha_pub", "")
        try:
            dt = datetime.fromisoformat(fp.replace("Z", "+00:00"))
            a["fecha_formateada"] = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            a["fecha_formateada"] = fp[:16] if fp else "—"
    return alertas


def _leer_historial(limit: int = 100, zona: str = None, categoria: str = None) -> list:
    """Consulta historial SQLite con filtros opcionales."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    where_clauses = []
    params = []
    if zona:
        where_clauses.append("zona = ?")
        params.append(zona)
    if categoria:
        where_clauses.append("categoria = ?")
        params.append(categoria)
    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = f"SELECT * FROM alertas {where} ORDER BY fecha_pub DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _leer_log_metricas(lines: int = 50) -> list[str]:
    """Lee las últimas N líneas del log de métricas."""
    log_path = LOGS_DIR / "metricas.log"
    if not log_path.exists():
        return ["(Sin registros de métricas todavía)"]
    try:
        with open(log_path, encoding="utf-8") as f:
            all_lines = f.readlines()
        return [l.rstrip() for l in all_lines[-lines:]]
    except Exception:
        return ["(Error leyendo log)"]


# ─────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("alertas"))


@app.route("/alertas")
def alertas():
    """Página principal – RF04, RNF01, RNF02."""
    zona_filtro = request.args.get("zona", "")
    cat_filtro  = request.args.get("categoria", "")

    data = _leer_json()
    lista = data.get("alertas", [])

    # Filtrado por zona/categoría via query params
    if zona_filtro:
        lista = [a for a in lista if zona_filtro.lower() in a.get("zona", "").lower()]
    if cat_filtro:
        lista = [a for a in lista if a.get("categoria", "") == cat_filtro]

    lista = _enriquecer(lista)

    ultima = data.get("ultima_actualizacion", "")
    try:
        dt = datetime.fromisoformat(ultima.replace("Z", "+00:00"))
        # Convertir a hora local (Colombia UTC-5)
        dt_local = dt.astimezone(timezone(timedelta(hours=-5)))
        ultima_fmt = dt_local.strftime("%d/%m/%Y a las %I:%M %p (Hora Local)")
    except Exception:
        ultima_fmt = ultima or "—"

    zonas_disponibles = [
        "El Tarra – Tibú",
        "El Tarra – Ocaña",
        "El Tarra – La Gabarra",
        "Regional Catatumbo",
    ]

    return render_template(
        "alertas.html",
        alertas=lista,
        total=len(lista),
        ultima_actualizacion=ultima_fmt,
        modo=data.get("modo", "normal"),
        zona_filtro=zona_filtro,
        cat_filtro=cat_filtro,
        zonas=zonas_disponibles,
        categorias=list(ETIQUETAS_CATEGORIA.keys()),
        etiquetas=ETIQUETAS_CATEGORIA,
    )


@app.route("/historial")
def historial():
    """Historial de alertas SQLite – RF03, RF06."""
    zona_filtro = request.args.get("zona", "")
    cat_filtro  = request.args.get("categoria", "")
    alertas_hist = _leer_historial(
        limit=200,
        zona=zona_filtro if zona_filtro else None,
        categoria=cat_filtro if cat_filtro else None,
    )
    alertas_hist = _enriquecer(alertas_hist)
    return render_template(
        "historial.html",
        alertas=alertas_hist,
        total=len(alertas_hist),
        zona_filtro=zona_filtro,
        cat_filtro=cat_filtro,
        categorias=list(ETIQUETAS_CATEGORIA.keys()),
        etiquetas=ETIQUETAS_CATEGORIA,
    )


@app.route("/api/alertas")
def api_alertas():
    """Endpoint JSON para integraciones futuras (RF05)."""
    data = _leer_json()
    return jsonify(data)


@app.route("/api/status")
def api_status():
    """Estado del sistema y métricas básicas."""
    data   = _leer_json()
    lineas = _leer_log_metricas(20)
    hist_count = 0
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        hist_count = conn.execute("SELECT COUNT(*) FROM alertas").fetchone()[0]
        conn.close()
    return jsonify({
        "status":              "ok",
        "timestamp":           datetime.now(timezone.utc).isoformat(),
        "alertas_activas":     data.get("total", 0),
        "alertas_historicas":  hist_count,
        "ultima_actualizacion": data.get("ultima_actualizacion"),
        "ultimas_metricas":    lineas,
    })


@app.route("/metricas")
def metricas():
    """Página de métricas técnicas del sistema (RF06)."""
    lineas  = _leer_log_metricas(100)
    data    = _leer_json()
    hist_count = 0
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        hist_count = conn.execute("SELECT COUNT(*) FROM alertas").fetchone()[0]
        conn.close()
    ultima_raw = data.get("ultima_actualizacion", "")
    try:
        dt = datetime.fromisoformat(ultima_raw.replace("Z", "+00:00"))
        dt_local = dt.astimezone(timezone(timedelta(hours=-5)))
        ultima_fmt = dt_local.strftime("%d/%m/%Y a las %I:%M %p (Hora Local)")
    except Exception:
        ultima_fmt = ultima_raw or "—"

    return render_template(
        "metricas.html",
        log_lines=lineas,
        alertas_activas=data.get("total", 0),
        alertas_historicas=hist_count,
        ultima=ultima_fmt,
    )


# ─────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Modo desarrollo local
    app.run(host="0.0.0.0", port=5000, debug=False)
