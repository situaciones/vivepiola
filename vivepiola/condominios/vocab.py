"""
Motor de vocabulario server-side (la "piel" multi-nicho en los canales de salida).

Dos categorias, deliberadamente separadas:

- TERMINOS: sustantivos cortos para incrustar en documentos legales (correo,
  PDF). Ej: "multa" -> "no conformidad".
- FRASES: bloques de texto completos con placeholders `{organizacion}`, para
  respetar el genero/numero del idioma (i18n clave-por-frase). NUNCA se
  concatenan palabras sueltas en una oracion.

Los mensajes de ERROR de la API NO usan este motor: van en redaccion neutra y
agnostica de nicho (ver views), porque un error tecnico no debe consultar el
vertical ni arriesgar incoherencia gramatical.
"""

TERMINOS_DEFAULT = {
    'organizacion': 'condominio',
    'organizacion_cap': 'Condominio',
    'unidad': 'unidad',
    'unidad_cap': 'Unidad',
    'multa': 'multa',
    'multa_cap': 'Multa',
    'sujeto': 'infractor',
    'sujeto_cap': 'Infractor',
    'organo_sancionador': 'Comite de Administracion',
    'destino_cobro': 'gastos comunes',
}

# Frases completas parametrizables. `{X}` se reemplaza con el TERMINO resuelto
# del vertical o con datos del caso pasados por kwargs.
FRASES_DEFAULT = {
    'notificacion_asunto': 'Notificacion de multa #{numero} - {organizacion_cap}',
    'notificacion_saludo': 'Estimado(a) {nombre},',
    'notificacion_cuerpo': (
        'Se le notifica que el {organo_sancionador} de {org_nombre} ha aprobado '
        'una multa asociada a la {unidad} {unidad_id} por la infraccion '
        '"{infraccion}" (Art. {articulo}).'
    ),
    'notificacion_monto': 'Monto: {monto} {unidad_monto}',
    'notificacion_plazo': (
        'Si desea presentar descargos, dispone de un plazo de {dias} dias corridos '
        'desde esta notificacion, hasta el {fecha_limite}.'
    ),
    'notificacion_canal_legal': 'Este correo constituye el canal legal de notificacion del sistema.',
    'pdf_titulo': 'Notificacion de Multa N° {numero}',
    'pdf_label_unidad': 'Unidad',
    'pdf_label_sujeto': 'Infractor',
    'pdf_label_organo': 'Aprobada por el Comite',
    'pdf_aviso_descargo': (
        'Usted dispone de un plazo de {dias} dias corridos desde esta notificacion, '
        'es decir, hasta el {fecha_limite}, para presentar descargos ante el '
        '{organo_sancionador} a traves de la plataforma. Transcurrido este plazo sin '
        'descargos, la multa quedara firme y sera incorporada como obligacion '
        'economica al proximo aviso de cobro de {destino_cobro}.'
    ),
}


def _terminos(condominio):
    terms = dict(TERMINOS_DEFAULT)
    vertical = getattr(condominio, 'vertical', None)
    if vertical and isinstance(vertical.vocabulario, dict):
        # Solo sobrescribe las claves de TERMINOS que el vertical redefina.
        for clave in TERMINOS_DEFAULT:
            if vertical.vocabulario.get(clave):
                terms[clave] = vertical.vocabulario[clave]
    return terms


def termino(condominio, clave):
    return _terminos(condominio).get(clave, clave)


def frase(condominio, clave, **datos):
    """
    Resuelve una frase completa: toma la plantilla del vertical (o el default),
    e inyecta los TERMINOS del vertical + los `datos` del caso. Es determinista
    y tolerante: un placeholder faltante queda como literal en vez de reventar.
    """
    vertical = getattr(condominio, 'vertical', None)
    plantilla = None
    if vertical and isinstance(vertical.vocabulario, dict):
        plantilla = vertical.vocabulario.get(clave)
    if not plantilla:
        plantilla = FRASES_DEFAULT.get(clave, '')

    contexto = {**_terminos(condominio), **datos}

    class _Tolerante(dict):
        def __missing__(self, key):
            return '{' + key + '}'

    return plantilla.format_map(_Tolerante(contexto))
