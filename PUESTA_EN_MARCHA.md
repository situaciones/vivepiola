# VIVE PIOLA — Puesta en marcha

Tres partes:

1. [Claves y servicios](#1-claves-y-servicios)
2. [Dominio vivepiola.cl](#2-dominio-vivepiolacl)
3. [Instructivo del primer condominio](#3-instructivo-del-primer-condominio)

Todas las variables se cargan en **DigitalOcean → tu app → Settings →
componente `vivepiola-backend` → Environment Variables**, marcando **Encrypt**
en las que son secretas.

---

## 1. Claves y servicios

### Resumen

| Servicio | Para qué | Costo | ¿Bloquea? |
|---|---|---|---|
| **DigitalOcean Spaces** | Guardar evidencias, PDFs y reglamentos | US$5/mes | 🔴 Sí |
| **Correo (Brevo o similar)** | Notificación legal con PDF | US$0/mes | 🔴 Sí |
| **Anthropic** | Leer el reglamento y clasificar denuncias | ~US$5 una vez | 🟠 Degrada |
| **Gemini** | Mirar las fotos y videos de la evidencia | ~US$5 una vez | 🟠 Degrada |
| **Twilio WhatsApp** | Avisos con link | ~US$2–6/mes | 🟡 Opcional |
| **Google OAuth** | Ingreso con Google | US$0 | 🟡 Opcional |

"Degrada" significa que el sistema **sigue funcionando** sin la clave, con una
versión más simple. "Bloquea" significa que sin eso no se puede operar.

---

### 1.1 DigitalOcean Spaces — 🔴 crítico

**Por qué:** el disco del contenedor se borra en cada despliegue. Sin esto,
las fotos de evidencia y los PDFs de notificación **desaparecen**, y con ellos
la prueba del expediente.

**Cómo obtenerlo**

1. DigitalOcean → menú izquierdo → **Spaces Object Storage**
2. **Create a Spaces Bucket** → región **NYC3** → nombre único (ej. `vivepiola-media`)
3. Pestaña **Access Keys** → **Create Access Key**
4. ⚠️ Copia **ambos** valores al momento: la clave secreta **solo se muestra una vez**

**Variables**

```
AWS_STORAGE_BUCKET_NAME=vivepiola-media
AWS_S3_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com
AWS_S3_REGION_NAME=nyc3
AWS_ACCESS_KEY_ID=DO00...
AWS_SECRET_ACCESS_KEY=(la clave larga)      🔒 Encrypt
AWS_QUERYSTRING_AUTH=True
```

> `AWS_QUERYSTRING_AUTH=True` mantiene las evidencias **privadas**: se sirven
> con enlaces firmados que caducan. No lo pongas en `False`.

---

### 1.2 Correo — 🔴 crítico

**Por qué:** es **el canal legal** de la Ley 21.442. El correo con el PDF es lo
que se muestra si alguien dice "nunca me avisaron". Sin esto, el flujo se
detiene: el sistema se niega a notificar.

**Ojo con SendGrid:** eliminó su plan gratuito permanente (ahora es prueba de
60 días, después US$19.95/mes). Para el volumen de un condominio conviene otro.

**Recomendado: Brevo** (300 correos/día gratis)

1. Crear cuenta en `brevo.com`
2. **Settings → Senders, Domains & Dedicated IPs** → verificar `vivepiola.cl`
   (agrega los registros SPF y DKIM que te indique en tu DNS)
3. **SMTP & API → pestaña SMTP** → copiar servidor, login y clave

**Variables**

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=(tu login SMTP)
EMAIL_HOST_PASSWORD=(tu clave SMTP)         🔒 Encrypt
DEFAULT_FROM_EMAIL=notificaciones@vivepiola.cl
```

> ⚠️ **Verificar el dominio no es opcional.** Sin SPF/DKIM las notificaciones
> caen en spam, y una notificación en spam es una notificación que no llegó.

---

### 1.3 Anthropic — 🟠 importante

**Por qué:** lee el reglamento en PDF y propone la infracción de cada denuncia
con su fundamento.

**Sin esta clave el sistema NO se cae:** cae a un respaldo por coincidencia de
palabras. Ese respaldo acierta **2 de 8** casos reales (lo medimos); el agente
entiende "el perro andaba suelto" aunque el reglamento diga "sin correa".

**Cómo obtenerlo**

1. `console.anthropic.com` → crear cuenta
2. **Billing → Add credits** → mínimo US$5 (es prepago)
3. **API Keys → Create Key** → copiar (empieza con `sk-ant-`, se ve una sola vez)

**Variable**

```
ANTHROPIC_API_KEY=sk-ant-...                🔒 Encrypt
```

**Costo real:** ~US$0.02 por denuncia, ~US$0.12 por reglamento. Con US$5
alcanza para miles de casos.

**Para verificar que funciona:**

```bash
python manage.py probar_clasificador --sembrar
```

---

### 1.4 Gemini (análisis de evidencia) — 🟠 importante

**Por qué:** es lo que hace que el sistema **mire** las fotos y los videos, no
solo lea la descripción escrita. Un auto sobre la rampa, basura fuera del punto
limpio, un forcejeo en el pasillo: hechos que la imagen prueba y el texto apenas
insinúa.

**Por qué Gemini y no Anthropic:** ningún modelo de Anthropic ni de OpenAI
ingiere **video**. Obligan a extraer fotogramas, o sea arrastrar una librería de
video al despliegue y elegir a ciegas qué instantes representan el hecho. Gemini
recibe el archivo completo. El razonamiento legal se queda en Anthropic, donde
están las salvaguardas del clasificador.

**Cómo obtenerlo**

1. `aistudio.google.com/apikey` → **Create API key**
2. Copiar (empieza con `AIza`)

**Variables**

```
GEMINI_API_KEY=AIza...                      🔒 Encrypt
GEMINI_MODELO_VISION=gemini-2.5-flash
```

**Sin esta clave el sistema NO se cae:** la evidencia se guarda igual en el
expediente y la sigue viendo una persona. Solo que la IA no la mira.

> El análisis tiene prohibido describir personas. Un sistema que anotara
> "hombre de unos 50, polera roja" estaría armando perfiles de residentes desde
> las cámaras, que es justo lo que la Ley 19.628 busca evitar. Describe la
> conducta y el lugar, no a quién aparece.

---

### 1.5 Twilio WhatsApp — 🟡 opcional

**Por qué:** el aviso que hace que el correo se lea, con link directo al caso.

**Cómo obtenerlo**

1. Crear cuenta en `twilio.com` (dan ~US$15 de crédito de prueba)
2. **Messaging → Try it out → Send a WhatsApp message** → activar el **Sandbox**
   (gratis; quien reciba debe enviar antes el código "join" que indica)
3. En el **Console Dashboard**: copiar **Account SID** y **Auth Token**

**Variables**

```
TWILIO_ACCOUNT_SID=AC...                    🔒 Encrypt
TWILIO_AUTH_TOKEN=...                       🔒 Encrypt
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

> ⚠️ **Trámite con Meta, empiézalo temprano.** Para producción (fuera del
> sandbox) Meta exige **plantillas pre-aprobadas**: no se puede enviar texto
> libre a quien no te escribió en las últimas 24 horas. Hay que registrar cada
> tipo de mensaje ("aviso de multa", "resumen de pendientes") y esperar
> aprobación. Toma días y no depende de nosotros.

---

### 1.6 Google OAuth — 🟡 opcional

**Por qué:** que cada persona entre con un toque, sin inventar contraseñas.
Sin esto, se entra con usuario y contraseña normal.

**Cómo obtenerlo**

1. `console.cloud.google.com/apis/credentials`
2. **Create Credentials → OAuth client ID → Web application**
3. En **Authorized JavaScript origins**: `https://vivepiola.cl`
4. Copiar el **Client ID**

**Variables** — el mismo valor va en dos lugares:

```
# backend
GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_OAUTH_MOCK=False
```

```
# frontend (componente vivepiola-frontend)
VITE_GOOGLE_CLIENT_ID=....apps.googleusercontent.com
```

> ⚠️ `GOOGLE_OAUTH_MOCK=False` en producción. En `True` se aceptan credenciales
> simuladas — sirve para probar, **jamás** para producción.

---

### 1.7 Variables que ya deberías tener

```
SECRET_KEY=(cadena larga y aleatoria)       🔒 Encrypt
DEBUG=False
ALLOWED_HOSTS=vivepiola.cl,www.vivepiola.cl
CORS_ALLOWED_ORIGINS=https://vivepiola.cl,https://www.vivepiola.cl
FRONTEND_URL=https://vivepiola.cl
DB_NAME= DB_USER= DB_PASSWORD= DB_HOST= DB_PORT=   (de tu base administrada)
```

`FRONTEND_URL` es la que arma los links de los WhatsApp. Si queda con el
dominio viejo, los avisos apuntarán a `ondigitalocean.app`.

---

## 2. Dominio vivepiola.cl

### 2.1 Registrarlo

1. Entrar a **nic.cl** → buscar `vivepiola.cl`
2. Registrar a nombre de tu empresa o RUT
3. **Costo: ~$9.990 CLP al año** (hay descuento por varios años: ~10% a 2 años,
   ~20% a 5 años). Verifica la tarifa vigente en nic.cl

### 2.2 Apuntarlo a DigitalOcean

1. En DigitalOcean: **Networking → Domains → Add Domain** → `vivepiola.cl`
2. Copiar los tres servidores de nombres que te muestra:
   ```
   ns1.digitalocean.com
   ns2.digitalocean.com
   ns3.digitalocean.com
   ```
3. En **nic.cl → Mis dominios → Cambiar servidores de nombre**, reemplazar por esos tres
4. Esperar la propagación (**hasta 24 horas**)

### 2.3 Conectarlo a la app

1. Tu app → **Settings → Domains → Add Domain** → `vivepiola.cl`
2. Agregar también `www.vivepiola.cl`
3. El **certificado HTTPS es automático** (Let's Encrypt) y se renueva solo

### 2.4 Actualizar las variables

Cuando el dominio responda, cambia:

```
ALLOWED_HOSTS=vivepiola.cl,www.vivepiola.cl
CORS_ALLOWED_ORIGINS=https://vivepiola.cl,https://www.vivepiola.cl
FRONTEND_URL=https://vivepiola.cl
DEFAULT_FROM_EMAIL=notificaciones@vivepiola.cl
```

Y en Brevo, verifica el dominio para que los correos salgan desde
`@vivepiola.cl` sin caer en spam.

---

## 3. Instructivo del primer condominio

### Paso 0 — Arreglar las rutas (bloqueante) 🔴

**Nada de lo que sigue funciona sin esto.** Hoy `/api` y `/admin` responden 404.

1. Tu app → **Settings** → componente **`vivepiola-backend`** → **Routing Rules**
2. Verás cuatro rutas: `/api`, `/admin`, `/static`, `/media`
3. En **cada una**: **Edit** → cambiar **"Path handling"** de *Trim Prefix* a
   **"Preserve Full Path"** → **Save**

**Por qué:** *Trim Prefix* le corta el `/api` al camino antes de entregárselo a
Django, que entonces no reconoce la ruta. *Preserve Full Path* se lo entrega
completo.

**Comprobación:** entrar a `https://vivepiola.cl/admin/` debe mostrar el
formulario de acceso de Django, no un "Not Found".

---

### Paso 1 — Crear la comunidad y su administrador

Esto se hace una vez por condominio, desde `/admin/`:

1. Entrar a `https://vivepiola.cl/admin/` con el superusuario
2. **Condominios → Add** → nombre, dirección, RUT de la administradora
   - `plazo_descargo_dias`: **5** (lo que exige la ley)
   - `ventana_duplicados_horas`: **24** (agrupa los reportes del mismo hecho)
3. **Usuarios → Add** → crear el administrador:
   - Usuario y contraseña
   - **Rol: ADMINISTRADOR**
   - **Condominio:** el recién creado
   - **Correo:** el real (ahí le llegan los resúmenes)

> A partir de aquí **todo lo hace el administrador desde la aplicación**. No
> hace falta volver a `/admin/`.

---

### Paso 2 — El administrador prepara la comunidad

Entra a `https://vivepiola.cl` con su usuario.

**a) Cargar el registro de copropietarios** → pestaña *Registro de copropietarios*

1. **Descargar plantilla Excel**
2. Llenarla con los datos de cada residente
3. **Importar**

> ⚠️ **El correo es obligatorio.** Sin correo registrado no se puede notificar
> y la multa queda bloqueada — es una salvaguarda deliberada, no un error.
> El teléfono es opcional pero es lo que habilita el aviso por WhatsApp.

**b) Subir el reglamento** → pestaña *Infracción y reglamento*

1. **Subir PDF del reglamento** de copropiedad vigente
2. **Extraer infracciones con IA** (requiere la clave de Anthropic)
3. Las infracciones quedan en estado **BORRADOR**

**c) El comité confirma el catálogo** ⚠️ paso que se olvida

Las infracciones sugeridas **no se pueden usar hasta que el comité las
confirme** una por una, desde su pestaña *Borradores IA*.

Es a propósito: una sanción no puede fundarse en un borrador que nadie revisó.
Si el catálogo queda vacío, ninguna multa podrá aprobarse.

Al confirmar, revisen de cada infracción:
- El **monto** y su unidad (UF, UTM o pesos)
- El **artículo** del reglamento
- El **factor de reincidencia** (1.00 = sin agravante; 2.00 = dobla el monto al reincidir)
- Si **conlleva contención** (riesgos que exigen parar la actividad de inmediato)

**d) Invitar al equipo** → pestaña *Equipo y accesos*

