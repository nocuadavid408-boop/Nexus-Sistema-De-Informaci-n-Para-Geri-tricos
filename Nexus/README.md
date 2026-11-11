#  Nexus — Sistema de Información para Hogares Geriátricos

Nexus es una aplicación web pensada para la gestión integral de un hogar
geriátrico: residentes, personal de cuidado, horarios de actividades,
medicamentos, seguimiento familiar, historial clínico/asistencial y
notificaciones de alertas. Todo desde un solo panel, con roles de acceso
diferenciados (Administrador, Cuidador, Familiar).

Construido con **FastAPI** + **MariaDB/MySQL** + **Jinja2** + **Bootstrap 5**.

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
- **MariaDB / MySQL** (PyMySQL) — base de datos
- **Bootstrap 5.3** — estilos base
- **Starlette SessionMiddleware** — sesiones de usuario

---

##  Instalación y ejecución

Requisitos: Python 3.10+, MariaDB 10.4+ / MySQL 8 (por ejemplo XAMPP) y Node.js (solo para `generar_pdf.js`).

### 1. Crear y activar el entorno virtual

**Windows**
```bash
cd Nexus
python -m venv venv
venv\Scripts\activate
```

**Linux / Mac**
```bash
cd Nexus
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
npm install
```

### 3. Configurar la base de datos (`nexus_v3.sql`)

Sigue este orden exacto:

1. **Inicia MariaDB/MySQL** (en XAMPP: *Start* en el módulo MySQL).
2. **(Opcional) Variables de entorno** si tu servidor no usa los valores por defecto de XAMPP:

   | Variable | Por defecto |
   |---|---|
   | `NEXUS_DB_HOST` | `127.0.0.1` |
   | `NEXUS_DB_PORT` | `3306` |
   | `NEXUS_DB_USER` | `root` |
   | `NEXUS_DB_PASSWORD` | *(vacía)* |
   | `NEXUS_DB_NAME` | `nexus_proyecto` |

3. **Crea la base, las tablas y los datos iniciales** con **una** de estas opciones:

   ```bash
   # Opción A — con el script del proyecto (entorno virtual activo)
   python -m database.schema

   # Opción B — con el cliente de MySQL
   mysql -u root < database/nexus_v3.sql
   ```

   Opción C: importar `database/nexus_v3.sql` desde phpMyAdmin (pestaña *Importar*).

   > ⚠️ El script elimina las tablas antiguas (`actividades` anterior, `medicamentos_residente`,
   > `medicamento_horas`, `catalogo_medicamentos`, `agenda_eventos`). Haz respaldo si tienes datos que conservar.

4. **Verifica** que existan las tablas: `usuarios`, `residentes`, `personal`, `asignaciones`,
   `categorias_medicamentos`, `medicamentos`, `categorias_actividades`, `actividades`,
   `itinerario_diario`, `itinerario_checks`, `itinerario_observaciones`.
   Si falta alguna, la aplicación **no arranca** y el error indica qué importar.

Modelo: `categorias_medicamentos → medicamentos` y `categorias_actividades → actividades` (1:N).
`itinerario_diario` guarda UNA fila por residente, día y medicamento/actividad, con las horas en JSON
(`["06:00","12:00"]`); el ✓ de cada hora está en `itinerario_checks`; las observaciones generales del día
en `itinerario_observaciones`.

### 4. Usuarios de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `admin123` |
| Cuidador | `cuidador` | `cuidador123` |
| Familiar | `familiar` | `familiar123` |

### 5. Ejecutar el servidor

```bash
uvicorn main:app --reload
```

- Aplicación: `http://localhost:8000/` (redirige al login o al panel según la sesión).
- Documentación Swagger: `http://localhost:8000/docs` (única ruta de la documentación).

---

##Estructura del proyecto

```
Nexus/
├── main.py                     # Creación de la app, middleware, lifespan, include_router
├── requirements.txt
├── core/
│   ├── config.py                # Rutas base, SECRET_KEY, roles, constantes
│   ├── security.py               # Hash de contraseñas
│   ├── templates.py              # Jinja2Templates, render(), flash()
│   ├── auth.py                    # login_required / admin_required / staff_required
│   └── tasks.py                   # Tarea en segundo plano de notificaciones (RF05)
├── database/
│   ├── connection.py             # get_db()
│   ├── schema.py                  # init_db(): ejecuta nexus_v3.sql
│   └── nexus_v3.sql               # Esquema + datos iniciales (MariaDB/MySQL)
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



## API y documentación (Swagger)

Con el servidor activo abre `http://localhost:8000/docs` (el esquema JSON está en `/docs/openapi.json`). Inicia sesión con `POST /api/v1/auth/login`
(`admin` / `admin123`) y prueba el resto con **Try it out**: lo que registres (por ejemplo
`POST /api/v1/residentes` o `POST /api/v1/residentes/{id}/medicamentos`) se guarda en MariaDB/MySQL y aparece en la agenda, el panel y el historial.
El esquema se genera en vivo desde `routers/api.py`.
