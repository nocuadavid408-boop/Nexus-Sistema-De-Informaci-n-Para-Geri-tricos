
"""
Nexus — Sistema de Información para Hogares Geriátricos
=========================================================
Aplicación FastAPI con conexión a MySQL.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from core.auth import RedirectException
from core.config import SECRET_KEY, STATIC_DIR
from core.tasks import tarea_notificaciones_automaticas
from database.connection import comprobar_esquema
from database.schema import inicializar_si_falta, sincronizar_personal

from routers import (
    agenda,
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
    inicializar_si_falta()  # crea las tablas la primera vez
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


app = FastAPI(title="Nexus", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(agenda.router)
app.include_router(itinerario.router)
app.include_router(residentes.router)
app.include_router(horarios.router)
app.include_router(usuarios.router)
app.include_router(familiar.router)
app.include_router(medicamentos.router)
app.include_router(personal.router)
app.include_router(historial.router)
app.include_router(notificaciones.router)
app.include_router(perfil.router)
app.include_router(pdf.router)
app.include_router(asignaciones.router)
