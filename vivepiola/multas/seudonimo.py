"""
Seudonimizacion de lo que sale hacia un proveedor de IA en el extranjero.

Enviar textos de residentes a servidores fuera de Chile es una transferencia
internacional de datos (Ley 19.628 / 21.719). Para clasificar un hecho no hace
falta saber quien es nadie: "Juan Perez, RUT 12.345.678-9, dejo basura" se
clasifica igual que "[PERSONA], RUT [RUT], dejo basura". Por eso, antes de cada
llamada, se reemplazan los identificadores directos por marcadores.

Las fotos y videos no se pueden seudonimizar de esta forma; por eso el
analisis visual tiene prohibido describir personas (ver vision.py).
"""

import re

RUT = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK]\b')
CORREO = re.compile(r'\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b')
TELEFONO = re.compile(r'(?<!\w)(?:\+?56[\s-]?)?9[\s-]?\d{4}[\s-]?\d{4}(?!\w)')
# Patentes chilenas: BBBB12 (actual), BB1234 (antigua), con o sin separadores.
PATENTE = re.compile(r'\b(?:[A-Z]{4}[\s·.-]?\d{2}|[A-Z]{2}[\s·.-]?\d{4})\b')


def _nombres_de(condominio):
    """Nombres completos y apellidos de las personas registradas, del mas largo al mas corto."""
    from condominios.models import Persona

    nombres = set()
    for nombre in Persona.objects.filter(condominio=condominio).values_list('nombre_completo', flat=True):
        partes = [p for p in (nombre or '').split() if len(p) > 2]
        if not partes:
            continue
        nombres.add(' '.join(partes))
        # "Juan Andres Perez Soto" tambien aparece como "Juan Perez", "Perez" o "Juan".
        nombres.update(partes)
        for apellido in partes[1:]:
            nombres.add(f'{partes[0]} {apellido}')
    return sorted(nombres, key=len, reverse=True)


def seudonimizar(texto, condominio=None):
    """Devuelve `texto` sin RUT, correos, telefonos, patentes ni nombres de personas registradas."""
    if not texto:
        return texto
    texto = RUT.sub('[RUT]', texto)
    texto = CORREO.sub('[CORREO]', texto)
    texto = TELEFONO.sub('[TELEFONO]', texto)
    texto = PATENTE.sub('[PATENTE]', texto)
    if condominio is not None:
        for nombre in _nombres_de(condominio):
            texto = re.sub(rf'\b{re.escape(nombre)}\b', '[PERSONA]', texto, flags=re.IGNORECASE)
    return texto
