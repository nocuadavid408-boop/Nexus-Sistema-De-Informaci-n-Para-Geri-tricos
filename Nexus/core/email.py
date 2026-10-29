"""
Envío del código de verificación por correo electrónico.

Si el servidor SMTP no está configurado (variables de entorno
NEXUS_SMTP_*), no es posible entregar correos reales: en ese caso el
código se registra en la consola del servidor para poder seguir
probando el flujo en desarrollo local, y la función devuelve False
para que el llamador sepa que el envío real no ocurrió.
"""

import smtplib
from email.message import EmailMessage

from core.config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
    CODIGO_VERIFICACION_MINUTOS,
)


def enviar_codigo_verificacion(destinatario: str, nombre: str, codigo: str) -> bool:
    """Envía el código de verificación al correo indicado.

    Devuelve True si el correo se envió realmente por SMTP, o False si el
    SMTP no está configurado (en ese caso el código queda impreso en la
    consola del servidor, únicamente como apoyo para desarrollo local).
    """
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        print(
            f"[email] SMTP no configurado. Código de verificación para "
            f"{destinatario}: {codigo} (válido {CODIGO_VERIFICACION_MINUTOS} min)"
        )
        return False

    mensaje = EmailMessage()
    mensaje["Subject"] = "Nexus — Código para cambiar tu contraseña"
    mensaje["From"] = SMTP_FROM
    mensaje["To"] = destinatario
    mensaje.set_content(
        f"Hola {nombre},\n\n"
        f"Tu código de verificación para cambiar la contraseña de tu cuenta "
        f"Nexus es:\n\n    {codigo}\n\n"
        f"Este código es válido por {CODIGO_VERIFICACION_MINUTOS} minutos y "
        f"solo puede usarse una vez.\n\n"
        f"Si tú no solicitaste este cambio, ignora este mensaje."
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as servidor:
            if SMTP_USE_TLS:
                servidor.starttls()
            servidor.login(SMTP_USER, SMTP_PASSWORD)
            servidor.send_message(mensaje)
        return True
    except Exception as e:  # el flujo nunca debe romperse por un error de envío
        print(f"[email] Error al enviar el código a {destinatario}: {e}")
        return False
