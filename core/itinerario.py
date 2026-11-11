"""
Itinerario diario: UNA fila por (residente, fecha, medicamento|actividad)
con las horas en un arreglo JSON. El ✓ de cada hora vive en itinerario_checks.
"""
import json
import re
from datetime import date

HORA_VALIDA = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
MAX_HORAS = 12
MAX_FECHAS = 62
TIPOS = {
    "medicamento": dict(cat="categorias_medicamentos", item="medicamentos", fk="medicamento_id"),
    "actividad":   dict(cat="categorias_actividades",  item="actividades",  fk="actividad_id"),
}


def _lista(valor):
    """El JSON puede llegar como str (MariaDB) o ya como list (MySQL)."""
    if isinstance(valor, (str, bytes)):
        return json.loads(valor)
    return valor or []


def horas_validas(valores):
    """['12:00','06:00','06:00'] -> (['06:00','12:00'], '')"""
    horas = sorted({(v or "").strip() for v in valores if (v or "").strip()})
    if not horas:
        return [], "Agrega al menos una hora."
    if len(horas) > MAX_HORAS:
        return [], f"Máximo {MAX_HORAS} horas."
    for h in horas:
        if not HORA_VALIDA.fullmatch(h):
            return [], f"La hora «{h}» no es válida (HH:MM)."
    return horas, ""


def fechas_validas(texto):
    """'2026-10-27, 2026-10-28' -> ([date, ...], error)"""
    fechas = set()
    for t in (texto or "").split(","):
        if t.strip():
            try:
                f = date.fromisoformat(t.strip())
            except ValueError:
                return [], "Alguna fecha no es válida."
            if f < date.today():
                return [], "No puedes programar días anteriores a hoy."
            fechas.add(f)
    if not fechas:
        return [], "Elige al menos un día."
    if len(fechas) > MAX_FECHAS:
        return [], f"Máximo {MAX_FECHAS} días."
    return sorted(fechas), ""


# ------------------------- catálogo en cascada -------------------------
def categorias(conn, tipo):
    t = TIPOS[tipo]
    with conn.cursor() as c:
        c.execute(f"SELECT id, nombre FROM {t['cat']} WHERE activo=1 ORDER BY nombre")
        return c.fetchall()


def items_de_categoria(conn, tipo, categoria_id):
    t = TIPOS[tipo]
    with conn.cursor() as c:
        c.execute(f"SELECT id, nombre FROM {t['item']} "
                  "WHERE categoria_id=%s AND activo=1 ORDER BY nombre", (categoria_id,))
        return c.fetchall()


def item_existe(conn, tipo, item_id, categoria_id):
    """Valida en el servidor que el ítem pertenece a la categoría elegida."""
    t = TIPOS[tipo]
    with conn.cursor() as c:
        c.execute(f"SELECT id FROM {t['item']} WHERE id=%s AND categoria_id=%s AND activo=1",
                  (item_id, categoria_id))
        return c.fetchone() is not None


# ------------------------- guardar (sin duplicar filas) -------------------------
def guardar(conn, *, residente_id, fechas, tipo, item_id, horas, dosis=None,
            observaciones=None, personal_id=None, creado_por=None):
    """Una fila por día. Si ya existe ese medicamento/actividad ese día, se
    FUSIONAN las horas en el JSON en vez de crear otra fila."""
    fk = TIPOS[tipo]["fk"]
    with conn.cursor() as c:
        for f in fechas:
            c.execute(
                f"SELECT id, horas FROM itinerario_diario "
                f"WHERE residente_id=%s AND fecha=%s AND tipo=%s AND {fk}=%s FOR UPDATE",
                (residente_id, f, tipo, item_id),
            )
            fila = c.fetchone()
            if fila:
                union = sorted(set(_lista(fila["horas"])) | set(horas))
                c.execute(
                    "UPDATE itinerario_diario SET horas=%s, "
                    "observaciones=COALESCE(%s, observaciones) WHERE id=%s",
                    (json.dumps(union), observaciones, fila["id"]),
                )
            else:
                c.execute(
                    f"INSERT INTO itinerario_diario (residente_id, fecha, tipo, {fk}, dosis, "
                    "horas, observaciones, personal_id, creado_por) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (residente_id, f, tipo, item_id, dosis, json.dumps(horas),
                     observaciones, personal_id, creado_por),
                )


