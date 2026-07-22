from django.contrib.auth.models import AbstractUser
from django.db import models


class Rol(models.TextChoices):
    """Roles legales definidos por la Ley 21.442 (separacion de funciones)."""

    FISCALIZADOR = 'FISCALIZADOR', 'Fiscalizador (Conserje)'
    COMITE = 'COMITE', 'Comite de Administracion'
    ADMINISTRADOR = 'ADMINISTRADOR', 'Administrador'
    RESIDENTE = 'RESIDENTE', 'Residente'
    SUPERADMIN = 'SUPERADMIN', 'Administrador del sistema'


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
