
import sqlite3
from core.config import DATABASE

conn = sqlite3.connect(DATABASE)

try:
    conn.execute("PRAGMA foreign_keys = ON")

    # Mostrar los registros que se van a eliminar.
    filas = conn.execute("""
        SELECT c.id, c.usuario_id
        FROM codigos_verificacion AS c
        LEFT JOIN usuarios AS u ON u.id = c.usuario_id
        WHERE u.id IS NULL
    """).fetchall()

    print("Códigos huérfanos encontrados:", filas)

    if filas:
        conn.execute("""
            DELETE FROM codigos_verificacion
            WHERE usuario_id NOT IN (
                SELECT id FROM usuarios
            )
        """)
        conn.commit()
        print("Códigos huérfanos eliminados:", len(filas))
    else:
        print("No hay códigos huérfanos.")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()
