
import sqlite3
from core.config import DATABASE

conn = sqlite3.connect(DATABASE)

try:
    conn.execute("BEGIN")

    # Confirmar que el residente 1 no existe.
    residente = conn.execute(
        "SELECT id FROM residentes WHERE id = 1"
    ).fetchone()

    if residente is not None:
        raise Exception(
            "El residente 1 existe. No se eliminará nada."
        )

    # Confirmar que el registro es exactamente el esperado.
    medicamento = conn.execute(
        """
        SELECT id, nombre, residente_id
        FROM medicamentos_residente
        WHERE id = 1
          AND residente_id = 1
          AND nombre = 'Metmorfina'
        """
    ).fetchone()

    if medicamento is None:
        raise Exception(
            "No se encontró el registro esperado. No se eliminó nada."
        )

    # Eliminar únicamente el medicamento huérfano.
    conn.execute(
        """
        DELETE FROM medicamentos_residente
        WHERE id = 1
          AND residente_id = 1
          AND nombre = 'Metmorfina'
        """
    )

    conn.commit()
    print("Registro de Metmorfina eliminado correctamente.")

    print("\n=== MEDICAMENTOS RESTANTES ===")
    for fila in conn.execute(
        """
        SELECT id, nombre, residente_id
        FROM medicamentos_residente
        """
    ):
        print(fila)

except Exception as error:
    conn.rollback()
    print("No se realizaron cambios:", error)

finally:
    conn.close()
