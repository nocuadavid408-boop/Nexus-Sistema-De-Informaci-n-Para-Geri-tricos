"""
Asignación de residentes a cuidadores (solo Administrador).

La pantalla lista a cada cuidador activo y, dentro de su tarjeta, los
residentes con casillas para marcar cuáles tiene a su cargo. Un cuidador
solo ve en el sistema los residentes que se le asignan aquí.
Compatible con MySQL mediante PyMySQL.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.auth import admin_required
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


def consultar_uno(conn, consulta, parametros=()):
    with conn.cursor() as cursor:
        cursor.execute(consulta, parametros)
        return cursor.fetchone()


def consultar_todos(conn, consulta, parametros=()):
    with conn.cursor() as cursor:
        cursor.execute(consulta, parametros)
        return cursor.fetchall()


def volver_asignaciones(request: Request):
    return RedirectResponse(request.url_for("asignaciones"), status_code=303)


@router.get("/asignaciones", name="asignaciones")
async def listar_asignaciones(
    request: Request,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        residentes = consultar_todos(
            conn,
            """
            SELECT id, nombre, documento, habitacion
            FROM residentes
            ORDER BY nombre
            """,
        )

        cuidadores = consultar_todos(
            conn,
            """
            SELECT p.id, p.nombre, p.turno
            FROM personal p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.activo = 1
              AND u.rol = 'Cuidador'
            ORDER BY p.nombre
            """,
        )

        filas = consultar_todos(
            conn,
            "SELECT personal_id, residente_id FROM asignaciones",
        )
    finally:
        conn.close()

    asignados = {}
    for fila in filas:
        asignados.setdefault(fila["personal_id"], set()).add(
            fila["residente_id"]
        )

    return render(
        request,
        "asignaciones/index.html",
        {
            "residentes": residentes,
            "cuidadores": cuidadores,
            "asignados": asignados,
        },
    )


@router.post(
    "/asignaciones/cuidador/{personal_id}",
    name="guardar_asignaciones_cuidador",
)
async def guardar_asignaciones_cuidador(
    request: Request,
    personal_id: int,
    session=Depends(admin_required),
):
    form = await request.form()

    try:
        nuevos = {int(valor) for valor in form.getlist("residente_ids")}
    except (TypeError, ValueError):
        flash(request, "Los datos de la asignación no son válidos.", "error")
        return volver_asignaciones(request)

    conn = get_db()

    try:
        cuidador = consultar_uno(
            conn,
            """
            SELECT p.id, p.nombre
            FROM personal p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.id = %s
              AND p.activo = 1
              AND u.rol = 'Cuidador'
            """,
            (personal_id,),
        )

        if not cuidador:
            flash(
                request,
                "El cuidador no existe o no está activo.",
                "error",
            )
            return volver_asignaciones(request)

        if nuevos:
            marcadores = ", ".join(["%s"] * len(nuevos))
            validos = consultar_todos(
                conn,
                f"SELECT id FROM residentes WHERE id IN ({marcadores})",
                tuple(nuevos),
            )

            if len(validos) != len(nuevos):
                flash(request, "Alguno de los residentes no existe.", "error")
                return volver_asignaciones(request)

        actuales = {
            fila["residente_id"]
            for fila in consultar_todos(
                conn,
                "SELECT residente_id FROM asignaciones WHERE personal_id = %s",
                (personal_id,),
            )
        }

        quitar = actuales - nuevos
        agregar = nuevos - actuales

        with conn.cursor() as cursor:
            if quitar:
                cursor.execute(
                    f"""
                    DELETE FROM asignaciones
                    WHERE personal_id = %s
                      AND residente_id IN ({', '.join(['%s'] * len(quitar))})
                    """,
                    (personal_id, *quitar),
                )

            if agregar:
                cursor.executemany(
                    """
                    INSERT INTO asignaciones (residente_id, personal_id)
                    VALUES (%s, %s)
                    """,
                    [(rid, personal_id) for rid in sorted(agregar)],
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash(
        request,
        f"Asignaciones de {cuidador['nombre']} guardadas "
        f"({len(nuevos)} residente(s)).",
        "exito",
    )
    return volver_asignaciones(request)
