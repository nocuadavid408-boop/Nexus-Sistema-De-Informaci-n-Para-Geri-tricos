"""
ACTIVIDAD (antes "Horarios")
Lista de residentes -> "Agregar actividad" (pantalla central de creación de la
agenda: categoría -> actividad, varias horas, varios días) o "Ver actividades".
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.acceso import filtro_ids, puede_ver_residente
from core.auth import staff_required
from core.itinerario import listado
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/horarios", name="horarios")
async def horarios(request: Request, session=Depends(staff_required)):
    conn = get_db()
    try:
        donde, params = filtro_ids(conn, session, "id")
        with conn.cursor() as c:
            c.execute(f"SELECT * FROM residentes WHERE {donde} ORDER BY nombre", params)
            residentes = c.fetchall()
    finally:
        conn.close()
    return render(request, "horarios/index.html", {"residentes": residentes})


@router.get("/horarios/{residente_id}", name="detalle_actividades")
async def detalle_actividades(request: Request, residente_id: int, session=Depends(staff_required)):
    conn = get_db()
    try:
        with conn.cursor() as c:
            c.execute("SELECT * FROM residentes WHERE id = %s", (residente_id,))
            residente = c.fetchone()
        if not residente or not puede_ver_residente(conn, session, residente_id):
            flash(request, "Residente no encontrado.", "error")
            return RedirectResponse(request.url_for("horarios"), status_code=303)
        actividades = listado(conn, residente_id, "actividad")
    finally:
        conn.close()
    return render(request, "horarios/detalle.html",
                  {"residente": residente, "actividades": actividades})


@router.get("/horarios/{residente_id}/agregar", name="nueva_actividad")
async def nueva_actividad(request: Request, residente_id: int, session=Depends(staff_required)):
    return RedirectResponse(
        request.url_for("agenda_crear", residente_id=residente_id).include_query_params(tab="actividad"),
        status_code=303)
