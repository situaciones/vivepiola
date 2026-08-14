import secrets

from django.conf import settings
from django.db import models

MARCO_LEGAL_DEFAULT = (
    'Documento generado conforme al procedimiento establecido en la Ley 21.442 '
    'sobre Copropiedad Inmobiliaria (Chile).'
)


class Vertical(models.Model):
    """
    Paquete de vertical: la configuracion en frio que hace al motor agnostico
    al nicho. Un Arquitecto de Cumplimiento define aqui vocabulario, marco
    legal de las notificaciones y plazos por defecto; las organizaciones
    (Condominio) se adhieren a un vertical. Sin vertical asignado, el
    comportamiento es el del nicho original (copropiedad / Ley 21.442).
    """

    slug = models.SlugField(unique=True)
    nombre = models.CharField(max_length=120, help_text='Ej: Copropiedad, Construccion, Seguridad Industrial')
    vocabulario = models.JSONField(
        default=dict, blank=True,
        help_text='Diccionario de etiquetas para la UI. Ej: {"unidad": "Subcontratista", "multa": "No conformidad"}.',
    )
    marco_legal_nombre = models.CharField(
        max_length=200, default='Ley 21.442 sobre Copropiedad Inmobiliaria — Chile',
    )
    marco_legal_texto_notificacion = models.TextField(
        default=MARCO_LEGAL_DEFAULT,
        help_text='Parrafo legal que se estampa en el PDF de notificacion (determinista, sin IA).',
    )
    plazo_descargo_dias_default = models.PositiveSmallIntegerField(default=5)
    plazo_ratificacion_horas_default = models.PositiveSmallIntegerField(default=24)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Paquete de vertical'
        verbose_name_plural = 'Paquetes de vertical'

    def __str__(self):
        return self.nombre


class Condominio(models.Model):
    nombre = models.CharField(max_length=200)
    direccion = models.CharField(max_length=255, blank=True)
    rut = models.CharField('RUT administradora', max_length=20, blank=True)
    vertical = models.ForeignKey(
        Vertical, on_delete=models.PROTECT, null=True, blank=True, related_name='organizaciones',
        help_text='Paquete de vertical al que se adhiere esta organizacion. Vacio = copropiedad (Ley 21.442).',
    )
    plazo_descargo_dias = models.PositiveSmallIntegerField(
        default=5,
        help_text='Dias corridos que tiene el residente para presentar descargos tras la notificacion.',
    )
    # El plazo tambien corre para el organo que resuelve. Sin el, una apelacion
    # puede quedar meses sin respuesta y el residente sin saber en que esta.
    plazo_resolucion_dias = models.PositiveSmallIntegerField(
        default=15,
        help_text='Dias corridos que tiene el Comite para resolver una apelacion presentada.',
    )
    # Con 1 resuelve quien entre primero, como hasta ahora. Con 2 o mas, la
    # resolucion exige acuerdo: los votos se acumulan hasta reunir el quorum.
    quorum_resolucion_apelacion = models.PositiveSmallIntegerField(
        default=1,
        help_text='Cuantos miembros del Comite deben coincidir para resolver una apelacion.',
    )
    # Codigo Unico de Comunidad: cualquier vecino puede registrarse via Google
    # con este codigo y queda PENDIENTE de que el Administrador le asigne rol.
    codigo_comunidad = models.CharField(max_length=12, unique=True, null=True, blank=True, db_index=True)
    # Ultimo resumen de pendientes enviado: evita repetir el aviso si el
    # comando corre varias veces al dia.
    ultimo_resumen_enviado = models.DateTimeField(null=True, blank=True, editable=False)
    ventana_duplicados_horas = models.PositiveSmallIntegerField(
        default=24,
        help_text=(
            'Horas dentro de las cuales un nuevo reporte sobre la misma unidad se '
            'entiende referido al mismo hecho y se suma como corroboracion, en vez '
            'de abrir otro expediente (evita sancionar dos veces lo mismo).'
        ),
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def save(self, *args, **kwargs):
        if not self.codigo_comunidad:
            for _ in range(20):
                candidato = secrets.token_hex(4).upper()  # 8 chars hex
                if not Condominio.objects.filter(codigo_comunidad=candidato).exists():
                    self.codigo_comunidad = candidato
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    @property
    def marco_legal_texto(self):
        if self.vertical_id:
            return self.vertical.marco_legal_texto_notificacion
        return MARCO_LEGAL_DEFAULT

    @property
    def marco_legal_nombre(self):
        if self.vertical_id:
            return self.vertical.marco_legal_nombre
        return 'Ley 21.442 sobre Copropiedad Inmobiliaria — Chile'


class CadenaEscalamiento(models.Model):
    """
    Cadena plana, estatica y VERSIONADA de escalamiento por organizacion.
    Editar la cadena = crear una nueva version y activarla; las versiones
    anteriores se conservan porque las actas selladas las referencian.
    Sin cadena activa, el fallback es notificar a Comite + Administrador.
    """

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name='cadenas_escalamiento')
    version = models.PositiveIntegerField()
    activa = models.BooleanField(default=True)
    descripcion = models.CharField(max_length=200, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('condominio', 'version')
        ordering = ['condominio_id', '-version']

    def __str__(self):
        return f'Cadena v{self.version} de {self.condominio.nombre}{" (activa)" if self.activa else ""}'


class NivelEscalamiento(models.Model):
    """Un peldano de la cadena. La notificacion es ACUMULATIVA: escalar al
    nivel N notifica a todos los niveles 1..N, para que la ausencia de una
    persona nunca bloquee la cadena."""

    cadena = models.ForeignKey(CadenaEscalamiento, on_delete=models.CASCADE, related_name='niveles')
    orden = models.PositiveSmallIntegerField(help_text='1 = primer notificado; el escalamiento sube de a uno.')
    usuarios = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='niveles_escalamiento')
    etiqueta = models.CharField(max_length=100, blank=True, help_text='Ej: "Jefatura de turno", "Gerencia".')

    class Meta:
        unique_together = ('cadena', 'orden')
        ordering = ['cadena_id', 'orden']

    def __str__(self):
        return f'Nivel {self.orden} ({self.etiqueta or "sin etiqueta"})'


