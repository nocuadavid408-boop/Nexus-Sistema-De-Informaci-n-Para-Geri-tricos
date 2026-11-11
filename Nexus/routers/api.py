"""
API REST de Nexus (JSON) — documentada en /docs.

Cada operación usa las mismas funciones del núcleo (core.itinerario,
core.acceso, core.agenda) que las pantallas del sistema, así que lo que se
hace desde Swagger se guarda en la misma base de datos y se ve de inmediato
en la agenda, el panel del cuidador, el historial y las notificaciones.

Autenticación: sesión por cookie. Se inicia con POST /api/v1/auth/login y el
navegador reenvía la cookie en las siguientes peticiones (Swagger incluido).
"""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

import pymysql
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from core.acceso import ids_visibles, nombre_para_registro, puede_ver_residente
from core.agenda import puede_editar_agenda, puede_ver_agenda
from core.auth import cuidador_activo, sesion_operativa
from core import residentes as core_residentes
from core.config import STAFF_ROLES
from core.itinerario import (
    TIPOS, categorias, detalle_entrada, dia, eliminar, fechas_validas, guardar,
    horas_validas, item_existe, items_de_categoria, listado, marcar, _lista,
)
from core.security import hash_password
from database.connection import get_db
from routers.historial import registrar_en_historial

router = APIRouter(prefix="/api/v1")


# ═══════════════════════════════════════════════════════════
# Modelos
# ═══════════════════════════════════════════════════════════
class Tipo(str, Enum):
    medicamento = "medicamento"
    actividad = "actividad"


class Error(BaseModel):
    detail: str = Field(..., examples=["No tienes permiso."])


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1, examples=["admin"])
    password: str = Field(..., min_length=1, examples=["admin123"])


class UsuarioOut(BaseModel):
    id: int
    username: str
    nombre: Optional[str] = None
    rol: str = Field(..., examples=["Administrador"])


class ResidenteOut(BaseModel):
    id: int
    nombre: str
    documento: str
    edad: Optional[int] = None
    habitacion: Optional[str] = None
    diagnostico: Optional[str] = None
    alergias: Optional[str] = None


class ResidenteIn(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=255, examples=["María Pérez"])
    documento: str = Field(..., min_length=3, max_length=100, examples=["41234567"])
    edad: Optional[int] = Field(None, ge=0, le=130, examples=[82])
    fecha_ingreso: Optional[date] = Field(None, examples=["2026-01-15"])
    habitacion: Optional[str] = Field(None, max_length=100, examples=["204"])
    diagnostico: Optional[str] = Field(None, examples=["Hipertensión"])
    medicamentos: Optional[str] = Field(None, examples=["Losartán 50 mg"])
    alergias: Optional[str] = Field(None, examples=["Penicilina"])
    familiar_nombre: Optional[str] = Field(None, max_length=255)
    familiar_parentesco: Optional[str] = Field(None, max_length=100)
    familiar_telefono: Optional[str] = Field(None, max_length=100)
    familiar_username: Optional[str] = Field(
        None, max_length=191, description="Usuario (rol Familiar) vinculado al residente.")


class CategoriaOut(BaseModel):
    id: int
    nombre: str


class ItemCatalogoOut(BaseModel):
    id: int
    nombre: str


class ItemCatalogoIn(BaseModel):
    categoria_id: int = Field(..., ge=1, examples=[3])
    nombre: str = Field(..., min_length=2, max_length=191, examples=["Bisoprolol"])
    presentacion: Optional[str] = Field(
        None, max_length=100, examples=["Tableta 5 mg"],
        description="Solo aplica a medicamentos.")


class ItemCatalogoCreado(BaseModel):
    id: int
    categoria_id: int
    nombre: str
    presentacion: Optional[str] = None


class _ProgramarBase(BaseModel):
    categoria_id: int = Field(..., ge=1, examples=[3])
    horas: List[str] = Field(..., min_length=1, max_length=12, examples=[["08:00", "20:00"]],
                             description="Formato HH:MM (24 h). Se ordenan y se quitan duplicados.")
    fechas: List[date] = Field(..., min_length=1, max_length=62,
                               description="Días a programar (hoy o posteriores).")
    observaciones: Optional[str] = Field(None, max_length=5000)
    personal_id: Optional[int] = Field(
        None, ge=1,
        description="Responsable. Solo lo usa el administrador; un cuidador queda como responsable.")


