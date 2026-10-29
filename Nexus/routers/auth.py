
"""
AUTH — login, registro y logout.
Compatible con MySQL mediante PyMySQL.
"""

import re
from datetime import datetime, timedelta

import pymysql
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from core.auth import MENSAJE_CUENTA_INACTIVA, cuidador_activo, home_url_for
from core.config import CODIGO_VERIFICACION_MINUTOS, ROLES_AUTORREGISTRO
from core.email import enviar_codigo_verificacion
from core.security import generar_codigo_verificacion, hash_password
from core.templates import flash, render
from database.connection import get_db

router = APIRouter()


@router.get("/", name="index")
async def index(request: Request):
    if "user_id" in request.session:
        return RedirectResponse(
            home_url_for(request, request.session.get("rol")),
            status_code=303,
        )
    return RedirectResponse(request.url_for("login"), status_code=303)


@router.get("/login", name="login")
async def login_form(request: Request):
    if "user_id" in request.session:
        return RedirectResponse(
            home_url_for(request, request.session.get("rol")),
            status_code=303,
        )
    return render(request, "login.html")


@router.post("/login")
async def login_submit(request: Request):
    if "user_id" in request.session:
        return RedirectResponse(
            home_url_for(request, request.session.get("rol")),
            status_code=303,
        )

    form = await request.form()
    username = form.get("username", "").strip()
    password = hash_password(form.get("password", ""))

    conn = get_db()
    try:
        with conn.cursor() as c:
            c.execute(
                """
                SELECT *
                FROM usuarios
                WHERE username = %s AND password = %s
                """,
                (username, password),
            )
            user = c.fetchone()
    finally:
        conn.close()

    if user and user["rol"] == "Cuidador" and not cuidador_activo(user["id"]):
        flash(request, MENSAJE_CUENTA_INACTIVA, "error")
        return render(request, "login.html", {"form_username": username})

    if user:
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        request.session["rol"] = user["rol"]
        request.session["nombre"] = user["nombre"]

        return RedirectResponse(
            home_url_for(request, user["rol"]),
            status_code=303,
        )

    flash(request, "Usuario o contraseña incorrectos.", "error")
    return render(request, "login.html", {"form_username": username})


@router.get("/registro", name="registro")
async def registro_form(request: Request):
    if "user_id" in request.session:
        return RedirectResponse(
            home_url_for(request, request.session.get("rol")),
            status_code=303,
        )
    return render(request, "registro.html", {"datos": {}})


