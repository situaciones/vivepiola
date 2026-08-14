from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class EstadoTicket(models.TextChoices):
    """
    Ya no existe un DESCARTADO: descartar un reporte es rechazar el
    expediente, y eso vive en EstadoMulta.RECHAZADA con su motivo y su acta
    sellada. Tener el descarte en dos lugares invitaba a perder la trazabilidad
    de por que un reporte no prospero.
    """

    PENDIENTE = 'PENDIENTE', 'Pendiente de revision'
    CONVERTIDO = 'CONVERTIDO', 'Convertido en multa'


class Ticket(models.Model):
    """
    Reporte generado por el Fiscalizador (conserje). Solo evidencia: nunca
    define monto ni aprueba sancion, conforme al Art. de separacion de roles.
    """

    condominio = models.ForeignKey('condominios.Condominio', on_delete=models.CASCADE, related_name='tickets')
    unidad = models.ForeignKey('condominios.Unidad', on_delete=models.CASCADE, related_name='tickets')
    persona_reportada = models.ForeignKey(
        'condominios.Persona', on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_reportado',
        help_text='Persona de la unidad senalada como presunta infractora (el Comite confirma al aprobar).',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='tickets_creados'
    )
    descripcion = models.TextField()
    fecha_hecho = models.DateTimeField(help_text='Fecha/hora en que ocurrio la presunta infraccion.')
    ubicacion = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoTicket.choices, default=EstadoTicket.PENDIENTE)
    # Anonimato del denunciante: se conserva creado_por en la base para la
    # auditoria interna, pero se omite en las vistas del expediente para no
    # exponer a quien reporta (Art. de proteccion al denunciante).
    anonimo = models.BooleanField(default=False)
    # Cuando varios vecinos reportan el MISMO hecho, el segundo y siguientes no
    # abren un expediente nuevo (nadie puede ser sancionado dos veces por lo
    # mismo): quedan aqui como corroboracion del expediente ya abierto, lo que
    # ademas lo refuerza como prueba.
    corrobora = models.ForeignKey(
        'multas.Multa', on_delete=models.CASCADE, null=True, blank=True, related_name='corroboraciones',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'Ticket #{self.id} - {self.unidad.identificador}'


class EvidenciaFoto(models.Model):
    """
    Prueba adjunta al reporte: una foto o un video.

    El nombre quedo de cuando solo habia fotos y se conserva porque lo
    referencia el resto del sistema. Un hecho como una pelea o un choque no se
    entiende en una imagen fija, y exigir foto obligaba a describir con
    palabras lo que la camara ya habia registrado.

    Ojo con la diferencia probatoria: la foto trae EXIF con fecha y GPS, y de
    ahi sale el anclaje fisico. El video que sale de un telefono no siempre lo
    trae, asi que suele quedar SIN anclar. Sigue siendo prueba, pero mas debil
    para acreditar cuando y donde.
    """

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='evidencias')
    imagen = models.ImageField(upload_to='evidencias/%Y/%m/', null=True, blank=True)
    video = models.FileField(upload_to='evidencias/video/%Y/%m/', null=True, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    subida_en = models.DateTimeField(auto_now_add=True)
    # Sellado V2: hash de contenido calculado en la ingesta. Vacio = evidencia
    # anterior a la epoca de sellado (legacy V1, sin garantia criptografica).
    sha256 = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Metadatos de origen (EXIF): fecha de captura y presencia de GPS. La
    # politica por defecto es marcar la falta de anclaje, no rechazar la foto.
    metadatos_origen = models.JSONField(default=dict, blank=True)
    anclaje_fisico = models.BooleanField(default=False)

    @property
    def archivo(self):
        """El medio adjunto, sea cual sea."""
        return self.video or self.imagen

    @property
    def es_video(self):
        return bool(self.video)

    def __str__(self):
        tipo = 'Video' if self.es_video else 'Foto'
        return f'{tipo} del reporte #{self.ticket_id}'


class EstadoMulta(models.TextChoices):
    EN_REVISION = 'EN_REVISION', 'En revision del Comite'
    RECHAZADA = 'RECHAZADA', 'Rechazada por el Comite'
    APROBADA = 'APROBADA', 'Aprobada, pendiente de notificacion'
    NOTIFICADA = 'NOTIFICADA', 'Notificada al residente'
    CON_DESCARGO = 'CON_DESCARGO', 'Con descargo presentado'
    # Vencio el plazo sin apelacion, pero hay una señal de que la persona pudo
    # no haber podido defenderse. Espera una confirmacion antes de cobrarse.
    POR_CONFIRMAR = 'POR_CONFIRMAR', 'Por confirmar antes del cobro'
    FIRME = 'FIRME', 'Firme (sin apelaciones pendientes)'
    # Se dio por acreditada la falta pero se resuelve sin cobro. No es lo mismo
    # que ANULADA: alli la falta se cae, aqui queda en el registro y cuenta para
    # la reincidencia, de modo que la proxima vez ya no hay cortesia que dar.
    CORTESIA = 'CORTESIA', 'Parte de cortesia (sin cobro)'
    ANULADA = 'ANULADA', 'Anulada'
    EXPORTADA = 'EXPORTADA', 'Exportada a gastos comunes'


class Multa(models.Model):
    """
    Nucleo del flujo legal. El Comite es el UNICO rol que puede aprobar
    (fija infraccion + monto tomados del catalogo). El Administrador solo
    puede notificar una multa ya aprobada; no puede aprobarla ni modificarla.
    """

    condominio = models.ForeignKey('condominios.Condominio', on_delete=models.CASCADE, related_name='multas')
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='multa')
    unidad = models.ForeignKey('condominios.Unidad', on_delete=models.CASCADE, related_name='multas')
    persona_infractor = models.ForeignKey(
        'condominios.Persona', on_delete=models.SET_NULL, null=True, related_name='multas'
    )
    infraccion = models.ForeignKey(
        'reglamentos.InfraccionCatalogo', on_delete=models.PROTECT, null=True, blank=True, related_name='multas'
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # Cuanto se habria cobrado si no fuera una cortesia. Es lo que le da sentido
    # al aviso: sin ese numero, "esto no se cobra" no dice nada.
    monto_sin_cortesia = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoMulta.choices, default=EstadoMulta.EN_REVISION)

    # Aprobacion (Comite)
    aprobada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='multas_aprobadas'
    )
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True)

    # Notificacion (Administrador)
    notificada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='multas_notificadas'
    )
    fecha_notificacion = models.DateTimeField(null=True, blank=True)
    pdf_notificacion = models.FileField(upload_to='notificaciones/%Y/%m/', null=True, blank=True)
    plazo_descargo_dias = models.PositiveSmallIntegerField(null=True, blank=True)
    # El plazo NO corre desde el envio sino desde el acuse: haber despachado un
    # correo no prueba que el residente se entero, y un plazo que vence sin que
    # el afectado supiera de la multa no resiste una impugnacion.
    fecha_acuse = models.DateTimeField(null=True, blank=True)
    canal_acuse = models.CharField(max_length=20, blank=True)
    fecha_limite_descargo = models.DateTimeField(null=True, blank=True)

    # Propuesta automatica al ingresar la denuncia. Es un BORRADOR para el
    # Comite: se guarda con su origen y fundamento para que quien decide sepa
    # de donde salio y pueda descartarla. Nunca sustituye la decision humana.
    propuesta_origen = models.CharField(
        max_length=20, blank=True,
        help_text='IA = clasificador; COINCIDENCIA = respaldo por terminos; vacio = sin propuesta.',
    )
    propuesta_confianza = models.PositiveSmallIntegerField(default=0)
    propuesta_fundamento = models.TextField(blank=True)

    # Reincidencia (Ley 21.442: misma infraccion dentro de 6 meses de la primera sancion)
    es_reincidencia = models.BooleanField(default=False)
    multa_primera_sancion = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reincidencias'
    )
    agravante_sugerido = models.CharField(max_length=255, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_firme = models.DateTimeField(null=True, blank=True)

    @property
    def es_aviso_de_cortesia(self):
        """Se notifico sin cobro por ser de las primeras faltas de la unidad."""
        return self.monto_sin_cortesia is not None

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'Multa #{self.id} - {self.unidad.identificador} ({self.get_estado_display()})'

    def calcular_fecha_limite_descargo(self):
        dias = self.plazo_descargo_dias or self.condominio.plazo_descargo_dias
        return timezone.now() + timedelta(days=dias)

    @property
    def descargo_vigente(self):
        return bool(self.fecha_limite_descargo and timezone.now() <= self.fecha_limite_descargo)


class ResolucionDescargo(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente de resolucion'
    ACEPTADO = 'ACEPTADO', 'Aceptado (multa anulada)'
    RECHAZADO = 'RECHAZADO', 'Rechazado (multa se mantiene firme)'
    DESCUENTO = 'DESCUENTO', 'Descuento parcial (firme, con el monto rebajado)'
    CORTESIA = 'CORTESIA', 'Parte de cortesia (falta acreditada, sin cobro)'


class Descargo(models.Model):
    """Defensa presentada por el residente dentro del plazo configurado."""

    multa = models.OneToOneField(Multa, on_delete=models.CASCADE, related_name='descargo')
    presentado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    texto = models.TextField()
    archivo_adjunto = models.FileField(upload_to='descargos/%Y/%m/', null=True, blank=True)
    fecha_presentacion = models.DateTimeField(auto_now_add=True)
    resolucion = models.CharField(max_length=20, choices=ResolucionDescargo.choices, default=ResolucionDescargo.PENDIENTE)
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='descargos_resueltos'
    )
    comentario_resolucion = models.TextField(blank=True)
    porcentaje_descuento = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Rebaja porcentual aplicada al monto cuando la resolucion es DESCUENTO (ej: 30, 50).',
    )
    monto_original = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Monto de la multa antes del descuento, congelado al resolver (trazabilidad).',
    )
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    # Hasta cuando tiene el Comite para resolver. Se fija al presentarse la
    # apelacion: el plazo obliga a las dos partes, no solo al residente.
    fecha_limite_resolucion = models.DateTimeField(null=True, blank=True)

    @property
    def resolucion_vencida(self):
        """El Comite se paso del plazo que tenia para responder."""
        from django.utils import timezone as _tz

        return bool(
            self.resolucion == ResolucionDescargo.PENDIENTE
            and self.fecha_limite_resolucion
            and self.fecha_limite_resolucion < _tz.now()
        )

    def __str__(self):
        return f'Descargo multa #{self.multa_id}'


