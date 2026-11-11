"""
Autenticación y control de acceso por rol.

Incluye la excepción/handler usados para redirigir desde dependencias tipo
"login_required" (FastAPI no permite retornar una RedirectResponse
directamente desde una Depends, así que se usa una excepción dedicada
capturada por un exception_handler registrado en main.py) y las
dependencias de autorización usadas por los routers.
"""

from fastapi import Request

from core.config import STAFF_ROLES
from core.templates import flash
from database.connection import get_db

MENSAJE_CUENTA_INACTIVA = (
    "Tu cuenta de cuidador está inactiva o sin registro de personal. "
    "Contacta al administrador."
)


def cuidador_activo(user_id) -> bool:
    """True si la cuenta tiene un registro de personal activo."""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM personal WHERE usuario_id = %s AND activo = 1 LIMIT 1",
                (user_id,),
            )
            return cursor.fetchone() is not None
    finally:
        conn.close()


def sesion_operativa(session) -> bool:
    """Un Cuidador inactivo (o sin registro de personal) no puede operar.
    Administrador y Familiar no dependen de esta regla."""
    if session.get("rol") == "Cuidador":
        return cuidador_activo(session.get("user_id"))
    return True


class RedirectException(Exception):
    """Señala que la petición debe redirigirse a `url` (usada por las
    dependencias de autenticación para cortar la ejecución del endpoint)."""

    def __init__(self, url: str):
        self.url = url


def login_required(request: Request):
    if "user_id" not in request.session:
        flash(request, "Debes iniciar sesión para continuar.", "error")
        raise RedirectException(str(request.url_for("login")))
    # Se revisa en cada petición: si el administrador desactiva al cuidador,
    # pierde el acceso de inmediato, aunque tenga la sesión abierta.
    if not sesion_operativa(request.session):
        request.session.clear()
        flash(request, MENSAJE_CUENTA_INACTIVA, "error")
        raise RedirectException(str(request.url_for("login")))
    return request.session


def admin_required(request: Request):
    session = login_required(request)
    if session.get("rol") != "Administrador":
        flash(request, "No tienes permisos para acceder a esta sección.", "error")
        raise RedirectException(str(request.url_for("dashboard")))
    return session


def staff_required(request: Request):
    session = login_required(request)
    if session.get("rol") not in STAFF_ROLES:
        flash(request, "Tu rol solo tiene acceso de consulta.", "error")
        raise RedirectException(str(request.url_for("lista_familiar")))
    return session


def home_url_for(request: Request, rol: str) -> str:
    """El rol Familiar no tiene Dashboard: su página de inicio es
    directamente la vista de su(s) adulto(s) mayor(es) vinculado(s)."""
    if rol == "Familiar":
        return str(request.url_for("lista_familiar"))
    return str(request.url_for("dashboard"))
