
"""
HISTORIAL (ex proyecto "Actividades")

El historial se registra automáticamente desde los módulos de
Horarios y Medicamentos. Aquí se muestra el listado completo
y se permite eliminar un registro puntual.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.acceso import es_admin, filtro_nombres, nombres_del_cuidador
from core.auth import admin_required, staff_required
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/historial", name="lista_historial")
async def lista_historial(
    request: Request,
    session=Depends(staff_required),
):
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            if es_admin(session):
                cursor.execute(
                    """
                    SELECT *
                    FROM historial
                    ORDER BY fecha DESC, hora DESC
                    """
                )
            else:
                # El cuidador solo ve lo que él mismo registró y solo de
                # los residentes que tiene asignados hoy.
                nombres = nombres_del_cuidador(conn, session)
                donde_res, params_res = filtro_nombres(conn, session, "residente")
                cursor.execute(
                    f"""
                    SELECT *
                    FROM historial
                    WHERE cuidador IN ({', '.join(['%s'] * len(nombres))})
                      AND {donde_res}
                    ORDER BY fecha DESC, hora DESC
                    """,
                    (*nombres, *params_res),
                )
            historial = cursor.fetchall()

        return render(
            request,
            "historial/index.html",
            {"historial": historial},
        )
    finally:
        conn.close()


@router.get("/historial/eliminar/{historial_id}", name="eliminar_historial")
async def eliminar_historial(
    request: Request,
    historial_id: int,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM historial WHERE id = %s",
                (historial_id,),
            )

        conn.commit()
        flash(request, "Registro eliminado del historial.", "exito")

    except Exception:
        conn.rollback()
        flash(
            request,
            "No se pudo eliminar el registro del historial.",
            "error",
        )
        raise

    finally:
        conn.close()

    return RedirectResponse(
        request.url_for("lista_historial"),
        status_code=303,
    )


def registrar_en_historial(
    conn,
    *,
    fecha,
    hora,
    tipo,
    actividad,
    residente,
    cuidador,
):
    """
    Guarda un registro en el historial.

    La llaman los módulos de Horarios y Medicamentos después
    de guardar sus datos. Recibe una conexión existente y no
    la cierra ni confirma la transacción: eso le corresponde
    al módulo que la llamó.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO historial (
                fecha,
                hora,
                tipo,
                actividad,
                residente,
                cuidador
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                fecha,
                hora,
                tipo,
                actividad,
                residente,
                cuidador or "Sin asignar",
            ),
        )
