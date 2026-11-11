"""
Configuración central del proyecto: rutas base, ubicación de la base de
datos, directorios de estáticos/plantillas y parámetros generales.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE = os.path.join(BASE_DIR, "nexus.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Clave usada por SessionMiddleware para firmar la cookie de sesión.
# En producción SIEMPRE debe definirse mediante la variable de entorno
# NEXUS_SECRET_KEY; el valor por defecto solo es válido para desarrollo
# local y nunca debería usarse en un despliegue real.
SECRET_KEY = os.environ.get("NEXUS_SECRET_KEY", "nexus_sena_3407184_2026")

# Roles con acceso operativo (gestión de residentes, personal, horarios,
# medicamentos, historial y notificaciones). El rol Familiar queda excluido
# de todos estos módulos y solo puede consultar su vista de solo lectura en
# /familiar, cumpliendo RF01 (control de acceso por rol) y RF09 (el familiar
# no debe poder crear, editar ni eliminar información).
STAFF_ROLES = ("Administrador", "Cuidador")

# Roles permitidos en el autorregistro público (/registro). El rol
# Administrador nunca debe poder crearse desde aquí; solo se asigna desde
# /usuarios por un Administrador ya existente.
ROLES_AUTORREGISTRO = ("Cuidador", "Familiar")

# Intervalo (segundos) de la tarea en segundo plano que revisa si hay
# actividades u horarios de medicamentos que coincidan con el minuto actual
# para generar notificaciones automáticas (RF05). La alerta se genera y
# suena exactamente a la hora programada de la actividad/medicamento (sin
# anticipación): el menú de notificaciones solo registra alertas que ya
# sonaron, vinculadas a los horarios de medicamentos y actividades.
INTERVALO_REVISION_SEGUNDOS = 15

# ══════════════════════════════════════════════════════════
# RECUPERACIÓN DE CONTRASEÑA POR CORREO
# ══════════════════════════════════════════════════════════
# Minutos que un código de verificación es válido antes de expirar.
CODIGO_VERIFICACION_MINUTOS = 10

# Configuración del servidor SMTP usado para enviar el código de
# verificación al correo del usuario. En producción SIEMPRE debe
# definirse mediante variables de entorno; si no está configurado,
# el sistema no puede enviar correos reales y el código se registra
# en la consola del servidor (SOLO para desarrollo/pruebas locales).
SMTP_HOST = os.environ.get("NEXUS_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("NEXUS_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("NEXUS_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("NEXUS_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("NEXUS_SMTP_FROM", SMTP_USER)
SMTP_USE_TLS = os.environ.get("NEXUS_SMTP_TLS", "1") != "0"