Dos formas:

- **Invitación directa:** correo + unidad + rol sugerido. Le llega un mensaje y
  al entrar con Google queda operativo de inmediato.
- **Código de Comunidad:** un código que puedes compartir por el grupo de
  WhatsApp del condominio. Quien entre con él queda **pendiente** y aparece en
  tu bandeja para que le confirmes el rol.

Roles a repartir:

| Rol | Quién | Qué hace |
|---|---|---|
| **Fiscalizador** | Conserjes | Reporta con foto. No fija montos |
| **Comité** | Miembros del comité | Único que aprueba y resuelve descargos |
| **Residente** | Copropietarios | Ve sus multas y presenta descargos |

---

### Paso 3 — Prueba de humo (antes de anunciarlo)

Recorre el circuito completo con un caso de mentira:

1. **Conserje** → *Nuevo reporte*: unidad, persona, descripción → crear ticket
2. **Conserje** → *Mis tickets* → **Agregar foto de evidencia**
3. **Comité** → *Bandeja de decisión*: revisa la propuesta automática, marca la
   casilla de revisión y **Aprobar**
4. **Administrador** → *Notificar multas*: **Notificar al residente**
   - ✅ **Comprueba que el correo llegó de verdad**, con el PDF adjunto
5. **Residente** → ve su multa, el plazo y presenta un descargo
6. **Comité** → resuelve: aceptar, rechazar o **aplicar descuento**
7. **Administrador** → *Gastos comunes* → exportar el período → descargar CSV
8. **Cualquiera** → *Descargar certificado (PDF)* del expediente

