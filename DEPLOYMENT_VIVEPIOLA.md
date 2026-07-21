# VIVEPIOLA.CL — Plan de Deployment a Producción

**Fecha**: 20 de julio de 2026  
**Dominio**: vivepiola.cl  
**Stack**: Django 6.0 + React 19 + MySQL 8.4  
**Presupuesto**: $5-20 USD/mes

---

## Fase 1: Preparación (Hoy)

### 1.1 Cambio de branding: Debido → VIVEPIOLA ✓
- [x] Actualizar nombre en Frontend (React) ✓
- [x] Actualizar nombre en Backend (Django) ✓
- [x] Cambiar email de notificación a notificaciones@vivepiola.cl ✓
- [x] Compilar React build ✓

### 1.2 Configurar email real (SendGrid)
**Por qué**: Hoy el email está en modo "consola" — las notificaciones no salen de verdad.

**Pasos**:
1. Crear cuenta gratuita en https://sendgrid.com (100 emails/día gratis)
2. Obtener API Key (Settings → API Keys → Create API Key)
3. Guardar en `.env`:
   ```
   EMAIL_BACKEND=sendgrid_backend.SendgridBackend
   SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   DEFAULT_FROM_EMAIL=notificaciones@vivepiola.cl
   ```
4. Instalar librería: `pip install sendgrid-django`

**Alternativa barata**: AWS SES (aun más barato, pero más complejo)

### 1.3 Dominio vivepiola.cl
**Por hacer**: Registrarlo en NIC.cl o tu registrador favorito (~$15-20 CLP/año)

Datos que necesitarás después:
- Acceso al panel de control del registrador
- Capacidad de cambiar los servidores de nombres (nameservers)

---

## Fase 2: Infraestructura (DigitalOcean)

**Opción elegida**: DigitalOcean (simple, barato, buena documentación)

### 2.1 Crear App en DigitalOcean
1. Ir a https://www.digitalocean.com/products/app-platform
2. "Create App" → GitHub/GitLab → conecta tu repo
3. Configuración:
   - **Framework**: Python / Django
   - **Branch**: main
   - **Build command**: `pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput`
   - **Run command**: `gunicorn condoadmin.wsgi --bind 0.0.0.0:8080`
   - **HTTP Port**: 8080

### 2.2 Crear Base de Datos Managed (MySQL)
1. En DigitalOcean Dashboard: **Databases** → **Create Database Cluster**
2. Elegir:
   - **Engine**: MySQL 8.4
   - **Size**: Basic (Shared CPU, 1GB RAM) ~$18/mes
   - **Datacenter**: Toronto (cercano a Chile)
   - **High Availability**: Sin (ahorrar costo)

3. Copiar credenciales de conexión

### 2.3 Configurar variables de ambiente en la App
En el dashboard de App Platform, agregar:
```
DEBUG=False
SECRET_KEY=<generar con Django>
ALLOWED_HOSTS=vivepiola.cl,www.vivepiola.cl,app.vivepiola.cl
DB_ENGINE=mysql
DB_NAME=<nombre de BD>
DB_USER=<usuario de BD>
DB_PASSWORD=<contraseña de BD>
DB_HOST=<host de BD>
DB_PORT=3306
EMAIL_BACKEND=sendgrid_backend.SendgridBackend
SENDGRID_API_KEY=<clave de SendGrid>
ANTHROPIC_API_KEY=<clave de Claude (opcional, para IA)>
CORS_ALLOWED_ORIGINS=https://vivepiola.cl,https://www.vivepiola.cl,https://app.vivepiola.cl
```

### 2.4 Archivos estáticos y media
DigitalOcean App Platform con Django requiere:
1. `STATIC_ROOT` debe ser accesible
2. `MEDIA_ROOT` debe persistir entre deploys

**Solución**:
- Usar **DigitalOcean Spaces** (objeto storage, $5/mes) 
- O servir assets desde el CDN de DigitalOcean

Para este MVP, usar S3-compatible:
```python
# settings.py en producción
if not DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {...}
        },
    }
```

### 2.5 Primeros deploys
DigitalOcean App Platform despliega automáticamente al hacer push a main.
- Monitoreo: Dashboard → Deployments

---

## Fase 3: DNS y dominio

**Una vez que vivepiola.cl esté registrado**:

### 3.1 Apuntar nameservers a DigitalOcean
1. En DigitalOcean: **Networking** → **Domains** → Add Domain → vivepiola.cl
2. Copiar los 3 nameservers de DigitalOcean
3. En tu registrador (NIC.cl): cambiar los nameservers al de DigitalOcean
4. Esperar ~24h para que se propague

