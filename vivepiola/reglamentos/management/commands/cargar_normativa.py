"""
Carga e indexa fuentes normativas en el corpus transversal.

Las fuentes las decide un abogado con experiencia en copropiedad: la ley, su
reglamento, circulares del MINVU o de la SEC, folletos, dictamenes. Se admite
PDF, Word o una URL.

Uso:
    python manage.py cargar_normativa --estado
    python manage.py cargar_normativa --desde normativa/
    python manage.py cargar_normativa --url https://... --id "Circular MINVU 15/2026" \\
        --titulo "Instrucciones sobre..." --tipo CIRCULAR_MINVU
    python manage.py cargar_normativa --reindexar

Sobre --desde: cada archivo se identifica por su nombre. Para que quede bien
citado conviene nombrarlos como se citan, por ejemplo "Ley 21.442.pdf".
"""

import os

from django.core.management.base import BaseCommand

from reglamentos.fuentes import FuenteIlegible, extraer_texto
from reglamentos.normativa import FuenteNormativa, TipoFuente, estado_del_corpus, indexar_fuente

EXTENSIONES = ('.pdf', '.docx', '.doc', '.txt', '.md')


class Command(BaseCommand):
    help = 'Carga e indexa fuentes normativas (PDF, Word o URL) en el corpus transversal.'

    def add_arguments(self, parser):
        parser.add_argument('--estado', action='store_true', help='Que hay cargado e indexado.')
        parser.add_argument('--desde', type=str, default='', help='Carpeta con los documentos.')
        parser.add_argument('--url', type=str, default='', help='URL de una fuente.')
        parser.add_argument('--id', type=str, default='', help='Como se cita. Ej: "Ley 21.442".')
        parser.add_argument('--titulo', type=str, default='', help='Titulo de la fuente.')
        parser.add_argument('--tipo', type=str, default=TipoFuente.OTRA, help='Ver TipoFuente.')
        parser.add_argument('--nota', type=str, default='', help='Por que se carga o actualiza.')
        parser.add_argument(
            '--reindexar', action='store_true',
            help='Vuelve a trocear e indexar todo lo ya cargado (tras cambiar el modelo).',
        )

    def handle(self, *args, **op):
        if op['desde']:
            self._desde_carpeta(op['desde'], op['tipo'], op['nota'])
        if op['url']:
            self._desde_url(op)
        if op['reindexar']:
            self._reindexar()
        if op['estado'] or not (op['desde'] or op['url'] or op['reindexar']):
            self._estado()

    # -- carga ---------------------------------------------------------

    def _guardar(self, identificador, titulo, tipo, texto, nota='', url=''):
        fuente, _ = FuenteNormativa.objects.update_or_create(
            identificador=identificador,
            defaults={
                'titulo': titulo or identificador,
                'tipo': tipo if tipo in TipoFuente.values else TipoFuente.OTRA,
                'url_fuente': url,
                'nota_version': nota,
                'vigente': True,
            },
        )
        cuantos = indexar_fuente(fuente, texto=texto)
        aviso = '' if fuente.fragmentos.filter(vector__isnull=False).exists() else \
            '  (sin vectores: falta GEMINI_API_KEY, se indexara al reindexar)'
        self.stdout.write(f'  {identificador}: {cuantos} fragmento(s){aviso}')
        return cuantos

    def _desde_carpeta(self, carpeta, tipo, nota):
        if not os.path.isdir(carpeta):
            self.stdout.write(self.style.ERROR(f'No existe la carpeta {carpeta}.'))
            return

        cargadas = 0
        for nombre in sorted(os.listdir(carpeta)):
            if not nombre.lower().endswith(EXTENSIONES):
                continue
            ruta = os.path.join(carpeta, nombre)
            identificador = os.path.splitext(nombre)[0].strip()
            try:
                with open(ruta, 'rb') as fh:
                    texto = extraer_texto(archivo=fh, nombre=nombre)
            except FuenteIlegible as exc:
                self.stdout.write(self.style.WARNING(f'  {nombre}: {exc}'))
                continue
            self._guardar(identificador, identificador, tipo, texto, nota=nota)
            cargadas += 1

        self.stdout.write(self.style.SUCCESS(f'Procesadas {cargadas} fuente(s) de {carpeta}.'))

    def _desde_url(self, op):
        identificador = op['id'] or op['url']
        try:
            texto = extraer_texto(url=op['url'])
        except FuenteIlegible as exc:
            self.stdout.write(self.style.ERROR(f'  {op["url"]}: {exc}'))
            return
        self._guardar(
            identificador, op['titulo'], op['tipo'], texto, nota=op['nota'], url=op['url'],
        )
        self.stdout.write(self.style.SUCCESS('Fuente cargada desde la URL.'))

    def _reindexar(self):
        total = 0
        for fuente in FuenteNormativa.objects.exclude(texto=''):
            cuantos = indexar_fuente(fuente)
            total += cuantos
            self.stdout.write(f'  {fuente.identificador}: {cuantos} fragmento(s)')
        self.stdout.write(self.style.SUCCESS(f'Reindexados {total} fragmento(s).'))

    # -- estado --------------------------------------------------------

    def _estado(self):
        e = estado_del_corpus()
        self.stdout.write('')
        self.stdout.write('CORPUS NORMATIVO TRANSVERSAL')
        self.stdout.write(f'  fuentes cargadas : {e["fuentes"]}  ({e["vigentes"]} vigentes)')
        self.stdout.write(f'  indexadas        : {e["indexadas"]}')
        self.stdout.write(
            f'  fragmentos       : {e["fragmentos"]}  '
            f'({e["fragmentos_con_vector"]} buscables)'
        )

        if e['sin_indexar']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('  SIN INDEXAR (no se pueden consultar):'))
            for identificador in e['sin_indexar']:
                self.stdout.write(f'    - {identificador}')

        if e['fragmentos'] and not e['fragmentos_con_vector']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '  Hay fragmentos sin vector: falta GEMINI_API_KEY.\n'
                '  Configurala y corre: python manage.py cargar_normativa --reindexar'
            ))

        if not e['fuentes']:
            self.stdout.write('')
            self.stdout.write(
                '  El sistema funciona igual sin corpus: la IA analiza solo con los\n'
                '  documentos de cada comunidad. Cargarlo mejora el encuadre.'
            )
        self.stdout.write('')
