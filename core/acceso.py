"""
Acceso a residentes según el rol.

- Administrador: ve todos los residentes.
- Cuidador: solo ve los residentes que el administrador le asignó
  (tabla `asignaciones`, a través de su registro de personal vinculado).
"""


def es_admin(session) -> bool:
    return session.get("rol") == "Administrador"


def ids_visibles(conn, session):
    """None si la persona ve todo (administrador); si no, la lista de ids de
    los residentes asignados a su cuenta."""
    if es_admin(session):
        return None
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id
            FROM asignaciones ag
            JOIN personal p   ON p.id = ag.personal_id
            JOIN residentes r ON r.id = ag.residente_id
            WHERE p.usuario_id = %s AND p.activo = 1
            """,
            (session["user_id"],),
        )
        return [fila["id"] for fila in cursor.fetchall()]


def puede_ver_residente(conn, session, residente_id) -> bool:
    ids = ids_visibles(conn, session)
    return ids is None or residente_id in ids


def filtro_ids(conn, session, columna: str = "id"):
    """Condición SQL (con marcadores %s) para limitar por id de residente."""
    ids = ids_visibles(conn, session)
    if ids is None:
        return "1 = 1", ()
    if not ids:
        return "1 = 0", ()
    return f"{columna} IN ({', '.join(['%s'] * len(ids))})", tuple(ids)


def nombres_visibles(conn, session):
    """None si la persona ve todo (administrador); si no, los nombres de los
    residentes asignados (las tablas actividades, notificaciones e historial
    guardan el residente por nombre)."""
    ids = ids_visibles(conn, session)
    if ids is None:
        return None
    if not ids:
        return []
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT nombre FROM residentes WHERE id IN ({', '.join(['%s'] * len(ids))})",
            tuple(ids),
        )
        return [fila["nombre"] for fila in cursor.fetchall()]


def filtro_nombres(conn, session, columna: str = "residente"):
    """Igual que filtro_ids, pero para columnas que guardan el nombre del
    residente (actividades, notificaciones, historial)."""
    nombres = nombres_visibles(conn, session)
    if nombres is None:
        return "1 = 1", ()
    if not nombres:
        return "1 = 0", ()
    return f"{columna} IN ({', '.join(['%s'] * len(nombres))})", tuple(nombres)


def nombres_del_cuidador(conn, session):
    """Nombres con los que los registros del cuidador pueden haber quedado
    guardados: su nombre en el personal, su nombre de cuenta y su usuario."""
    nombres = set()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT nombre FROM personal WHERE usuario_id = %s",
            (session["user_id"],),
        )
        for fila in cursor.fetchall():
            if fila["nombre"]:
                nombres.add(fila["nombre"].strip())
    for clave in ("nombre", "username"):
        if session.get(clave):
            nombres.add(str(session[clave]).strip())
    return sorted(nombres)


def nombre_para_registro(conn, session) -> str:
    """Nombre con el que se firma lo que hace el cuidador (personal primero)."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT nombre FROM personal WHERE usuario_id = %s AND activo = 1",
            (session["user_id"],),
        )
        fila = cursor.fetchone()
    if fila and fila["nombre"]:
        return fila["nombre"]
    return session.get("nombre") or session.get("username") or ""
