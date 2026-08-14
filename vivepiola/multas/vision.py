"""
Analisis de la evidencia adjunta: que se ve en las fotos y los videos.

POR QUE OTRO PROVEEDOR
----------------------
Hay hechos que solo la imagen prueba: un auto sobre la rampa, basura fuera del
punto limpio, una pelea. Hasta ahora el clasificador leia unicamente la
descripcion escrita, o sea que la evidencia estaba en el expediente pero nadie
la miraba hasta que llegaba una persona.

Anthropic y OpenAI reciben imagenes pero NO video: obligan a extraer
fotogramas, lo que significa arrastrar una libreria de video al despliegue y
elegir a ciegas que instantes representan el hecho. Gemini acepta el archivo de
video completo, asi que se usa para esta tarea y solo para esta.

El razonamiento legal se queda donde estan las salvaguardas: este modulo
describe lo que ve y nada mas. No propone infracciones, no califica gravedad y
no decide. Su salida es texto que entra al clasificador como un dato mas del
reporte, y queda escrita en el expediente para que cualquiera pueda contrastar
lo que el sistema dijo ver con lo que la foto realmente muestra.

PRIVACIDAD
----------
La instruccion prohibe describir personas identificables. Un sistema que
anotara "hombre de unos 50 anos, polera roja" estaria construyendo perfiles de
residentes a partir de camaras, que es justo lo que la Ley 19.628 busca evitar.
Se describe la conducta y el lugar, no a quien aparece.
"""

import mimetypes

from django.conf import settings

# El analisis mira la conducta y el lugar. Lo que NO debe hacer esta escrito
# con la misma claridad que lo que si, porque un modelo que no lo tiene
# prohibido explicitamente tiende a describir a las personas.
PROMPT_VISION = """Eres un asistente que describe evidencia de convivencia en condominios chilenos.

Describe UNICAMENTE lo que se observa, de forma objetiva y breve:
- que objetos, vehiculos o animales aparecen y donde estan;
- en que lugar ocurre (pasillo, estacionamiento, area comun, fachada);
- que conducta o situacion se aprecia;
- si hay senaletica, demarcacion o numeracion visible, transcribela.

PROHIBIDO:
- describir a las personas o cualquier rasgo que permita identificarlas
  (edad, sexo, contextura, vestimenta, rostro, color de piel);
- nombrar o suponer quien es alguien;
- afirmar que se cometio una infraccion o citar normas: eso lo decide otro paso;
- inventar lo que no se ve. Si la imagen es ambigua o no se distingue, dilo.

Responde en 2 a 4 frases, en español de Chile, sin encabezados ni vinetas."""

# Formatos que el proveedor acepta. Lo que no este aqui se omite en silencio:
# una evidencia que no se puede analizar no invalida el reporte.
MIME_IMAGEN = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MIME_VIDEO = {'video/mp4', 'video/quicktime', 'video/webm', 'video/3gpp', 'video/x-m4v'}


class VisionNoDisponible(Exception):
    """No hay proveedor configurado para analizar evidencia."""


def _mime_de(evidencia):
    archivo = evidencia.archivo
    if not archivo:
        return ''
    adivinado, _ = mimetypes.guess_type(archivo.name)
    if adivinado:
        return adivinado
    return 'video/mp4' if evidencia.es_video else 'image/jpeg'


def _analizar_con_gemini(piezas):
    """
    Manda las piezas a Gemini y devuelve su descripcion.

    Se elige Gemini porque ingiere el video completo sin fotogramas
    intermedios. Si manana conviene otro proveedor, se reemplaza esta funcion:
    el resto del sistema solo conoce `analizar_evidencias`.
    """
    from google import genai
    from google.genai import types

    cliente = genai.Client(api_key=settings.GEMINI_API_KEY)

    partes = [types.Part.from_text(text=PROMPT_VISION)]
    for datos, mime in piezas:
        partes.append(types.Part.from_bytes(data=datos, mime_type=mime))

    respuesta = cliente.models.generate_content(
        model=settings.GEMINI_MODELO_VISION,
        contents=partes,
    )
    return (respuesta.text or '').strip()


def analizar_evidencias(ticket):
    """
    Describe la evidencia adjunta al reporte.

    Devuelve (descripcion, cuantas_piezas_analizadas). Cadena vacia cuando no
    hay proveedor, no hay evidencia o el analisis falla: la evidencia no
    analizada sigue en el expediente y la sigue viendo una persona, asi que
    ninguna falla aqui puede detener una denuncia.
    """
    if not settings.GEMINI_API_KEY:
        return '', 0

    evidencias = list(ticket.evidencias.all()[:settings.VISION_MAX_PIEZAS])
    if not evidencias:
        return '', 0

    piezas = []
    for evidencia in evidencias:
        mime = _mime_de(evidencia)
        if mime not in MIME_IMAGEN and mime not in MIME_VIDEO:
            continue
        archivo = evidencia.archivo
        try:
            archivo.open('rb')
            datos = archivo.read()
        except Exception:
            continue
        finally:
            try:
                archivo.close()
            except Exception:
                pass

        if len(datos) > settings.VISION_MAX_BYTES_POR_PIEZA:
            continue  # demasiado pesado para el analisis; sigue como prueba
        piezas.append((datos, mime))

    if not piezas:
        return '', 0

    try:
        descripcion = _analizar_con_gemini(piezas)
    except Exception:
        # Igual que el clasificador: la caida de un servicio externo nunca
        # interrumpe el flujo legal.
        return '', 0

    return descripcion[:settings.VISION_MAX_CARACTERES], len(piezas)
