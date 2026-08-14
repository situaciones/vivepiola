"""
Reenvia las notificaciones que todavia no tienen acuse de recibo.

Una notificacion enviada una sola vez no prueba nada: el correo pudo caer en
spam, el telefono pudo estar sin datos. Se reintenta hasta tres veces, con
cinco minutos entre intentos, y se corta apenas el residente confirma. Cuando
se agotan los intentos sin respuesta, el caso queda listado para que alguien
imprima la constancia y la deje en el buzon de la unidad.

Pensado para correr cada pocos minutos como job programado.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone

from multas.models import EstadoMulta, Multa
from multas.services import despachar_notificacion

INTENTOS_MAXIMOS = 3
MINUTOS_ENTRE_INTENTOS = 5


class Command(BaseCommand):
    help = 'Reintenta las notificaciones sin acuse de recibo (hasta 3 veces, cada 5 minutos).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--intentos', type=int, default=INTENTOS_MAXIMOS,
            help=f'Cuantos envios como maximo por expediente (por defecto {INTENTOS_MAXIMOS}).',
        )
        parser.add_argument(
            '--minutos', type=int, default=MINUTOS_ENTRE_INTENTOS,
            help=f'Minutos de espera entre intentos (por defecto {MINUTOS_ENTRE_INTENTOS}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra que haria sin enviar nada.',
        )

    def handle(self, *args, **opciones):
        intentos_maximos = opciones['intentos']
        espera = timedelta(minutes=opciones['minutos'])
        ahora = timezone.now()

        pendientes = (
            Multa.objects
            .filter(estado=EstadoMulta.NOTIFICADA, fecha_acuse__isnull=True)
            .annotate(ultimo_intento=Max('entregas__intento'), ultimo_envio=Max('entregas__enviada_en'))
        )

        reenviadas = agotadas = 0
        for multa in pendientes:
            intento_previo = multa.ultimo_intento or 0

            if intento_previo >= intentos_maximos:
                agotadas += 1
                self.stdout.write(
                    f'  Multa #{multa.id}: {intento_previo} intentos sin acuse. '
                    f'Corresponde dejar constancia en el buzon de {multa.unidad}.'
                )
                continue

            if multa.ultimo_envio and (ahora - multa.ultimo_envio) < espera:
                continue  # todavia no toca

            if opciones['dry_run']:
                self.stdout.write(f'  Multa #{multa.id}: reenviaria el intento {intento_previo + 1}.')
                reenviadas += 1
                continue

            enviados, _ = despachar_notificacion(multa, intento=intento_previo + 1)
            if enviados:
                reenviadas += 1
                self.stdout.write(f'  Multa #{multa.id}: intento {intento_previo + 1} por {enviados} canal(es).')

        self.stdout.write(self.style.SUCCESS(
            f'Reenviadas: {reenviadas}. Sin acuse tras agotar intentos: {agotadas}.'
        ))
