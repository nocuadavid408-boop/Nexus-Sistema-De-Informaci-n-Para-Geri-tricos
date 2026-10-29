
from database.connection import get_db

def verificar_mysql():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            print("Base de datos:", cursor.fetchone())

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
                cursor.execute(f"SHOW COLUMNS FROM `{tabla}`")
                columnas = [fila["Field"] for fila in cursor.fetchall()]
                print(f"\n{tabla}: {columnas}")
    finally:
        conn.close()

if __name__ == "__main__":
    verificar_mysql()
