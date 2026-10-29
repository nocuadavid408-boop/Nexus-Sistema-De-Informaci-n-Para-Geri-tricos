
import sqlite3
from core.config import DATABASE

conn = sqlite3.connect(DATABASE)

try:
    print("=== USUARIOS EN SQLITE ===")
    for fila in conn.execute(
        "SELECT id, username FROM usuarios ORDER BY id"
    ):
        print(fila)

    print("\n=== CODIGOS DE VERIFICACION ===")
    for fila in conn.execute("""
        SELECT
            c.id,
            c.usuario_id,
            u.username
        FROM codigos_verificacion AS c
        LEFT JOIN usuarios AS u
            ON u.id = c.usuario_id
        ORDER BY c.id
    """):
        print(fila)

    print("\n=== CODIGOS SIN USUARIO ===")
    for fila in conn.execute("""
        SELECT c.id, c.usuario_id
        FROM codigos_verificacion AS c
        LEFT JOIN usuarios AS u
            ON u.id = c.usuario_id
        WHERE u.id IS NULL
    """):
        print(fila)

    print("\n=== DETALLES DE LOS CODIGOS HUERFANOS ===")
    for fila in conn.execute("""
        SELECT
            c.id,
            c.usuario_id,
            c.creado,
            c.expira,
            c.usado
        FROM codigos_verificacion AS c
        LEFT JOIN usuarios AS u
            ON u.id = c.usuario_id
        WHERE u.id IS NULL
        ORDER BY c.id
    """):
        print(fila)
        
finally:
    conn.close()