# ------------------------- leer el día (solo lectura) -------------------------
def dia(conn, residente_id, fecha):
    """Lista plana ordenada por hora: una entrada por (fila, hora)."""
    with conn.cursor() as c:
        c.execute(
            """
            SELECT i.id, i.tipo, i.dosis, i.horas, i.observaciones,
                   COALESCE(m.nombre, a.nombre) AS nombre
            FROM itinerario_diario i
            LEFT JOIN medicamentos m ON m.id = i.medicamento_id
            LEFT JOIN actividades  a ON a.id = i.actividad_id
            WHERE i.residente_id=%s AND i.fecha=%s
            """, (residente_id, fecha))
        filas = c.fetchall()
        c.execute(
            """
            SELECT k.itinerario_id, k.hora, u.nombre AS por,
                   DATE_FORMAT(k.completado_en,'%%H:%%i') AS en
            FROM itinerario_checks k
            JOIN itinerario_diario i ON i.id = k.itinerario_id
            LEFT JOIN usuarios u ON u.id = k.completado_por
            WHERE i.residente_id=%s AND i.fecha=%s
            """, (residente_id, fecha))
        checks = {(k["itinerario_id"], k["hora"]): k for k in c.fetchall()}

    salida = []
    for f in filas:
        for h in _lista(f["horas"]):
            k = checks.get((f["id"], h))
            salida.append({
                "id": f["id"], "hora": h, "tipo": f["tipo"],
                "nombre": f["nombre"] + (f" — {f['dosis']}" if f["dosis"] else ""),
                "observaciones": f["observaciones"],
                "completado": bool(k), "por": k["por"] if k else None,
                "en": k["en"] if k else None,
            })
    return sorted(salida, key=lambda e: (e["hora"], e["id"]))


def marcar(conn, itinerario_id, hora, completado, user_id):
    """✓ = inserta el check; ✗ = lo borra. Solo si la hora existe en el JSON."""
    with conn.cursor() as c:
        c.execute("SELECT horas FROM itinerario_diario WHERE id=%s", (itinerario_id,))
        f = c.fetchone()
        if not f or hora not in _lista(f["horas"]):
            return False
        if completado:
            c.execute("INSERT INTO itinerario_checks (itinerario_id, hora, completado_por) "
                      "VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE "
                      "completado_por=VALUES(completado_por), completado_en=NOW()",
                      (itinerario_id, hora, user_id))
        else:
            c.execute("DELETE FROM itinerario_checks WHERE itinerario_id=%s AND hora=%s",
                      (itinerario_id, hora))
    return True


# ============================================================
# Consultas para las pantallas (calendario, módulos, panel, PDF)
# ============================================================
import calendar as _cal
from datetime import timedelta


def resumen_mes(conn, residente_id, anio, mes):
    """{ '2026-10-21': {'total': 4, 'hechos': 2}, ... } (una unidad = una hora)."""
    primero = date(anio, mes, 1)
    ultimo = date(anio, mes, _cal.monthrange(anio, mes)[1])
    with conn.cursor() as c:
        c.execute(
            """
            SELECT i.fecha, i.horas,
                   (SELECT COUNT(*) FROM itinerario_checks k WHERE k.itinerario_id = i.id) AS hechos
            FROM itinerario_diario i
            WHERE i.residente_id=%s AND i.fecha BETWEEN %s AND %s
            """, (residente_id, primero, ultimo))
        filas = c.fetchall()
    out = {}
    for f in filas:
        r = out.setdefault(f["fecha"].isoformat(), {"total": 0, "hechos": 0})
        r["total"] += len(_lista(f["horas"]))
        r["hechos"] += int(f["hechos"])
    return out


def ruta_personal(conn, personal_id, fecha):
    """Tareas del día de un miembro del personal: las que tiene asignadas
    directamente o las de sus residentes asignados sin responsable."""
    with conn.cursor() as c:
        c.execute(
            """
            SELECT i.id, i.tipo, i.dosis, i.horas, i.observaciones,
                   r.id AS residente_id, r.nombre AS residente_nombre,
                   COALESCE(m.nombre, a.nombre) AS nombre
            FROM itinerario_diario i
            JOIN residentes r ON r.id = i.residente_id
            LEFT JOIN medicamentos m ON m.id = i.medicamento_id
            LEFT JOIN actividades  a ON a.id = i.actividad_id
            WHERE i.fecha = %s
              AND (i.personal_id = %s
                   OR (i.personal_id IS NULL AND i.residente_id IN
                       (SELECT residente_id FROM asignaciones WHERE personal_id = %s)))
            """, (fecha, personal_id, personal_id))
        filas = c.fetchall()
        ids = [f["id"] for f in filas]
        hechos = set()
        if ids:
            c.execute("SELECT itinerario_id, hora FROM itinerario_checks WHERE itinerario_id IN (%s)"
                      % ", ".join(["%s"] * len(ids)), tuple(ids))
            hechos = {(k["itinerario_id"], k["hora"]) for k in c.fetchall()}
    out = []
    for f in filas:
        for h in _lista(f["horas"]):
            out.append({
                "id": f["id"], "hora": h, "tipo": f["tipo"],
                "nombre": f["nombre"] + (f" — {f['dosis']}" if f["dosis"] else ""),
                "observaciones": f["observaciones"],
                "residente_id": f["residente_id"], "residente_nombre": f["residente_nombre"],
                "completado": (f["id"], h) in hechos,
            })
    return sorted(out, key=lambda e: (e["hora"], e["id"]))


