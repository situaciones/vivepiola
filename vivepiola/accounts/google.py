"""
Verificacion del ID token de Google Identity Services.

Sin dependencias nuevas: el token se valida contra el endpoint oficial
tokeninfo usando `requests` (ya presente en el proyecto). Cuando no hay
GOOGLE_OAUTH_CLIENT_ID configurado y el modo simulado esta activo
(GOOGLE_OAUTH_MOCK, por defecto = DEBUG), se aceptan credenciales con el
formato "mock:correo[:Nombre Completo]" para probar el flujo completo de
invitaciones y asignacion de roles sin claves reales.
"""

import requests
from django.conf import settings

TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo'


class GoogleAuthError(Exception):
    """Credencial invalida o proveedor no configurado."""


def verificar_credencial_google(credential):
    """Devuelve {'email', 'nombre', 'apellido', 'mock'} o lanza GoogleAuthError."""
    credential = (credential or '').strip()
    if not credential:
        raise GoogleAuthError('Debe enviar la credencial de Google.')

    client_id = settings.GOOGLE_OAUTH_CLIENT_ID

    if not client_id:
        if not settings.GOOGLE_OAUTH_MOCK:
            raise GoogleAuthError('El ingreso con Google no esta configurado (falta GOOGLE_OAUTH_CLIENT_ID).')
        if not credential.startswith('mock:'):
            raise GoogleAuthError('Modo simulado: la credencial debe ser "mock:correo[:Nombre Completo]".')
        partes = credential[len('mock:'):].split(':', 1)
        email = partes[0].strip().lower()
        if '@' not in email:
            raise GoogleAuthError('Modo simulado: correo invalido.')
        nombre_completo = (partes[1].strip() if len(partes) > 1 else '') or email.split('@')[0]
        trozos = nombre_completo.split(' ', 1)
        return {
            'email': email,
            'nombre': trozos[0],
            'apellido': trozos[1] if len(trozos) > 1 else '',
            'mock': True,
        }

    try:
        resp = requests.get(TOKENINFO_URL, params={'id_token': credential}, timeout=10)
    except requests.RequestException as exc:
        raise GoogleAuthError(f'No se pudo validar el token con Google: {exc}')
    if resp.status_code != 200:
        raise GoogleAuthError('El token de Google es invalido o expiro.')

    data = resp.json()
    if data.get('aud') != client_id:
        raise GoogleAuthError('El token no fue emitido para esta aplicacion.')
    if str(data.get('email_verified')).lower() != 'true':
        raise GoogleAuthError('El correo de la cuenta Google no esta verificado.')

    return {
        'email': data['email'].lower(),
        'nombre': data.get('given_name') or data.get('name') or data['email'].split('@')[0],
        'apellido': data.get('family_name') or '',
        'mock': False,
    }