class OrigenAntecedente(models.TextChoices):
    RESIDENTE = 'RESIDENTE', 'Aportado por el residente'
    REUNION = 'REUNION', 'Aportado en la reunion'


class AntecedenteDescargo(models.Model):
    """
    Prueba que se suma a una apelacion ya presentada.

    La defensa no se agota en el formulario inicial: el residente puede
    conseguir despues una boleta, un certificado o el testimonio de un vecino.
    Obligarlo a tenerlo todo listo en el primer intento seria recortarle la
    defensa por un problema de calendario.

    Solo se puede aportar mientras la apelacion siga sin resolver: despues de
    la resolucion el expediente esta cerrado y agregarle piezas lo falsearia.
    """

    descargo = models.ForeignKey(Descargo, on_delete=models.CASCADE, related_name='antecedentes')
    texto = models.TextField()
    archivo_adjunto = models.FileField(upload_to='antecedentes/%Y/%m/', null=True, blank=True)
    origen = models.CharField(
        max_length=20, choices=OrigenAntecedente.choices, default=OrigenAntecedente.RESIDENTE,
    )
    aportado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha']

    def __str__(self):
        return f'Antecedente de la apelacion #{self.descargo_id} ({self.origen})'


class ModalidadReunion(models.TextChoices):
    ONLINE = 'ONLINE', 'En linea'
    PRESENCIAL = 'PRESENCIAL', 'Presencial'


