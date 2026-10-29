"""
Agenda: permisos y utilidades del calendario.
Los datos (medicamentos, actividades, ✓/✗) viven en core/itinerario.py.
"""
import calendar
from datetime import date

from core.acceso import puede_ver_residente
from core.itinerario import HORA_VALIDA, horas_validas, resumen_mes  # noqa: F401  (reexportados)


def puede_ver_agenda(conn, session, residente_id: int) -> bool:
    """Admin ve todo; Cuidador solo sus residentes asignados; Familiar solo
    el residente vinculado a su usuario."""
    if session.get("rol") == "Familiar":
        with conn.cursor() as c:
            c.execute(
                "SELECT 1 FROM residentes WHERE id = %s AND LOWER(familiar_username) = LOWER(%s)",
                (residente_id, (session.get("username") or "").strip()),
            )
            return c.fetchone() is not None
    return puede_ver_residente(conn, session, residente_id)


def puede_editar_agenda(conn, session, residente_id: int) -> bool:
    """Crear y marcar ✓/✗: solo Administrador y Cuidador (enfermería)."""
    return session.get("rol") in ("Administrador", "Cuidador") and puede_ver_residente(
        conn, session, residente_id
    )


def semanas_del_mes(anio: int, mes: int):
    """Matriz de semanas (lunes primero) con objetos date o None."""
    return [
        [date(anio, mes, d) if d else None for d in semana]
        for semana in calendar.Calendar(firstweekday=0).monthdayscalendar(anio, mes)
    ]