class ProgramarMedicamentoIn(_ProgramarBase):
    medicamento_id: int = Field(..., ge=1, examples=[5])
    dosis: str = Field(..., min_length=1, max_length=100, examples=["50 mg"])

    model_config = ConfigDict(json_schema_extra={"example": {
        "categoria_id": 3, "medicamento_id": 5, "dosis": "50 mg",
        "horas": ["08:00", "20:00"], "fechas": [date.today().isoformat()],
        "observaciones": "Administrar después de comer."}})


class ProgramarActividadIn(_ProgramarBase):
    actividad_id: int = Field(..., ge=1, examples=[2])

    model_config = ConfigDict(json_schema_extra={"example": {
        "categoria_id": 1, "actividad_id": 2, "horas": ["10:00"],
        "fechas": [date.today().isoformat()], "observaciones": None}})


class ItinerarioFilaOut(BaseModel):
    id: int
    fecha: date
    tipo: Tipo
    nombre: str
    dosis: Optional[str] = None
    horas: List[str]
    observaciones: Optional[str] = None


class ProgramadoOut(BaseModel):
    nombre: str
    categoria: str
    dosis: Optional[str] = None
    horas: List[str]
    fechas: List[date]
    ids: List[int]
    observaciones: Optional[str] = None


class EntradaDiaOut(BaseModel):
    id: int
    hora: str
    tipo: Tipo
    nombre: str
    observaciones: Optional[str] = None
    completado: bool
    por: Optional[str] = None
    en: Optional[str] = None


class DiaOut(BaseModel):
    fecha: date
    editable: bool
    observaciones: str
    items: List[EntradaDiaOut]


class CheckIn(BaseModel):
    hora: str = Field(..., examples=["08:00"], description="Una de las horas del itinerario (HH:MM).")
    completado: bool = Field(..., description="true = ✓ realizado, false = ✗ pendiente.")


class CheckOut(BaseModel):
    id: int
    hora: str
    completado: bool


class EliminadoOut(BaseModel):
    eliminados: int


# ═══════════════════════════════════════════════════════════
# Dependencias de autenticación (devuelven 401/403 en JSON)
# ═══════════════════════════════════════════════════════════
def api_user(request: Request):
    s = request.session
    if "user_id" not in s:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Inicia sesión con POST /api/v1/auth/login.")
    if not sesion_operativa(s):
        s.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Tu cuenta de cuidador está inactiva.")
    return s


def api_staff(session=Depends(api_user)):
    if session.get("rol") not in STAFF_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu rol solo tiene acceso de consulta.")
    return session


def api_admin(session=Depends(api_user)):
    if session.get("rol") != "Administrador":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el administrador puede hacer esto.")
    return session


R401 = {401: {"model": Error, "description": "Sin sesión iniciada."}}
R403 = {403: {"model": Error, "description": "Sin permiso para esta operación."}}
R404 = {404: {"model": Error, "description": "No encontrado."}}


def _bd():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# Autenticación
# ═══════════════════════════════════════════════════════════
@router.post("/auth/login", response_model=UsuarioOut, tags=["Autenticación"],
             summary="Iniciar sesión",
             responses={401: {"model": Error, "description": "Credenciales incorrectas."}})
def login(datos: LoginIn, request: Request, conn=Depends(_bd)):
    """Valida usuario y contraseña y guarda la sesión en una cookie.
    Después de esto, el resto de operaciones funcionan desde esta misma página."""
    with conn.cursor() as c:
        c.execute("SELECT * FROM usuarios WHERE username=%s AND password=%s",
                  (datos.username.strip(), hash_password(datos.password)))
        u = c.fetchone()
    if not u:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    if u["rol"] == "Cuidador" and not cuidador_activo(u["id"]):
        raise HTTPException(401, "Tu cuenta de cuidador está inactiva o sin registro de personal.")
    request.session.update(user_id=u["id"], username=u["username"], rol=u["rol"], nombre=u["nombre"])
    return UsuarioOut(id=u["id"], username=u["username"], nombre=u["nombre"], rol=u["rol"])


