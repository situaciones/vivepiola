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
    # El catalogo guarda la referencia completa ("Art. 4"), por eso la frase
    # NO antepone "Art.": hacerlo producia "(Art. Art. 4)" en la notificacion.
    'notificacion_cuerpo': (
        'Se le notifica que el {organo_sancionador} de {org_nombre} ha aprobado '
        'una multa asociada a la {unidad} {unidad_id} por la infraccion '
        '"{infraccion}" ({articulo}).'
    ),
    # Cuando la multa se cursa sin intervencion humana previa, la notificacion
    # no puede decir que el organo sancionador "aprobo": nadie la aprobo. Una
    # notificacion legal no afirma hechos que no ocurrieron; el contrapeso es
    # el derecho a apelar, que se explica en la frase del plazo.
    'notificacion_cuerpo_automatica': (
        'Se le notifica que en {org_nombre} se ha cursado una multa asociada a la '
        '{unidad} {unidad_id} por la infraccion "{infraccion}" ({articulo}), '
        'conforme al reglamento de copropiedad vigente. La multa fue emitida '
        'automaticamente al registrarse el reporte; si no esta de acuerdo, puede '
        'apelar y el {organo_sancionador} resolvera.'
    ),
    'notificacion_monto': 'Monto: {monto} {unidad_monto}',
    # El aviso de cortesia tiene que decir tres cosas: que no se cobra, cuanto
    # se habria cobrado (sin ese numero el aviso no dice nada), y que la
    # proxima vez si se cobra. Si no, se lee como una multa y asusta igual.
    'notificacion_asunto_cortesia': 'Aviso de {organizacion} #{numero} - sin cobro',
    # Un aviso de cortesia no puede empezar diciendo "se ha cursado una multa"
    # y terminar diciendo que no hay cobro: se contradice y se lee como multa.
    'notificacion_cuerpo_cortesia': (
        'Se le informa que en {org_nombre} se registro una falta asociada a la '
        '{unidad} {unidad_id} por "{infraccion}" ({articulo}), conforme al reglamento '
        'de copropiedad vigente.'
    ),
    'notificacion_cortesia_sin_cobro': (
        'ESTE AVISO NO TIENE COBRO. La falta queda registrada, pero no se le cargara '
        'nada en el gasto comun. Si esta misma situacion se repite, la sancion que '
        'corresponde es de {monto_evitado} {unidad_monto}.'
    ),
    'notificacion_cortesia_cupo': (
        'La comunidad avisa sin cobrar las primeras {cupo} faltas de cada unidad. '
        'Esta es la numero {numero}.'
    ),
    'notificacion_plazo': (
        'Si desea presentar descargos, dispone de un plazo de {dias} dias corridos '
        'desde esta notificacion, hasta el {fecha_limite}.'
    ),
    # El plazo no corre desde el envio sino desde el acuse, asi que el correo
    # tiene que pedirlo de forma explicita y decir para que sirve.
    # El enlace no es solo para acusar recibo: es el buzon del residente, donde
    # esta todo su caso. Anunciarlo como "confirme aqui" desperdiciaba la unica
    # puerta que tiene quien no usa la app.
    'notificacion_pide_acuse': (
        'IMPORTANTE: en este enlace esta todo su caso. Ahi puede confirmar que lo '
        'recibio, ver la norma y la evidencia, descargar este documento las veces '
        'que necesite y presentar su apelacion, sin crear ninguna cuenta:\n'
        '{enlace}\n\n'
        'El plazo para defenderse empieza a correr recien cuando usted confirma, de '
        'modo que nadie pierde su defensa por un correo que no llego a tiempo.'
    ),
    'notificacion_plazo_sin_acuse': (
        'Dispondra de {dias} dias corridos para presentar sus descargos, contados '
        'desde que confirme la recepcion de esta notificacion.'
    ),
    'notificacion_canal_legal': 'Este correo constituye el canal legal de notificacion del sistema.',
    # Se envia en copia al copropietario cuando el infractor es transitorio o
    # ocupa por vinculo con el: la Ley 21.442 lo hace obligado principal al pago.
    'notificacion_copia_copropietario': (
        'Se envia copia de esta notificacion a {nombre}, copropietario(a) de la '
        '{unidad} {unidad_id}, por ser el obligado principal al pago de las '
        'obligaciones economicas de la unidad.'
    ),
    'pdf_titulo': 'Notificacion de Multa N° {numero}',
    'pdf_label_unidad': 'Unidad',
    'pdf_label_sujeto': 'Infractor',
    'pdf_label_organo': 'Aprobada por el Comite',
    'pdf_label_organo_automatica': 'Cursada automaticamente',
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
