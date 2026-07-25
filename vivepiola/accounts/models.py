import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    """Roles legales definidos por la Ley 21.442 (separacion de funciones)."""

    FISCALIZADOR = 'FISCALIZADOR', 'Fiscalizador (Conserje)'
    COMITE = 'COMITE', 'Comite de Administracion'
    ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador'
    RESIDENTE = 'RESIDENTE', 'Residente'
    SUPERADMIN = 'SUPERADMIN', 'Administrador del sistema'
    # Registro self-serve (Google) sin invitacion: la cuenta existe pero no
    # accede a ningun modulo hasta que un Administrador le asigne rol final.
    PENDIENTE = 'PENDIENTE', 'Pendiente de asignacion'


# Roles que un Administrador de condominio puede asignar/invitar. El rol
# ADMINISTRADOR y SUPERADMIN quedan fuera: solo el Django admin los otorga.
ROLES_ASIGNABLES = (Rol.FISCALIZADOR, Rol.COMITE, Rol.RESIDENTE)


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
