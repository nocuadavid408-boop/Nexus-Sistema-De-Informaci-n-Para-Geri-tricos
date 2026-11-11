"""
Utilidades de seguridad: hashing de contraseñas y códigos de verificación.
"""

import hashlib
import secrets


def hash_password(password: str) -> str:
    """Devuelve el hash SHA-256 (hexadecimal) de una contraseña en texto plano."""
    return hashlib.sha256(password.encode()).hexdigest()


def generar_codigo_verificacion() -> str:
    """Genera un código numérico de 6 dígitos, aleatorio y distinto en cada
    llamada, usado para verificar por correo el cambio de contraseña."""
    return f"{secrets.randbelow(1_000_000):06d}"
