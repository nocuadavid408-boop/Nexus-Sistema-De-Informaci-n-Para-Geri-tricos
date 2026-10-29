
"""
Diagnóstico de solo lectura para la migración de Nexus.
Comprueba SQLite y MySQL sin modificar ninguna base de datos.
Ejecutar desde la raíz del proyecto:
    python -m database.check_mysql
"""

import sqlite3

import pymysql
from core.config import DATABASE

MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "nexus_proyecto",
    "charset": "utf8mb4",
    "connect_timeout": 5,
}


def comprobar_sqlite():
    print("\n--- SQLite: nexus.db ---")

    try:
        with sqlite3.connect(DATABASE) as conn:
            tablas = conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """).fetchall()

            if not tablas:
                print("No se encontraron tablas.")
                return False

            for (tabla,) in tablas:
                # El nombre proviene del catálogo de SQLite.
                nombre_seguro = tabla.replace('"', '""')
                total = conn.execute(
                    f'SELECT COUNT(*) FROM "{nombre_seguro}"'
                ).fetchone()[0]
                print(f"{tabla}: {total} registros")

        print("SQLite: lectura correcta.")
        return True

    except (sqlite3.Error, OSError) as error:
        print(f"Error leyendo SQLite: {error}")
        return False


def comprobar_mysql():
    print("\n--- MySQL: nexus ---")
    conn = None

    try:
        conn = pymysql.connect(**MYSQL_CONFIG)

        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE(), VERSION()")
            base, version = cursor.fetchone()

            cursor.execute("SHOW TABLES")
            tablas = cursor.fetchall()

        print(f"Conexión correcta. Base seleccionada: {base}")
        print(f"Versión de MySQL: {version}")
        print(f"Tablas existentes: {len(tablas)}")

        if tablas:
            for (tabla,) in tablas:
                print(f"  - {tabla}")
        else:
            print("La base está vacía; todavía no se ha migrado.")

        return True

    except pymysql.MySQLError as error:
        print(f"No se pudo conectar a MySQL: {error}")
        print("Comprueba que MySQL esté iniciado y el puerto sea 3306.")
        return False

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sqlite_ok = comprobar_sqlite()
    mysql_ok = comprobar_mysql()

    print("\n--- Resultado ---")
    if sqlite_ok and mysql_ok:
        print("Ambas bases son accesibles. Podemos preparar la migración.")
    else:
        print("Hay que resolver los errores antes de continuar.")
