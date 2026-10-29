
"""
USUARIOS (solo Administrador)
Compatible con MySQL mediante PyMySQL.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from core.auth import admin_required
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/usuarios", name="lista_usuarios")
async def lista_usuarios(
    request: Request,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                """
                SELECT id, username, nombre, correo, rol
                FROM usuarios
                ORDER BY nombre
                """
            )
            usuarios = c.fetchall()
    finally:
        conn.close()

    return render(
        request,
        "usuarios/lista.html",
        {"usuarios": usuarios},
    )


@router.get("/usuarios/eliminar/{uid}", name="eliminar_usuario")
async def eliminar_usuario(
    request: Request,
    uid: int,
    session=Depends(admin_required),
):
    if uid == session["user_id"]:
        flash(request, "No puedes eliminar tu propia cuenta.", "error")
        return RedirectResponse(
            request.url_for("lista_usuarios"),
            status_code=303,
        )

    conn = get_db()

    try:
        with conn.cursor() as c:
            # Un cuidador tiene su registro de personal (y sus asignaciones,
            # que se borran en cascada) y puede tener códigos de recuperación.
            c.execute("DELETE FROM personal WHERE usuario_id = %s", (uid,))
            c.execute(
                "DELETE FROM codigos_verificacion WHERE usuario_id = %s",
                (uid,),
            )
            c.execute(
                "DELETE FROM usuarios WHERE id = %s",
                (uid,),
            )
            eliminado = c.rowcount > 0

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    if eliminado:
        flash(request, "Usuario eliminado.", "exito")
    else:
        flash(request, "No se encontró ese usuario.", "error")

    return RedirectResponse(
        request.url_for("lista_usuarios"),
        status_code=303,
    )
