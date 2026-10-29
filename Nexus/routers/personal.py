
"""
PERSONAL Y ASIGNACIONES DE RESIDENTES
Gestión compatible con MySQL.
"""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.itinerario import ruta_personal
from core.auth import admin_required, staff_required
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


# ---------------------------------------------------------
# FUNCIONES AUXILIARES MYSQL
# ---------------------------------------------------------

def consultar_uno(conn, consulta, parametros=()):
    with conn.cursor() as cursor:
        cursor.execute(consulta, parametros)
        return cursor.fetchone()


def consultar_todos(conn, consulta, parametros=()):
    with conn.cursor() as cursor:
        cursor.execute(consulta, parametros)
        return cursor.fetchall()


def ejecutar(conn, consulta, parametros=()):
    with conn.cursor() as cursor:
        cursor.execute(consulta, parametros)
        return cursor.rowcount


def obtener_cuentas_cuidador(conn, personal_id=None):
    """Cuentas de cuidador que no estén vinculadas a otro registro."""
    return consultar_todos(
        conn,
        """
        SELECT u.id, u.username, u.nombre
        FROM usuarios u
        WHERE u.rol = 'Cuidador'
          AND (
              NOT EXISTS (
                  SELECT 1
                  FROM personal p
                  WHERE p.usuario_id = u.id
              )
              OR EXISTS (
                  SELECT 1
                  FROM personal p
                  WHERE p.usuario_id = u.id
                    AND p.id = %s
              )
          )
        ORDER BY u.nombre
        """,
        (personal_id if personal_id is not None else -1,),
    )


# ---------------------------------------------------------
# LISTA DEL PERSONAL
# ---------------------------------------------------------

@router.get("/personal", name="lista_personal")
async def lista_personal(
    request: Request,
    session=Depends(staff_required),
):
    conn = get_db()

    try:
        if session.get("rol") != "Administrador":
            propio = consultar_uno(
                conn,
                "SELECT id FROM personal WHERE usuario_id = %s",
                (session["user_id"],),
            )

            if not propio:
                flash(
                    request,
                    "Tu cuenta no está vinculada a un registro de personal. "
                    "Contacta al administrador.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("dashboard"),
                    status_code=303,
                )

            return RedirectResponse(
                request.url_for("detalle_personal", personal_id=propio["id"]),
                status_code=303,
            )

        personal = consultar_todos(
            conn,
            "SELECT * FROM personal ORDER BY nombre",
        )
    finally:
        conn.close()

    return render(
        request,
        "personal/lista.html",
        {
            "personal": personal,
            "es_admin": session.get("rol") == "Administrador",
        },
    )


# ---------------------------------------------------------
# REGISTRAR PERSONAL
# ---------------------------------------------------------

