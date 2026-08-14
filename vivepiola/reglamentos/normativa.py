"""
Base normativa transversal: lo que rige a TODOS los condominios de Chile.

COMO FUNCIONA Y POR QUE ASI
---------------------------
Un abogado con experiencia en copropiedad decide que fuentes entran: la ley, su
reglamento, circulares del MINVU o de la SEC, folletos, dictamenes. Sube el PDF,
el Word o la URL, y el sistema la trocea por articulo, indexa cada trozo y lo
guarda.

Cuando hace falta consultar la normativa NO se le manda la ley entera al modelo.
Se busca el pasaje preciso y se le mandan solo esos fragmentos, con su
referencia. Es la diferencia entre pedirle a alguien que se aprenda el codigo
de memoria y darle el articulo que necesita: lo primero no escala, cuesta una
fortuna en contexto y ademas empeora la respuesta, porque lo relevante queda
enterrado entre miles de lineas que no vienen al caso.

La consecuencia practica es que el corpus puede crecer sin limite. Agregar la
circular de este mes no encarece ni degrada ninguna consulta: solo la hace
encontrable.

TRAZABILIDAD
------------
Cada fragmento recuperado viaja con su fuente y su referencia ("Ley 21.442,
Art. 12"), y eso es lo que el modelo debe citar. Un fundamento que dice "segun
la ley" sin decir cual articulo no sirve para sostener una sancion.
"""

import numpy as np
from django.conf import settings
from django.db import models


class TipoFuente(models.TextChoices):
    LEY = 'LEY', 'Ley'
    REGLAMENTO_LEY = 'REGLAMENTO_LEY', 'Reglamento de la ley'
    CIRCULAR_MINVU = 'CIRCULAR_MINVU', 'Circular u ordinario MINVU'
    CIRCULAR_SEC = 'CIRCULAR_SEC', 'Circular SEC'
    DICTAMEN = 'DICTAMEN', 'Dictamen o jurisprudencia'
    FOLLETO = 'FOLLETO', 'Folleto o guia oficial'
    OTRA = 'OTRA', 'Otra fuente aplicable'


# Cuando dos fragmentos empatan en pertinencia, manda el que manda mas.
ORDEN_JERARQUICO = {
    TipoFuente.LEY: 1,
    TipoFuente.REGLAMENTO_LEY: 2,
    TipoFuente.CIRCULAR_MINVU: 3,
    TipoFuente.CIRCULAR_SEC: 3,
    TipoFuente.DICTAMEN: 4,
    TipoFuente.FOLLETO: 5,
    TipoFuente.OTRA: 6,
}


class FuenteNormativa(models.Model):
    """
    Un documento que un abogado incorporo al corpus.

    No tiene FK a Condominio a proposito: no pertenece a ninguna comunidad. La
    mantiene la plataforma y todas la consultan igual.
    """

    tipo = models.CharField(max_length=20, choices=TipoFuente.choices)
    identificador = models.CharField(
        max_length=120, unique=True,
        help_text='Como se cita. Ej: "Ley 21.442", "Circular MINVU 15/2026".',
    )
    titulo = models.CharField(max_length=300)
    fecha_documento = models.DateField(null=True, blank=True)

    # La fuente puede llegar como archivo o como enlace. Se conserva el origen
    # porque una norma sin procedencia no sirve para fundar nada.
    archivo = models.FileField(upload_to='normativa/%Y/%m/', null=True, blank=True)
    url_fuente = models.URLField(max_length=500, blank=True)

    texto = models.TextField(blank=True, editable=False)
    vigente = models.BooleanField(
        default=True,
        help_text='Al derogarse o reemplazarse, se desmarca. Sus fragmentos dejan de consultarse.',
    )
    nota_version = models.CharField(
        max_length=300, blank=True,
        help_text='Por que se cargo o actualizo. Ej: "Reemplaza la circular 8/2025".',
    )

    cargada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fuentes_normativas',
    )
    fecha_carga = models.DateTimeField(auto_now_add=True)
    indexada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['identificador']
        verbose_name = 'Fuente normativa'
        verbose_name_plural = 'Fuentes normativas (Chile)'

    def __str__(self):
        estado = '' if self.vigente else ' (no vigente)'
        return f'{self.identificador} - {self.titulo[:60]}{estado}'

    @property
    def indexada(self):
        return self.indexada_en is not None and self.fragmentos.exists()

    @property
    def total_fragmentos(self):
        return self.fragmentos.count()