Si el paso 4 falla, el problema es el correo. **Es el único que no admite
"lo vemos después"**: sin correo no hay notificación legal.

---

### Paso 4 — Programar el resumen diario

Para que el comité reciba "tienes 3 casos esperando" sin que nadie lo dispare:

En DigitalOcean → tu app → **Create → Job** → tipo **Scheduled**, una vez al día:

```bash
python manage.py enviar_resumenes
```

Puedes probarlo antes sin enviar nada:

```bash
python manage.py enviar_resumenes --simular
```

Manda **un** aviso por rol, solo si hay pendientes, y no repite dentro del
mismo día.

---

### Cargar la base normativa de Chile

El sistema trae **declaradas** las normas generales que rigen a todos los
condominios, pero **el texto hay que cargarlo una vez**. No viene escrito en el
código a propósito: lo que se cargue aquí termina citado en notificaciones que
le llegan a residentes, y un articulado escrito de memoria es la forma más
rápida de fundar una sanción en un artículo que no existe.

Ver qué falta:

```bash
python manage.py cargar_normativa --estado
```

Te va a listar cada norma con **el enlace oficial** de dónde bajarla y el
nombre de archivo que espera. Baja el texto desde bcn.cl, guárdalo como `.txt`
en una carpeta, y carga:

```bash
python manage.py cargar_normativa --desde normativa/
```

