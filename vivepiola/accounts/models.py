import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    """Roles legales definidos por la Ley 21.442 (separacion de funciones)."""

    # Se muestra como "Denunciante". La clave sigue siendo FISCALIZADOR porque
    # es la que esta guardada en las cuentas y la que reconocen las apps ya
    # instaladas; cambiarla dejaria sin panel a esos usuarios.
    FISCALIZADOR = 'FISCALIZADOR', 'Denunciante'
    COMITE = 'COMITE', 'Comite de Administracion'
    ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador'
    RESIDENTE = 'RESIDENTE', 'Residente'
    SUPERADMIN = 'SUPERADMIN', 'Administrador del sistema'
    # Registro self-serve (Google) sin invitacion: la cuenta existe pero no
    # accede a ningun modulo hasta que un Administrador le asigne rol final.
    PENDIENTE = 'PENDIENTE', 'Pendiente de asignacion'


# Roles que un Administrador de condominio puede asignar/invitar. El rol
# ADMINISTRADOR y SUPERADMIN quedan fuera: solo el Django admin los otorga.
# COMITE tambien: el Comite nace de la designacion con acta de asamblea
# (condominios/comite.py), no de una invitacion suelta.
ROLES_ASIGNABLES = (Rol.FISCALIZADOR, Rol.RESIDENTE)


class Usuario(AbstractUser):
    """
    Usuario del sistema. El rol determina que acciones puede ejecutar en el
    flujo legal (ver permissions.py de cada app) y es inmutable desde la API
    para evitar que un usuario se autoasigne permisos que la ley reserva a
    otro organo del condominio.
    """

    rol = models.CharField(max_length=20, choices=Rol.choices)
    condominio = models.ForeignKey(
        'condominios.Condominio',
        on_delete=models.CASCADE,
        related_name='usuarios',
        null=True,
        blank=True,
        help_text='Condominio al que pertenece este usuario (no aplica a SUPERADMIN).',
    )
    persona = models.OneToOneField(
        'condominios.Persona',
        on_delete=models.SET_NULL,
        related_name='usuario_cuenta',
        null=True,
        blank=True,
        help_text='Vinculo a su ficha del registro de copropietarios (obligatorio si rol=RESIDENTE).',
    )
    telefono = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_rol_display()})'

    def eliminar_cuenta(self):
        """
        Borra los datos personales de la cuenta y la deja sin acceso.

        No se borra la fila: denuncias, descargos, votos y actas son registros
        del procedimiento sancionatorio que la comunidad debe conservar (Ley
        21.442), y varios apuntan a la cuenta con PROTECT. Quedan firmados por
        "Cuenta eliminada". La ficha del registro de copropietarios (Persona)
        es de la comunidad, no de la cuenta, asi que solo se desvincula.
        """
        self.username = f'eliminado-{self.pk}'
        self.email = ''
        self.first_name = 'Cuenta eliminada'
        self.last_name = ''
        self.telefono = ''
        self.persona = None
        self.is_active = False
        self.is_staff = False
        self.is_superuser = False
        self.set_unusable_password()
        self.save()
        PermisoDenuncia.objects.filter(usuario=self).delete()
        self.niveles_escalamiento.clear()