@router.post("/registro")
async def registro_submit(request: Request):
    if "user_id" in request.session:
        return RedirectResponse(
            home_url_for(request, request.session.get("rol")),
            status_code=303,
        )

    form = await request.form()
    nombre = form.get("nombre", "").strip()
    username = form.get("username", "").strip()
    correo = form.get("correo", "").strip()
    password = form.get("password", "")
    confirmar = form.get("confirmar", "")
    rol = form.get("rol", "Cuidador")

    # El registro público nunca permite crear administradores.
    errores = []

    if not nombre:
        errores.append("El nombre completo es obligatorio.")

    if not username or len(username) < 4:
        errores.append("El usuario debe tener al menos 4 caracteres.")

    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        errores.append(
            "El usuario solo puede contener letras, números y guión bajo."
        )

    if correo and not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", correo):
        errores.append("El correo electrónico no es válido.")

    if len(password) < 6:
        errores.append("La contraseña debe tener al menos 6 caracteres.")

    if password != confirmar:
        errores.append("Las contraseñas no coinciden.")

    if rol not in ROLES_AUTORREGISTRO:
        errores.append("Rol no válido.")

    if errores:
        for error in errores:
            flash(request, error, "error")
        return render(request, "registro.html", {"datos": form})

    hashed = hash_password(password)
    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                """
                INSERT INTO usuarios
                    (username, password, rol, nombre, correo)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, hashed, rol, nombre, correo or None),
            )

            # Un cuidador nace activo y con sus permisos: se crea de una vez
            # su registro de personal vinculado a la cuenta. Sin asignaciones
            # no ve residentes hasta que el administrador se los asigne.
            if rol == "Cuidador":
                c.execute(
                    """
                    INSERT INTO personal
                        (nombre, correo, telefono, turno, activo, usuario_id)
                    VALUES (%s, %s, NULL, NULL, 1, %s)
                    """,
                    (nombre, correo or None, c.lastrowid),
                )
        conn.commit()

    except pymysql.err.IntegrityError as e:
        conn.rollback()

        if "username" in str(e).lower():
            flash(request, "Ese nombre de usuario ya está en uso.", "error")
        else:
            flash(
                request,
                "Error al crear la cuenta. Intenta de nuevo.",
                "error",
            )

        return render(request, "registro.html", {"datos": form})

    finally:
        conn.close()

    flash(request, "Cuenta creada exitosamente.", "exito")
    return RedirectResponse(request.url_for("login"), status_code=303)


@router.get("/logout", name="logout")
async def logout(request: Request):
    request.session.clear()
    flash(request, "Sesión cerrada correctamente.", "exito")
    return RedirectResponse(request.url_for("login"), status_code=303)


# RECUPERACIÓN DE CONTRASEÑA


@router.get("/password", name="cambiar_password")
async def cambiar_password_form(request: Request):
    request.session.pop("reset_usuario_id", None)
    request.session.pop("reset_correo", None)

    return render(request, "password.html", {"paso": "correo"})


def _generar_y_enviar_codigo(usuario) -> None:
    """Genera un código nuevo e invalida los códigos anteriores."""

    conn = get_db()

    try:
        codigo = generar_codigo_verificacion()
        ahora = datetime.now()
        expira = ahora + timedelta(minutes=CODIGO_VERIFICACION_MINUTOS)

        with conn.cursor() as c:
            c.execute(
                """
                UPDATE codigos_verificacion
                SET usado = 1
                WHERE usuario_id = %s AND usado = 0
                """,
                (usuario["id"],),
            )

            c.execute(
                """
                INSERT INTO codigos_verificacion
                    (usuario_id, codigo, creado, expira, usado)
                VALUES (%s, %s, %s, %s, 0)
                """,
                (
                    usuario["id"],
                    codigo,
                    ahora.isoformat(),
                    expira.isoformat(),
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    enviar_codigo_verificacion(
        usuario["correo"],
        usuario["nombre"] or usuario["username"],
        codigo,
    )


@router.post("/password", name="cambiar_password_solicitar")
async def cambiar_password_solicitar(request: Request):
    form = await request.form()
    correo = form.get("correo", "").strip().lower()

    if not correo:
        flash(request, "Ingresa tu correo electrónico.", "error")
        return render(request, "password.html", {"paso": "correo"})

    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT * FROM usuarios WHERE LOWER(correo) = %s",
                (correo,),
            )
            usuario = c.fetchone()
    finally:
        conn.close()

    # El mensaje no revela si el correo está registrado.
    if usuario and usuario["correo"]:
        _generar_y_enviar_codigo(usuario)
        request.session["reset_usuario_id"] = usuario["id"]
    else:
        request.session.pop("reset_usuario_id", None)

    request.session["reset_correo"] = correo

    flash(request, "Te enviamos un código de verificación.", "exito")
    return render(
        request,
        "password.html",
        {"paso": "codigo", "form_correo": correo},
    )


@router.post("/password/reenviar", name="cambiar_password_reenviar")
async def cambiar_password_reenviar(request: Request):
    correo = request.session.get("reset_correo", "")
    usuario_id = request.session.get("reset_usuario_id")

    if usuario_id:
        conn = get_db()
        try:
            with conn.cursor() as c:
                c.execute(
                    "SELECT * FROM usuarios WHERE id = %s",
                    (usuario_id,),
                )
                usuario = c.fetchone()
        finally:
            conn.close()

        if usuario:
            _generar_y_enviar_codigo(usuario)

    flash(request, "Te enviamos un nuevo código a tu correo.", "exito")
    return render(
        request,
        "password.html",
        {"paso": "codigo", "form_correo": correo},
    )


@router.post("/password/verificar", name="cambiar_password_verificar")
async def cambiar_password_verificar(request: Request):
    form = await request.form()
    correo = form.get("correo", "").strip().lower()
    codigo = form.get("codigo", "").strip()
    password = form.get("password", "")
    confirmar = form.get("confirmar", "")

    contexto = {"paso": "codigo", "form_correo": correo}

    usuario_id = request.session.get("reset_usuario_id")

    if not usuario_id or correo != request.session.get("reset_correo", ""):
        flash(
            request,
            "La solicitud expiró. Ingresa tu correo nuevamente.",
            "error",
        )
        request.session.pop("reset_usuario_id", None)
        request.session.pop("reset_correo", None)
        return render(request, "password.html", {"paso": "correo"})

    if not codigo or not password:
        flash(request, "Todos los campos son obligatorios.", "error")
        return render(request, "password.html", contexto)

    if len(password) < 6:
        flash(request, "La contraseña debe tener al menos 6 caracteres.", "error")
        return render(request, "password.html", contexto)

    if password != confirmar:
        flash(request, "Las contraseñas no coinciden.", "error")
        return render(request, "password.html", contexto)

    conn = get_db()

    try:
        with conn.cursor() as c:
            c.execute(
                """
                SELECT *
                FROM codigos_verificacion
                WHERE usuario_id = %s
                  AND codigo = %s
                  AND usado = 0
                """,
                (usuario_id, codigo),
            )
            fila = c.fetchone()

            if not fila or datetime.fromisoformat(fila["expira"]) < datetime.now():
                conn.rollback()
                flash(request, "Código incorrecto o expirado.", "error")
                return render(request, "password.html", contexto)

            password_hash = hash_password(password)

            c.execute(
                "UPDATE usuarios SET password = %s WHERE id = %s",
                (password_hash, usuario_id),
            )
            c.execute(
                "UPDATE codigos_verificacion SET usado = 1 WHERE id = %s",
                (fila["id"],),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    request.session.pop("reset_usuario_id", None)
    request.session.pop("reset_correo", None)

    flash(request, "Contraseña cambiada correctamente.", "exito")
    return RedirectResponse(request.url_for("login"), status_code=303)
