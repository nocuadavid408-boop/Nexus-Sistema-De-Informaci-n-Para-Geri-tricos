"""
Esquema de la base de datos MySQL/MariaDB (nexus_proyecto).

- init_db(): ejecuta database/nexus_v3.sql (crea la base y las tablas si no
  existen, y carga categorías, catálogos y usuarios de prueba). A mano:
      python -m database.schema
  ⚠️ Ese script elimina las tablas VIEJAS (actividades antigua,
  medicamentos_residente, medicamento_horas, catalogo_medicamentos,
  agenda_eventos). Haz respaldo si tienes datos que conservar.
- sincronizar_personal(): se ejecuta al arrancar la app; asegura que toda
  cuenta de Cuidador tenga su registro de personal activo.
"""
import os
import re

import pymysql

from database.connection import DB_CONFIG, comprobar_esquema, get_db

SQL_FILE = os.path.join(os.path.dirname(__file__), "nexus_v3.sql")


def _sentencias(texto: str):
    sin_comentarios = "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


def init_db() -> None:
    """Ejecuta nexus_v3.sql. Si la base no existe (XAMPP local) la crea; en la nube
    la base ya viene creada por el proveedor y se usa tal cual."""
    try:
        conn = pymysql.connect(**DB_CONFIG)
    except pymysql.err.OperationalError as e:
        if not e.args or e.args[0] != 1049:
            raise
        cfg = {k: v for k, v in DB_CONFIG.items() if k != "database"}
        conn = pymysql.connect(**cfg)
        with conn.cursor() as c:
            c.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
            c.execute(f"USE `{DB_CONFIG['database']}`")
    try:
        with open(SQL_FILE, encoding="utf-8") as f, conn.cursor() as c:
            for sentencia in _sentencias(f.read()):
                c.execute(sentencia)
        conn.commit()
    finally:
        conn.close()
    sincronizar_personal()


def inicializar_si_falta() -> None:
    """Primer arranque: si faltan tablas, importa nexus_v3.sql automáticamente.
    Con las tablas ya creadas no toca nada (no se pierden datos al redesplegar)."""
    try:
        comprobar_esquema()
    except RuntimeError:
        init_db()


def sincronizar_personal() -> None:
    """Toda cuenta de Cuidador debe tener su registro de personal activo; así
    aparece en Asignaciones y puede recibir residentes."""
    conn = get_db()
    try:
        with conn.cursor() as c:
            c.execute(
                """
                INSERT INTO personal (nombre, correo, turno, activo, usuario_id)
                SELECT COALESCE(NULLIF(u.nombre, ''), u.username), u.correo, NULL, 1, u.id
                FROM usuarios u
                WHERE u.rol = 'Cuidador'
                  AND NOT EXISTS (SELECT 1 FROM personal p WHERE p.usuario_id = u.id)
                """
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Base de datos lista.")
