# Debido

Sistema de debido proceso legal para multas y convivencia en condominios,
basado en la Ley 21.442 (Chile). Separa estrictamente los roles del proceso
sancionatorio:

- **Fiscalizador (Conserje):** crea tickets con evidencia fotografica. No define monto ni aprueba.
- **Comite de Administracion:** revisa evidencia y es el UNICO que aprueba/rechaza multas, eligiendo la infraccion del catalogo del reglamento. Tambien confirma el catalogo de infracciones y resuelve descargos.
- **Administrador:** notifica al residente (genera PDF + envia correo, el canal legal), gestiona el registro de copropietarios, carga el reglamento y exporta multas firmes a gastos comunes.
- **Residente:** ve sus multas y evidencia, presenta descargos dentro del plazo, usa el Libro de Novedades.

## Arquitectura

- **Backend:** Django 6 + Django REST Framework + JWT (simplejwt) + MySQL.
- **Frontend:** React 19 (Vite) SPA consumiendo la API REST.
- **PDF:** xhtml2pdf (puro Python, no requiere GTK como WeasyPrint).
- **IA:** Claude (Anthropic API) sugiere infracciones desde el PDF del reglamento como *borrador*; siempre requieren confirmacion humana antes de activarse en el catalogo.

## Estructura

```
backend/        Proyecto Django (apps: accounts, condominios, reglamentos, multas, novedades, gastos_comunes)
frontend/       SPA React (Vite)
venv/           Entorno virtual Python
```

## Puesta en marcha

### Base de datos MySQL

Se instalo MySQL Server 8.4 localmente (Windows) sin registrarlo como servicio
(no habia permisos de administrador en este entorno). Para iniciarlo manualmente:

```
"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --defaults-file="C:\ProgramData\MySQL\MySQL Server 8.4\my.ini"
```

Root sin contrasena (`--initialize-insecure`). Para produccion, instala MySQL
como servicio de Windows con permisos de administrador y define una
contrasena de root, actualizando `backend/.env`.

Base de datos: `condoadmin` (ya creada). Es solo el identificador interno de
conexion (nadie lo ve en la app); se mantuvo para no perder los datos de
prueba ya cargados al renombrar el producto a "Debido".

### Backend

```
cd backend
..\venv\Scripts\activate
python manage.py migrate
python manage.py runserver
```

Variables de entorno en `backend/.env` (copiar de `.env.example`):
- `DB_*`: credenciales MySQL.
- `EMAIL_BACKEND`: `django.core.mail.backends.console.EmailBackend` en desarrollo (los correos se imprimen en la consola). Cambiar a `...backends.smtp.EmailBackend` con un proveedor transaccional (SendGrid, Mailgun, etc.) en produccion.
- `ANTHROPIC_API_KEY`: necesaria solo para el boton "Generar borradores de infracciones con IA".

Datos de demostracion (`python manage.py seed_demo`): crea el condominio
"Condominio Los Alerces" con usuarios `conserje` / `comite` / `administrador` /
`residente` (contrasena `Demo12345`) y dos infracciones activas.

Superusuario admin: `admin` / `Admin12345` (rol SUPERADMIN, acceso a `/admin/`).

### Frontend

```
cd frontend
npm install
npm run dev
```

Configurar `frontend/.env` -> `VITE_API_URL=http://127.0.0.1:8000/api`.

## Flujo legal implementado

1. Fiscalizador crea un **Ticket** con evidencia -> se genera automaticamente una **Multa** en estado `EN_REVISION`.
2. Comite **aprueba** (elige infraccion del catalogo activo) o **rechaza**. Al aprobar, el sistema detecta **reincidencia** automaticamente (misma infraccion en los ultimos 6 meses) y sugiere el agravante.
3. Administrador **notifica**: genera el PDF y envia el correo al residente (canal legal), fijando el plazo de descargo.
4. Residente puede **presentar descargo** dentro del plazo.
5. Comite **resuelve** el descargo (acepta -> anula la multa; rechaza -> multa firme).
6. Si no hay descargo, la multa pasa a **firme** automaticamente al vencer el plazo.
7. Administrador **exporta** las multas firmes a un lote CSV de gastos comunes por periodo.