def listado(conn, residente_id, tipo, desde=None):
    """Lo programado de hoy en adelante, agrupado: el mismo medicamento/actividad,
    con la misma dosis, horas y observaciones, se junta en una sola tarjeta
    con todas sus fechas."""
    t = TIPOS[tipo]
    desde = desde or date.today()
    with conn.cursor() as c:
        c.execute(
            f"""
            SELECT i.id, i.fecha, i.dosis, i.horas, i.observaciones,
                   x.nombre, cat.nombre AS categoria, i.{t['fk']} AS item_id
            FROM itinerario_diario i
            JOIN {t['item']} x   ON x.id = i.{t['fk']}
            JOIN {t['cat']} cat ON cat.id = x.categoria_id
            WHERE i.residente_id=%s AND i.tipo=%s AND i.fecha >= %s
            ORDER BY x.nombre, i.fecha
            """, (residente_id, tipo, desde))
        filas = c.fetchall()
    grupos = {}
    for f in filas:
        horas = _lista(f["horas"])
        k = (f["item_id"], f["dosis"], tuple(horas), f["observaciones"] or "")
        g = grupos.setdefault(k, {
            "nombre": f["nombre"], "categoria": f["categoria"], "dosis": f["dosis"],
            "horas": horas, "observaciones": f["observaciones"], "fechas": [], "ids": [],
        })
        g["fechas"].append(f["fecha"].isoformat())
        g["ids"].append(str(f["id"]))
    out = []
    for g in grupos.values():
        g["dia"] = ", ".join(g["fechas"])          # el filtro dias_txt lo vuelve legible
        g["ids_txt"] = ",".join(g["ids"])
        out.append(g)
    return sorted(out, key=lambda g: (g["fechas"][0], g["nombre"]))


def eliminar(conn, residente_id, ids, desde=None):
    """Borra filas del itinerario de hoy en adelante (los ✓ se van en cascada)."""
    ids = [int(i) for i in ids if str(i).isdigit()]
    if not ids:
        return 0
    with conn.cursor() as c:
        c.execute(
            "DELETE FROM itinerario_diario WHERE residente_id=%%s AND fecha >= %%s AND id IN (%s)"
            % ", ".join(["%s"] * len(ids)),
            (residente_id, desde or date.today(), *ids))
        return c.rowcount


def detalle_entrada(conn, itinerario_id):
    with conn.cursor() as c:
        c.execute(
            """
            SELECT i.id, i.fecha, i.tipo, i.residente_id, r.nombre AS residente,
                   COALESCE(m.nombre, a.nombre) AS nombre
            FROM itinerario_diario i
            JOIN residentes r ON r.id = i.residente_id
            LEFT JOIN medicamentos m ON m.id = i.medicamento_id
            LEFT JOIN actividades  a ON a.id = i.actividad_id
            WHERE i.id=%s
            """, (itinerario_id,))
        return c.fetchone()


def programados_en(conn, fecha, hora):
    """Para las notificaciones automáticas: lo que toca exactamente a `hora`."""
    with conn.cursor() as c:
        c.execute(
            """
            SELECT i.tipo, i.dosis, i.horas, r.nombre AS residente,
                   COALESCE(m.nombre, a.nombre) AS nombre
            FROM itinerario_diario i
            JOIN residentes r ON r.id = i.residente_id
            LEFT JOIN medicamentos m ON m.id = i.medicamento_id
            LEFT JOIN actividades  a ON a.id = i.actividad_id
            WHERE i.fecha = %s
            """, (fecha,))
        filas = c.fetchall()
    out = []
    for f in filas:
        if hora in _lista(f["horas"]):
            if f["tipo"] == "medicamento":
                out.append((f["residente"], "Medicamento",
                            f"Hora de administrar {f['nombre']} ({f['dosis']})"))
            else:
                out.append((f["residente"], "Actividad", f"Hora de la actividad: {f['nombre']}"))
    return out


def actividades_planas(conn, residente_id=None, personal_nombre=None):
    """Una fila por (actividad, día, hora): para PDF y vista del familiar."""
    sql = """
        SELECT i.fecha, i.horas, a.nombre AS actividad, r.nombre AS residente,
               p.nombre AS cuidador
        FROM itinerario_diario i
        JOIN actividades a ON a.id = i.actividad_id
        JOIN residentes r  ON r.id = i.residente_id
        LEFT JOIN personal p ON p.id = i.personal_id
        WHERE i.tipo='actividad'"""
    params = []
    if residente_id is not None:
        sql += " AND i.residente_id=%s"; params.append(residente_id)
    if personal_nombre is not None:
        sql += (" AND (LOWER(TRIM(p.nombre))=LOWER(TRIM(%s)) OR (i.personal_id IS NULL AND i.residente_id IN"
                " (SELECT ag.residente_id FROM asignaciones ag JOIN personal pp ON pp.id=ag.personal_id"
                " WHERE LOWER(TRIM(pp.nombre))=LOWER(TRIM(%s)))))")
        params += [personal_nombre, personal_nombre]
    with conn.cursor() as c:
        c.execute(sql + " ORDER BY i.fecha, r.nombre", tuple(params))
        filas = c.fetchall()
    return [{"fecha": f["fecha"].isoformat(), "hora": h, "actividad": f["actividad"],
             "residente": f["residente"], "cuidador": f["cuidador"]}
            for f in filas for h in sorted(_lista(f["horas"]))]
