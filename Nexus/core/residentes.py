"""
Operaciones de escritura sobre `residentes`.
Cada función recibe la conexión y NO hace commit: quien la llama decide
cuándo confirmar (así la API y las pantallas comparten la misma lógica).
"""

CAMPOS = (
    "nombre", "documento", "edad", "fecha_ingreso", "habitacion",
    "diagnostico", "medicamentos", "alergias",
    "familiar_nombre", "familiar_parentesco", "familiar_telefono",
    "familiar_username",
)


def documento_en_uso(conn, documento: str, excluir_id: int | None = None) -> bool:
    with conn.cursor() as c:
        if excluir_id is None:
            c.execute("SELECT id FROM residentes WHERE documento = %s", (documento,))
        else:
            c.execute(
                "SELECT id FROM residentes WHERE documento = %s AND id != %s",
                (documento, excluir_id),
            )
        return c.fetchone() is not None


def crear(conn, datos: dict) -> int:
    columnas = ", ".join(CAMPOS)
    marcas = ", ".join(["%s"] * len(CAMPOS))
    with conn.cursor() as c:
        c.execute(
            f"INSERT INTO residentes ({columnas}) VALUES ({marcas})",
            tuple(datos.get(k) for k in CAMPOS),
        )
        return c.lastrowid


def actualizar(conn, residente_id: int, datos: dict) -> bool:
    asignaciones = ", ".join(f"{k} = %s" for k in CAMPOS)
    with conn.cursor() as c:
        c.execute(
            f"UPDATE residentes SET {asignaciones} WHERE id = %s",
            (*(datos.get(k) for k in CAMPOS), residente_id),
        )
        return c.rowcount > 0


def eliminar(conn, residente_id: int) -> bool:
    with conn.cursor() as c:
        c.execute("DELETE FROM residentes WHERE id = %s", (residente_id,))
        return c.rowcount > 0