class FragmentoNormativo(models.Model):
    """
    Un trozo citable de una fuente, con su vector para poder encontrarlo.

    El corte se hace por articulo y no por largo fijo: el articulo es la unidad
    que se cita, y partirlo por la mitad produce fragmentos que no se pueden
    invocar en el fundamento de una sancion.
    """

    fuente = models.ForeignKey(FuenteNormativa, on_delete=models.CASCADE, related_name='fragmentos')
    orden = models.PositiveIntegerField()
    referencia = models.CharField(
        max_length=100,
        help_text='Lo que se cita. Ej: "Art. 12". Nunca un indice interno.',
    )
    texto = models.TextField()
    # float32 crudo: 768 dimensiones ocupan 3 KB aqui y 20 KB como JSON, y el
    # corpus completo se lee entero en cada busqueda.
    vector = models.BinaryField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['fuente_id', 'orden']
        unique_together = ('fuente', 'orden')

    def __str__(self):
        return f'{self.fuente.identificador} {self.referencia}'

    @property
    def cita(self):
        """Como se nombra este pasaje al fundar una sancion."""
        return f'{self.fuente.identificador}, {self.referencia}'


# ----------------------------------------------------------------- embeddings

def _cliente_embeddings():
    from google import genai

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _embeber(textos, es_consulta=False):
    """
    Convierte textos en vectores.

    Los documentos y las consultas se embeben con proposito distinto: un
    articulo de ley y la pregunta "el perro andaba suelto" no se parecen como
    textos, pero deben quedar cerca en el espacio vectorial. Declararlo mejora
    bastante lo que se recupera.
    """
    from google.genai import types

    cliente = _cliente_embeddings()
    respuesta = cliente.models.embed_content(
        model=settings.NORMATIVA_MODELO_EMBEDDING,
        contents=list(textos),
        config=types.EmbedContentConfig(
            task_type='RETRIEVAL_QUERY' if es_consulta else 'RETRIEVAL_DOCUMENT',
            output_dimensionality=settings.NORMATIVA_DIMENSIONES,
        ),
    )
    return [np.asarray(e.values, dtype=np.float32) for e in respuesta.embeddings]


def _normalizar(vector):
    norma = np.linalg.norm(vector)
    return vector / norma if norma else vector


def indexar_fuente(fuente, texto=None):
    """
    Trocea la fuente y calcula el vector de cada fragmento.

    Reindexar reemplaza lo anterior: una norma actualizada no puede convivir
    con la version vieja, porque la busqueda devolveria las dos y el modelo no
    tiene como saber cual rige.

    Devuelve cuantos fragmentos quedaron indexados.
    """
    from django.utils import timezone

    from .fuentes import trocear

    contenido = texto if texto is not None else fuente.texto
    piezas = trocear(contenido)
    if not piezas:
        return 0

    fuente.fragmentos.all().delete()

    vectores = [None] * len(piezas)
    if settings.GEMINI_API_KEY:
        # Por lotes: una llamada por fragmento seria lentisimo en un corpus de
        # miles, y la API acepta varios textos de una vez.
        lote = settings.NORMATIVA_LOTE_EMBEDDING
        for inicio in range(0, len(piezas), lote):
            trozo = [t for _, t in piezas[inicio:inicio + lote]]
            for i, vector in enumerate(_embeber(trozo)):
                vectores[inicio + i] = _normalizar(vector)

    FragmentoNormativo.objects.bulk_create([
        FragmentoNormativo(
            fuente=fuente, orden=i, referencia=referencia, texto=cuerpo,
            vector=vectores[i].tobytes() if vectores[i] is not None else None,
        )
        for i, (referencia, cuerpo) in enumerate(piezas)
    ])

    fuente.texto = contenido
    fuente.indexada_en = timezone.now()
    fuente.save(update_fields=['texto', 'indexada_en'])
    return len(piezas)


