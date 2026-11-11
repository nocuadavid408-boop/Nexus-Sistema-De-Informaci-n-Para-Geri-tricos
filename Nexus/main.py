
"""
Nexus — Sistema de Información para Hogares Geriátricos
=========================================================
Aplicación FastAPI con conexión a MySQL.
"""

import asyncio
from contextlib import asynccontextmanager

import os

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from core.auth import RedirectException
from core.config import SECRET_KEY, STATIC_DIR
from core.tasks import tarea_notificaciones_automaticas
from database.connection import comprobar_esquema
from database.schema import sincronizar_personal

from routers import (
    agenda,
    api,
    auth,
    asignaciones,
    dashboard,
    familiar,
    historial,
    horarios,
    itinerario,
    medicamentos,
    notificaciones,
    perfil,
    personal,
    residentes,
    usuarios,
    pdf,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Si no hay conexión o faltan tablas, la app NO arranca y el error dice por qué.
    # Se crea todo con:  python -m database.schema   (o importando database/nexus_v3.sql)
    comprobar_esquema()
    sincronizar_personal()

    tarea = asyncio.create_task(tarea_notificaciones_automaticas())

    try:
        yield
    finally:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass


DESCRIPCION_API = """
API REST de **Nexus** para la gestión de residentes, catálogo e itinerario (medicamentos y actividades).

Cada operación usa las mismas funciones y la misma base de datos MySQL que la aplicación web:
lo que se registre aquí aparece de inmediato en la agenda, el panel del cuidador, el historial y las alertas.

**Cómo probar**
1. Ejecuta `POST /api/v1/auth/login` con un usuario (por ejemplo `admin` / `admin123`). La sesión queda guardada en una cookie del navegador.
2. Usa el resto de endpoints con **Try it out**. Los permisos dependen del rol (Administrador, Cuidador, Familiar).
3. Para registrar un medicamento: consulta `/catalogo/medicamento/categorias` y `/catalogo/medicamento/items`, y luego `POST /residentes/{id}/medicamentos`.

[← Volver a Nexus](/)
"""

ETIQUETAS_API = [
    {"name": "Autenticación", "description": "Inicio y cierre de sesión."},
    {"name": "Residentes", "description": "Consulta de residentes según el rol."},
    {"name": "Catálogo", "description": "Categorías, medicamentos y actividades disponibles."},
    {"name": "Itinerario", "description": "Programar, consultar, marcar (✓/✗) y eliminar medicamentos y actividades."},
]

app = FastAPI(
    title="Nexus API",
    version="1.0.0",
    description=DESCRIPCION_API,
    openapi_tags=ETIQUETAS_API,
    lifespan=lifespan,
    docs_url=None,      # /docs se sirve abajo con la identidad de Nexus
    redoc_url=None,
    openapi_url="/docs/openapi.json",   # el esquema también queda bajo /docs; la raíz no expone nada de la API
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# DOCUMENTACIÓN SWAGGER (/docs) — el esquema se genera en vivo desde el código
@app.get("/docs", include_in_schema=False)
async def swagger_docs():
    html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Nexus API — Documentación",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css",
        swagger_favicon_url="/static/img/favicon-32.png",
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "filter": True,
            "tryItOutEnabled": True,
            "persistAuthorization": True,
        },
    ).body.decode()
    html = html.replace("</head>", '<link rel="stylesheet" href="/static/css/swagger.css"></head>')
    return HTMLResponse(html)


# FAVICON (los navegadores lo piden en /favicon.ico aunque la página no lo declare)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "img", "favicon.ico"), media_type="image/x-icon")


# CONTROL DE CACHÉ DEL NAVEGADOR
@app.middleware("http")
async def sin_cache_paginas_dinamicas(request: Request, call_next):
    response = await call_next(request)

    if not request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate"
        )
        response.headers["Pragma"] = "no-cache"

    return response


# REDIRECCIONES DE AUTENTICACIÓN
@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    return RedirectResponse(exc.url, status_code=303)


# ROUTERS
# Las pantallas HTML no se listan en /docs; la API pública está en routers/api.py
app.include_router(api.router)
app.include_router(auth.router, include_in_schema=False)
app.include_router(dashboard.router, include_in_schema=False)
app.include_router(agenda.router, include_in_schema=False)
app.include_router(itinerario.router, include_in_schema=False)
app.include_router(residentes.router, include_in_schema=False)
app.include_router(horarios.router, include_in_schema=False)
app.include_router(usuarios.router, include_in_schema=False)
app.include_router(familiar.router, include_in_schema=False)
app.include_router(medicamentos.router, include_in_schema=False)
app.include_router(personal.router, include_in_schema=False)
app.include_router(historial.router, include_in_schema=False)
app.include_router(notificaciones.router, include_in_schema=False)
app.include_router(perfil.router, include_in_schema=False)
app.include_router(pdf.router, include_in_schema=False)
app.include_router(asignaciones.router, include_in_schema=False)
