"""
MEDICAMENTOS
Lista de residentes -> "Agregar medicamento" (pantalla central de creación de
la agenda: categoría -> medicamento, varias horas, varios días) o "Ver
medicamentos" (lo programado de hoy en adelante).
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.acceso import filtro_ids, puede_ver_residente
from core.auth import staff_required
from core.itinerario import listado
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/medicamentos", name="lista_medicamentos")
async def lista_medicamentos(request: Request, session=Depends(staff_required)):
    conn = get_db()
    try:
        donde, params = filtro_ids(conn, session, "id")
        with conn.cursor() as c:
            c.execute(f"SELECT * FROM residentes WHERE {donde} ORDER BY nombre", params)
            residentes = c.fetchall()
    finally:
        conn.close()
    return render(request, "medicamentos/lista.html", {"residentes": residentes})


@router.get("/medicamentos/{residente_id}", name="detalle_medicamentos")
async def detalle_medicamentos(request: Request, residente_id: int, session=Depends(staff_required)):
    conn = get_db()
    try:
        with conn.cursor() as c:
            c.execute("SELECT * FROM residentes WHERE id = %s", (residente_id,))
            residente = c.fetchone()
        if not residente or not puede_ver_residente(conn, session, residente_id):
            flash(request, "Residente no encontrado.", "error")
            return RedirectResponse(request.url_for("lista_medicamentos"), status_code=303)
        medicamentos = listado(conn, residente_id, "medicamento")
    finally:
        conn.close()
    return render(request, "medicamentos/detalle.html",
                  {"residente": residente, "medicamentos": medicamentos})


@router.get("/medicamentos/{residente_id}/agregar", name="nuevo_medicamento")
async def nuevo_medicamento(request: Request, residente_id: int, session=Depends(staff_required)):
    return RedirectResponse(
        request.url_for("agenda_crear", residente_id=residente_id).include_query_params(tab="medicamento"),
        status_code=303)
