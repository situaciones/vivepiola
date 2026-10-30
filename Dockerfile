# Imagen de SINCONFLICTO para Cloud Run (Google Cloud, region Santiago).
#
# Una sola imagen sirve todo: la API de Django (web, Android, iPhone y el
# webhook de WhatsApp) y la app web ya compilada. La misma imagen corre los
# jobs (migrate, resumen diario, reintentos): solo cambia el comando.

# --- 1. La app web (React) -------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Web y API comparten dominio: la API queda en /api del mismo sitio.
RUN VITE_API_URL=/api npx vite build

# --- 2. El backend (Django) -------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# mysqlclient compila contra la libreria cliente de MySQL.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY vivepiola/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vivepiola/ ./
COPY --from=web /web/dist ./frontend_dist

# Los estaticos del admin se empaquetan en la imagen y los sirve whitenoise.
# collectstatic no toca la base: sqlite evita exigir credenciales al construir.
RUN SECRET_KEY=solo-para-construir DB_ENGINE=sqlite python manage.py collectstatic --noinput

# Cloud Run indica el puerto en $PORT.
CMD exec gunicorn condoadmin.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120
