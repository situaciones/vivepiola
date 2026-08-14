import json
import re
from decimal import Decimal, InvalidOperation

import pdfplumber
from django.conf import settings

from .models import Gravedad

PROMPT_SISTEMA = """Eres un asistente que apoya a administradores de condominios en Chile a \
digitalizar su reglamento de copropiedad (Ley 21.442). A partir del texto de un reglamento, \
identifica las infracciones/faltas sancionables y sugiere una entrada de catalogo para cada una.

Responde SOLO con un arreglo JSON (sin texto adicional), donde cada elemento tiene:
- "codigo": string corto y unico, ej "RUIDO-01"
- "descripcion": redaccion clara y breve de la infraccion, fiel al texto original
- "articulo_referencia": articulo o clausula del reglamento donde se basa (ej "Art. 12")
- "monto": numero (sin simbolos) del monto de la multa si el reglamento lo indica; usa 0 si no se especifica
- "unidad_monto": "UF", "UTM" o "CLP" segun corresponda
- "gravedad": "LEVE", "GRAVE" o "GRAVISIMA" segun el texto o tu mejor estimacion
- "texto_fuente": la cita textual exacta del reglamento en la que se basa esta infraccion

Estas sugerencias son un BORRADOR: un humano debe revisarlas y confirmarlas antes de que \
tengan validez, asi que prioriza fidelidad al texto por sobre completar campos con inventos.
No inventes infracciones que no esten razonablemente respaldadas por el texto."""

# Como leer cada clase de documento. El acta es el caso distinto: no tiene
# articulos sino acuerdos, y citar un "Art. 12" que no existe seria inventar
# la base legal de una sancion.
INSTRUCCIONES_POR_TIPO = {
    'REGLAMENTO_COPROPIEDAD': 'Es el reglamento de copropiedad. Cita el articulo o clausula.',
    'ESTACIONAMIENTOS': (
        'Es un instructivo de uso de estacionamientos. Las faltas suelen ser ocupar un lugar '
        'ajeno, estacionar en zonas de circulacion o exceder el tiempo de visitas.'
    ),
    'ESPACIOS_COMUNES': (
        'Es un instructivo de uso de espacios comunes (quincho, piscina, gimnasio, salon). '
        'Las faltas suelen ser usar fuera de horario, exceder aforo o no dejar aseado.'
    ),
    'SEGURIDAD': (
        'Son normas de seguridad. Trata con especial cuidado las faltas que ponen en riesgo '
        'a personas: describelas con precision y no las suavices.'
    ),
    'AMBIENTAL': (
        'Es normativa ambiental. Las faltas suelen referirse a residuos, reciclaje, ruido '
        'ambiental o manejo de sustancias.'
    ),
    'ACTA_ASAMBLEA': (
        'Es un ACTA O ACUERDO DE ASAMBLEA, no un reglamento. No tiene articulos: tiene '
        'acuerdos adoptados. En "articulo_referencia" escribe el acuerdo tal como aparece '
        '(ej: "Acuerdo 3 de la asamblea"), NUNCA un numero de articulo que no exista. '
        'Extrae solo los acuerdos que establecen una obligacion o prohibicion sancionable; '
        'ignora lo que sea informativo, administrativo o de mera constancia.'
    ),
    'OTRO': 'Es otro cuerpo normativo de la comunidad. Cita la seccion en que te bases.',
}


class ReglamentoIlegible(Exception):
    """El PDF no entrega texto utilizable: escaneado como imagen, vacio o corrupto."""


# Un reglamento de copropiedad real tiene miles de caracteres. Por debajo de
# esto no hay nada que leer: casi siempre es un PDF escaneado como imagen
# (el caso mas comun en condominios) o un archivo que no era el que se queria.
MINIMO_CARACTERES_UTILES = 100