class EstadoReunion(models.TextChoices):
    PROPUESTA = 'PROPUESTA', 'Propuesta, esperando al residente'
    CONFIRMADA = 'CONFIRMADA', 'Confirmada por el residente'
    REALIZADA = 'REALIZADA', 'Realizada'
    CANCELADA = 'CANCELADA', 'Cancelada'


class ReunionApelacion(models.Model):
    """
    Instancia para que el residente exponga su caso en persona o en linea.

    Un formulario no siempre alcanza: hay explicaciones que se entienden
    hablando. Convocarla extiende el plazo que tiene el Comite para resolver,
    porque de otro modo citar a alguien cerca del vencimiento seria imposible
    o quedaria como incumplimiento del propio organo.
    """

    descargo = models.ForeignKey(Descargo, on_delete=models.CASCADE, related_name='reuniones')
    modalidad = models.CharField(max_length=20, choices=ModalidadReunion.choices)
    fecha_propuesta = models.DateTimeField()
    # Sala de videollamada si es en linea, o el lugar fisico si es presencial.
    lugar_o_enlace = models.CharField(max_length=300)
    estado = models.CharField(max_length=20, choices=EstadoReunion.choices, default=EstadoReunion.PROPUESTA)
    convocada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='reuniones_convocadas',
    )
    confirmada_en = models.DateTimeField(null=True, blank=True)
    acta = models.TextField(blank=True, help_text='Lo que se expuso en la reunion.')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_propuesta']

    def __str__(self):
        return f'Reunion {self.modalidad} de la apelacion #{self.descargo_id} ({self.estado})'