| Norma | Para qué sirve |
|---|---|
| Ley 21.442 | El marco de toda la copropiedad |
| D.S. N° 7 (2023) MINVU | Su reglamento |
| Ley 19.496 | Protección al consumidor |
| Ley 19.628 | Datos personales |

**Sin esto el sistema funciona igual**, solo que la IA analiza únicamente con
los documentos de cada comunidad. Con la ley cargada puede notar que una
sanción del reglamento excede un tope legal o que un plazo contradice el que
fija la ley — y decirlo en el fundamento en vez de reproducir el error.

También se puede administrar desde el panel de Django, en **Normas
transversales (Chile)**.

---

### Cuánta autonomía le das al sistema

Dos parámetros deciden cuánto hace solo el sistema y cuánto pasa por el comité.
Los valores por defecto son conservadores; puedes ajustarlos como variables de
entorno cuando veas cómo se comporta tu comunidad.

**Cuántos avisos antes de cobrar** (`cortesias_antes_de_multar`, por comunidad):

| valor | qué pasa |
|-------|----------|
| 2 (por defecto) | Las dos primeras faltas no graves se avisan sin cobro |
| 0 | Se cobra desde la primera |

Las faltas **gravísimas** y las que paralizan algo nunca reciben aviso: se
cobran desde la primera vez, por muy primera que sea.

