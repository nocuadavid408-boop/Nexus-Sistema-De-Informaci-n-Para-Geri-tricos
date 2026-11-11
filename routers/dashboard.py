
"""
DASHBOARD
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.acceso import es_admin, filtro_ids, filtro_nombres
from core.auth import login_required
from core.templates import render
from database.connection import get_db

router = APIRouter()


@router.get("/dashboard", name="dashboard")
async def dashboard(
    request: Request,
    session=Depends(login_required),
):
    # Los familiares no tienen acceso al Dashboard.
    if session.get("rol") == "Familiar":
        return RedirectResponse(
            request.url_for("lista_familiar"),
            status_code=303,
        )

    conn = get_db()

    try:
        # El cuidador solo cuenta lo que corresponde a sus residentes.
        donde_id, params_id = filtro_ids(conn, session, "id")
        donde_nom, params_nom = filtro_nombres(conn, session, "residente")
        donde_rid, params_rid = filtro_ids(conn, session, "residente_id")

        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM residentes WHERE {donde_id}",
                params_id,
            )
            total_residentes = cursor.fetchone()["total"]

            cursor.execute(
                f"SELECT COUNT(*) AS total FROM itinerario_diario "
                f"WHERE tipo = 'actividad' AND fecha >= CURDATE() AND {donde_rid}",
                params_rid,
            )
            total_actividades = cursor.fetchone()["total"]

            total_usuarios = 0
            if es_admin(session):
                cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
                total_usuarios = cursor.fetchone()["total"]

            cursor.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM notificaciones
                WHERE estado = 'Pendiente' AND {donde_nom}
                """,
                params_nom,
            )
            total_notificaciones_pendientes = cursor.fetchone()["total"]

        return render(
            request,
            "dashboard.html",
            {
                "total_residentes": total_residentes,
                "total_actividades": total_actividades,
                "total_usuarios": total_usuarios,
                "total_notificaciones_pendientes": (
                    total_notificaciones_pendientes
                ),
            },
        )

    finally:
        conn.close()