class Unidad(models.Model):
    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name='unidades')
    identificador = models.CharField(max_length=50, help_text='Ej: Depto 302, Estacionamiento 12')
    alicuota = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)

    class Meta:
        unique_together = ('condominio', 'identificador')
        ordering = ['identificador']

    def __str__(self):
        return f'{self.identificador} ({self.condominio.nombre})'

    @property
    def propietario(self):
        """
        Quien responde por las obligaciones economicas de la unidad.

        La Ley 21.442 hace al copropietario el obligado principal al pago: una
        multa aplicada al arrendatario igual se cobra en el gasto comun de la
        unidad, y quien responde ante la comunidad es su dueño. Por eso el
        cobro se emite a nombre del propietario, no del infractor.
        """
        return self.personas.filter(
            rol_ocupacion=RolOcupacion.PROPIETARIO, activo=True,
        ).order_by('id').first()


class RolOcupacion(models.TextChoices):
    """
    Titulo juridico con que la persona ocupa la unidad (Ley 21.442).

    El PROPIETARIO es el obligado principal al pago: la multa se cobra en el
    gasto comun de la unidad y responde su dueño, aunque el infractor haya
    sido quien la ocupa. Los demas titulos ocupan y pueden ser sancionados,
    pero no son los deudores frente a la comunidad.
    """

    PROPIETARIO = 'PROPIETARIO', 'Propietario'
    ARRENDATARIO = 'ARRENDATARIO', 'Arrendatario'
    USUFRUCTUARIO = 'USUFRUCTUARIO', 'Usufructuario'
    COMODATARIO = 'COMODATARIO', 'Comodatario (uso gratuito)'
    OCUPANTE = 'OCUPANTE', 'Ocupante a otro titulo'


class Permanencia(models.TextChoices):
    """
    Cuanto tiempo permanece, con independencia del titulo: un arrendatario
    puede ser permanente (contrato anual) o transitorio (hospedaje turistico).
    El reglamento suele restringir a los transitorios el uso de bienes comunes
    como piscina o gimnasio, y de ahi salen infracciones reales.
    """

    PERMANENTE = 'PERMANENTE', 'Permanente (reside 30 dias corridos o mas)'
    TRANSITORIO = 'TRANSITORIO', 'Transitorio (alojamiento temporal)'