class VotoResolucion(models.Model):
    """
    Voto de un miembro del Comite sobre como resolver una apelacion.

    Solo entra en juego cuando la comunidad exige quorum mayor a uno: ahi la
    resolucion deja de ser de quien llegue primero y pasa a necesitar acuerdo.
    Un mismo actor no puede votar dos veces la misma apelacion.
    """

    descargo = models.ForeignKey(Descargo, on_delete=models.CASCADE, related_name='votos')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    resolucion = models.CharField(max_length=20, choices=ResolucionDescargo.choices)
    porcentaje_descuento = models.PositiveSmallIntegerField(null=True, blank=True)
    comentario = models.TextField(blank=True)
    ts = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ts']
        unique_together = ('descargo', 'actor')

    def __str__(self):
        return f'Voto {self.resolucion} de {self.actor} en la apelacion #{self.descargo_id}'


class HistorialMulta(models.Model):
    """Bitacora inmutable de cada cambio de estado, para el debido proceso."""

    multa = models.ForeignKey(Multa, on_delete=models.CASCADE, related_name='historial')
    estado_anterior = models.CharField(max_length=20, blank=True)
    estado_nuevo = models.CharField(max_length=20)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    comentario = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha']

    def __str__(self):
        return f'Multa #{self.multa_id}: {self.estado_anterior} -> {self.estado_nuevo}'


class CanalNotificacion(models.TextChoices):
    EMAIL = 'EMAIL', 'Correo electronico'
    WHATSAPP = 'WHATSAPP', 'WhatsApp'
    APP = 'APP', 'Ingreso a la aplicacion'
    TELEFONO = 'TELEFONO', 'Llamada telefonica'
    PRESENCIAL = 'PRESENCIAL', 'Entrega en mano'
    BUZON = 'BUZON', 'Constancia dejada en el buzon de la unidad'


class EstadoEntrega(models.TextChoices):
    ENVIADA = 'ENVIADA', 'Enviada, sin acuse todavia'
    FALLIDA = 'FALLIDA', 'El envio fallo'
    ACUSADA = 'ACUSADA', 'Recepcion acusada por el destinatario'


