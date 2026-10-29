
"""
GENERACIÓN DE REPORTES PDF PARA CUIDADORES

Incluye:
- Reporte del cuidador autenticado.
- Reporte de un cuidador seleccionado por el administrador.
- Datos de residentes, actividades y medicamentos.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse

from core.acceso import nombres_visibles
from core.auth import admin_required, login_required
from core.fechas import etiqueta_dias
from core.itinerario import actividades_planas, listado
from core.templates import flash
from database.connection import get_db

router = APIRouter()


def eliminar_archivo(ruta):
    """Elimina el PDF temporal después de enviarlo."""
    try:
        if os.path.exists(ruta):
            os.unlink(ruta)
    except OSError:
        pass


def obtener_datos_residentes(conn, cursor, actividades):
    """
    Obtiene los datos de los residentes relacionados con las
    actividades del cuidador, incluidos sus medicamentos.
    """
    nombres_residentes = sorted({
        actividad["residente"]
        for actividad in actividades
        if actividad["residente"]
    })

    if not nombres_residentes:
        return []

    # Los marcadores se generan según la cantidad de nombres.
    # Los valores siguen enviándose como parámetros SQL.
    placeholders = ", ".join(
        ["%s"] * len(nombres_residentes)
    )

    cursor.execute(
        f"""
        SELECT *
        FROM residentes
        WHERE nombre IN ({placeholders})
        ORDER BY nombre
        """,
        tuple(nombres_residentes),
    )

    residentes = cursor.fetchall()

    residentes_db = {
        residente["nombre"]: residente
        for residente in residentes
    }

    datos_residentes = []

    for nombre_residente in nombres_residentes:
        residente = residentes_db.get(nombre_residente)

        if not residente:
            continue

        actividades_residente = [
            {
                "fecha": str(actividad["fecha"]),
                "hora": str(actividad["hora"]),
                "actividad": actividad["actividad"],
            }
            for actividad in actividades
            if actividad["residente"] == nombre_residente
        ]

        medicamentos_residente = [
            {
                "nombre": g["nombre"],
                "dosis": g["dosis"],
                "dia": etiqueta_dias(g["dia"]),
                "horario": ", ".join(g["horas"]),
                "observaciones": g["observaciones"],
            }
            for g in listado(conn, residente["id"], "medicamento")
        ]

        datos_residentes.append({
            "nombre": residente["nombre"],
            "documento": residente["documento"],
            "edad": residente["edad"],
            "habitacion": residente["habitacion"],
            "diagnostico": residente["diagnostico"],
            "actividades": actividades_residente,
            "medicamentos": medicamentos_residente,
        })

    return datos_residentes


def ejecutar_generador_pdf(
    request,
    background_tasks,
    datos,
    nombre_archivo,
    nombre_ruta_error,
):
    """
    Ejecuta generar_pdf.js y devuelve el PDF al navegador.
    """
    archivo_temporal = tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,
    )
    ruta_pdf = archivo_temporal.name
    archivo_temporal.close()

    proyecto = Path(__file__).resolve().parent.parent
    script_pdf = proyecto / "generar_pdf.js"

    if not script_pdf.exists():
        flash(
            request,
            "No se encontró generar_pdf.js.",
            "error",
        )
        eliminar_archivo(ruta_pdf)

        return RedirectResponse(
            request.url_for(nombre_ruta_error),
            status_code=303,
        )

    try:
        resultado = subprocess.run(
            ["node", str(script_pdf), ruta_pdf],
            input=json.dumps(datos, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=True,
        )

        print(resultado.stdout)

    except FileNotFoundError:
        flash(
            request,
            "No se encontró Node.js instalado en el sistema.",
            "error",
        )
        eliminar_archivo(ruta_pdf)

        return RedirectResponse(
            request.url_for(nombre_ruta_error),
            status_code=303,
        )

    except subprocess.CalledProcessError as error:
        print("ERROR NODE:")
        print(error.stdout)
        print(error.stderr)

        flash(
            request,
            "Ocurrió un error al generar el PDF.",
            "error",
        )
        eliminar_archivo(ruta_pdf)

        return RedirectResponse(
            request.url_for(nombre_ruta_error),
            status_code=303,
        )

    background_tasks.add_task(eliminar_archivo, ruta_pdf)

    return FileResponse(
        ruta_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="{nombre_archivo}"'
            )
        },
    )


@router.get("/pdf/cuidador", name="pdf_cuidador")
async def generar_pdf_cuidador(
    request: Request,
    background_tasks: BackgroundTasks,
    session=Depends(login_required),
):
    # Solo los cuidadores pueden generar su propio reporte.
    if session.get("rol") != "Cuidador":
        flash(
            request,
            "Solo los cuidadores pueden generar este reporte.",
            "error",
        )
        return RedirectResponse(
            request.url_for("dashboard"),
            status_code=303,
        )

    nombre_cuidador = (
        session.get("nombre") or ""
    ).strip()

    if not nombre_cuidador:
        flash(
            request,
            "No se pudo identificar al cuidador.",
            "error",
        )
        return RedirectResponse(
            request.url_for("dashboard"),
            status_code=303,
        )

    conn = get_db()

    try:
        with conn.cursor() as cursor:
            # Información del personal.
            cursor.execute(
                """
                SELECT *
                FROM personal
                WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))
                  AND activo = 1
                LIMIT 1
                """,
                (nombre_cuidador,),
            )
            cuidador = cursor.fetchone()

            # Actividades asignadas.
            actividades = actividades_planas(conn, personal_nombre=nombre_cuidador)

            # Solo residentes que el cuidador tiene asignados actualmente.
            permitidos = nombres_visibles(conn, session)
            if permitidos is not None:
                actividades = [
                    a for a in actividades if a["residente"] in permitidos
                ]

            datos_residentes = obtener_datos_residentes(
                conn,
                cursor,
                actividades,
            )

        datos = {
            "cuidador": {
                "nombre": nombre_cuidador,
                "correo": cuidador["correo"] if cuidador else None,
                "telefono": cuidador["telefono"] if cuidador else None,
                "turno": cuidador["turno"] if cuidador else None,
            },
            "residentes": datos_residentes,
        }

    finally:
        conn.close()

    return ejecutar_generador_pdf(
        request=request,
        background_tasks=background_tasks,
        datos=datos,
        nombre_archivo="reporte_cuidador.pdf",
        nombre_ruta_error="dashboard",
    )


@router.get(
    "/pdf/cuidador/{cuidador_id}",
    name="pdf_cuidador_admin",
)
async def generar_pdf_cuidador_admin(
    cuidador_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    session=Depends(admin_required),
):
    conn = get_db()

    try:
        with conn.cursor() as cursor:
            # El administrador selecciona una cuenta de cuidador.
            cursor.execute(
                """
                SELECT *
                FROM usuarios
                WHERE id = %s
                  AND rol = 'Cuidador'
                LIMIT 1
                """,
                (cuidador_id,),
            )
            cuidador = cursor.fetchone()

            if not cuidador:
                flash(
                    request,
                    "El cuidador seleccionado no existe.",
                    "error",
                )
                return RedirectResponse(
                    request.url_for("lista_usuarios"),
                    status_code=303,
                )

            nombre_cuidador = (
                cuidador.get("nombre") or ""
            ).strip()

            # Información adicional del personal.
            cursor.execute(
                """
                SELECT *
                FROM personal
                WHERE LOWER(TRIM(nombre)) =
                      LOWER(TRIM(%s))
                  AND activo = 1
                LIMIT 1
                """,
                (nombre_cuidador,),
            )
            personal = cursor.fetchone()

            # Actividades asignadas al cuidador.
            actividades = actividades_planas(conn, personal_nombre=nombre_cuidador)

            datos_residentes = obtener_datos_residentes(
                conn,
                cursor,
                actividades,
            )

        datos = {
            "cuidador": {
                "nombre": nombre_cuidador,
                "correo": cuidador.get("correo"),
                "telefono": personal["telefono"] if personal else None,
                "turno": personal["turno"] if personal else None,
            },
            "residentes": datos_residentes,
        }

    finally:
        conn.close()

    return ejecutar_generador_pdf(
        request=request,
        background_tasks=background_tasks,
        datos=datos,
        nombre_archivo="reporte_cuidador.pdf",
        nombre_ruta_error="lista_usuarios",
    )