# ----------------------------------------------------------------- busqueda

def buscar_normativa(consulta, k=None, minimo_pertinencia=None):
    """
    Devuelve los fragmentos mas pertinentes para la consulta.

    Esta es la pieza que hace que el corpus pueda crecer sin limite: agregar la
    circular de este mes no encarece ninguna consulta, solo la hace
    encontrable.

    Sin clave de embeddings o sin corpus devuelve lista vacia, y todo el
    sistema sigue funcionando sin normativa transversal.
    """
    k = k or settings.NORMATIVA_FRAGMENTOS_POR_CONSULTA
    minimo = (
        minimo_pertinencia if minimo_pertinencia is not None
        else settings.NORMATIVA_PERTINENCIA_MINIMA
    )

    if not (settings.GEMINI_API_KEY and consulta and consulta.strip()):
        return []

    fragmentos = list(
        FragmentoNormativo.objects
        .filter(fuente__vigente=True, vector__isnull=False)
        .select_related('fuente')
    )
    if not fragmentos:
        return []

    try:
        vector_consulta = _normalizar(_embeber([consulta[:8000]], es_consulta=True)[0])
    except Exception:
        # La caida del servicio de embeddings no puede interrumpir una denuncia.
        return []

    matriz = np.vstack([
        np.frombuffer(f.vector, dtype=np.float32) for f in fragmentos
    ])
    # Ambos lados estan normalizados, asi que el producto punto ES el coseno.
    puntajes = matriz @ vector_consulta

    candidatos = [
        (float(p), f) for p, f in zip(puntajes, fragmentos) if float(p) >= minimo
    ]
    # A igual pertinencia manda la jerarquia: entre una ley y un folleto que
    # dicen lo mismo, se cita la ley.
    candidatos.sort(
        key=lambda par: (-par[0], ORDEN_JERARQUICO.get(par[1].fuente.tipo, 99)),
    )
    return [
        {'fragmento': f, 'cita': f.cita, 'texto': f.texto, 'pertinencia': round(p, 3)}
        for p, f in candidatos[:k]
    ]


def contexto_normativo(consulta, k=None):
    """
    Bloque de normativa listo para entregarle al modelo, ya recortado a lo
    pertinente y con las citas puestas.

    Devuelve cadena vacia si no hay nada que aportar, y quien lo llama debe
    seguir funcionando igual: la normativa mejora el encuadre, no lo habilita.
    """
    resultados = buscar_normativa(consulta, k=k)
    if not resultados:
        return ''

    piezas = [f'[{r["cita"]}]\n{r["texto"]}' for r in resultados]
    return (
        'NORMATIVA GENERAL DE CHILE PERTINENTE A ESTE CASO (prevalece sobre el '
        'reglamento de la comunidad en lo que lo contradiga). Cita SIEMPRE la '
        'referencia entre corchetes cuando te apoyes en alguna:\n\n'
        + '\n\n'.join(piezas)
    )


def estado_del_corpus():
    """Que hay cargado, que falta indexar y cuanto pesa."""
    fuentes = list(FuenteNormativa.objects.all())
    indexadas = [f for f in fuentes if f.indexada]
    return {
        'fuentes': len(fuentes),
        'vigentes': len([f for f in fuentes if f.vigente]),
        'indexadas': len(indexadas),
        'sin_indexar': [f.identificador for f in fuentes if not f.indexada],
        'fragmentos': FragmentoNormativo.objects.count(),
        'fragmentos_con_vector': FragmentoNormativo.objects.filter(vector__isnull=False).count(),
    }
