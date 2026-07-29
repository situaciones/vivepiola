"""
Envia a cada comunidad UN resumen de lo pendiente, por rol.

Pensado para correr una vez al dia desde un programador (cron / job).
Es seguro ejecutarlo de mas: no vuelve a avisar antes de que pasen las horas
minimas, y nunca envia nada si no hay pendientes.

    manage.py enviar_resumenes                 # respeta el intervalo diario
    manage.py enviar_resumenes --forzar        # envia igual (para probar)
    manage.py enviar_resumenes --simular       # solo muestra, no envia
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Rol, Usuario
from condominios.models import Condominio
from multas.resumenes import (
    enviar_resumen, redactar_mensaje, resumen_para_administracion, resumen_para_comite,
)


class Command(BaseCommand):
    help = 'Envia a comite y administracion un resumen agrupado de lo pendiente en su comunidad.'

    def add_arguments(self, parser):
        parser.add_argument('--condominio', type=int, help='Limitar a una comunidad.')
        parser.add_argument('--horas-minimas', type=int, default=20,
                            help='No reenviar si ya se aviso hace menos de estas horas (por defecto 20).')
        parser.add_argument('--forzar', action='store_true', help='Ignorar el intervalo minimo.')
        parser.add_argument('--simular', action='store_true', help='Mostrar sin enviar.')

    def handle(self, *args, **opciones):
        comunidades = Condominio.objects.all()
        if opciones.get('condominio'):
            comunidades = comunidades.filter(id=opciones['condominio'])

        corte = timezone.now() - timedelta(hours=opciones['horas_minimas'])
        avisados = omitidos = 0

        for condominio in comunidades:
            if not opciones['forzar'] and condominio.ultimo_resumen_enviado and condominio.ultimo_resumen_enviado > corte:
                omitidos += 1
                continue

            hubo_envio = False
            for construir, rol in (
                (resumen_para_comite, Rol.COMITE),
                (resumen_para_administracion, Rol.ADMINISTRADOR),
            ):
                resumen = construir(condominio)
                if not resumen['puntos']:
                    continue

                destinatarios = list(Usuario.objects.filter(
                    condominio=condominio, rol=rol, is_active=True,
                ))
                if not destinatarios:
                    self.stdout.write(
                        f'{condominio.nombre}: hay pendientes para {rol} pero nadie con ese rol.'
                    )
                    continue

                if opciones['simular']:
                    self.stdout.write(f'\n--- {condominio.nombre} / {rol} '
                                      f'({len(destinatarios)} destinatarios) ---')
                    self.stdout.write(redactar_mensaje(condominio, resumen))
                else:
                    enviar_resumen(condominio, resumen, destinatarios)
                hubo_envio = True

            if hubo_envio:
                avisados += 1
                if not opciones['simular']:
                    condominio.ultimo_resumen_enviado = timezone.now()
                    condominio.save(update_fields=['ultimo_resumen_enviado'])

        modo = ' (simulacion)' if opciones['simular'] else ''
        self.stdout.write(
            f'\nComunidades avisadas: {avisados}{modo}. '
            f'Omitidas por aviso reciente: {omitidos}.'
        )