class EstadoInvitacion(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    ACEPTADA = 'ACEPTADA', 'Aceptada'
    REVOCADA = 'REVOCADA', 'Revocada'


def _generar_codigo_invitacion():
    return secrets.token_urlsafe(9)  # 12 chars URL-safe


class Invitacion(models.Model):
    """
    Invitacion delegada: el Administrador del condominio (no el Superadmin)
    invita por correo indicando unidad y rol sugerido. Al aceptar via Google,
    la cuenta nace ya asociada a la comunidad con ese rol.
    """

    condominio = models.ForeignKey('condominios.Condominio', on_delete=models.CASCADE, related_name='invitaciones')
    correo = models.EmailField()
    unidad = models.ForeignKey(
        'condominios.Unidad', on_delete=models.SET_NULL, null=True, blank=True, related_name='invitaciones'
    )
    rol_sugerido = models.CharField(max_length=20, choices=Rol.choices)
    codigo = models.CharField(max_length=32, unique=True, default=_generar_codigo_invitacion)
    estado = models.CharField(max_length=20, choices=EstadoInvitacion.choices, default=EstadoInvitacion.PENDIENTE)
    creada_por = models.ForeignKey(
        'accounts.Usuario', on_delete=models.SET_NULL, null=True, related_name='invitaciones_enviadas'
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    aceptada_por = models.ForeignKey(
        'accounts.Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='invitaciones_aceptadas'
    )
    aceptada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creada_en']

    def save(self, *args, **kwargs):
        if not self.expira_en:
            self.expira_en = timezone.now() + timedelta(days=14)
        super().save(*args, **kwargs)

    @property
    def vigente(self):
        return self.estado == EstadoInvitacion.PENDIENTE and timezone.now() <= self.expira_en

    def __str__(self):
        return f'Invitacion a {self.correo} ({self.rol_sugerido}) - {self.condominio.nombre}'


DIAS_SEMANA = ('Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo')


class PermisoDenuncia(models.Model):
    """
    Limites que el Administrador pone a un Denunciante: desde cuando y hasta
    cuando puede reportar, que dias, en que horario y sobre que unidades.

    Sin esta ficha el Denunciante reporta sin limites, como siempre. Cada
    campo vacio significa "sin limite" en ese aspecto, de modo que se puede
    acotar solo lo que haga falta (por ejemplo, solo el turno de noche).
    """

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='permiso_denuncia')
    suspendido = models.BooleanField(default=False, help_text='Suspende el permiso sin quitar el rol.')
    vigente_desde = models.DateField(null=True, blank=True)
    vigente_hasta = models.DateField(null=True, blank=True)
    # 0 = lunes ... 6 = domingo. Vacio = todos los dias.
    dias = models.JSONField(default=list, blank=True)
    # Si hora_hasta es menor que hora_desde, el turno cruza la medianoche.
    hora_desde = models.TimeField(null=True, blank=True)
    hora_hasta = models.TimeField(null=True, blank=True)
    unidades = models.ManyToManyField('condominios.Unidad', blank=True, related_name='denunciantes_permitidos')
    notas = models.CharField(max_length=255, blank=True)
    actualizado_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Permiso para denunciar de {self.usuario}'

    def motivo_rechazo(self, momento, unidad=None):
        """
        Por que este permiso no cubre un reporte hecho en `momento` sobre
        `unidad`; None si lo cubre. El mensaje se muestra tal cual al
        Denunciante, asi que dice que limite fallo y cual es.
        """
        local = timezone.localtime(momento)
        hoy = local.date()
        if self.suspendido:
            return 'Su permiso para denunciar esta suspendido por la administracion.'
        if self.vigente_desde and hoy < self.vigente_desde:
            return f'Su permiso para denunciar comienza el {self.vigente_desde:%d-%m-%Y}.'
        if self.vigente_hasta and hoy > self.vigente_hasta:
            return f'Su permiso para denunciar vencio el {self.vigente_hasta:%d-%m-%Y}.'
        ahora = local.time()
        cruza_medianoche = bool(self.hora_desde and self.hora_hasta and self.hora_hasta < self.hora_desde)
        # En un turno de 22:00 a 06:00, la madrugada del sabado es el turno del
        # viernes: el dia que cuenta es el dia en que empezo el turno.
        dia_turno = local.weekday()
        if cruza_medianoche and ahora <= self.hora_hasta:
            dia_turno = (dia_turno - 1) % 7
        if self.dias and dia_turno not in self.dias:
            permitidos = ', '.join(DIAS_SEMANA[d] for d in sorted(self.dias))
            return f'Hoy no esta dentro de sus dias para denunciar ({permitidos}).'
        if self.hora_desde and self.hora_hasta:
            if cruza_medianoche:
                dentro = ahora >= self.hora_desde or ahora <= self.hora_hasta
            else:
                dentro = self.hora_desde <= ahora <= self.hora_hasta
            if not dentro:
                return (
                    f'Esta fuera de su horario para denunciar '
                    f'({self.hora_desde:%H:%M} a {self.hora_hasta:%H:%M}).'
                )
        if unidad is not None and self.pk:
            permitidas = list(self.unidades.values_list('id', flat=True))
            if permitidas and unidad.id not in permitidas:
                return f'No tiene permiso para denunciar {unidad.identificador}.'
        return None


def motivo_fuera_de_permiso(usuario, unidad=None, momento=None):
    """
    None si el usuario puede reportar ahora sobre esa unidad. Solo limita al
    Denunciante: Comite y Residentes reportan por derecho propio (Ley 21.442).
    """
    if usuario.rol != Rol.FISCALIZADOR:
        return None
    try:
        permiso = usuario.permiso_denuncia
    except PermisoDenuncia.DoesNotExist:
        return None
    return permiso.motivo_rechazo(momento or timezone.now(), unidad)
