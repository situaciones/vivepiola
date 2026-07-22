from django.core.management.base import BaseCommand

from multas.contencion import escalar_medidas_vencidas


class Command(BaseCommand):
    help = (
        'Barre las medidas inmediatas activas cuyo plazo de ratificacion vencio y '
        'sella el acto de omision, escalando el nivel. La contencion NUNCA se levanta '
        'automaticamente (fail-closed). Pensado para cron: cada 15-30 minutos.'
    )

    def handle(self, *args, **options):
        escaladas = escalar_medidas_vencidas()
        self.stdout.write(self.style.SUCCESS(f'{escaladas} medida(s) escaladas por omision.'))
