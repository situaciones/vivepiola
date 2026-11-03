# Borradores legales de SinConflicto

> **BORRADOR PARA REVISIÓN DEL ABOGADO.** Estos textos describen cómo funciona hoy el sistema. No son asesoría legal ni están listos para firmar. Lo que aparece entre corchetes [ ] hay que completarlo o confirmarlo.

Contiene tres documentos:

1. Acuerdo de Tratamiento de Datos entre la comunidad y SinConflicto.
2. Términos y Condiciones de uso.
3. Política de Conservación de Datos.

---

## 1. Acuerdo de Tratamiento de Datos Personales

**Entre:**
- **La Comunidad de Copropietarios** [nombre del condominio], RUT [__], representada por [presidente(a) del Comité de Administración, o administrador(a) facultado(a) por acuerdo del Comité de fecha __] ("la Comunidad", responsable del tratamiento).
- **[Razón social de SinConflicto]**, RUT [__], con domicilio en [__] ("SinConflicto", encargado del tratamiento).

### 1.1 Objeto
SinConflicto trata datos personales solo por cuenta de la Comunidad y para lo siguiente:
- llevar el registro de copropietarios, arrendatarios y ocupantes que exige la Ley 21.442;
- recibir reportes de infracciones al reglamento;
- notificar a los residentes;
- tramitar descargos y apelaciones;
- dejar constancia de los acuerdos del Comité;
- exportar las multas firmes al cobro de gastos comunes.

SinConflicto no usa los datos para ningún otro fin, no los vende y no los cede a terceros, salvo a los subencargados de la cláusula 1.5.

### 1.2 Datos que se tratan
- **Datos de identificación y contacto:** nombre, RUT, domicilio, correo, teléfono, unidad y rol de ocupación (propietario, arrendatario u ocupante).
- **Vehículos:** patentes asociadas a cada unidad.
- **Reportes:** descripción del hecho, fecha, lugar, fotos y videos.
- **Expedientes:** infracciones, montos, notificaciones, acuses de recibo, descargos, votos y resoluciones.
- **Datos sensibles (solo con consentimiento):** la condición de discapacidad o la necesidad de apoyo para trámites digitales se registra solo si el titular lo autorizó. El sistema guarda la fecha de ese consentimiento.

### 1.3 Base de licitud
La Comunidad declara que trata estos datos para cumplir las obligaciones de la Ley 21.442 y su reglamento: registro de copropietarios, administración, notificación y cobro de obligaciones económicas. Los datos sensibles se tratan solo con el consentimiento de su titular. [Confirmar con el abogado.]

### 1.4 Obligaciones de SinConflicto
- Tratar los datos solo siguiendo las instrucciones de la Comunidad, que son las que el Comité y la administración ejecutan en la plataforma.
- Mantener la confidencialidad. Solo accede el personal que lo necesita para operar el servicio.
- Medidas de seguridad:
  - conexión cifrada (HTTPS);
  - acceso por usuario y contraseña con roles separados (administración, Comité, personal y residentes);
  - registro sellado de cada acto, con una cadena de huellas digitales que permite detectar cambios;
  - en producción, un usuario de base de datos que no puede modificar ni borrar las actas selladas.
- **Seudonimización:** antes de enviar un texto a un proveedor de inteligencia artificial se quitan nombres, RUT, correos, teléfonos y patentes. Las fotos y videos se envían sin seudonimizar, pero el análisis visual tiene prohibido describir personas identificables.
- **Brechas de seguridad:** avisar a la Comunidad sin demora indebida, a más tardar en [__] horas desde que se detecten.
- **Ayuda con los derechos de los titulares:** apoyar a la Comunidad para responder solicitudes de acceso, rectificación, supresión, oposición y portabilidad.
- **Término del contrato:** devolver o eliminar los datos según la Política de Conservación (documento 3).

### 1.5 Subencargados y transferencias internacionales
La Comunidad autoriza estos subencargados:

