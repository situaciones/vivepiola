"""
Settings para la suite de pruebas: base SQLite en memoria.

Permite correr `manage.py test --settings=condoadmin.settings_test` sin
levantar MySQL. Los triggers de inmutabilidad de ActaSellada se emiten
tambien en SQLite (ver migracion 0004), de modo que la prueba de
inmutabilidad a nivel de motor sigue siendo real y no un placebo.
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Integraciones externas apagadas: la suite no debe salir a la red.
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ANTHROPIC_API_KEY = ''
TWILIO_ACCOUNT_SID = ''
TWILIO_AUTH_TOKEN = ''
TWILIO_WHATSAPP_FROM = ''
GOOGLE_OAUTH_CLIENT_ID = ''
GOOGLE_OAUTH_MOCK = True

# Archivos en disco temporal, nunca en el bucket de produccion.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # tests mas rapidos
