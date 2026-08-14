"""
Base normativa transversal: lo que rige a TODOS los condominios de Chile.

Un condominio no se rige solo por su reglamento. Encima esta la Ley 21.442, su
reglamento, la normativa del MINVU y otras normas generales que ninguna
comunidad redacta ni deberia tener que cargar. Eso lo mantiene la plataforma y
esta disponible desde el primer dia, sin que el administrador haga nada.

Por que importa que la IA la tenga a la vista: sin ella, al leer el reglamento
de una comunidad no puede notar que una sancion excede el tope legal, ni que un
plazo contradice el que fija la ley. Con ella, el catalogo que propone nace
encuadrado.

SOBRE EL TEXTO OFICIAL
----------------------
El texto de cada norma NO viene escrito en el codigo, y es deliberado: escribir
de memoria el articulado de una ley que despues se cita en una notificacion es
la forma mas rapida de fundar una sancion en un articulo que no existe. Se
carga desde los archivos oficiales con el comando `cargar_normativa`.

Mientras el corpus este vacio el sistema funciona igual, solo que sin ese
encuadre: se degrada, no se cae.
"""

from django.conf import settings
from django.db import models


class TipoNormaTransversal(models.TextChoices):
    LEY = 'LEY', 'Ley'
    REGLAMENTO_LEY = 'REGLAMENTO_LEY', 'Reglamento de la ley'
    CIRCULAR_MINVU = 'CIRCULAR_MINVU', 'Circular u ordinario MINVU'
    DICTAMEN = 'DICTAMEN', 'Dictamen o jurisprudencia'
    OTRA = 'OTRA', 'Otra norma aplicable'


# Jerarquia normativa: cuando hay que recortar por espacio, lo primero que se
# manda es lo que manda mas. Una circular no puede desplazar a la ley.
ORDEN_JERARQUICO = {
    TipoNormaTransversal.LEY: 1,
    TipoNormaTransversal.REGLAMENTO_LEY: 2,
    TipoNormaTransversal.CIRCULAR_MINVU: 3,
    TipoNormaTransversal.DICTAMEN: 4,
    TipoNormaTransversal.OTRA: 5,
}


class NormaTransversal(models.Model):
    """
    Una norma general del ordenamiento chileno, comun a todos los condominios.

    No tiene FK a Condominio a proposito: no pertenece a ninguna comunidad. La
    mantiene la plataforma y todas la reciben igual.
    """

    tipo = models.CharField(max_length=20, choices=TipoNormaTransversal.choices)
    # Como se cita: "Ley 21.442", "D.S. N 7 (2023) MINVU".
    identificador = models.CharField(max_length=100, unique=True)
    titulo = models.CharField(max_length=300)
    fecha_publicacion = models.DateField(null=True, blank=True)
    # De donde salio el texto. Sin esto nadie puede verificar que lo cargado sea
    # lo vigente, y una norma sin procedencia no sirve para fundar nada.
    fuente_url = models.URLField(
        max_length=500, blank=True,
        help_text='Enlace oficial (bcn.cl, leychile.cl, minvu.cl) del que se obtuvo el texto.',
    )
    texto = models.TextField(
        blank=True,
        help_text='Texto oficial. Se carga con el comando cargar_normativa, no se escribe a mano.',
    )
    vigente = models.BooleanField(default=True)
    # Resumen operativo corto, para cuando el texto completo no cabe en el
    # contexto. Lo redacta una persona, no la IA.
    resumen = models.TextField(
        blank=True,
        help_text='Sintesis de lo que esta norma exige, para usar cuando el texto completo no cabe.',
    )
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['identificador']
        verbose_name = 'Norma transversal'
        verbose_name_plural = 'Normas transversales (Chile)'

    def __str__(self):
        estado = '' if self.vigente else ' (no vigente)'
        return f'{self.identificador} - {self.titulo[:60]}{estado}'

    @property
    def cargada(self):
        """Tiene texto o resumen utilizable. Una norma sin ninguno no aporta."""
        return bool(self.texto.strip() or self.resumen.strip())


def contexto_normativo(presupuesto_caracteres=None):
    """
    Arma el bloque de normativa transversal que se le entrega a la IA.

    Se recorta por jerarquia y no por orden de carga: si no cabe todo, lo que
    se conserva es lo que manda mas. De cada norma se prefiere el texto
    completo y, si no alcanza, su resumen; peor es mandar media ley cortada
    que una sintesis entera.

    Devuelve cadena vacia si no hay corpus cargado, y el resto del sistema
    sigue funcionando sin el.
    """
    presupuesto = presupuesto_caracteres or settings.NORMATIVA_PRESUPUESTO_CARACTERES

    normas = sorted(
        (n for n in NormaTransversal.objects.filter(vigente=True) if n.cargada),
        key=lambda n: (ORDEN_JERARQUICO.get(n.tipo, 99), n.identificador),
    )
    if not normas:
        return ''

    piezas = []
    restante = presupuesto
    for norma in normas:
        encabezado = f'--- {norma.identificador}: {norma.titulo} ---\n'
        cuerpo = norma.texto.strip() or norma.resumen.strip()

        disponible = restante - len(encabezado)
        if disponible <= 200:  # ya no cabe nada util
            break
        if len(cuerpo) > disponible:
            # No cabe entero: se prefiere el resumen completo antes que el
            # texto cortado a la mitad de un articulo.
            resumen = norma.resumen.strip()
            if resumen and len(resumen) <= disponible:
                cuerpo = resumen
            else:
                continue

        piezas.append(encabezado + cuerpo)
        restante -= len(encabezado) + len(cuerpo)

    if not piezas:
        return ''

    return (
        'NORMATIVA GENERAL VIGENTE EN CHILE (aplica a todos los condominios; '
        'prevalece sobre el reglamento de la comunidad en lo que lo contradiga):\n\n'
        + '\n\n'.join(piezas)
    )


def estado_del_corpus():
    """Que hay cargado y que falta. Para el panel y el comando de carga."""
    todas = list(NormaTransversal.objects.all())
    cargadas = [n for n in todas if n.cargada]
    return {
        'declaradas': len(todas),
        'cargadas': len(cargadas),
        'faltantes': [n.identificador for n in todas if not n.cargada],
        'caracteres': sum(len(n.texto) for n in cargadas),
    }
