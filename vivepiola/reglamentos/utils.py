import json

import pdfplumber
from django.conf import settings

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


def extraer_texto_pdf(archivo_pdf):
    texto_paginas = []
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_paginas.append(pagina.extract_text() or '')
    return '\n'.join(texto_paginas)


def sugerir_infracciones_desde_texto(texto_reglamento):
    """
    Llama a la API de Anthropic para obtener un borrador de infracciones.
    Devuelve una lista de dicts; nunca escribe directamente en el catalogo activo.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY no esta configurada en el .env')

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    texto_recortado = texto_reglamento[:60000]  # limite de contexto razonable

    mensaje = client.messages.create(
        model='claude-sonnet-5',
        max_tokens=4096,
        system=PROMPT_SISTEMA,
        messages=[{'role': 'user', 'content': texto_recortado}],
    )

    contenido = ''.join(bloque.text for bloque in mensaje.content if bloque.type == 'text')
    contenido = contenido.strip()
    if contenido.startswith('```'):
        contenido = contenido.strip('`')
        if contenido.startswith('json'):
            contenido = contenido[4:]
    return json.loads(contenido)
