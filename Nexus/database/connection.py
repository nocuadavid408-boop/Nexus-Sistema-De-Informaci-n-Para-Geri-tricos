"""
Conexión a MySQL/MariaDB. Los datos salen de variables de entorno
(con los valores de XAMPP por defecto) y los errores dicen QUÉ falló.
"""
import os

import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = dict(
    host=os.environ.get("NEXUS_DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("NEXUS_DB_PORT", "3306")),
    user=os.environ.get("NEXUS_DB_USER", "root"),
    password=os.environ.get("NEXUS_DB_PASSWORD", ""),
    database=os.environ.get("NEXUS_DB_NAME", "nexus_proyecto"),
    charset="utf8mb4",
    connect_timeout=5,
    cursorclass=DictCursor,
    autocommit=False,
)

# Bases en la nube (Aiven, etc.) exigen SSL: apunta NEXUS_DB_SSL_CA al certificado CA.
_ssl_ca = os.environ.get("NEXUS_DB_SSL_CA")
if _ssl_ca:
    DB_CONFIG["ssl_ca"] = _ssl_ca


def get_db():
    try:
        return pymysql.connect(**DB_CONFIG)
    except pymysql.err.OperationalError as e:
        codigo = e.args[0] if e.args else 0
        pistas = {
            2003: "MySQL no está corriendo (inicia MySQL en XAMPP) o el puerto no es 3306.",
            1045: "Usuario/contraseña incorrectos (NEXUS_DB_USER / NEXUS_DB_PASSWORD).",
            1049: "La base no existe: importa nexus_v3.sql primero.",
        }
        raise RuntimeError(
            f"No se pudo conectar a '{DB_CONFIG['database']}' en "
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']} → {pistas.get(codigo, e)}"
        ) from e


def comprobar_esquema():
    """Se llama al arrancar: falla fuerte si falta alguna tabla requerida."""
    requeridas = {
        "usuarios", "residentes", "personal", "asignaciones",
        "categorias_medicamentos", "medicamentos",
        "categorias_actividades", "actividades",
        "itinerario_diario", "itinerario_checks", "itinerario_observaciones",
    }
    conn = get_db()
    try:
        with conn.cursor() as c:
            c.execute("SELECT TABLE_NAME AS t FROM information_schema.TABLES "
                      "WHERE TABLE_SCHEMA = DATABASE()")
            faltan = requeridas - {f["t"] for f in c.fetchall()}
    finally:
        conn.close()
    if faltan:
        raise RuntimeError(f"Faltan tablas {sorted(faltan)}: importa nexus_v3.sql.")
