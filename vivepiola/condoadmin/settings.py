"""
Django settings for condoadmin project.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = config('DEBUG', default=True, cast=bool)

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


# WhatsApp (Twilio) — canal COMPLEMENTARIO de aviso. El canal legal de la
# notificacion sigue siendo el correo; el WhatsApp nunca lo reemplaza y su
# fallo jamas bloquea el flujo. Vacio = canal deshabilitado.

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_WHATSAPP_FROM = config('TWILIO_WHATSAPP_FROM', default='')  # ej: whatsapp:+14155238886


# Parametros legales del negocio (Ley 21.442 - Chile)

NOVEDADES_PLAZO_RESPUESTA_DIAS = config('NOVEDADES_PLAZO_RESPUESTA_DIAS', default=20, cast=int)
REINCIDENCIA_VENTANA_MESES = config('REINCIDENCIA_VENTANA_MESES', default=6, cast=int)
DESCARGO_PLAZO_DEFAULT_DIAS = config('DESCARGO_PLAZO_DEFAULT_DIAS', default=5, cast=int)