El **Libro de Novedades Digital** permite a cualquier residente registrar
reclamos/solicitudes, con alerta de plazo legal de 20 dias corridos para que
la administracion responda.

## Sellado criptografico de actos (V2)

Cada acto de decision (aprobar, rechazar, notificar, presentar descargo,
resolver, firmeza automatica) genera un **acta sellada**: un manifiesto
canonico de todo lo que el decisor tenia a la vista (evidencias con su
SHA-256, texto de la norma aplicada embebido, estado del expediente, actor y
metodo de autenticacion), hasheado y **encadenado** al acta anterior:

```
hash_acto = SHA256(hash_previo || SHA256(manifiesto_canonico))
```

Garantias y limites:
- Las evidencias reciben SHA-256 y metadatos EXIF (fecha de captura, GPS) en
  la ingesta; la falta de anclaje fisico se marca, no se rechaza.
- La tabla de actas es INSERT-only: la aplicacion no expone actualizacion y
  **triggers de MySQL abortan cualquier UPDATE/DELETE**. En produccion se
  recomienda ademas un usuario de conexion sin esos privilegios sobre la
  tabla, y anclaje externo del hash-raiz (correo diario o RFC 3161).
- El endpoint `GET /api/multas/{id}/verificar-integridad/` recalcula toda la
  cadena y los hashes de archivos (boton "Verificar integridad" en el panel
  del Comite).
- Sin backfill de garantias: los expedientes anteriores a esta version son
  legacy V1 y el verificador los declara como tales.

## Audit Trail PDF (la Prueba Maestra)

`GET /api/multas/{id}/audit-trail/` genera el **certificado de integridad
imprimible** del expediente: recalcula la cadena completa al momento de la
emision y produce un PDF de alta autoridad con el sello "INMUTABILIDAD
VERIFICADA" (o "INTEGRIDAD COMPROMETIDA" si el recalculo detecta
alteraciones — el certificado delata, no oculta), la tabla de actos con
actor, timestamp, metodo de autenticacion y columna de verificacion
criptografica por acto, la tabla de evidencias con su huella SHA-256 y
anclaje EXIF, el hash raiz que ancla el papel a la cadena digital, y la
explicacion del metodo de verificacion. 100% determinista (plantilla rigida,
cero IA). Boton "Descargar certificado (PDF)" en el panel del Comite; los
expedientes legacy V1 devuelven 400 (no se afirman garantias retroactivas).

El vocabulario del vertical se expone en `GET /api/auth/me/` (campo
`vocabulario`) y la UI lo consume via `useVocab()`
([frontend/src/vocab.js](frontend/src/vocab.js)): misma build, distinta piel
segun la organizacion del usuario. El hook memoiza `t` por el diccionario de
la sesion (`useMemo`) para no romper la memoizacion de hijos en listas pesadas.
Demo del vertical Construccion: `python manage.py seed_demo_obras` crea la obra
"Edificio Vista Norte" con usuarios `supervisor` / `admincontrato` /
`oficinatecnica` / `contratista` (contrasena `Demo12345`). La piel cubre TODAS
las pantallas de rol: el contratista ve "Mis no conformidades", "Presentar
reclamacion" y "El contrato de obra la tipifica como no conformidad" donde el
residente ve "Mis multas", "Presentar descargo" y "el reglamento de
copropiedad la tipifica como infraccion"; la oficina tecnica ve "Registro de
subcontratistas" y "Estados de pago del contrato" donde el administrador ve
"Registro de copropietarios" y "Gastos comunes".

### Cierre hermetico server-side (canales de salida)

La piel no vive solo en la UI: los **canales legales de salida** hablan el
idioma del vertical, para que el Audit Trail y la notificacion no muestren
"multa de su condominio" en una auditoria de "paralizacion de faena".

- **Motor de vocabulario** ([backend/condominios/vocab.py](backend/condominios/vocab.py)):
  `termino(condominio, clave)` para sustantivos y `frase(condominio, clave, **datos)`
  para bloques de texto completos con placeholders (i18n **clave-por-frase**,
  nunca concatenacion de palabras sueltas — respeta genero/numero). Defaults
  del nicho original; el vertical solo sobrescribe lo que redefine; placeholder
  faltante degrada a literal en vez de reventar.
