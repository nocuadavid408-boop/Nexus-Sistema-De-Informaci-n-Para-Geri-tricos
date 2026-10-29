
"""
PERFIL DEL USUARIO
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.auth import login_required
from core.security import hash_password
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/perfil", name="perfil")
async def perfil(
    request: Request,
    session=Depends(login_required),
):
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM usuarios WHERE id = %s",
                (session["user_id"],),
            )
            usuario = cursor.fetchone()

        return render(
            request,
            "perfil/perfil.html",
            {"usuario": usuario},
        )
    finally:
        conn.close()


@router.post("/perfil")
async def actualizar_perfil(
    request: Request,
    session=Depends(login_required),
):
    form = await request.form()
    nombre = form.get("nombre")
    correo = form.get("correo")

    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE usuarios
                SET nombre = %s,
                    correo = %s
                WHERE id = %s
                """,
                (nombre, correo, session["user_id"]),
            )

        conn.commit()
        request.session["nombre"] = nombre

        flash(
            request,
            "Perfil actualizado correctamente.",
            "exito",
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return RedirectResponse(
        request.url_for("perfil"),
        status_code=303,
    )


@router.post("/perfil/password")
async def cambiar_password(
    request: Request,
    session=Depends(login_required),
):
    form = await request.form()

    actual = hash_password(form.get("actual", ""))
    nueva = form.get("nueva", "")
    confirmar = form.get("confirmar", "")

    conn = get_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM usuarios WHERE id = %s",
                (session["user_id"],),
            )
            usuario = cursor.fetchone()

            if not usuario:
                flash(
                    request,
                    "No se encontró el usuario.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("perfil"),
                    status_code=303,
                )

            if usuario["password"] != actual:
                flash(
                    request,
                    "La contraseña actual es incorrecta.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("perfil"),
                    status_code=303,
                )

            if not nueva:
                flash(
                    request,
                    "La nueva contraseña no puede estar vacía.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("perfil"),
                    status_code=303,
                )

            if nueva != confirmar:
                flash(
                    request,
                    "Las contraseñas no coinciden.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("perfil"),
                    status_code=303,
                )

            nueva_hash = hash_password(nueva)

            cursor.execute(
                """
                UPDATE usuarios
                SET password = %s
                WHERE id = %s
                """,
                (nueva_hash, session["user_id"]),
            )

        conn.commit()

        flash(
            request,
            "Contraseña actualizada correctamente.",
            "exito",
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return RedirectResponse(
        request.url_for("perfil"),
        status_code=303,
    )