class EntregaNotificacion(models.Model):
    """
    Cada intento de hacerle llegar la notificacion al residente, por el canal
    que sea.

    Existe porque "se envio un correo" no prueba que alguien se haya enterado.
    Si manana el residente alega que nunca supo de la multa, esta bitacora
    muestra a que direccion se escribio, cuantas veces, por que canales y si
    hubo o no acuse. Sin esa prueba, el plazo de apelacion es indefendible.
    """

    multa = models.ForeignKey(Multa, on_delete=models.CASCADE, related_name='entregas')
    canal = models.CharField(max_length=20, choices=CanalNotificacion.choices)
    # A donde se envio: el correo, el telefono, o la unidad en el caso del buzon.
    destino = models.CharField(max_length=200)
    intento = models.PositiveSmallIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=EstadoEntrega.choices, default=EstadoEntrega.ENVIADA)
    enviada_en = models.DateTimeField(auto_now_add=True)
    acusada_en = models.DateTimeField(null=True, blank=True)
    # Quien dejo la constancia fisica o registro la entrega en mano. Vacio en
    # los canales que despacha el sistema.
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='entregas_registradas',
    )
    detalle = models.TextField(blank=True, help_text='Error del envio o nota de quien entrego.')

    class Meta:
        ordering = ['enviada_en']

    def __str__(self):
        return f'Multa #{self.multa_id} por {self.canal} (intento {self.intento}): {self.estado}'


class TipoActo(models.TextChoices):
    CURSE_AUTOMATICO = 'CURSE_AUTOMATICO', 'Curse automatico de la multa (sin filtro previo)'
    APROBACION = 'APROBACION', 'Aprobacion de la multa'
    RECHAZO = 'RECHAZO', 'Rechazo del reporte'
    NOTIFICACION = 'NOTIFICACION', 'Notificacion al residente'
    DESCARGO_PRESENTADO = 'DESCARGO_PRESENTADO', 'Descargo presentado'
    ACUSE_RECIBO = 'ACUSE_RECIBO', 'Acuse de recibo de la notificacion'
    ANTECEDENTE_APORTADO = 'ANTECEDENTE_APORTADO', 'Antecedente sumado a la apelacion'
    REUNION_CONVOCADA = 'REUNION_CONVOCADA', 'Reunion convocada con el residente'
    REUNION_REALIZADA = 'REUNION_REALIZADA', 'Reunion realizada'
    VOTO_RESOLUCION = 'VOTO_RESOLUCION', 'Voto del Comite sobre la apelacion'
    RESOLUCION_DESCARGO = 'RESOLUCION_DESCARGO', 'Resolucion del descargo'
    FIRMEZA_AUTOMATICA = 'FIRMEZA_AUTOMATICA', 'Firmeza automatica por vencimiento de plazo'
    CONFIRMACION_PREVIA_COBRO = 'CONFIRMACION_PREVIA_COBRO', 'Confirmacion antes del cobro'
    # Carril de contencion (manifiesto polimorfico tipo CONTENCION)
    CONTENCION_EJECUTADA = 'CONTENCION_EJECUTADA', 'Medida inmediata ejecutada'
    VOTO_RATIFICACION = 'VOTO_RATIFICACION', 'Voto de ratificacion (quorum)'
    CONTENCION_RATIFICADA = 'CONTENCION_RATIFICADA', 'Medida inmediata ratificada'
    CONTENCION_LEVANTADA = 'CONTENCION_LEVANTADA', 'Medida inmediata levantada'
    ESCALAMIENTO_POR_OMISION = 'ESCALAMIENTO_POR_OMISION', 'Escalamiento por omision de ratificacion'


