"""El plazo para apelar corre en dias habiles: sin fines de semana ni feriados de Chile."""

from datetime import datetime

from django.test import SimpleTestCase
from django.utils import timezone

from multas.plazos import es_habil, sumar_dias_habiles


def _cl(anio, mes, dia, hora=10):
    return timezone.make_aware(datetime(anio, mes, dia, hora), timezone.get_current_timezone())


class PlazosHabilesTestCase(SimpleTestCase):
    def test_no_cuentan_sabado_ni_domingo(self):
        # Viernes 6-nov-2026 + 1 habil = lunes 9-nov, al final del dia.
        fin = timezone.localtime(sumar_dias_habiles(_cl(2026, 11, 6), 1))
        self.assertEqual((fin.year, fin.month, fin.day, fin.hour, fin.minute), (2026, 11, 9, 23, 59))

    def test_no_cuentan_los_feriados(self):
        self.assertFalse(es_habil(datetime(2026, 9, 18).date()))  # Fiestas Patrias
        # Jueves 17-sep-2026 + 1 habil: 18 y 19 son feriado y 20 domingo -> lunes 21.
        fin = timezone.localtime(sumar_dias_habiles(_cl(2026, 9, 17), 1))
        self.assertEqual((fin.month, fin.day), (9, 21))

    def test_diez_habiles_son_dos_semanas(self):
        fin = timezone.localtime(sumar_dias_habiles(_cl(2026, 11, 2), 10))  # lunes, sin feriados cerca
        self.assertEqual((fin.month, fin.day), (11, 16))