class VinculoCopropietario(models.TextChoices):
    """
    Relacion con el copropietario. Importa porque el conyuge o conviviente
    civil puede integrar el Comite de Administracion aunque no sea dueño.
    """

    NINGUNO = '', 'Sin vinculo declarado'
    CONYUGE = 'CONYUGE', 'Conyuge'
    CONVIVIENTE_CIVIL = 'CONVIVIENTE_CIVIL', 'Conviviente civil'
    FAMILIAR = 'FAMILIAR', 'Otro familiar'


class CondicionEspecial(models.TextChoices):
    """
    Circunstancias que pueden impedirle a alguien defenderse en plazo.

    No dan impunidad ni anulan nada por si solas: hacen que el expediente se
    detenga antes de cobrarse, para que una persona lo mire en vez de que el
    plazo venza en silencio. La lista es corta y verificable a proposito.
    """

    NINGUNA = '', 'Sin condicion declarada'
    FALLECIDO = 'FALLECIDO', 'Fallecido'
    DISCAPACIDAD = 'DISCAPACIDAD', 'Situacion de discapacidad'
    # Cubre al adulto mayor que no logra usar la app sin ayuda, sin tener que
    # deducirlo de una fecha de nacimiento que nadie va a mantener al dia.
    REQUIERE_APOYO = 'REQUIERE_APOYO', 'Requiere apoyo para tramites digitales'


class Persona(models.Model):
    """
    Ficha individual del registro de copropietarios exigido por la Ley 21.442:
    individualiza a propietarios, arrendatarios y ocupantes con su nombre
    completo, cedula, domicilio y correo (canal legal de notificacion).
    """

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name='personas')
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, related_name='personas')
    rol_ocupacion = models.CharField(max_length=20, choices=RolOcupacion.choices)
    permanencia = models.CharField(
        max_length=20, choices=Permanencia.choices, default=Permanencia.PERMANENTE,
        help_text='Independiente del titulo: define si le aplican las restricciones a transitorios.',
    )
    vinculo_copropietario = models.CharField(
        max_length=20, choices=VinculoCopropietario.choices, blank=True, default='',
        help_text='Conyuge o conviviente civil pueden integrar el Comite aunque no sean dueños.',
    )
    condicion_especial = models.CharField(
        max_length=20, choices=CondicionEspecial.choices, blank=True, default='',
        help_text='Detiene el cobro automatico para que alguien revise el caso antes.',
    )
    nombre_completo = models.CharField(max_length=255)
    cedula_identidad = models.CharField(max_length=20)
    domicilio = models.CharField(max_length=255)
    correo_electronico = models.EmailField()
    telefono = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['unidad__identificador', 'nombre_completo']
        indexes = [
            models.Index(fields=['condominio', 'cedula_identidad']),
        ]

    def __str__(self):
        return f'{self.nombre_completo} - {self.get_rol_ocupacion_display()} ({self.unidad.identificador})'


class RegistroImportacion(models.Model):
    """Trazabilidad de cada carga masiva del registro de copropietarios."""

    class Estado(models.TextChoices):
        PROCESADO = 'PROCESADO', 'Procesado'
        CON_ERRORES = 'CON_ERRORES', 'Procesado con errores'
        FALLIDO = 'FALLIDO', 'Fallido'

    condominio = models.ForeignKey(Condominio, on_delete=models.CASCADE, related_name='importaciones')
    archivo = models.FileField(upload_to='registros_importados/%Y/%m/')
    cargado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    filas_totales = models.PositiveIntegerField(default=0)
    filas_ok = models.PositiveIntegerField(default=0)
    filas_error = models.PositiveIntegerField(default=0)
    detalle_errores = models.JSONField(default=list, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PROCESADO)

    class Meta:
        ordering = ['-fecha_carga']

    def __str__(self):
        return f'Importacion {self.id} - {self.condominio.nombre} ({self.fecha_carga:%Y-%m-%d})'
