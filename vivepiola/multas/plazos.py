"""
Plazos en dias habiles.

El plazo para apelar se cuenta en dias habiles (5 a 10, segun la orientacion
legal recibida): no corren sabados, domingos ni feriados de Chile. Vence al
final del ultimo dia habil, en hora de Chile, para que nadie pierda su plazo
por la hora en que le llego el aviso.
"""

from datetime import datetime, time, timedelta

import holidays
from django.utils import timezone


def usa_dias_habiles(condominio):
    """Solo la copropiedad (Ley 21.442) cuenta en habiles; otros verticales siguen su regla."""
    vertical = condominio.vertical
    return vertical is None or vertical.slug == 'copropiedad'


def vencimiento_descargo(condominio, desde, dias):
    if usa_dias_habiles(condominio):
        return sumar_dias_habiles(desde, dias)
    return desde + timedelta(days=dias)


def es_habil(dia):
    return dia.weekday() < 5 and dia not in holidays.Chile(years=dia.year)


def sumar_dias_habiles(desde, dias):
    """Fin del dia habil numero `dias` contado desde el dia siguiente a `desde`."""
    dia = timezone.localtime(desde).date()
    contados = 0
    while contados < dias:
        dia += timedelta(days=1)
        if es_habil(dia):
            contados += 1
    fin = datetime.combine(dia, time(23, 59, 59))
    return timezone.make_aware(fin, timezone.get_current_timezone())
