
"""
Migración controlada de Nexus desde SQLite hacia MariaDB/MySQL.

Ejecutar desde la raíz del proyecto:
    python -m database.migrate_sqlite_to_mysql

No modifica ni elimina el archivo SQLite original.
"""

import sqlite3
import sys

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
    "autocommit": False,
}

# Orden de inserción respetando las claves foráneas.
TABLAS = [
    "usuarios",
    "residentes",
    "actividades",
    "medicamentos_residente",
    "personal",
    "asignaciones",
    "historial",
    "notificaciones",
    "notificaciones_generadas",
    "codigos_verificacion",
]

ESQUEMA = {
    "usuarios": """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(191) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            rol VARCHAR(100) NOT NULL DEFAULT 'Cuidador',
            nombre VARCHAR(255),
            correo VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "residentes": """
        CREATE TABLE IF NOT EXISTS residentes (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(255) NOT NULL,
            documento VARCHAR(100) NOT NULL UNIQUE,
            edad INT,
            fecha_ingreso VARCHAR(30),
            habitacion VARCHAR(100),
            diagnostico TEXT,
            medicamentos TEXT,
            alergias TEXT,
            familiar_nombre VARCHAR(255),
            familiar_parentesco VARCHAR(100),
            familiar_telefono VARCHAR(100),
            familiar_username VARCHAR(191)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    "actividades": """
        CREATE TABLE IF NOT EXISTS actividades (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            residente VARCHAR(255) NOT NULL,
            hora VARCHAR(30) NOT NULL,
            actividad TEXT NOT NULL,
            cuidador VARCHAR(255),
            fecha VARCHAR(30),
            dia VARCHAR(100)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    "medicamentos_residente": """
        CREATE TABLE IF NOT EXISTS medicamentos_residente (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            residente_id INT NOT NULL,
            nombre VARCHAR(255) NOT NULL,
            dosis VARCHAR(255) NOT NULL,
            horario VARCHAR(100) NOT NULL,
            observaciones TEXT,
            dia VARCHAR(100),
            CONSTRAINT fk_mr_residente
                FOREIGN KEY (residente_id)
                REFERENCES residentes(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "personal": """
        CREATE TABLE IF NOT EXISTS personal (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(255) NOT NULL,
            correo VARCHAR(255),
            telefono VARCHAR(100),
            turno VARCHAR(100),
            activo TINYINT DEFAULT 1,
            usuario_id INT,
            CONSTRAINT fk_personal_usuario
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "asignaciones": """
        CREATE TABLE IF NOT EXISTS asignaciones (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            residente_id INT NOT NULL,
            personal_id INT NOT NULL,
            fecha_asignacion DATE NOT NULL DEFAULT (CURRENT_DATE),
            UNIQUE KEY uq_asignacion (residente_id, personal_id),
            CONSTRAINT fk_asig_residente
                FOREIGN KEY (residente_id) REFERENCES residentes(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_asig_personal
                FOREIGN KEY (personal_id) REFERENCES personal(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "historial": """
        CREATE TABLE IF NOT EXISTS historial (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            fecha VARCHAR(30) NOT NULL,
            hora VARCHAR(30) NOT NULL,
            tipo VARCHAR(100) NOT NULL,
            actividad TEXT NOT NULL,
            residente VARCHAR(255) NOT NULL,
            cuidador VARCHAR(255) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "notificaciones": """
        CREATE TABLE IF NOT EXISTS notificaciones (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            residente VARCHAR(255) NOT NULL,
            tipo VARCHAR(100) NOT NULL,
            detalle TEXT,
            fecha VARCHAR(30) NOT NULL,
            hora VARCHAR(30) NOT NULL,
            estado VARCHAR(100) NOT NULL DEFAULT 'Pendiente',
            mostrada TINYINT NOT NULL DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "notificaciones_generadas": """
        CREATE TABLE IF NOT EXISTS notificaciones_generadas (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            residente VARCHAR(255) NOT NULL,
            tipo VARCHAR(100) NOT NULL,
            detalle VARCHAR(255),
            fecha VARCHAR(30) NOT NULL,
            hora VARCHAR(30) NOT NULL,
            UNIQUE KEY uq_notificacion_generada
                (residente, tipo, fecha, hora, detalle)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "codigos_verificacion": """
        CREATE TABLE IF NOT EXISTS codigos_verificacion (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            codigo VARCHAR(255) NOT NULL,
            creado VARCHAR(40) NOT NULL,
            expira VARCHAR(40) NOT NULL,
            usado TINYINT NOT NULL DEFAULT 0,
            CONSTRAINT fk_codigo_usuario
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}


def obtener_tablas_sqlite(conn):
    filas = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
    """).fetchall()
    return {fila[0] for fila in filas}


def contar_sqlite(conn, tabla):
    return conn.execute(
        f'SELECT COUNT(*) FROM "{tabla}"'
    ).fetchone()[0]


def contar_mysql(cursor, tabla):
    cursor.execute(f"SELECT COUNT(*) FROM `{tabla}`")
    return cursor.fetchone()[0]


def migrar():
    sqlite_conn = None
    mysql_conn = None

    try:
        # Abrir SQLite en modo de solo lectura.
        sqlite_uri = "file:" + DATABASE.replace("\\", "/") + "?mode=ro"
        sqlite_conn = sqlite3.connect(sqlite_uri, uri=True)

        tablas_origen = obtener_tablas_sqlite(sqlite_conn)
        esperadas = set(TABLAS)

        if tablas_origen != esperadas:
            faltan = sorted(esperadas - tablas_origen)
            sobran = sorted(tablas_origen - esperadas)
            raise RuntimeError(
                f"El esquema SQLite no coincide. "
                f"Faltan: {faltan}; adicionales: {sobran}. "
                "No se realizaron cambios."
            )

        columnas_origen = {}
        conteos_origen = {}

        for tabla in TABLAS:
            columnas_origen[tabla] = [
                fila[1]
                for fila in sqlite_conn.execute(
                    f'PRAGMA table_info("{tabla}")'
                ).fetchall()
            ]
            conteos_origen[tabla] = contar_sqlite(
                sqlite_conn, tabla
            )

        mysql_conn = pymysql.connect(**MYSQL_CONFIG)

        with mysql_conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            existentes = {fila[0] for fila in cursor.fetchall()}

            desconocidas = existentes - esperadas
            if desconocidas:
                raise RuntimeError(
                    f"MySQL contiene tablas ajenas a esta migración: "
                    f"{sorted(desconocidas)}. No se modificó nada."
                )


            # No sobrescribir registros existentes.
            for tabla in existentes:
                if contar_mysql(cursor, tabla) != 0:
                    raise RuntimeError(
                        f"La tabla {tabla} ya tiene datos. "
                        "Se cancela para evitar sobrescribirlos."
                    )

            # Reconstruir únicamente las tablas existentes que están vacías.
            if existentes:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                try:
                    for tabla in reversed(TABLAS):
                        if tabla in existentes:
                            cursor.execute(f"DROP TABLE `{tabla}`")
                finally:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

            # Crear todas las tablas con el esquema corregido.
            for tabla in TABLAS:
                cursor.execute(ESQUEMA[tabla])

            # Validar columnas antes de insertar.
            for tabla in TABLAS:
                cursor.execute(f"SHOW COLUMNS FROM `{tabla}`")
                columnas_destino = {
                    fila[0] for fila in cursor.fetchall()
                }
                incompatibles = (
                    set(columnas_origen[tabla]) - columnas_destino
                )
                if incompatibles:
                    raise RuntimeError(
                        f"Columnas no contempladas en {tabla}: "
                        f"{sorted(incompatibles)}"
                    )


            # Validar columnas antes de insertar.
            for tabla in TABLAS:
                cursor.execute(f"SHOW COLUMNS FROM `{tabla}`")
                columnas_destino = {
                    fila[0] for fila in cursor.fetchall()
                }
                incompatibles = (
                    set(columnas_origen[tabla]) - columnas_destino
                )
                if incompatibles:
                    raise RuntimeError(
                        f"Columnas no contempladas en {tabla}: "
                        f"{sorted(incompatibles)}"
                    )

            # Copiar los registros sin recalcular IDs ni contraseñas.
            for tabla in TABLAS:
                columnas = columnas_origen[tabla]
                if not columnas:
                    continue

                nombres = ", ".join(
                    f"`{columna}`" for columna in columnas
                )
                marcadores = ", ".join(
                    ["%s"] * len(columnas)
                )

                filas = sqlite_conn.execute(
                    f'SELECT * FROM "{tabla}"'
                ).fetchall()

                if filas:
                    sql = (
                        f"INSERT INTO `{tabla}` ({nombres}) "
                        f"VALUES ({marcadores})"
                    )
                    cursor.executemany(sql, filas)

            # Confirmar la transacción de datos.
            mysql_conn.commit()

            print("\n--- Verificación de migración ---")
            errores = []

            for tabla in TABLAS:
                origen = conteos_origen[tabla]
                destino = contar_mysql(cursor, tabla)
                estado = "OK" if origen == destino else "DIFERENCIA"
                print(
                    f"{tabla}: SQLite={origen}, "
                    f"MySQL={destino} [{estado}]"
                )
                if origen != destino:
                    errores.append(tabla)

            if errores:
                print(
                    "\nATENCIÓN: los conteos no coinciden en "
                    + ", ".join(errores)
                )
                print(
                    "No vuelvas a ejecutar el script automáticamente. "
                    "Revisaremos las diferencias primero."
                )
                return

            print("\nMigración y conteos completados correctamente.")
            print(
                "La base SQLite original no fue modificada. "
                "Nexus todavía no se ha cambiado para usar MySQL."
            )

    except Exception as error:
        if mysql_conn is not None:
            mysql_conn.rollback()
        print(f"\nMIGRACIÓN CANCELADA: {error}")
        print(
            "Revisa el mensaje antes de volver a ejecutar el script."
        )
        sys.exit(1)

    finally:
        if sqlite_conn is not None:
            sqlite_conn.close()
        if mysql_conn is not None:
            mysql_conn.close()


if __name__ == "__main__":
    migrar()