- **Correo y PDF de notificacion** consumen ese motor: asunto, cuerpo,
  etiquetas de la tabla y aviso de descargo salen del `vocabulario` del
  `Vertical`. Verificado extrayendo el texto del PDF real: en obra dice
  "Responsable del subcontratista", "Aprobada por Administrador de contrato",
  "estados de pago del contrato" — cero fugas de multa/condominio/Comite.
- **Errores de la API** en **redaccion neutra** agnostica de nicho
  ("La entidad no pertenece a la organizacion activa", "Debe indicarse el
  sujeto responsable"): un error tecnico no consulta el vertical ni arriesga
  incoherencia gramatical.

## Carril de contencion (MedidaInmediata)

Paralelo al carril sancionatorio de 6 etapas (que no cambia), para hallazgos
que exigen accion inmediata antes de completar el debido proceso:

- **Contrato minimalista de terreno**: `POST /api/medidas-inmediatas/` con
  `expediente_id`, `hallazgo_codigo`, `evidencia_ids[]` y `auth_metodo`. El
  BACKEND decide si el hallazgo detona contencion leyendo la calificacion
  hecha en frio en el catalogo (`conlleva_contencion`,
  `plazo_ratificacion_horas` en InfraccionCatalogo); el operario nunca
  clasifica juridicamente.
- **Maquina de estados FAIL-CLOSED**: `EJECUTADA -> RATIFICADA |
  EN_ESCALAMIENTO -> LEVANTADA`. Ninguna transicion automatica libera la
  contencion: la omision de ratificar escala (`python manage.py
  escalar_medidas`, cron-able, tambien barrido perezoso al listar), notifica
  a los adjudicadores y sella el acto de omision con los nombres de los
  notificados. Levantar exige actor facultado + causal
  (CORREGIDA/DESESTIMADA) + fundamento escrito.
- **Candado pesimista**: todo sellado abre transaccion y bloquea la fila del
  expediente (`SELECT ... FOR UPDATE`); si el Comite ratifica y el job escala
  al mismo tiempo, el motor los encola y el segundo se aborta al releer la
  realidad.
- **Manifiesto polimorfico**: `tipo_manifiesto: SANCION | CONTENCION`. Los
  actos de contencion sellan `criticidad` (hallazgo embebido),
  `plazo_ratificacion_horas` y `estado_contencion`, en la MISMA cadena de
  hashes del expediente.

## Jerarquias Enterprise: quorum, delegacion y votos sellados

Fases 0-1 sobre el carril de contencion, para continuidad operativa sin perder
trazabilidad (el prevencionista ratifica en terreno cuando el titular no esta).

- **Quorum K-de-N fijo por politica de riesgo** (`quorum_ratificacion` en
  InfraccionCatalogo, atado a la gravedad, no a la disponibilidad de personal).
  Se congela en la medida al ejecutar. `quorum=1` = ratificacion simple
  (comportamiento previo intacto: un solo acto `CONTENCION_RATIFICADA`).
- **Voto sellado e idempotente** (`VotoRatificacion`, `unique(medida, actor)` +
  candado): un actor fisico incrementa el quorum una sola vez, llegue por su
  cargo o por delegacion. Con `quorum>1`, cada voto sella un
  `VOTO_RATIFICACION`; el que completa K sella ademas `CONTENCION_RATIFICADA`.
- **Delegacion tactica** (`Delegacion`): vencimiento OBLIGATORIO, techo de
  gravedad (lo GRAVISIMA no se delega ad-hoc), profundidad 1, sin
  auto-delegacion. Nace con su `otorgamiento_hash`. `POST /api/delegaciones/`
  (otorgar, Comite) y `/revocar/` (solo el delegante).
- **Autoridad en un solo lugar**: `_resolver_autoridad` decide TITULAR vs.
  DELEGADO (o 403 `SinAutoridad`); el permiso DRF de `ratificar` se relaja a
  autenticado para que la delegacion habilite a otros roles.
- **Auditoria criptografica de la delegacion**: el acta `VOTO_RATIFICACION`
  embebe un SNAPSHOT congelado del otorgamiento (no un FK). El verificador,
  offline y aritmetico, comprueba contra el `ts` sellado que la ventana lo
  cubre (`vigencia_desde <= ts <= vigencia_hasta`), que la accion esta cubierta
  y que la gravedad no supera el techo — "vigente en ese milisegundo exacto"
  sin consultar el estado vivo. Alterar la ventana rompe `hash_acto`.
- **Especificacion ejecutable** (`JerarquiasQuorumTestCase`): idempotencia
  (mismo actor por dos vias cuenta 1), voto que completa quorum vs. job de
  escalamiento (el job se aborta al releer), el escalamiento no invalida votos
  previos, techo de gravedad, delegacion vencida sin autoridad, y auditoria de
  la ventana por el verificador.

### UI de quorum y delegacion

- **Panel del otorgante (Comite)**: barra segmentada de quorum inline en cada
  medida (K casillas, quien firmo y en que calidad; ambar mientras falte, verde
  al completar), firma con gesto mantener-para-confirmar, e idempotencia visual
  ("Ya firmaste · esperando el resto del quorum"). Drawer "Estoy fuera de
  terreno · delegar" con el vencimiento como protagonista visual y GRAVISIMA
  bloqueada.
- **Panel del delegado** (`PanelFirmasDelegadas`): pestaña "Firmas por
  delegacion" que aparece SOLO si el usuario tiene una delegacion vigente. Un
  jefe de area rol ADMINISTRADOR ve un banner "Actuas por delegacion de X ·
  techo GRAVE · N h hasta vencer" y firma las paralizaciones pendientes desde
  su propio dashboard — cierra el ciclo de la delegacion de punta a punta.

## Capa de gobernanza (multi-vertical)

- **Paquetes de vertical** (`Vertical` en condominios): vocabulario JSON,
  marco legal del PDF de notificacion (plantilla determinista, cero IA en la
  emision) y plazos por defecto. Cada organizacion se adhiere a un vertical;
  sin vertical, el comportamiento es el del nicho original (Ley 21.442).
- **Cadena de escalamiento versionada** (`CadenaEscalamiento` +
  `NivelEscalamiento`): plana y estatica; editar = crear nueva version (las
  anteriores se conservan porque las actas las referencian). Notificacion
  ACUMULATIVA: ejecucion notifica nivel 1; cada omision sube un peldano
  (1..N+1); superar el largo marca `tope_alcanzado` en el acta. Fallback sin
  cadena: Comite + Administrador.
- **UI de gobernanza v1**: Django admin (`/admin/`) para el equipo de
  implementacion (verticales y cadenas); la criticidad de hallazgos se
  configura desde el propio catalogo del Comite en la app.
- **UI de terreno**: pestaña "Contencion" del Fiscalizador con gesto
  mantener-para-confirmar (1.4s, `auth_metodo` sellado como
  `hold_to_confirm_1400ms+jwt`); pestaña "Contenciones" del Comite para
  ratificar o levantar con causal y fundamento.

## Tests

```
cd backend
..\venv\Scripts\activate
python manage.py test
```

La suite (38 tests) cubre el flujo legal completo (ticket -> aprobacion ->
notificacion -> descargo -> firmeza -> exportacion), la separacion estricta
de roles (cada accion bloqueada para los roles no habilitados), la
inmutabilidad de tickets y multas, reincidencia, plazos de descargo,
aislamiento entre condominios, la importacion del registro de copropietarios,
y el sellado criptografico: cadena integra en el flujo completo,
congelamiento de la norma y de la evidencia en el manifiesto, deteccion de
archivos alterados, inmutabilidad por triggers y declaracion de expedientes
legacy V1.
Requiere que MySQL este corriendo (crea una base `test_condoadmin` temporal).

## Notas

- El registro de copropietarios se carga por plantilla Excel/CSV (descargable desde el panel de Administrador), no por PDF, para evitar errores de OCR en datos criticos (cedula, correo).
- Las infracciones sugeridas por IA quedan siempre en estado `BORRADOR` y no pueden usarse para fundar una multa hasta que el Comite o Administrador las confirme.