### 3.2 Configurar subdominios
En DigitalOcean Domains, crear:
- `app.vivepiola.cl` → apunta a la App
- `www.vivepiola.cl` → apunta al mismo lugar (landing)
- `api.vivepiola.cl` → opcional, si quieres separar la API

### 3.3 SSL automático
DigitalOcean proporciona certificado Let's Encrypt gratis y lo renueva automáticamente.

---

## Fase 4: Datos iniciales (demo)

### 4.1 Condominio de demostración
Crear un condominio ficticio para mostrar a clientes:

```bash
python manage.py shell
from condominios.models import Condominio, Vertical
from accounts.models import Usuario, Rol

# Crear vertical (si no existe)
vert, _ = Vertical.objects.get_or_create(
    slug='condominios',
    defaults={'nombre': 'Condominios', 'vocabulario': {...}}
)

# Crear condominio demo
condo = Condominio.objects.create(
    nombre='Condominio Demo - VIVEPIOLA',
    vertical=vert,
    plazo_descargo_dias=5,
)

# Crear usuarios demo
admin = Usuario.objects.create_user(
    username='admin@vivepiola.cl',
    password='VivePiola2026!',
    rol=Rol.ADMINISTRADOR,
    condominio=condo,
)
# ... crear más usuarios (comité, conserje, residentes)
```

### 4.2 Infracciones de demostración
Cargar un reglamento PDF de prueba y crear infracciones típicas:
- "Ruido excesivo" (3 UF)
- "Mascota suelta" (2 UF)
- "Alteración de fachada" (5 UF)

---

## Fase 5: Testing en producción

### 5.1 Flujo completo
1. Conserje sube foto de "ruido"
2. Comité aprueba la infracción
3. Admin notifica
4. **Verificar que el correo de verdad llegue** ✓
5. Residente entra, ve la multa, presenta descargo
6. Comité resuelve el descargo
7. Verificar que el correo de resolución llegue

### 5.2 Checklist de producción
- [ ] Email real funcionando (SendGrid)
- [ ] HTTPS activo (Let's Encrypt)
- [ ] Base de datos persistente
- [ ] Backup automático de BD (DigitalOcean lo hace)
- [ ] DEBUG = False
- [ ] SECRET_KEY robusta (random, no hardcodeada)
- [ ] ALLOWED_HOSTS correcto (vivepiola.cl, www, app)
- [ ] Logging configurado (para debuggear después)
- [ ] Monitoreo mínimo (alertas si la app cae)

---

## Costos mensuales estimados

| Concepto | Costo |
|---|---|
| DigitalOcean App (pequeño) | $5-12 |
| DigitalOcean MySQL Managed | $18 |
| DigitalOcean Spaces (storage media) | $5 |
| SendGrid (100 emails/día gratuito) | $0 |
| Dominio vivepiola.cl (anual, amortizado) | ~$2 |
| **TOTAL mensual** | **$30** |

**Reducir a $15-20**: Usar VPS pequeño en vez de App (requiere config manual) o usar Railway/Render (Heroku alternativo).

---

## Próximos pasos inmediatos

1. **HOY**:
   - [ ] Registrar dominio vivepiola.cl en NIC.cl
   - [ ] Crear cuenta SendGrid y obtener API Key
   - [ ] Crear cuenta DigitalOcean ($5 crédito inicial)

2. **MAÑANA**:
   - [ ] Configurar SendGrid en `.env`
   - [ ] Crear App en DigitalOcean
   - [ ] Crear MySQL managed en DigitalOcean
   - [ ] Deploy automático

3. **DÍA 3**:
   - [ ] Apuntar DNS (después que dominio esté registrado)
   - [ ] Crear condominio demo
   - [ ] Testing end-to-end

---

## Comandos útiles para Django en producción

```bash
# Ejecutar migración en producción
python manage.py migrate

# Crear superuser
python manage.py createsuperuser

# Recolectar archivos estáticos
python manage.py collectstatic --noinput

# Cargar datos demo
python manage.py seed_demo

# Ver logs en vivo
heroku logs -t  # (si fuera Heroku)
# O en DigitalOcean App: Dashboard → Logs
```

---

## Soporte y debugging

**Si algo falla después de deployed**:

1. Revisar **DigitalOcean App logs** (Dashboard → Logs)
2. Revisar **base de datos** (¿se conecta?)
3. Revisar **SendGrid** (¿se envían emails?)
4. SSH a la app (si es VPS) y revisar `/var/log/syslog`

---

**Versión de este plan**: 1.0  
**Última actualización**: 2026-07-20  
**Estado**: Listo para implementar