def extraer_texto_pdf(archivo_pdf):
    """
    Devuelve el texto plano del reglamento, o levanta ReglamentoIlegible con
    un mensaje que el administrador pueda accionar. Nunca devuelve vacio en
    silencio: un reglamento sin texto no permite operar el condominio.
    """
    try:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto = '\n'.join(pagina.extract_text() or '' for pagina in pdf.pages)
    except Exception as exc:
        raise ReglamentoIlegible(
            'No se pudo leer el archivo como PDF. Revisa que sea el documento '
            'correcto y que no este danado.'
        ) from exc

    if len(texto.strip()) < MINIMO_CARACTERES_UTILES:
        raise ReglamentoIlegible(
            'El PDF no contiene texto legible: parece un documento escaneado como '
            'imagen. Sube una version digital (con texto que se pueda seleccionar) '
            'o pasa el escaneo por un OCR antes de subirlo.'
        )
    return texto


# ------------------------------------------------------------------ sugerencias

UNIDADES_MONTO = {'CLP', 'UF', 'UTM'}
MONTO_MAXIMO = Decimal('9999999999.99')  # tope del campo del catalogo


def _a_decimal(valor):
    """'1,5' / '2 UF' / 1.5 -> Decimal; cualquier otra cosa -> 0."""
    numero = re.search(r'-?\d+(?:[.,]\d+)?', str(valor if valor is not None else ''))
    if not numero:
        return Decimal('0.00')
    try:
        monto = Decimal(numero.group().replace(',', '.')).quantize(Decimal('0.01'))
    except InvalidOperation:
        return Decimal('0.00')
    return min(max(monto, Decimal('0.00')), MONTO_MAXIMO)


def normalizar_sugerencia(item):
    """
    La IA es un tercero: puede devolver 'cinco UF' donde se espera un numero,
    una gravedad que no existe o un texto mas largo que el campo. Se normaliza
    aqui para que una sugerencia mala no bote la carga completa del catalogo.

    Devuelve None si la sugerencia no es utilizable (sin codigo no hay entrada).
    """
    if not isinstance(item, dict):
        return None

    codigo = str(item.get('codigo') or '').strip()[:30]
    if not codigo:
        return None

    gravedad = str(item.get('gravedad') or '').strip().upper()
    unidad = str(item.get('unidad_monto') or '').strip().upper()
    return {
        'codigo': codigo,
        'descripcion': str(item.get('descripcion') or '').strip()[:500],
        'articulo_referencia': str(item.get('articulo_referencia') or '').strip()[:100],
        'monto': _a_decimal(item.get('monto')),
        'unidad_monto': unidad if unidad in UNIDADES_MONTO else 'UF',
        'gravedad': gravedad if gravedad in Gravedad.values else Gravedad.LEVE,
        'texto_fuente': str(item.get('texto_fuente') or '').strip(),
    }


def sugerir_infracciones_desde_texto(texto_reglamento, tipo='REGLAMENTO_COPROPIEDAD'):
    """
    Llama a la API de Anthropic para obtener un borrador de infracciones.

    El tipo de documento cambia como se lee: un acta de asamblea no tiene
    articulos sino acuerdos, y pedirle a la IA que cite un "Art. 12"
    inexistente seria inventarle base legal a una sancion.

    Devuelve una lista de dicts; nunca escribe directamente en el catalogo activo.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY no esta configurada en el .env')

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    texto_recortado = texto_reglamento[:60000]  # limite de contexto razonable

    instruccion = INSTRUCCIONES_POR_TIPO.get(tipo, INSTRUCCIONES_POR_TIPO['OTRO'])
    sistema = f'{PROMPT_SISTEMA}\n\nSOBRE ESTE DOCUMENTO: {instruccion}'
    mensaje = client.messages.create(
        model='claude-sonnet-5',
        max_tokens=4096,
        system=sistema,
        messages=[{'role': 'user', 'content': texto_recortado}],
    )

    contenido = ''.join(bloque.text for bloque in mensaje.content if bloque.type == 'text')
    contenido = contenido.strip()
    if contenido.startswith('```'):
        contenido = contenido.strip('`')
        if contenido.startswith('json'):
            contenido = contenido[4:]
    return json.loads(contenido)
