"""
Configuración de Jinja2Templates y helpers de renderizado / mensajes flash.
"""

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from core.acceso import ids_visibles
from core.config import TEMPLATES_DIR
from database.connection import get_db
from core.fechas import etiqueta_dias

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def flash(request: Request, message: str, category: str = "message") -> None:
    flashes = request.session.setdefault("_flashes", [])
    flashes.append([category, message])


@pass_context
def _get_flashed_messages(context, with_categories: bool = False):
    request: Request = context["request"]
    flashes = request.session.pop("_flashes", [])
    if with_categories:
        return flashes
    return [m for _, m in flashes]


templates.env.globals["get_flashed_messages"] = _get_flashed_messages
templates.env.filters["dias_txt"] = etiqueta_dias


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    context = context or {}
    context["session"] = request.session
    # Cuidador sin residentes asignados: no ve nada hasta que se le asigne.
    context["sin_asignaciones"] = False
    if request.session.get("rol") == "Cuidador" and "user_id" in request.session:
        conn = get_db()
        try:
            context["sin_asignaciones"] = not ids_visibles(conn, request.session)
        finally:
            conn.close()
    return templates.TemplateResponse(request, name, context, status_code=status_code)