class ActaSellada(models.Model):
    """
    Registro criptografico de cada acto de decision (sellado V2).

    Cada acta congela un manifiesto canonico de lo que el actor tenia a la
    vista al decidir (evidencias con su hash, texto de la norma aplicada,
    estado del expediente) y se encadena a la anterior:

        hash_acto = SHA256(hash_previo || SHA256(manifiesto_canonico))

    Es INSERT-only: la aplicacion no expone actualizacion, y triggers a nivel
    de base de datos abortan cualquier UPDATE/DELETE (ver migracion de
    triggers). Los expedientes sin actas son legacy V1, anteriores a la epoca
    de sellado, y no reciben garantias retroactivas.
    """

    GENESIS = '0' * 64

    multa = models.ForeignKey(Multa, on_delete=models.PROTECT, related_name='actas_selladas')
    indice = models.PositiveIntegerField()
    tipo_acto = models.CharField(max_length=30, choices=TipoActo.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    auth_metodo = models.CharField(max_length=40, default='jwt_password_session')
    ts = models.DateTimeField()
    manifiesto = models.JSONField()
    manifiesto_sha256 = models.CharField(max_length=64)
    hash_previo = models.CharField(max_length=64)
    hash_acto = models.CharField(max_length=64, db_index=True)

    class Meta:
        ordering = ['multa_id', 'indice']
        unique_together = ('multa', 'indice')

    def __str__(self):
        return f'Acta {self.indice} ({self.tipo_acto}) de multa #{self.multa_id}'


class EstadoMedida(models.TextChoices):
    EJECUTADA = 'EJECUTADA', 'Ejecutada (contencion activa, pendiente de ratificacion)'
    RATIFICADA = 'RATIFICADA', 'Ratificada (contencion activa, con dueño)'
    EN_ESCALAMIENTO = 'EN_ESCALAMIENTO', 'En escalamiento por omision (contencion ACTIVA)'
    LEVANTADA = 'LEVANTADA', 'Levantada por acto humano'


ESTADOS_MEDIDA_ACTIVOS = (EstadoMedida.EJECUTADA, EstadoMedida.RATIFICADA, EstadoMedida.EN_ESCALAMIENTO)


class CausalLevantamiento(models.TextChoices):
    CORREGIDA = 'CORREGIDA', 'Hallazgo corregido (con evidencia)'
    DESESTIMADA = 'DESESTIMADA', 'Hallazgo desestimado (con fundamento)'


class MedidaInmediata(models.Model):
    """
    Carril de contencion, paralelo al carril sancionatorio de 6 etapas.

    Maquina de estados FAIL-CLOSED: ninguna transicion automatica apunta a
    LEVANTADA. La no-ratificacion escala (y queda registrada como omision
    atribuible), jamas libera. Levantar exige acto humano con facultad,
    causal y fundamento. La sancion sigue su propio carril: esta medida se
    anexa al expediente como contexto, nunca la sustituye.
    """

    multa = models.ForeignKey(Multa, on_delete=models.PROTECT, related_name='medidas_inmediatas')
    hallazgo = models.ForeignKey(
        'reglamentos.InfraccionCatalogo', on_delete=models.PROTECT, related_name='medidas_inmediatas'
    )
    descripcion = models.CharField(max_length=500, blank=True)
    evidencias = models.ManyToManyField(EvidenciaFoto, blank=True, related_name='medidas_inmediatas')

    estado = models.CharField(max_length=20, choices=EstadoMedida.choices, default=EstadoMedida.EJECUTADA)

    ejecutada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='medidas_ejecutadas'
    )
    auth_metodo_ejecucion = models.CharField(max_length=40, default='jwt_password_session')
    ejecutada_en = models.DateTimeField()

    plazo_ratificacion_horas = models.PositiveSmallIntegerField()
    proxima_revision = models.DateTimeField(db_index=True)
    nivel_escalamiento = models.PositiveSmallIntegerField(default=0)
    # Quorum congelado desde el catalogo al ejecutar (no se re-lee: la politica
    # de riesgo vigente al momento del hallazgo es la que rige ese expediente).
    quorum_requerido = models.PositiveSmallIntegerField(default=1)

    ratificada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='medidas_ratificadas'
    )
    ratificada_en = models.DateTimeField(null=True, blank=True)

    levantada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='medidas_levantadas'
    )
    levantada_en = models.DateTimeField(null=True, blank=True)
    causal_levantamiento = models.CharField(max_length=20, choices=CausalLevantamiento.choices, blank=True)
    fundamento_levantamiento = models.TextField(blank=True)

    class Meta:
        ordering = ['-ejecutada_en']

    def __str__(self):
        return f'Medida #{self.id} ({self.get_estado_display()}) - multa #{self.multa_id}'

    @property
    def activa(self):
        return self.estado in ESTADOS_MEDIDA_ACTIVOS


# Orden de gravedad para el techo del delegado (indice mayor = mas grave).
ORDEN_GRAVEDAD = {'LEVE': 0, 'GRAVE': 1, 'GRAVISIMA': 2}


class AccionDelegable(models.TextChoices):
    RATIFICAR_CONTENCION = 'RATIFICAR_CONTENCION', 'Ratificar contencion'


