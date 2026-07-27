"""
Clasificador de denuncias: propone que infraccion del catalogo corresponde a
un reporte y por que.

Tres reglas de diseño, en orden de importancia:

1. PROPONE, NO DECIDE. La multa nace EN_REVISION siempre. El Comite confirma
   o cambia la propuesta antes de aprobar; la ley le reserva a el la sancion.
2. NUNCA INVENTA. La respuesta del modelo se valida contra el catalogo real:
   un codigo que no exista se descarta. Una alucinacion no puede convertirse
   en una infraccion imputada.
3. NUNCA BLOQUEA. Sin clave configurada, con la API caida o con una respuesta
   ilegible, cae a coincidencia por palabras clave. El flujo legal no depende
   de la disponibilidad de un tercero.
"""

import json
import re

from django.conf import settings

MODELO = 'claude-sonnet-5'
MAX_INFRACCIONES_EN_PROMPT = 60
MAX_CARACTERES_DESCRIPCION = 240

ORIGEN_IA = 'IA'
ORIGEN_COINCIDENCIA = 'COINCIDENCIA'

PROMPT_SISTEMA = """Eres un asistente de un comite de administracion de condominios en Chile \
(Ley 21.442). Recibes el reporte de un hecho y el catalogo de infracciones vigente de esa \
comunidad, y propones cual infraccion corresponde.

Responde SOLO con un objeto JSON, sin texto adicional, con estas claves:
- "codigo": el codigo EXACTO de una infraccion del catalogo entregado, o null si ninguna \
corresponde razonablemente.
- "confianza": entero de 0 a 100 segun que tan claramente el hecho encaja en esa infraccion.
- "fundamento": una o dos frases explicando por que ese hecho encaja en esa infraccion, \
citando el articulo. Escribe en español de Chile, en tono formal y neutro, dirigido al comite.

Reglas estrictas:
- Nunca inventes un codigo que no este en el catalogo.
- Si el reporte es vago, no corresponde a una infraccion, o no hay una coincidencia \
razonable, devuelve codigo null y explica en el fundamento por que no propones ninguna.
- No afirmes hechos que el reporte no diga. Tu propuesta es un borrador que un humano revisa."""


def _catalogo_para_prompt(infracciones):
    filas = []
    for inf in infracciones[:MAX_INFRACCIONES_EN_PROMPT]:
        filas.append({
            'codigo': inf.codigo,
            'descripcion': inf.descripcion[:MAX_CARACTERES_DESCRIPCION],
            'articulo': inf.articulo_referencia,
            'gravedad': inf.gravedad,
        })
    return filas


def _extraer_json(texto):
    """El modelo puede envolver el JSON en ```json ... ```; se recorta a la llave."""
    texto = (texto or '').strip()
    inicio, fin = texto.find('{'), texto.rfind('}')
    if inicio == -1 or fin == -1 or fin < inicio:
        return None
    try:
        return json.loads(texto[inicio:fin + 1])
    except (json.JSONDecodeError, ValueError):
        return None


def clasificar_con_ia(ticket, infracciones):
    """
    Devuelve (infraccion, confianza, fundamento) o (None, 0, '') si no hay
    propuesta. Lanza excepcion solo si la API falla: el orquestador la captura.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    reporte = {
        'descripcion': (ticket.descripcion or '')[:4000],
        'ubicacion': ticket.ubicacion or '',
        'fecha_hecho': ticket.fecha_hecho.isoformat() if ticket.fecha_hecho else '',
        'unidad': ticket.unidad.identificador,
    }
    contenido_usuario = (
        f'CATALOGO DE INFRACCIONES VIGENTE:\n{json.dumps(_catalogo_para_prompt(infracciones), ensure_ascii=False)}\n\n'
        f'REPORTE A CLASIFICAR:\n{json.dumps(reporte, ensure_ascii=False)}'
    )

    mensaje = client.messages.create(
        model=MODELO,
        max_tokens=600,
        system=PROMPT_SISTEMA,
        messages=[{'role': 'user', 'content': contenido_usuario}],
    )
    texto = ''.join(bloque.text for bloque in mensaje.content if bloque.type == 'text')

    datos = _extraer_json(texto)
    if not isinstance(datos, dict):
        return None, 0, ''

    codigo = datos.get('codigo')
    fundamento = str(datos.get('fundamento') or '').strip()[:1000]
    try:
        confianza = max(0, min(100, int(datos.get('confianza') or 0)))
    except (TypeError, ValueError):
        confianza = 0

    if not codigo:
        return None, confianza, fundamento

    # Anti-alucinacion: el codigo debe existir en el catalogo que se envio.
    por_codigo = {inf.codigo: inf for inf in infracciones}
    infraccion = por_codigo.get(str(codigo).strip())
    if infraccion is None:
        return None, 0, ''
    return infraccion, confianza, fundamento


def clasificar_por_coincidencia(ticket, infracciones):
    """
    Respaldo determinista: cuenta cuantas palabras significativas del codigo y
    la descripcion de cada infraccion aparecen en el reporte. Sin red, sin
    costo y sin sorpresas; menos fino que la IA, pero siempre disponible.
    """
    texto = (ticket.descripcion or '').lower()
    if not texto:
        return None, 0, ''

    mejor, mejor_score = None, 0
    for inf in infracciones:
        crudo = f'{inf.codigo} {inf.descripcion}'.lower()
        tokens = {t for t in re.split(r'[^a-záéíóúñ]+', crudo) if len(t) >= 4}
        score = sum(1 for t in tokens if t in texto)
        if score > mejor_score:
            mejor, mejor_score = inf, score

    if not mejor:
        return None, 0, ''
    fundamento = (
        f'Propuesta por coincidencia de terminos entre el reporte y la infraccion '
        f'{mejor.codigo} ({mejor.articulo_referencia or "sin articulo"}). '
        f'Revise el encuadre antes de aprobar.'
    )
    return mejor, min(60, mejor_score * 20), fundamento