@router.get("/personal/registrar", name="registrar_personal")
async def registrar_personal_form(
    request: Request,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        usuarios = obtener_cuentas_cuidador(conn)
    finally:
        conn.close()

    return render(
        request,
        "personal/form.html",
        {
            "datos": {},
            "editando": False,
            "usuarios": usuarios,
        },
    )


@router.post(
    "/personal/registrar",
    name="registrar_personal_submit",
)
async def registrar_personal_submit(
    request: Request,
    session=Depends(admin_required),
):
    form = await request.form()

    nombre = form.get("nombre", "").strip()
    turno = form.get("turno", "").strip()
    usuario_id = form.get("usuario_id") or None

    if not nombre or turno not in ("Mañana", "Tarde", "Noche"):
        flash(request, "Verifica el nombre y el turno.", "error")
        return RedirectResponse(
            request.url_for("registrar_personal"),
            status_code=303,
        )

    try:
        usuario_id_num = int(usuario_id) if usuario_id else None
    except (TypeError, ValueError):
        flash(request, "La cuenta seleccionada no es válida.", "error")
        return RedirectResponse(
            request.url_for("registrar_personal"),
            status_code=303,
        )

    conn = get_db()

    try:
        if usuario_id_num is not None:
            cuenta = consultar_uno(
                conn,
                """
                SELECT id
                FROM usuarios
                WHERE id = %s AND rol = 'Cuidador'
                """,
                (usuario_id_num,),
            )

            vinculada = consultar_uno(
                conn,
                "SELECT id FROM personal WHERE usuario_id = %s",
                (usuario_id_num,),
            )

            if not cuenta or vinculada:
                flash(
                    request,
                    "La cuenta seleccionada no es válida o ya está vinculada.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("registrar_personal"),
                    status_code=303,
                )

        ejecutar(
            conn,
            """
            INSERT INTO personal
                (nombre, correo, telefono, turno, activo, usuario_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                nombre,
                form.get("correo", "").strip(),
                form.get("telefono", "").strip(),
                turno,
                1 if form.get("activo", "1") == "1" else 0,
                usuario_id_num,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash(request, "Personal registrado exitosamente.", "exito")
    return RedirectResponse(
        request.url_for("lista_personal"),
        status_code=303,
    )


# ---------------------------------------------------------
# EDITAR PERSONAL
# ---------------------------------------------------------

@router.get("/personal/editar/{personal_id}", name="editar_personal")
async def editar_personal_form(
    request: Request,
    personal_id: int,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        personal = consultar_uno(
            conn,
            "SELECT * FROM personal WHERE id = %s",
            (personal_id,),
        )

        if not personal:
            flash(
                request,
                "Miembro del personal no encontrado.",
                "error",
            )
            return RedirectResponse(
                request.url_for("lista_personal"),
                status_code=303,
            )

        usuarios = obtener_cuentas_cuidador(conn, personal_id)

    finally:
        conn.close()

    return render(
        request,
        "personal/form.html",
        {
            "datos": dict(personal),
            "editando": True,
            "personal_id": personal_id,
            "usuarios": usuarios,
        },
    )


@router.post("/personal/editar/{personal_id}")
async def editar_personal_submit(
    request: Request,
    personal_id: int,
    session=Depends(admin_required),
):
    form = await request.form()

    nombre = form.get("nombre", "").strip()
    turno = form.get("turno", "").strip()
    usuario_id = form.get("usuario_id") or None

    if not nombre or turno not in ("Mañana", "Tarde", "Noche"):
        flash(request, "Verifica el nombre y el turno.", "error")
        return RedirectResponse(
            request.url_for("editar_personal", personal_id=personal_id),
            status_code=303,
        )

    try:
        usuario_id_num = int(usuario_id) if usuario_id else None
    except (TypeError, ValueError):
        flash(request, "La cuenta seleccionada no es válida.", "error")
        return RedirectResponse(
            request.url_for("editar_personal", personal_id=personal_id),
            status_code=303,
        )

    conn = get_db()

    try:
        actual = consultar_uno(
            conn,
            "SELECT id FROM personal WHERE id = %s",
            (personal_id,),
        )

        if not actual:
            flash(
                request,
                "Miembro del personal no encontrado.",
                "error",
            )
            return RedirectResponse(
                request.url_for("lista_personal"),
                status_code=303,
            )

        if usuario_id_num is not None:
            cuenta = consultar_uno(
                conn,
                """
                SELECT id
                FROM usuarios
                WHERE id = %s AND rol = 'Cuidador'
                """,
                (usuario_id_num,),
            )

            vinculada = consultar_uno(
                conn,
                """
                SELECT id
                FROM personal
                WHERE usuario_id = %s AND id != %s
                """,
                (usuario_id_num, personal_id),
            )

            if not cuenta or vinculada:
                flash(
                    request,
                    "La cuenta seleccionada no es válida o ya está vinculada.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for(
                        "editar_personal",
                        personal_id=personal_id,
                    ),
                    status_code=303,
                )

        ejecutar(
            conn,
            """
            UPDATE personal
            SET nombre = %s,
                correo = %s,
                telefono = %s,
                turno = %s,
                activo = %s,
                usuario_id = %s
            WHERE id = %s
            """,
            (
                nombre,
                form.get("correo", "").strip(),
                form.get("telefono", "").strip(),
                turno,
                1 if form.get("activo", "1") == "1" else 0,
                usuario_id_num,
                personal_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash(request, "Personal actualizado correctamente.", "exito")
    return RedirectResponse(
        request.url_for("lista_personal"),
        status_code=303,
    )


# ---------------------------------------------------------
# ELIMINAR PERSONAL
# ---------------------------------------------------------

@router.get(
    "/personal/eliminar/{personal_id}",
    name="eliminar_personal",
)
async def eliminar_personal(
    request: Request,
    personal_id: int,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        personal = consultar_uno(
            conn,
            "SELECT id FROM personal WHERE id = %s",
            (personal_id,),
        )

        if not personal:
            flash(
                request,
                "Miembro del personal no encontrado.",
                "error",
            )
            return RedirectResponse(
                request.url_for("lista_personal"),
                status_code=303,
            )

        ejecutar(
            conn,
            "DELETE FROM personal WHERE id = %s",
            (personal_id,),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    flash(request, "Personal eliminado.", "exito")
    return RedirectResponse(
        request.url_for("lista_personal"),
        status_code=303,
    )


# ---------------------------------------------------------
# PANEL DEL PERSONAL
# ---------------------------------------------------------

@router.get("/personal/{personal_id}", name="detalle_personal")
async def detalle_personal(
    request: Request,
    personal_id: int,
    session=Depends(staff_required),
):
    conn = get_db()

    try:
        personal = consultar_uno(
            conn,
            "SELECT * FROM personal WHERE id = %s",
            (personal_id,),
        )

        if not personal:
            flash(
                request,
                "Miembro del personal no encontrado.",
                "error",
            )
            return RedirectResponse(
                request.url_for("lista_personal"),
                status_code=303,
            )

        es_admin = session.get("rol") == "Administrador"

        # Un cuidador solo puede consultar su propio panel.
        if (
            not es_admin
            and personal["usuario_id"] != session["user_id"]
        ):
            flash(
                request,
                "No tienes permiso para consultar ese panel.",
                "error",
            )
            return RedirectResponse(
                request.url_for("dashboard"),
                status_code=303,
            )

        hoy = date.today()

        # Ruta del día: una entrada por hora de cada medicamento/actividad.
        eventos = ruta_personal(conn, personal_id, hoy)
        hoy = hoy.isoformat()

    finally:
        conn.close()

    return render(
        request,
        "personal/panel.html",
        {
            "personal": personal,
            "eventos": eventos,
            "hechos": sum(1 for e in eventos if e["completado"]),
            "puede_marcar": True,
            "hoy": hoy,
        },
    )
