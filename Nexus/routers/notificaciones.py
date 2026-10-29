
"""
NOTIFICACIONES / ALERTAS

Las alertas se generan automáticamente desde core/tasks.py.
Aquí se pueden consultar, completar y eliminar. También se
gestionan las alertas emergentes con sonido.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

from core.acceso import filtro_nombres
from core.auth import admin_required, sesion_operativa, staff_required
from core.config import STAFF_ROLES
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/notificaciones", name="lista_notificaciones")
async def lista_notificaciones(
    request: Request,
    session=Depends(staff_required),
):
    conn = get_db()

    try:
        donde, params = filtro_nombres(conn, session, "residente")
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT *
                FROM notificaciones
                WHERE {donde}
                ORDER BY fecha, hora
                """,
                params,
            )
            notificaciones = cursor.fetchall()

        return render(
            request,
            "notificaciones/index.html",
            {"notificaciones": notificaciones},
        )
    finally:
        conn.close()


@router.get(
    "/notificaciones/completar/{notificacion_id}",
    name="completar_notificacion",
)
async def completar_notificacion(
    request: Request,
    notificacion_id: int,
    session=Depends(staff_required),
):
    conn = get_db()

    try:
        donde, params = filtro_nombres(conn, session, "residente")
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE notificaciones
                SET estado = 'Completada'
                WHERE id = %s AND {donde}
                """,
                (notificacion_id, *params),
            )

        conn.commit()
        flash(request, "Alerta marcada como completada.", "exito")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return RedirectResponse(
        request.url_for("lista_notificaciones"),
        status_code=303,
    )


@router.get(
    "/notificaciones/eliminar/{notificacion_id}",
    name="eliminar_notificacion",
)
async def eliminar_notificacion(
    request: Request,
    notificacion_id: int,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM notificaciones WHERE id = %s",
                (notificacion_id,),
            )

        conn.commit()
        flash(request, "Alerta eliminada.", "exito")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return RedirectResponse(
        request.url_for("lista_notificaciones"),
        status_code=303,
    )


# ==========================================================
# ALERTA EMERGENTE (ventana + sonido) — RF05
# ==========================================================
# base.html consulta esta ruta periódicamente mientras el
# personal tiene la sesión abierta. Cuando hay una alerta
# pendiente de mostrarse, se devuelve para activar la ventana
# emergente y el sonido.
#
# Al cerrar la ventana, se marca mostrada = 1 para evitar
# que la misma alerta vuelva a aparecer.


@router.get(
    "/notificaciones/emergente",
    name="notificacion_emergente",
)
async def notificacion_emergente(request: Request):
    if request.session.get("rol") not in STAFF_ROLES or not sesion_operativa(
        request.session
    ):
        return JSONResponse({"activa": False})

    conn = get_db()

    try:
        donde, params = filtro_nombres(conn, request.session, "residente")
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT *
                FROM notificaciones
                WHERE mostrada = 0 AND {donde}
                ORDER BY fecha, hora, id
                LIMIT 1
                """,
                params,
            )
            alerta = cursor.fetchone()
    finally:
        conn.close()

    if not alerta:
        return JSONResponse({"activa": False})

    return JSONResponse({
        "activa": True,
        "id": alerta["id"],
        "residente": alerta["residente"],
        "tipo": alerta["tipo"],
        "detalle": alerta["detalle"] or "",
        "fecha": str(alerta["fecha"]),
        "hora": str(alerta["hora"]),
    })


@router.post(
    "/notificaciones/emergente/{notificacion_id}/cerrar",
    name="cerrar_notificacion_emergente",
)
async def cerrar_notificacion_emergente(
    request: Request,
    notificacion_id: int,
):
    if request.session.get("rol") not in STAFF_ROLES or not sesion_operativa(
        request.session
    ):
        return JSONResponse({"ok": False}, status_code=403)

    conn = get_db()

    try:
        donde, params = filtro_nombres(conn, request.session, "residente")
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE notificaciones
                SET mostrada = 1
                WHERE id = %s AND {donde}
                """,
                (notificacion_id, *params),
            )

        conn.commit()
        return JSONResponse({"ok": True})

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