| Proveedor | Para qué | Dónde |
|---|---|---|
| Google Cloud (Cloud Run y base de datos) | Hosting de la aplicación y la base de datos | Chile, región Santiago (southamerica-west1) [confirmar ubicación de la base de datos y de los archivos] |
| Anthropic | Clasificar el reporte según el reglamento y el asistente de consultas (texto seudonimizado) | Estados Unidos |
| Google (Gemini) | Describir lo que se ve en fotos y videos, sin describir personas | Estados Unidos |
| [Proveedor de correo] | Envío de notificaciones por correo | [__] |
| Twilio (cuando se active) | Avisos por WhatsApp | Estados Unidos |

El envío de datos a proveedores en Estados Unidos es una **transferencia internacional**. SinConflicto se obliga a:
- mantener contratos con esos proveedores que exijan medidas de seguridad y confidencialidad adecuadas;
- enviarles solo lo necesario, seudonimizado cuando sea posible.

[El abogado debe revisar las cláusulas con cada proveedor y el estándar que exige la Ley 21.719.]

### 1.6 Responsabilidad
- **La Comunidad** es responsable de la licitud de los datos que carga y de las decisiones que toma su Comité.
- **SinConflicto** responde por el cumplimiento de este acuerdo y de las medidas de seguridad descritas.

### 1.7 Vigencia
Este acuerdo rige mientras dure el contrato de servicio, y hasta que se devuelvan o eliminen los datos según la Política de Conservación.

---

## 2. Términos y Condiciones de uso

### 2.1 Qué es SinConflicto
SinConflicto es una herramienta de apoyo para la gestión de reclamos, infracciones, notificaciones y apelaciones en condominios. **No reemplaza a los órganos de la comunidad ni a los tribunales.**

### 2.2 Quién decide
- **El Comité de Administración** es el único órgano que impone multas (Ley 21.442, art. 2 N.º 5 y 17).
  - En la plataforma, ninguna multa con cobro se notifica sin la aprobación de la mitad más uno de los miembros del Comité.
  - Las apelaciones también se resuelven por mayoría de sus miembros.
- **La inteligencia artificial solo propone:**
  - qué falta del catálogo corresponde, con el artículo y su fundamento;
  - el monto según el catálogo confirmado por el Comité.

  La decisión de aplicar una multa es siempre del Comité.
- **Las advertencias sin cobro** se emiten automáticamente según las reglas que la comunidad configuró. El aviso informa que es automatizado y ofrece pedir que una persona del Comité revise el caso.

### 2.3 Responsabilidad
- **Decisiones:** la responsabilidad por las decisiones sancionatorias y su fundamento corresponde a la Comunidad y a su Comité.
- **Errores de la IA:** SinConflicto no garantiza que las propuestas de la IA sean correctas. Por eso toda multa con cobro requiere el voto del Comité, y el residente puede apelar.
- **Qué sí garantiza SinConflicto:** la trazabilidad y la auditoría de los actos registrados. No interfiere con las facultades del Comité, de la asamblea ni de los tribunales para revisar, corregir o anular una multa.

[El abogado debe definir los límites de responsabilidad, compatibles con la Ley 19.496.]

### 2.4 Catálogo de faltas
- **Origen de las faltas y montos:** solo los que establece el reglamento de copropiedad inscrito o la ley. Las normas internas, instructivos y actas pueden detallar una conducta, pero no crear faltas ni montos nuevos.
- **Confirmación:** la comunidad debe confirmar cada falta del catálogo antes de usarla, indicando el artículo en que se funda.
- **Monto:** el Comité gradúa el monto dentro del rango que fija el reglamento.

