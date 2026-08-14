"""
Carga la base normativa transversal de Chile desde archivos oficiales.

Por que el texto no viene escrito en el codigo: lo que se cargue aqui termina
citado en notificaciones que se le envian a residentes. Escribir de memoria el
articulado de una ley real es la forma mas rapida de fundar una sancion en un
articulo que no existe. Por eso el sistema declara QUE normas necesita y de
donde se obtienen, pero el texto entra desde el archivo oficial.

Uso:
    python manage.py cargar_normativa --estado
    python manage.py cargar_normativa --declarar
    python manage.py cargar_normativa --desde normativa/
"""

import os

from django.core.management.base import BaseCommand

from reglamentos.normativa import NormaTransversal, TipoNormaTransversal, estado_del_corpus

# Las normas que el sistema espera tener. Cada una declara de donde se saca el
# texto oficial, para que quien la cargue no tenga que adivinar ni conformarse
# con una copia de dudosa procedencia.
CATALOGO_ESPERADO = [
    {
        'identificador': 'Ley 21.442',
        'tipo': TipoNormaTransversal.LEY,
        'titulo': 'Ley sobre Copropiedad Inmobiliaria',
        'fuente_url': 'https://www.bcn.cl/leychile/navegar?idNorma=1174851',
        'archivo': 'ley-21442.txt',
    },
    {
        'identificador': 'D.S. 7 (2023) MINVU',
        'tipo': TipoNormaTransversal.REGLAMENTO_LEY,
        'titulo': 'Reglamento de la Ley 21.442 sobre Copropiedad Inmobiliaria',
        'fuente_url': 'https://www.bcn.cl/leychile/navegar?idNorma=1191886',
        'archivo': 'ds-7-2023-minvu.txt',
    },
    {
        'identificador': 'Ley 19.496',
        'tipo': TipoNormaTransversal.OTRA,
        'titulo': 'Ley sobre proteccion de los derechos de los consumidores',
        'fuente_url': 'https://www.bcn.cl/leychile/navegar?idNorma=61438',
        'archivo': 'ley-19496.txt',
    },
    {
        'identificador': 'Ley 19.628',
        'tipo': TipoNormaTransversal.OTRA,
        'titulo': 'Ley sobre proteccion de la vida privada (datos personales)',
        'fuente_url': 'https://www.bcn.cl/leychile/navegar?idNorma=141599',
        'archivo': 'ley-19628.txt',
    },
]


class Command(BaseCommand):
    help = 'Declara y carga la base normativa transversal de Chile.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--estado', action='store_true',
            help='Muestra que normas estan declaradas, cuales tienen texto y cuales faltan.',
        )
        parser.add_argument(
            '--declarar', action='store_true',
            help='Crea las entradas del catalogo esperado, sin texto, para saber que falta.',
        )
        parser.add_argument(
            '--desde', type=str, default='',
            help='Carpeta con los archivos .txt del texto oficial de cada norma.',
        )

    def handle(self, *args, **opciones):
        if opciones['declarar']:
            self._declarar()
        if opciones['desde']:
            self._cargar(opciones['desde'])
        if opciones['estado'] or not (opciones['declarar'] or opciones['desde']):
            self._estado()

    def _declarar(self):
        creadas = 0
        for entrada in CATALOGO_ESPERADO:
            _, creada = NormaTransversal.objects.get_or_create(
                identificador=entrada['identificador'],
                defaults={
                    'tipo': entrada['tipo'],
                    'titulo': entrada['titulo'],
                    'fuente_url': entrada['fuente_url'],
                },
            )
            creadas += int(creada)
        self.stdout.write(self.style.SUCCESS(f'Declaradas {creadas} norma(s) nueva(s).'))

    def _cargar(self, carpeta):
        if not os.path.isdir(carpeta):
            self.stdout.write(self.style.ERROR(f'No existe la carpeta {carpeta}.'))
            return

        cargadas = 0
        for entrada in CATALOGO_ESPERADO:
            ruta = os.path.join(carpeta, entrada['archivo'])
            if not os.path.exists(ruta):
                continue
            with open(ruta, encoding='utf-8') as fh:
                texto = fh.read().strip()
            if not texto:
                self.stdout.write(f'  {entrada["identificador"]}: el archivo esta vacio, se omite.')
                continue

            NormaTransversal.objects.update_or_create(
                identificador=entrada['identificador'],
                defaults={
                    'tipo': entrada['tipo'],
                    'titulo': entrada['titulo'],
                    'fuente_url': entrada['fuente_url'],
                    'texto': texto,
                    'vigente': True,
                },
            )
            cargadas += 1
            self.stdout.write(f'  {entrada["identificador"]}: {len(texto):,} caracteres.')

        self.stdout.write(self.style.SUCCESS(f'Cargadas {cargadas} norma(s) desde {carpeta}.'))

    def _estado(self):
        estado = estado_del_corpus()
        self.stdout.write('')
        self.stdout.write('BASE NORMATIVA TRANSVERSAL')
        self.stdout.write(f'  declaradas : {estado["declaradas"]}')
        self.stdout.write(f'  con texto  : {estado["cargadas"]}  ({estado["caracteres"]:,} caracteres)')

        if estado['faltantes']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('  SIN TEXTO (la IA no las puede considerar):'))
            for identificador in estado['faltantes']:
                entrada = next(
                    (e for e in CATALOGO_ESPERADO if e['identificador'] == identificador), None,
                )
                fuente = f'  ->  {entrada["fuente_url"]}' if entrada else ''
                archivo = f'  (guardar como {entrada["archivo"]})' if entrada else ''
                self.stdout.write(f'    - {identificador}{fuente}{archivo}')

        if estado['cargadas'] == 0:
            self.stdout.write('')
            self.stdout.write(
                '  El sistema funciona igual sin corpus: la IA analiza solo con los\n'
                '  documentos de cada comunidad. Cargarlo mejora el encuadre, no lo habilita.'
            )
        self.stdout.write('')
