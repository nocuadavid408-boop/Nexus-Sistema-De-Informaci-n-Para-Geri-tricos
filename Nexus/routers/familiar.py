
"""
FAMILIAR

Permite consultar el seguimiento de los residentes.
Los familiares solo pueden acceder a los adultos mayores
vinculados a su propia cuenta.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.acceso import filtro_ids, puede_ver_residente
from core.auth import login_required
from core.itinerario import actividades_planas, listado
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/familiar", name="lista_familiar")
async def lista_familiar(
    request: Request,
    session=Depends(login_required),
):
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            if session.get("rol") == "Familiar":
                # El familiar solo ve residentes vinculados
                # al nombre de usuario de su propia cuenta.
                username = (session.get("username") or "").strip()

                cursor.execute(
                    """
                    SELECT *
                    FROM residentes
                    WHERE LOWER(familiar_username) = LOWER(%s)
                    ORDER BY nombre
                    """,
                    (username,),
                )
            else:
                # Administrador: todos. Cuidador: solo los asignados.
                donde, params = filtro_ids(conn, session, "id")
                cursor.execute(
                    f"SELECT * FROM residentes WHERE {donde} ORDER BY nombre",
                    params,
                )

            residentes = cursor.fetchall()

    finally:
        conn.close()

    # Si el familiar tiene un solo residente vinculado,
    # se abre directamente su seguimiento.
    if session.get("rol") == "Familiar" and len(residentes) == 1:
        return RedirectResponse(
            request.url_for(
                "seguimiento_familiar",
                residente_id=residentes[0]["id"],
            ),
            status_code=303,
        )

    return render(
        request,
        "familiar/lista.html",
        {"residentes": residentes},
    )


@router.get("/familiar/{residente_id}", name="seguimiento_familiar")
async def seguimiento_familiar(
    request: Request,
    residente_id: int,
    session=Depends(login_required),
):
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            # Buscar al residente solicitado.
            cursor.execute(
                "SELECT * FROM residentes WHERE id = %s",
                (residente_id,),
            )
            residente = cursor.fetchone()

            if not residente:
                flash(request, "Residente no encontrado.", "error")
                return RedirectResponse(
                    request.url_for("lista_familiar"),
                    status_code=303,
                )

            # Un cuidador solo consulta a sus residentes asignados.
            if session.get("rol") == "Cuidador" and not puede_ver_residente(
                conn, session, residente_id
            ):
                flash(
                    request,
                    "Ese residente no está asignado a tu cuenta.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("lista_familiar"),
                    status_code=303,
                )

            # Verificar que el familiar tenga autorización
            # para consultar a este residente.
            if session.get("rol") == "Familiar":
                username = (
                    session.get("username") or ""
                ).strip().lower()

                familiar_username = (
                    residente.get("familiar_username") or ""
                ).strip().lower()

                if familiar_username != username:
                    flash(
                        request,
                        "Solo puedes consultar la información "
                        "de tu propio adulto mayor.",
                        "error",
                    )
                    return RedirectResponse(
                        request.url_for("lista_familiar"),
                        status_code=303,
                    )

            # Actividades y medicamentos programados (solo lectura).
            planas = actividades_planas(conn, residente_id=residente_id)
            actividades = sorted(
                sorted(planas, key=lambda x: x["hora"]), key=lambda x: x["fecha"], reverse=True
            )
            medicamentos = listado(conn, residente_id, "medicamento")

        return render(
            request,
            "familiar/vista.html",
            {
                "residente": residente,
                "actividades": actividades,
                "medicamentos": medicamentos,
            },
        )

    finally:
        conn.close()
