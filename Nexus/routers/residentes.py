
"""
RESIDENTES
Compatible con MySQL mediante PyMySQL.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.acceso import filtro_ids
from core.auth import admin_required, staff_required
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/residentes", name="lista_residentes")
async def lista_residentes(
    request: Request,
    session=Depends(staff_required),
):
    conn = get_db()
    try:
        # El administrador ve todos; el cuidador solo los que tiene asignados.
        donde, params = filtro_ids(conn, session, "id")
        with conn.cursor() as c:
            c.execute(
                f"SELECT * FROM residentes WHERE {donde} ORDER BY nombre",
                params,
            )
            residentes = c.fetchall()
    finally:
        conn.close()

    return render(
        request,
        "residentes/lista.html",
        {"residentes": residentes},
    )


@router.get("/residentes/registrar", name="registrar_residente")
async def registrar_residente_form(
    request: Request,
    session=Depends(admin_required),
):
    return render(
        request,
        "residentes/form.html",
        {"datos": {}, "editando": False},
    )


@router.post("/residentes/registrar")
async def registrar_residente_submit(
    request: Request,
    session=Depends(admin_required),
):
    form = await request.form()
    doc = form.get("documento", "").strip()
    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT id FROM residentes WHERE documento = %s",
                (doc,),
            )
            existing = c.fetchone()

            if existing:
                flash(
                    request,
                    "Ya existe un residente con ese número de documento.",
                    "error",
                )
                return render(
                    request,
                    "residentes/form.html",
                    {"datos": form, "editando": False},
                )

            c.execute(
                """
                INSERT INTO residentes (
                    nombre, documento, edad, fecha_ingreso, habitacion,
                    diagnostico, medicamentos, alergias,
                    familiar_nombre, familiar_parentesco,
                    familiar_telefono, familiar_username
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    form["nombre"],
                    doc,
                    form["edad"],
                    form["fecha_ingreso"],
                    form["habitacion"],
                    form["diagnostico"],
                    form["medicamentos"],
                    form["alergias"],
                    form["familiar_nombre"],
                    form["familiar_parentesco"],
                    form["familiar_telefono"],
                    form.get("familiar_username", "").strip() or None,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash(request, "Residente registrado exitosamente.", "exito")
    return RedirectResponse(
        request.url_for("lista_residentes"),
        status_code=303,
    )


@router.get("/residentes/editar/{residente_id}", name="editar_residente")
async def editar_residente_form(
    request: Request,
    residente_id: int,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT * FROM residentes WHERE id = %s",
                (residente_id,),
            )
            residente = c.fetchone()
    finally:
        conn.close()

    if not residente:
        flash(request, "Residente no encontrado.", "error")
        return RedirectResponse(
            request.url_for("lista_residentes"),
            status_code=303,
        )

    return render(
        request,
        "residentes/form.html",
        {
            "datos": dict(residente),
            "editando": True,
            "residente_id": residente_id,
        },
    )


@router.post("/residentes/editar/{residente_id}")
async def editar_residente_submit(
    request: Request,
    residente_id: int,
    session=Depends(admin_required),
):
    form = await request.form()
    doc = form.get("documento", "").strip()
    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT * FROM residentes WHERE id = %s",
                (residente_id,),
            )
            residente = c.fetchone()

            if not residente:
                flash(request, "Residente no encontrado.", "error")
                return RedirectResponse(
                    request.url_for("lista_residentes"),
                    status_code=303,
                )

            c.execute(
                """
                SELECT id
                FROM residentes
                WHERE documento = %s AND id != %s
                """,
                (doc, residente_id),
            )
            conflict = c.fetchone()

            if conflict:
                flash(
                    request,
                    "Ya existe otro residente con ese número de documento.",
                    "error",
                )
                return render(
                    request,
                    "residentes/form.html",
                    {
                        "datos": form,
                        "editando": True,
                        "residente_id": residente_id,
                    },
                )

            c.execute(
                """
                UPDATE residentes SET
                    nombre = %s,
                    documento = %s,
                    edad = %s,
                    fecha_ingreso = %s,
                    habitacion = %s,
                    diagnostico = %s,
                    medicamentos = %s,
                    alergias = %s,
                    familiar_nombre = %s,
                    familiar_parentesco = %s,
                    familiar_telefono = %s,
                    familiar_username = %s
                WHERE id = %s
                """,
                (
                    form["nombre"],
                    doc,
                    form["edad"],
                    form["fecha_ingreso"],
                    form["habitacion"],
                    form["diagnostico"],
                    form["medicamentos"],
                    form["alergias"],
                    form["familiar_nombre"],
                    form["familiar_parentesco"],
                    form["familiar_telefono"],
                    form.get("familiar_username", "").strip() or None,
                    residente_id,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash(request, "Residente actualizado correctamente.", "exito")
    return RedirectResponse(
        request.url_for("lista_residentes"),
        status_code=303,
    )


@router.get("/residentes/eliminar/{residente_id}", name="eliminar_residente")
async def eliminar_residente(
    request: Request,
    residente_id: int,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                "DELETE FROM residentes WHERE id = %s",
                (residente_id,),
            )
            eliminado = c.rowcount > 0

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    if eliminado:
        flash(request, "Residente eliminado.", "exito")
    else:
        flash(request, "Residente no encontrado.", "error")

    return RedirectResponse(
        request.url_for("lista_residentes"),
        status_code=303,
    )
