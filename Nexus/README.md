#  Nexus — Sistema de Información para Hogares Geriátricos

Nexus es una aplicación web pensada para la gestión integral de un hogar
geriátrico: residentes, personal de cuidado, horarios de actividades,
medicamentos, seguimiento familiar, historial clínico/asistencial y
notificaciones de alertas. Todo desde un solo panel, con roles de acceso
diferenciados (Administrador, Cuidador, Familiar).

Construido con **FastAPI** + **SQLite** + **Jinja2** + **Bootstrap 5**.

---

## Equipo Nexus

- Dilan Carreño
- Jarek Luque
- Joshua Nocua
- Susan López

Proyecto desarrollado como parte del programa **Tecnólogo en Análisis y
Desarrollo de Software** — SENA.

---

##  Funcionalidades

| Módulo | Descripción |
|---|---|
|  **Autenticación** | Login, registro y roles (Administrador, Cuidador, Familiar) |
|  **Residentes** | Registro completo: datos personales, diagnóstico, alergias, familiar responsable |
|  **Personal** | Gestión de cuidadores, turnos, estado activo/inactivo y panel individual con sus actividades asignadas |
|  **Asignaciones** | El administrador asigna residentes a cada cuidador; el cuidador solo ve (y su historial solo muestra) lo suyo |
|  **Horarios** | Programación de actividades por residente, con cuidador asignado |
|  **Medicamentos** | Control de medicamentos por residente: dosis, horario y observaciones |
|  **Vista Familiar** | Panel de solo lectura para que un familiar consulte el estado de su residente |
|  **Historial** | Bitácora de actividades y medicamentos aplicados, con filtros por residente, cuidador y rango de fechas |
|  **Notificaciones** | Alertas con estado Pendiente / Completada — crear, editar, completar y eliminar |
|  **Usuarios** | Panel exclusivo de Administrador para gestionar las cuentas del sistema |

---

##  Tecnologías

- **FastAPI** — backend y enrutamiento
- **Jinja2** — plantillas del lado del servidor
- **SQLite** — base de datos
- **Bootstrap 5.3** — estilos base
- **Starlette SessionMiddleware** — sesiones de usuario

---

##  Instalación y ejecución

La generación de PDF (`generar_pdf.js`) usa Node.js, así que también hay que instalar sus dependencias:

```bash
npm install
```

### 1. Crear y activar entorno virtual

**Windows**
```bash
cd nexus
python -m venv venv
venv\Scripts\activate
```

**Linux / Mac**
```bash
cd nexus
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```
Docuementacion Swagger: python -m database.schema

### 3. usuarios de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `admin123` |
| Cuidador | `cuidador` | `cuidador123` |
| Familiar | `familiar` | `familiar123` |

### 4. Ejecutar el servidor

```bash
uvicorn main:app --reload
```

Abre  `http://127.0.0.1:8000`

---

##Estructura del proyecto

```
Nexus/
├── main.py                     # Creación de la app, middleware, lifespan, include_router
├── requirements.txt
├── nexus.db
├── core/
│   ├── config.py                # Rutas base, SECRET_KEY, roles, constantes
│   ├── security.py               # Hash de contraseñas
│   ├── templates.py              # Jinja2Templates, render(), flash()
│   ├── auth.py                    # login_required / admin_required / staff_required
│   └── tasks.py                   # Tarea en segundo plano de notificaciones (RF05)
├── database/
│   ├── connection.py             # get_db()
│   └── schema.py                  # init_db(): creación de tablas + migraciones
├── routers/
│   ├── auth.py                    # /, /login, /registro, /logout
│   ├── dashboard.py
│   ├── residentes.py
│   ├── horarios.py
│   ├── usuarios.py
│   ├── familiar.py
│   ├── medicamentos.py
│   ├── personal.py
│   ├── historial.py
│   ├── notificaciones.py
│   └── perfil.py
├── static/
│   ├── css/nexus.css
│   └── img/logo.png
└── templates/
    ├── base.html
    ├── login.html / registro.html
    ├── dashboard.html
    ├── residentes/
    ├── personal/
    ├── horarios/
    ├── medicamentos/
    ├── familiar/
    ├── historial/
    ├── notificaciones/
    ├── perfil/
    └── usuarios/
```


---

## Roles del sistema

- **Administrador** — acceso total, incluida la gestión de usuarios.
- **Cuidador** — acceso operativo: residentes, horarios, medicamentos, personal, historial y notificaciones.
- **Familiar** — acceso restringido únicamente a `/familiar` en modo lectura. El resto de los módulos
  responde con un redireccionamiento y un mensaje de permisos (`staff_required` en `main.py`).

---


Equipo Nexus. 💙

