"""
AGENDA (calendario tipo Google Calendar + itinerario diario)

- Ver:    los 3 roles (cada uno con sus permisos).
- Marcar ✓/✗ y observaciones del día: Administrador y Cuidador.
- Crear:  Administrador y Cuidador, desde la pantalla "Crear".
Los datos y endpoints JSON están en routers/itinerario.py.
"""
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.acceso import filtro_ids
from core.agenda import puede_editar_agenda, puede_ver_agenda, semanas_del_mes
from core.auth import login_required, staff_required
from core.itinerario import resumen_mes
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _uno(conn, sql, params=()):
    with conn.cursor() as c:
        c.execute(sql, params)
        return c.fetchone()


@router.get("/agenda", name="agenda_inicio")
async def agenda_inicio(request: Request, session=Depends(login_required)):
    conn = get_db()
    try:
        with conn.cursor() as c:
            if session.get("rol") == "Familiar":
                c.execute(
                    "SELECT * FROM residentes WHERE LOWER(familiar_username) = LOWER(%s) ORDER BY nombre",
                    ((session.get("username") or "").strip(),),
                )
            else:
                donde, params = filtro_ids(conn, session, "id")
                c.execute(f"SELECT * FROM residentes WHERE {donde} ORDER BY nombre", params)
            residentes = c.fetchall()
    finally:
        conn.close()

    if len(residentes) == 1:
        return RedirectResponse(
            request.url_for("agenda_residente", residente_id=residentes[0]["id"]), status_code=303)
    return render(request, "agenda/lista.html", {"residentes": residentes})


@router.get("/agenda/{residente_id}", name="agenda_residente")
async def agenda_residente(request: Request, residente_id: int, mes: str = "", dia: str = "",
                           session=Depends(login_required)):
    hoy = date.today()
    try:
        anio, m = (int(x) for x in (mes or hoy.strftime("%Y-%m")).split("-"))
        date(anio, m, 1)
    except ValueError:
        anio, m = hoy.year, hoy.month

    conn = get_db()
    try:
        if not puede_ver_agenda(conn, session, residente_id):
            flash(request, "No tienes acceso a la agenda de ese residente.", "error")
            return RedirectResponse(request.url_for("agenda_inicio"), status_code=303)
        residente = _uno(conn, "SELECT * FROM residentes WHERE id = %s", (residente_id,))
        resumen = resumen_mes(conn, residente_id, anio, m)
        editable = puede_editar_agenda(conn, session, residente_id)
    finally:
        conn.close()

    ant = (anio - 1, 12) if m == 1 else (anio, m - 1)
    sig = (anio + 1, 1) if m == 12 else (anio, m + 1)
    return render(request, "agenda/calendario.html", {
        "residente": residente,
        "semanas": semanas_del_mes(anio, m),
        "resumen": resumen,
        "titulo_mes": f"{MESES[m - 1]} {anio}",
        "mes_ant": f"{ant[0]}-{ant[1]:02d}",
        "mes_sig": f"{sig[0]}-{sig[1]:02d}",
        "hoy": hoy,
        "dia_abrir": dia,
        "editable": editable,
    })


@router.get("/agenda/{residente_id}/crear", name="agenda_crear")
async def agenda_crear(request: Request, residente_id: int, tab: str = "medicamento",
                       session=Depends(staff_required)):
    conn = get_db()
    try:
        if not puede_editar_agenda(conn, session, residente_id):
            flash(request, "Ese residente no está asignado a tu cuenta.", "error")
            return RedirectResponse(request.url_for("agenda_inicio"), status_code=303)
        residente = _uno(conn, "SELECT * FROM residentes WHERE id = %s", (residente_id,))
        with conn.cursor() as c:
            c.execute("SELECT id, nombre FROM personal WHERE activo = 1 ORDER BY nombre")
            personal = c.fetchall()
    finally:
        conn.close()
    return render(request, "agenda/crear.html", {
        "residente": residente,
        "tab": tab if tab in ("medicamento", "actividad") else "medicamento",
        "hoy": date.today().isoformat(),
        "fechas_sel": "",
        "personal": personal,
    })
