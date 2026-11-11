"""
NOTIFICACIONES AUTOMÁTICAS (RF05)
Genera una notificación cuando la hora actual coincide con una hora del
itinerario diario (medicamento o actividad), evitando duplicados.
"""
import asyncio
from datetime import datetime

from core.config import INTERVALO_REVISION_SEGUNDOS
from core.itinerario import programados_en
from database.connection import get_db


def generar_notificaciones_automaticas() -> None:
    ahora = datetime.now()
    fecha, hora = ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M")

    conn = get_db()
    try:
        pendientes = programados_en(conn, fecha, hora)
        with conn.cursor() as c:
            for residente, tipo, detalle in pendientes:
                c.execute(
                    "SELECT id FROM notificaciones_generadas WHERE residente=%s AND tipo=%s "
                    "AND fecha=%s AND hora=%s AND detalle=%s",
                    (residente, tipo, fecha, hora, detalle[:255]),
                )
                if c.fetchone():
                    continue
                c.execute(
                    "INSERT INTO notificaciones (residente, tipo, detalle, fecha, hora, estado, mostrada) "
                    "VALUES (%s,%s,%s,%s,%s,'Pendiente',0)",
                    (residente, tipo, detalle, fecha, hora),
                )
                c.execute(
                    "INSERT INTO notificaciones_generadas (residente, tipo, detalle, fecha, hora) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (residente, tipo, detalle[:255], fecha, hora),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def tarea_notificaciones_automaticas() -> None:
    while True:
        try:
            generar_notificaciones_automaticas()
        except Exception as e:
            print(f"[notificaciones_automaticas] error: {e}")
        await asyncio.sleep(INTERVALO_REVISION_SEGUNDOS)