class EstadoDelegacion(models.TextChoices):
    VIGENTE = 'VIGENTE', 'Vigente'
    REVOCADA = 'REVOCADA', 'Revocada'


class Delegacion(models.Model):
    """
    Transferencia TACTICA de autoridad, no estructural. Restricciones duras:
    vencimiento OBLIGATORIO (vigencia_hasta NOT NULL), techo de gravedad, y
    profundidad 1 (un delegado no re-delega). Cada uso de esta delegacion se
    sella en el acta del voto con un SNAPSHOT congelado de este otorgamiento
    (no un FK): el verificador audita la ventana contra el ts del voto sin
    consultar el estado vivo. Nace con su propio hash de contenido para que el
    snapshot embebido sea cotejable (otorgamiento_hash).
    """

    condominio = models.ForeignKey('condominios.Condominio', on_delete=models.CASCADE, related_name='delegaciones')
    delegante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delegaciones_otorgadas')
    delegado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='delegaciones_recibidas')
    version = models.PositiveIntegerField(default=1)
    acciones = models.JSONField(default=list)  # lista de AccionDelegable
    tope_gravedad = models.CharField(max_length=20, default='GRAVE')  # no delegable lo GRAVISIMA
    vigencia_desde = models.DateTimeField()
    vigencia_hasta = models.DateTimeField()  # OBLIGATORIO: no hay delegacion indefinida
    estado = models.CharField(max_length=20, choices=EstadoDelegacion.choices, default=EstadoDelegacion.VIGENTE)
    motivo = models.CharField(max_length=255, blank=True)
    otorgamiento_hash = models.CharField(max_length=64, editable=False)
    revocada_en = models.DateTimeField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada_en']

    def __str__(self):
        return f'Delegacion #{self.id}: {self.delegante_id}->{self.delegado_id} ({self.estado})'

    def snapshot(self):
        """Dict congelado del otorgamiento, para embeber en el manifiesto del voto."""
        return {
            'tipo': 'DELEGACION',
            'delegacion_id': self.id,
            'delegacion_version': self.version,
            'delegante': {'id': self.delegante_id, 'username': self.delegante.username},
            'acciones': list(self.acciones),
            'tope_gravedad': self.tope_gravedad,
            'vigencia_desde': self.vigencia_desde.isoformat(),
            'vigencia_hasta': self.vigencia_hasta.isoformat(),
            'otorgamiento_hash': self.otorgamiento_hash,
        }

    def vigente_para(self, accion, gravedad, momento):
        """Chequeo aritmetico: ventana + alcance + techo. Mismo criterio que aplica el verificador."""
        if self.estado != EstadoDelegacion.VIGENTE:
            return False
        if accion not in self.acciones:
            return False
        if self.vigencia_desde > momento or momento > self.vigencia_hasta:
            return False
        return ORDEN_GRAVEDAD.get(gravedad, 99) <= ORDEN_GRAVEDAD.get(self.tope_gravedad, -1)


class EnCalidadDe(models.TextChoices):
    TITULAR = 'TITULAR', 'Titular (cargo propio)'
    DELEGADO = 'DELEGADO', 'Delegado'


class VotoRatificacion(models.Model):
    """
    Un voto sellado individualmente hacia el quorum de una medida. Idempotente
    por (medida, actor): el candado pesimista del expediente garantiza que un
    mismo actor fisico incremente el quorum una sola vez, llegue por su cargo
    o por delegacion. El acta VOTO_RATIFICACION correspondiente lleva el
    snapshot de la delegacion cuando en_calidad_de = DELEGADO.
    """

    medida = models.ForeignKey(MedidaInmediata, on_delete=models.PROTECT, related_name='votos')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='votos_ratificacion')
    en_calidad_de = models.CharField(max_length=20, choices=EnCalidadDe.choices)
    delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, null=True, blank=True, related_name='votos_emitidos')
    ts = models.DateTimeField()

    class Meta:
        unique_together = ('medida', 'actor')  # idempotencia a nivel de base de datos
        ordering = ['medida_id', 'ts']

    def __str__(self):
        return f'Voto de {self.actor_id} en medida #{self.medida_id} ({self.en_calidad_de})'