### 2.5 Debido proceso en la plataforma
- **Notificación:** se envía al correo registrado en el Registro de Copropietarios. Si no hay acuse de recibo, se puede dejar una constancia en el buzón de la unidad. WhatsApp es solo un aviso informativo.
- **Plazo para apelar:** 10 días hábiles desde el acuse de recibo, configurable entre 5 y 10.
- **Plazo del Comité:** como máximo 20 días para resolver. Si no resuelve a tiempo, la multa no se cobra mientras no haya una resolución expresa.
- **Contenido de la notificación:**
  - el hecho, con fecha y hora;
  - las pruebas;
  - el artículo;
  - la calificación de la falta y el monto;
  - el plazo para apelar;
  - el derecho a recurrir al Juzgado de Policía Local.

### 2.6 Cuentas y uso aceptable
- **Cuentas:** cada usuario es responsable de su contraseña.
- **Prohibiciones:** está prohibido registrar reportes falsos, subir contenido ajeno al hecho o usar la plataforma para hostigar a otros residentes.
- **Datos de terceros:** no se pueden publicar fuera de la plataforma los datos de otros residentes ni las patentes.

### 2.7 Contratación
El servicio lo contrata la Comunidad, representada por:
- el presidente del Comité de Administración; o
- el administrador expresamente facultado por acuerdo del Comité.

[Confirmar.]

### 2.8 Datos personales
El tratamiento de datos se rige por el Acuerdo de Tratamiento de Datos (documento 1) y por la Política de Privacidad publicada en la plataforma.

### 2.9 Ley aplicable
Estos términos se rigen por las leyes de Chile. [Tribunales competentes: __.]

---

## 3. Política de Conservación de Datos

### 3.1 Cuánto se guarda cada cosa

| Información | Cuánto se conserva | Por qué |
|---|---|---|
| Registro de copropietarios, arrendatarios y ocupantes | Mientras la persona tenga relación con la unidad, más [__] años | Obligación de registro (Ley 21.442) |
| Expedientes de multas: reportes, pruebas, notificaciones, descargos, votos, resoluciones y actas selladas | Al menos 5 años desde que la multa quedó firme, anulada o derivada [confirmar: 3 años para el cobro ejecutivo y 5 para la acción ordinaria] | Defensa ante reclamos y cobro judicial |
| Advertencias sin cobro | [__] años | Antecedente para la reincidencia, que se cuenta en una ventana de 6 meses |
| Libro de Actas digital | Lo que exija la ley para el Libro de Actas [confirmar] | Respaldo de los acuerdos del Comité |
| Consentimiento para datos sensibles | Mientras se conserve el dato sensible | Prueba de que el titular lo autorizó |
| Datos de vehículos | Mientras el vehículo esté asociado a la unidad | Identificar al responsable de una alerta |

### 3.2 Solicitudes de borrado
Ante una solicitud de supresión de datos, la Comunidad puede negarse a eliminar los registros sancionatorios e históricos mientras estén dentro de los plazos de la tabla, porque su conservación responde a una obligación legal. Los demás datos se eliminan o se anonimizan. [Confirmar con el abogado.]

### 3.3 Actas selladas
Las actas selladas no se pueden modificar ni borrar desde la aplicación: es lo que permite probar que el expediente no fue alterado. Vencido el plazo de conservación, se eliminan o anonimizan por expediente completo, para no romper la cadena de sellos. [Definir el procedimiento técnico antes de aplicarlo.]

### 3.4 Al terminar el contrato
SinConflicto entrega a la Comunidad una exportación de sus datos y expedientes en un formato legible. Después de [__] días, los elimina de sus sistemas, salvo lo que deba conservar por obligación legal.

---

**Preguntas que quedan para el abogado:**
- Plazos exactos de conservación de cada tipo de dato.
- Si el tope de "1 a 3 UTM" de la Ley 21.442 aplica también a las multas que impone la comunidad, o solo a las que aplica el Juzgado de Policía Local.
- Las cláusulas de transferencia internacional que exige la Ley 21.719.
- El límite de responsabilidad de SinConflicto.
- El procedimiento para eliminar actas selladas cuando vence el plazo de conservación.