**Cuánta certeza se exige para notificar sin que nadie revise:**

| variable | por defecto | qué significa |
|----------|-------------|---------------|
| `CURSE_CONFIANZA_MINIMA_LEVE` | 65 | Una leve termina en aviso sin cobro: equivocarse cuesta poco |
| `CURSE_CONFIANZA_MINIMA_GRAVE` | 80 | |
| `CURSE_CONFIANZA_MINIMA_GRAVISIMA` | 90 | Cobro inmediato y alto: hay que estar muy seguro |

Poner cualquiera sobre 100 significa **siempre revisión humana** para esa
gravedad, porque el clasificador nunca supera 100.

Lo que no alcanza el umbral no se pierde: queda esperando que el comité lo
tipifique, con el motivo escrito en el expediente.

---

### Paso 5 — Programar los reintentos de notificación

Este es el más importante de los dos, porque de él depende que una multa se
pueda sostener. El plazo para apelar **no corre desde que se envía el correo,
sino desde que el residente confirma que lo recibió**. Mientras no confirme, el
sistema reintenta.

En DigitalOcean → **Create → Job** → tipo **Scheduled**, cada 5 minutos:

```bash
python manage.py reintentar_notificaciones
```

Para ver qué haría, sin enviar nada:

```bash
python manage.py reintentar_notificaciones --dry-run
```

Reenvía por todos los canales registrados (correo y WhatsApp), hasta 3 veces,
y se detiene apenas hay confirmación. Cuando se agotan los intentos sin
respuesta, lo lista para que alguien imprima la notificación y **la deje en el
buzón de la unidad**; esa entrega se registra desde el panel del administrador
y es lo que hace arrancar el plazo.

Si no programas este job, las notificaciones salen una sola vez: quien no vea
ese correo nunca confirmará, su plazo nunca arrancará y su multa quedará
detenida sin poder cobrarse.

---

### Paso 5 — Lo que conviene explicar a la comunidad

Cuando lo presentes en asamblea, tres ideas:

1. **Nadie es juez y parte.** Quien reporta no fija el monto; quien decide es
   solo el comité; quien cobra es la administración.
2. **Todo queda registrado y sellado.** Cada decisión guarda quién, cuándo y
   con qué evidencia. Se puede emitir un certificado verificable.
3. **El residente siempre tiene derecho a defenderse**, con 5 días de plazo y
   la posibilidad de que le rebajen o anulen la multa.

---

## Orden recomendado

1. 🔴 **Rutas** en Preserve Full Path — sin esto no hay nada
2. 🔴 **Spaces** — 5 minutos, evita perder las evidencias
3. 🔴 **Correo** + verificación del dominio — habilita notificar
4. 🟠 **Anthropic** — enciende la lectura del reglamento
5. 🟢 **Dominio** — puede correr en paralelo (la propagación tarda)
6. 🟢 **Primer condominio** y prueba de humo
7. 🟡 **WhatsApp** y **Google** — cuando lo anterior esté firme

**Costo mensual para arrancar: ~US$5** (Spaces), más US$5 una vez de crédito
de IA, más el dominio (~$9.990 CLP al año). Aparte va lo que ya pagas de la
app y la base de datos en DigitalOcean.
