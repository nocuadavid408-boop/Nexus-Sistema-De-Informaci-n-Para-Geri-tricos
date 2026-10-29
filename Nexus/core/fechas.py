"""
Fechas de los medicamentos.

La columna `medicamentos_residente.dia` guarda en un solo texto cuándo se
administra el medicamento:

- vacío ............................ todos los días (registros antiguos)
- "2026-10-21, 2026-10-23" ......... fechas elegidas en el mini calendario
- "Lunes, Miércoles" ............... días de la semana (registros antiguos)
"""

import unicodedata
from datetime import date

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic"]

# Tope de fechas por medicamento (un mes completo, dos meses de margen).
MAX_FECHAS = 62


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").strip().lower()


def _a_fecha(texto: str):
    try:
        return date.fromisoformat(texto.strip())
    except ValueError:
        return None


def fechas_desde_formulario(valor, desde: date | None = None):
    """Valida el texto del mini calendario ("2026-10-21,2026-10-23").

    Devuelve (texto_para_guardar, error). El texto sale ordenado, sin
    repetidos y separado por ", ". Si hay error, el texto es "".
    """
    desde = desde or date.today()
    fechas = set()
    for trozo in (valor or "").split(","):
        if not trozo.strip():
            continue
        f = _a_fecha(trozo)
        if f is None:
            return "", "Alguna de las fechas elegidas no es válida."
        if f < desde:
            return "", "No puedes elegir días anteriores a hoy."
        fechas.add(f)

    if not fechas:
        return "", "Elige en el calendario al menos un día."
    if len(fechas) > MAX_FECHAS:
        return "", f"Puedes elegir máximo {MAX_FECHAS} días por medicamento."
    return ", ".join(f.isoformat() for f in sorted(fechas)), ""


def medicamento_aplica(dia, fecha: date) -> bool:
    """¿El medicamento se administra en `fecha`?"""
    dia = (dia or "").strip()
    if not dia:
        return True

    iso = fecha.isoformat()
    for trozo in dia.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        if _a_fecha(trozo) is not None:
            if trozo == iso:
                return True
        elif _normalizar(trozo) == DIAS_SEMANA[fecha.weekday()]:
            return True
    return False


def _rangos(dias) -> str:
    """[22, 23, 24, 25, 28] -> "22–25, 28" (rangos desde 3 días seguidos)."""
    tramos, inicio = [], 0
    for i in range(1, len(dias) + 1):
        if i == len(dias) or dias[i] != dias[i - 1] + 1:
            tramos.append(dias[inicio:i])
            inicio = i
    textos = []
    for t in tramos:
        textos.extend([f"{t[0]}–{t[-1]}"] if len(t) >= 3 else [str(d) for d in t])
    return ", ".join(textos)


def etiqueta_dias(dia) -> str:
    """Texto corto para mostrar los días: "21, 23 oct 2026 · 2 nov 2026"."""
    dia = (dia or "").strip()
    if not dia:
        return "Todos los días"

    fechas, otros = [], []
    for trozo in dia.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        f = _a_fecha(trozo)
        (fechas if f else otros).append(f or trozo)

    grupos = {}
    for f in sorted(fechas):
        grupos.setdefault((f.year, f.month), []).append(f.day)
    partes = [
        f"{_rangos(dias)} {MESES_CORTOS[mes - 1]} {anio}"
        for (anio, mes), dias in grupos.items()
    ]
    if otros:
        partes.append(", ".join(otros))
    return " · ".join(partes)
