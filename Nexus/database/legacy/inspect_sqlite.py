
import sqlite3
from core.config import DATABASE

conn = sqlite3.connect(DATABASE)

tablas = [
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

for tabla in tablas:
    print(f"\n--- {tabla} ---")
    columnas = conn.execute(
        f'PRAGMA table_info("{tabla}")'
    ).fetchall()

    for columna in columnas:
        print(f"{columna[1]} ({columna[2]})")

conn.close()
