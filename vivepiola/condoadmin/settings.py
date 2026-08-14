"""
Django settings for condoadmin project.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# Por defecto FALSE: si una variable falta en el entorno, el sistema debe
# fallar cerrado (sin trazas ni datos expuestos), nunca abrir el modo debug.
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',

    'accounts',
    'condominios',
    'reglamentos',
    'multas',
    'novedades',
    'gastos_comunes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'condoadmin.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'condoadmin.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# Produccion usa MySQL. DB_ENGINE=sqlite levanta el sistema completo sobre un
# archivo local, para probar el flujo end-to-end sin instalar un motor.
if config('DB_ENGINE', default='mysql') == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_local.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME', default='condoadmin'),
            'USER': config('DB_USER', default='root'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='127.0.0.1'),
            'PORT': config('DB_PORT', default='3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
            },
        }
    }

AUTH_USER_MODEL = 'accounts.Usuario'


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'es-cl'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True


# Static / media files

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Almacenamiento de archivos.
#
# CRITICO: en PaaS (DigitalOcean App Platform) el disco del contenedor es
# EFIMERO — todo lo subido a MEDIA_ROOT (evidencias, PDFs de notificacion,
# reglamentos, descargos) se PIERDE en cada deploy/reinicio. Para un producto
# de prueba legal eso rompe la integridad del expediente. Por eso, si hay un
# bucket S3-compatible configurado (DigitalOcean Spaces), los archivos de media
# se guardan alli de forma persistente. Los estaticos los sigue sirviendo
# WhiteNoise desde el contenedor.

AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL', default='')  # ej: https://nyc3.digitaloceanspaces.com
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='')
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default='')  # ej: cdn.vivepiola.cl o <bucket>.<region>.cdn.digitaloceanspaces.com
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = config('AWS_QUERYSTRING_AUTH', default=True, cast=bool)  # URLs firmadas: evidencias privadas por defecto

_USA_SPACES = bool(AWS_STORAGE_BUCKET_NAME)

_default_storage = (
    {'BACKEND': 'storages.backends.s3.S3Storage'}
    if _USA_SPACES
    else {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
)

STORAGES = {
    'default': _default_storage,
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}


# CORS (frontend React en Vite, puerto 5173 por defecto)

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173',
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True


# Correo (canal legal de notificacion)

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='notificaciones@vivepiola.cl')


# Integracion IA (extraccion de infracciones desde reglamento en PDF)

ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')


# Analisis de evidencia (fotos y videos).
#
# Se usa Gemini y no Anthropic porque es el unico de los grandes que ingiere el
# archivo de VIDEO completo: los demas exigen extraer fotogramas, o sea
# arrastrar una libreria de video al despliegue y elegir a ciegas que instantes
# representan el hecho. El razonamiento legal se queda en Anthropic, donde
# viven las salvaguardas del clasificador.
#
# Vacio = sin analisis visual. La evidencia igual queda en el expediente y la
# sigue viendo una persona: el sistema se degrada, no se cae.

GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODELO_VISION = config('GEMINI_MODELO_VISION', default='gemini-2.5-flash')

# Cuantas piezas se mandan por reporte y cuanto puede pesar cada una. Sin tope,
# tres videos de 50 MB en un solo reporte harian una llamada carisima y lenta.
VISION_MAX_PIEZAS = config('VISION_MAX_PIEZAS', default=4, cast=int)
VISION_MAX_BYTES_POR_PIEZA = config(
    'VISION_MAX_BYTES_POR_PIEZA', default=20 * 1024 * 1024, cast=int,
)
VISION_MAX_CARACTERES = config('VISION_MAX_CARACTERES', default=1500, cast=int)


# WhatsApp (Twilio) — canal COMPLEMENTARIO de aviso. El canal legal de la
# notificacion sigue siendo el correo; el WhatsApp nunca lo reemplaza y su
# fallo jamas bloquea el flujo. Vacio = canal deshabilitado.

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_WHATSAPP_FROM = config('TWILIO_WHATSAPP_FROM', default='')  # ej: whatsapp:+14155238886


# Ingreso con Google (Google Identity Services).
# Sin CLIENT_ID y con GOOGLE_OAUTH_MOCK=True (default en DEBUG), el endpoint
# /api/auth/google/ acepta credenciales "mock:correo[:Nombre]" para probar el
# flujo de invitaciones sin claves reales. En produccion (DEBUG=False) el modo
# simulado queda apagado salvo que se habilite explicitamente.

GOOGLE_OAUTH_CLIENT_ID = config('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_MOCK = config('GOOGLE_OAUTH_MOCK', default=DEBUG, cast=bool)

# URL publica del frontend, usada en los correos de invitacion.
FRONTEND_URL = config('FRONTEND_URL', default='https://vivepiola-p3oup.ondigitalocean.app')


# Parametros legales del negocio (Ley 21.442 - Chile)

NOVEDADES_PLAZO_RESPUESTA_DIAS = config('NOVEDADES_PLAZO_RESPUESTA_DIAS', default=20, cast=int)
REINCIDENCIA_VENTANA_MESES = config('REINCIDENCIA_VENTANA_MESES', default=6, cast=int)

# Confianza minima (0-100) del clasificador para notificar una denuncia sin que
# una persona la tipifique antes.
#
# El umbral SUBE con la gravedad, porque los dos numeros responden preguntas
# distintas: la confianza dice "entendi bien que paso" y la gravedad dice
# "cuanto pesa equivocarse". Cursar sola una falta leve que ademas sera un
# aviso sin cobro casi no tiene costo si el encuadre falla; cursar sola una
# gravisima significa cobrar de inmediato un monto alto, sin cortesia y
# posiblemente con una paralizacion detras.
#
# Poner un umbral sobre 100 equivale a exigir siempre revision humana para esa
# gravedad, porque el clasificador nunca supera 100.
CURSE_CONFIANZA_MINIMA_LEVE = config('CURSE_CONFIANZA_MINIMA_LEVE', default=65, cast=int)
CURSE_CONFIANZA_MINIMA_GRAVE = config('CURSE_CONFIANZA_MINIMA_GRAVE', default=80, cast=int)
CURSE_CONFIANZA_MINIMA_GRAVISIMA = config('CURSE_CONFIANZA_MINIMA_GRAVISIMA', default=90, cast=int)

# Cuanta normativa transversal se le entrega a la IA por llamada. Mandar la ley
# completa en cada clasificacion es caro y casi siempre innecesario, porque el
# catalogo ya la tiene encarnada; al leer un reglamento nuevo, en cambio, es
# justo donde mas sirve. Por eso el presupuesto es distinto en cada caso.
NORMATIVA_PRESUPUESTO_CARACTERES = config(
    'NORMATIVA_PRESUPUESTO_CARACTERES', default=40000, cast=int,
)
NORMATIVA_PRESUPUESTO_CLASIFICACION = config(
    'NORMATIVA_PRESUPUESTO_CLASIFICACION', default=6000, cast=int,
)

CURSE_CONFIANZA_MINIMA = {
    'LEVE': CURSE_CONFIANZA_MINIMA_LEVE,
    'GRAVE': CURSE_CONFIANZA_MINIMA_GRAVE,
    'GRAVISIMA': CURSE_CONFIANZA_MINIMA_GRAVISIMA,
}

# Un video de evidencia sin tope se sube entero al almacenamiento y lo paga la
# comunidad. 50 MB alcanza de sobra para el clip de unos segundos que prueba un
# hecho; lo que exceda eso no es evidencia, es una grabacion sin recortar.
EVIDENCIA_VIDEO_MAX_MB = config('EVIDENCIA_VIDEO_MAX_MB', default=50, cast=int)
EVIDENCIA_VIDEO_FORMATOS = ('.mp4', '.mov', '.webm', '.3gp', '.m4v')
DESCARGO_PLAZO_DEFAULT_DIAS = config('DESCARGO_PLAZO_DEFAULT_DIAS', default=5, cast=int)