@router.post("/auth/logout", tags=["Autenticación"], summary="Cerrar sesión",
             response_class=RedirectResponse, status_code=303)
def logout(request: Request):
    """Destruye la sesión y redirige a la pantalla de inicio de sesión (sin JSON)."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/logout", include_in_schema=False, response_class=RedirectResponse,
            status_code=303)
def logout_get(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/me", response_model=UsuarioOut, tags=["Autenticación"],
            summary="Usuario de la sesión actual", responses=R401)
def me(session=Depends(api_user)):
    return UsuarioOut(id=session["user_id"], username=session["username"],
                      nombre=session.get("nombre"), rol=session["rol"])


# ═══════════════════════════════════════════════════════════
# Residentes
# ═══════════════════════════════════════════════════════════
_COLS_RES = "id, nombre, documento, edad, habitacion, diagnostico, alergias"


@router.get("/residentes", response_model=List[ResidenteOut], tags=["Residentes"],
            summary="Listar residentes visibles", responses=R401)
def listar_residentes(session=Depends(api_user), conn=Depends(_bd)):
    """Administrador: todos. Cuidador: los asignados. Familiar: el vinculado a su usuario."""
    with conn.cursor() as c:
        if session["rol"] == "Familiar":
            c.execute(f"SELECT {_COLS_RES} FROM residentes WHERE LOWER(familiar_username)=LOWER(%s) "
                      "ORDER BY nombre", ((session.get("username") or "").strip(),))
        else:
            ids = ids_visibles(conn, session)
            if ids is None:
                c.execute(f"SELECT {_COLS_RES} FROM residentes ORDER BY nombre")
            elif not ids:
                return []
            else:
                c.execute(f"SELECT {_COLS_RES} FROM residentes WHERE id IN ({', '.join(['%s'] * len(ids))}) "
                          "ORDER BY nombre", tuple(ids))
        return c.fetchall()


@router.get("/residentes/{residente_id}", response_model=ResidenteOut, tags=["Residentes"],
            summary="Detalle de un residente", responses={**R401, **R404})
def detalle_residente(residente_id: int, session=Depends(api_user), conn=Depends(_bd)):
    if not puede_ver_agenda(conn, session, residente_id):
        raise HTTPException(404, "Residente no encontrado.")
    with conn.cursor() as c:
        c.execute(f"SELECT {_COLS_RES} FROM residentes WHERE id=%s", (residente_id,))
        fila = c.fetchone()
    if not fila:
        raise HTTPException(404, "Residente no encontrado.")
    return fila


def _datos_residente(d: ResidenteIn) -> dict:
    datos = d.model_dump()
    datos["fecha_ingreso"] = d.fecha_ingreso.isoformat() if d.fecha_ingreso else None
    for k, v in datos.items():
        if isinstance(v, str):
            datos[k] = v.strip() or None
    return datos


@router.post("/residentes", response_model=ResidenteOut, status_code=201, tags=["Residentes"],
             summary="Registrar un residente (solo admin)",
             responses={**R401, **R403,
                        409: {"model": Error, "description": "El documento ya está registrado."}})
def crear_residente(datos: ResidenteIn, session=Depends(api_admin), conn=Depends(_bd)):
    """Inserta en `residentes` (MySQL) con la misma lógica que el formulario web."""
    d = _datos_residente(datos)
    if core_residentes.documento_en_uso(conn, d["documento"]):
        raise HTTPException(409, "Ya existe un residente con ese número de documento.")
    try:
        nuevo = core_residentes.crear(conn, d)
        conn.commit()
    except pymysql.err.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "Ya existe un residente con ese número de documento.")
    except Exception:
        conn.rollback()
        raise
    with conn.cursor() as c:
        c.execute(f"SELECT {_COLS_RES} FROM residentes WHERE id=%s", (nuevo,))
        return c.fetchone()


@router.put("/residentes/{residente_id}", response_model=ResidenteOut, tags=["Residentes"],
            summary="Actualizar un residente (solo admin)",
            responses={**R401, **R403, **R404,
                       409: {"model": Error, "description": "El documento ya está registrado."}})
def actualizar_residente(residente_id: int, datos: ResidenteIn,
                         session=Depends(api_admin), conn=Depends(_bd)):
    d = _datos_residente(datos)
    with conn.cursor() as c:
        c.execute("SELECT 1 FROM residentes WHERE id=%s", (residente_id,))
        if not c.fetchone():
            raise HTTPException(404, "Residente no encontrado.")
    if core_residentes.documento_en_uso(conn, d["documento"], excluir_id=residente_id):
        raise HTTPException(409, "Ya existe otro residente con ese número de documento.")
    try:
        core_residentes.actualizar(conn, residente_id, d)
        conn.commit()
    except pymysql.err.IntegrityError:
        conn.rollback()
        raise HTTPException(409, "Ya existe otro residente con ese número de documento.")
    except Exception:
        conn.rollback()
        raise
    with conn.cursor() as c:
        c.execute(f"SELECT {_COLS_RES} FROM residentes WHERE id=%s", (residente_id,))
        return c.fetchone()


@router.delete("/residentes/{residente_id}", response_model=EliminadoOut, tags=["Residentes"],
               summary="Eliminar un residente (solo admin)", responses={**R401, **R403, **R404})
def eliminar_residente(residente_id: int, session=Depends(api_admin), conn=Depends(_bd)):
    try:
        ok = core_residentes.eliminar(conn, residente_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if not ok:
        raise HTTPException(404, "Residente no encontrado.")
    return EliminadoOut(eliminados=1)


# ═══════════════════════════════════════════════════════════
# Catálogo (categoría 1:N medicamentos / actividades)
# ═══════════════════════════════════════════════════════════
@router.get("/catalogo/{tipo}/categorias", response_model=List[CategoriaOut], tags=["Catálogo"],
            summary="Categorías de medicamentos o actividades", responses=R401)
def catalogo_categorias(tipo: Tipo, session=Depends(api_staff), conn=Depends(_bd)):
    return categorias(conn, tipo.value)


@router.get("/catalogo/{tipo}/items", response_model=List[ItemCatalogoOut], tags=["Catálogo"],
            summary="Medicamentos o actividades de una categoría", responses=R401)
def catalogo_items(tipo: Tipo, categoria_id: int = Query(..., ge=1),
                   session=Depends(api_staff), conn=Depends(_bd)):
    return items_de_categoria(conn, tipo.value, categoria_id)


@router.post("/catalogo/{tipo}/items", response_model=ItemCatalogoCreado, status_code=201,
             tags=["Catálogo"], summary="Registrar un medicamento o actividad en el catálogo",
             responses={**R401, **R403, **R404,
                        409: {"model": Error, "description": "Ya existe en esa categoría."}})
def catalogo_crear(tipo: Tipo, datos: ItemCatalogoIn, session=Depends(api_admin), conn=Depends(_bd)):
    """Inserta una fila nueva en `medicamentos` o `actividades`. Queda disponible de
    inmediato en las listas en cascada de la agenda. Solo administrador."""
    t = TIPOS[tipo.value]
    nombre = datos.nombre.strip()
    with conn.cursor() as c:
        c.execute(f"SELECT id FROM {t['cat']} WHERE id=%s AND activo=1", (datos.categoria_id,))
        if not c.fetchone():
            raise HTTPException(404, "La categoría no existe.")
        try:
            if tipo == Tipo.medicamento:
                c.execute("INSERT INTO medicamentos (categoria_id, nombre, presentacion) VALUES (%s,%s,%s)",
                          (datos.categoria_id, nombre, (datos.presentacion or "").strip() or None))
            else:
                c.execute("INSERT INTO actividades (categoria_id, nombre) VALUES (%s,%s)",
                          (datos.categoria_id, nombre))
        except pymysql.err.IntegrityError:
            conn.rollback()
            raise HTTPException(409, f"«{nombre}» ya existe en esa categoría.")
        nuevo = c.lastrowid
    conn.commit()
    pres = (datos.presentacion or "").strip() or None
    return ItemCatalogoCreado(id=nuevo, categoria_id=datos.categoria_id, nombre=nombre,
                              presentacion=pres if tipo == Tipo.medicamento else None)


# ═══════════════════════════════════════════════════════════
# Itinerario: programar, consultar, marcar y eliminar
# ═══════════════════════════════════════════════════════════
def _programar(conn, session, residente_id: int, tipo: str, item_id: int, datos: _ProgramarBase,
               dosis: Optional[str]):
    horas, e1 = horas_validas(datos.horas)
    fechas, e2 = fechas_validas(",".join(f.isoformat() for f in datos.fechas))
    if e1 or e2:
        raise HTTPException(422, e1 or e2)

    if not puede_editar_agenda(conn, session, residente_id):
        raise HTTPException(403, "Ese residente no está asignado a tu cuenta.")
    with conn.cursor() as c:
        c.execute("SELECT 1 FROM residentes WHERE id=%s", (residente_id,))
        if not c.fetchone():
            raise HTTPException(404, "Residente no encontrado.")
    if not item_existe(conn, tipo, item_id, datos.categoria_id):
        raise HTTPException(422, "El elemento no pertenece a esa categoría.")

    personal_id = None
    with conn.cursor() as c:
        if session["rol"] == "Administrador":
            if datos.personal_id:
                c.execute("SELECT id FROM personal WHERE id=%s AND activo=1", (datos.personal_id,))
                if not c.fetchone():
                    raise HTTPException(422, "El responsable no existe o está inactivo.")
                personal_id = datos.personal_id
        else:
            c.execute("SELECT id FROM personal WHERE usuario_id=%s AND activo=1", (session["user_id"],))
            p = c.fetchone()
            personal_id = p["id"] if p else None

    try:
        guardar(conn, residente_id=residente_id, fechas=fechas, tipo=tipo, item_id=item_id,
                horas=horas, dosis=dosis, observaciones=(datos.observaciones or "").strip() or None,
                personal_id=personal_id, creado_por=session["user_id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    fk = TIPOS[tipo]["fk"]
    marcas = ", ".join(["%s"] * len(fechas))
    with conn.cursor() as c:
        c.execute(
            f"""SELECT i.id, i.fecha, i.tipo, i.dosis, i.horas, i.observaciones,
                       COALESCE(m.nombre, a.nombre) AS nombre
                FROM itinerario_diario i
                LEFT JOIN medicamentos m ON m.id = i.medicamento_id
                LEFT JOIN actividades  a ON a.id = i.actividad_id
                WHERE i.residente_id=%s AND i.tipo=%s AND i.{fk}=%s AND i.fecha IN ({marcas})
                ORDER BY i.fecha""", (residente_id, tipo, item_id, *fechas))
        filas = c.fetchall()
    for f in filas:
        f["horas"] = _lista(f["horas"])
    return filas


@router.post("/residentes/{residente_id}/medicamentos", response_model=List[ItinerarioFilaOut],
             status_code=201, tags=["Itinerario"], summary="Programar un medicamento",
             responses={**R401, **R403, **R404})
def programar_medicamento(residente_id: int, datos: ProgramarMedicamentoIn,
                          session=Depends(api_staff), conn=Depends(_bd)):
    """Guarda en `itinerario_diario` UNA fila por día. Si ese medicamento ya estaba
    programado ese día, las horas se fusionan en la misma fila. Aparece al instante en
    la agenda del residente, en el panel del cuidador y genera la alerta a su hora."""
    return _programar(conn, session, residente_id, "medicamento", datos.medicamento_id,
                      datos, datos.dosis.strip())


@router.post("/residentes/{residente_id}/actividades", response_model=List[ItinerarioFilaOut],
             status_code=201, tags=["Itinerario"], summary="Programar una actividad",
             responses={**R401, **R403, **R404})
def programar_actividad(residente_id: int, datos: ProgramarActividadIn,
                        session=Depends(api_staff), conn=Depends(_bd)):
    return _programar(conn, session, residente_id, "actividad", datos.actividad_id, datos, None)


@router.get("/residentes/{residente_id}/medicamentos", response_model=List[ProgramadoOut],
            tags=["Itinerario"], summary="Medicamentos programados (hoy en adelante)",
            responses={**R401, **R404})
def medicamentos_programados(residente_id: int, session=Depends(api_staff), conn=Depends(_bd)):
    if not puede_ver_residente(conn, session, residente_id):
        raise HTTPException(404, "Residente no encontrado.")
    return [{**g, "ids": [int(i) for i in g["ids"]],
             "fechas": [date.fromisoformat(f) for f in g["fechas"]]}
            for g in listado(conn, residente_id, "medicamento")]


@router.get("/residentes/{residente_id}/itinerario/{fecha}", response_model=DiaOut,
            tags=["Itinerario"], summary="Itinerario de un día", responses={**R401, **R403})
def itinerario_del_dia(residente_id: int, fecha: date, session=Depends(api_user), conn=Depends(_bd)):
    """Lectura del día: medicamentos y actividades con su estado ✓/✗."""
    if not puede_ver_agenda(conn, session, residente_id):
        raise HTTPException(403, "Sin acceso a ese residente.")
    with conn.cursor() as c:
        c.execute("SELECT texto FROM itinerario_observaciones WHERE residente_id=%s AND fecha=%s",
                  (residente_id, fecha))
        o = c.fetchone()
    return {"fecha": fecha, "editable": puede_editar_agenda(conn, session, residente_id),
            "observaciones": o["texto"] if o else "", "items": dia(conn, residente_id, fecha)}


@router.patch("/itinerario/{itinerario_id}/check", response_model=CheckOut, tags=["Itinerario"],
              summary="Marcar una hora como realizada (✓) o pendiente (✗)",
              responses={**R401, **R403, 422: {"model": Error, "description": "La hora no existe."}})
def marcar_hora(itinerario_id: int, datos: CheckIn, session=Depends(api_staff), conn=Depends(_bd)):
    """Al marcar ✓ también queda un registro en el Historial."""
    with conn.cursor() as c:
        c.execute("SELECT residente_id FROM itinerario_diario WHERE id=%s", (itinerario_id,))
        fila = c.fetchone()
    if not fila or not puede_editar_agenda(conn, session, fila["residente_id"]):
        raise HTTPException(403, "No tienes permiso.")
    try:
        if not marcar(conn, itinerario_id, datos.hora, datos.completado, session["user_id"]):
            raise HTTPException(422, "Esa hora no existe en el itinerario.")
        if datos.completado:
            d = detalle_entrada(conn, itinerario_id)
            registrar_en_historial(
                conn, fecha=d["fecha"].isoformat(), hora=datetime.now().strftime("%H:%M"),
                tipo="Medicamento" if d["tipo"] == "medicamento" else "Actividad",
                actividad=f"Realizado: {d['nombre']} ({datos.hora})", residente=d["residente"],
                cuidador=nombre_para_registro(conn, session))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return CheckOut(id=itinerario_id, hora=datos.hora, completado=datos.completado)


@router.delete("/residentes/{residente_id}/itinerario/{itinerario_id}", response_model=EliminadoOut,
               tags=["Itinerario"], summary="Eliminar una entrada del itinerario (solo admin)",
               responses={**R401, **R403, **R404})
def eliminar_entrada(residente_id: int, itinerario_id: int, session=Depends(api_admin), conn=Depends(_bd)):
    """Borra la fila (de hoy en adelante) y, en cascada, sus ✓."""
    try:
        n = eliminar(conn, residente_id, [itinerario_id])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if not n:
        raise HTTPException(404, "No se encontró esa entrada (o es de un día anterior).")
    return EliminadoOut(eliminados=n)


# Las rutas de la API llevan el prefijo "api_" en su nombre interno. Sin esto,
# url_for("login") y url_for("logout") de las pantallas HTML resolvían a
# /api/v1/auth/... (mismo nombre de función) y devolvían JSON en crudo.
for _ruta in router.routes:
    _ruta.name = f"api_{_ruta.name}"
