"""
Itinerario diario + catálogos en cascada.
Reutiliza los helpers que ya existen en el proyecto (core.agenda, core.auth).
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

from core.acceso import nombre_para_registro
from core.agenda import puede_editar_agenda, puede_ver_agenda
from core.auth import login_required, staff_required
from core.itinerario import (
    TIPOS, categorias, detalle_entrada, dia, eliminar, fechas_validas, guardar,
    horas_validas, item_existe, items_de_categoria, marcar,
)
from core.templates import flash
from database.connection import get_db
from routers.historial import registrar_en_historial

router = APIRouter()


def _err(msg, code=400):
    return JSONResponse({"ok": False, "error": msg}, status_code=code)


# ----------- Cascada: Categoría -> Medicamento / Actividad -----------
@router.get("/api/catalogo/{tipo}/categorias")
async def api_categorias(tipo: str, session=Depends(staff_required)):
    if tipo not in TIPOS:
        return _err("Tipo no válido.", 404)
    conn = get_db()
    try:
        return {"ok": True, "items": categorias(conn, tipo)}
    finally:
        conn.close()


@router.get("/api/catalogo/{tipo}/items")
async def api_items(tipo: str, categoria_id: int, session=Depends(staff_required)):
    if tipo not in TIPOS:
        return _err("Tipo no válido.", 404)
    conn = get_db()
    try:
        return {"ok": True, "items": items_de_categoria(conn, tipo, categoria_id)}
    finally:
        conn.close()


# ----------- Guardar (varias horas, varios días, 1 fila por día) -----------
@router.post("/itinerario/{residente_id}/guardar", name="itinerario_guardar")
async def itinerario_guardar(request: Request, residente_id: int, session=Depends(staff_required)):
    f = await request.form()
    tipo = f.get("tipo", "")
    if tipo not in TIPOS:
        return _err("Tipo no válido.")
    if not (f.get("categoria_id", "").isdigit() and f.get("item_id", "").isdigit()):
        return _err("Elige la categoría y el elemento.")
    horas, e1 = horas_validas(f.getlist("horas"))
    fechas, e2 = fechas_validas(f.get("fechas", ""))
    dosis = (f.get("dosis") or "").strip()[:100]
    if e1 or e2:
        return _err(e1 or e2)
    if tipo == "medicamento" and not dosis:
        return _err("Completa la dosis.")

    conn = get_db()
    try:
        if not puede_editar_agenda(conn, session, residente_id):
            return _err("Ese residente no está asignado a tu cuenta.", 403)
        if not item_existe(conn, tipo, int(f["item_id"]), int(f["categoria_id"])):
            return _err("El elemento no pertenece a esa categoría.")
        personal_id = None
        if session.get("rol") == "Administrador":
            if (f.get("personal_id") or "").isdigit():
                personal_id = int(f["personal_id"])
        else:
            with conn.cursor() as c:
                c.execute("SELECT id FROM personal WHERE usuario_id=%s AND activo=1", (session["user_id"],))
                p = c.fetchone()
            personal_id = p["id"] if p else None
        guardar(conn, residente_id=residente_id, fechas=fechas, tipo=tipo,
                item_id=int(f["item_id"]), horas=horas,
                dosis=dosis if tipo == "medicamento" else None,
                observaciones=(f.get("observaciones") or "").strip() or None,
                personal_id=personal_id, creado_por=session["user_id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"ok": True}


# ----------- Día del calendario (SOLO LECTURA) -----------
@router.get("/itinerario/{residente_id}/dia/{fecha}")
async def itinerario_dia(residente_id: int, fecha: str, session=Depends(login_required)):
    try:
        d = date.fromisoformat(fecha)
    except ValueError:
        return _err("Fecha no válida.")
    conn = get_db()
    try:
        if not puede_ver_agenda(conn, session, residente_id):
            return _err("Sin acceso.", 403)
        with conn.cursor() as c:
            c.execute("SELECT texto FROM itinerario_observaciones WHERE residente_id=%s AND fecha=%s",
                      (residente_id, d))
            o = c.fetchone()
        return {"ok": True, "fecha": fecha, "items": dia(conn, residente_id, d),
                "observaciones": o["texto"] if o else "",
                "editable": puede_editar_agenda(conn, session, residente_id)}
    finally:
        conn.close()


# ----------- ✓ / ✗ (panel del personal y calendario) -----------
@router.post("/itinerario/{itinerario_id}/check")
async def itinerario_check(request: Request, itinerario_id: int, session=Depends(staff_required)):
    f = await request.form()
    hora, estado = f.get("hora", ""), f.get("estado")
    if estado not in ("completado", "pendiente"):
        return _err("Estado no válido.")
    conn = get_db()
    try:
        with conn.cursor() as c:
            c.execute("SELECT residente_id FROM itinerario_diario WHERE id=%s", (itinerario_id,))
            fila = c.fetchone()
        if not fila or not puede_editar_agenda(conn, session, fila["residente_id"]):
            return _err("No tienes permiso.", 403)
        if not marcar(conn, itinerario_id, hora, estado == "completado", session["user_id"]):
            return _err("Esa hora no existe en el itinerario.")
        if estado == "completado":
            d = detalle_entrada(conn, itinerario_id)
            registrar_en_historial(
                conn, fecha=d["fecha"].isoformat(), hora=datetime.now().strftime("%H:%M"),
                tipo="Medicamento" if d["tipo"] == "medicamento" else "Actividad",
                actividad=f"Realizado: {d['nombre']} ({hora})", residente=d["residente"],
                cuidador=nombre_para_registro(conn, session))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "estado": estado}


# ----------- Observaciones generales del día (textarea grande) -----------
@router.post("/itinerario/{residente_id}/{fecha}/observaciones")
async def itinerario_obs(request: Request, residente_id: int, fecha: str,
                         session=Depends(staff_required)):
    texto = ((await request.form()).get("texto") or "").strip()[:5000]
    try:
        d = date.fromisoformat(fecha)
    except ValueError:
        return _err("Fecha no válida.")
    conn = get_db()
    try:
        if not puede_editar_agenda(conn, session, residente_id):
            return _err("No tienes permiso.", 403)
        with conn.cursor() as c:
            if texto:
                c.execute("INSERT INTO itinerario_observaciones (residente_id, fecha, texto, actualizado_por) "
                          "VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE texto=VALUES(texto), "
                          "actualizado_por=VALUES(actualizado_por)",
                          (residente_id, d, texto, session["user_id"]))
            else:
                c.execute("DELETE FROM itinerario_observaciones WHERE residente_id=%s AND fecha=%s",
                          (residente_id, d))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


# ----------- Eliminar (solo desde los módulos de creación, no desde el itinerario) -----------
@router.post("/itinerario/{residente_id}/eliminar", name="itinerario_eliminar")
async def itinerario_eliminar(request: Request, residente_id: int, session=Depends(staff_required)):
    f = await request.form()
    destino = f.get("volver") or str(request.url_for("agenda_inicio"))
    if not destino.startswith("/"):                       # evita redirecciones a otros sitios
        destino = str(request.url_for("agenda_inicio"))
    conn = get_db()
    try:
        if session.get("rol") != "Administrador" or not puede_editar_agenda(conn, session, residente_id):
            flash(request, "Solo el administrador puede eliminar.", "error")
            return RedirectResponse(destino, status_code=303)
        n = eliminar(conn, residente_id, (f.get("ids") or "").split(","))
        conn.commit()
    finally:
        conn.close()
    flash(request, "Eliminado del itinerario." if n else "No se encontró.", "exito" if n else "error")
    return RedirectResponse(destino, status_code=303)
