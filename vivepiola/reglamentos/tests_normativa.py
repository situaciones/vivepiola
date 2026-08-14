"""
Tests de la base normativa transversal.

Es la unica parte del sistema cuyo contenido no lo produce el software: son
textos legales oficiales que alguien carga. Por eso lo que se prueba aqui es
sobre todo como se comporta cuando NO estan, y que no se pueda colar texto sin
procedencia como si fuera ley.
"""

import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from io import StringIO
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio
from reglamentos.models import Reglamento, TipoNorma
from reglamentos.normativa import (
    NormaTransversal, TipoNormaTransversal, contexto_normativo, estado_del_corpus,
)
from reglamentos.tests import REGLAMENTO_TEXTO, pdf_con_texto

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_normativa_')


class CorpusNormativoTestCase(APITestCase):
    def _norma(self, identificador, tipo, texto='', resumen='', vigente=True):
        return NormaTransversal.objects.create(
            identificador=identificador, tipo=tipo, titulo=f'Titulo de {identificador}',
            texto=texto, resumen=resumen, vigente=vigente,
            fuente_url='https://www.bcn.cl/leychile/ejemplo',
        )

    # -- Sin corpus el sistema no se cae --------------------------------

    def test_sin_normativa_cargada_el_contexto_va_vacio(self):
        """El corpus mejora el encuadre; no habilita el sistema."""
        self.assertEqual(contexto_normativo(), '')

    def test_una_norma_declarada_sin_texto_no_cuenta_como_cargada(self):
        """Declararla sirve para saber que falta, no para simular que esta."""
        norma = self._norma('Ley 21.442', TipoNormaTransversal.LEY)

        self.assertFalse(norma.cargada)
        self.assertEqual(contexto_normativo(), '')
        self.assertIn('Ley 21.442', estado_del_corpus()['faltantes'])

    def test_una_norma_no_vigente_no_entra_al_contexto(self):
        self._norma('Ley Derogada', TipoNormaTransversal.LEY, texto='Texto viejo', vigente=False)
        self.assertEqual(contexto_normativo(), '')

    # -- Como se arma el contexto ---------------------------------------

    def test_el_contexto_trae_el_texto_con_su_identificador(self):
        self._norma('Ley 21.442', TipoNormaTransversal.LEY, texto='Articulo 1. Contenido de prueba.')

        contexto = contexto_normativo()
        self.assertIn('Ley 21.442', contexto)
        self.assertIn('Articulo 1. Contenido de prueba.', contexto)
        self.assertIn('prevalece sobre el reglamento de la comunidad', contexto)

    def test_manda_primero_lo_que_manda_mas(self):
        """Si hay que recortar, una circular no puede desplazar a la ley."""
        self._norma('Circular 99', TipoNormaTransversal.CIRCULAR_MINVU, texto='C' * 500)
        self._norma('Ley 21.442', TipoNormaTransversal.LEY, texto='L' * 500)
        self._norma('D.S. 7', TipoNormaTransversal.REGLAMENTO_LEY, texto='R' * 500)

        contexto = contexto_normativo()
        posiciones = [contexto.index(x) for x in ('Ley 21.442', 'D.S. 7', 'Circular 99')]
        self.assertEqual(posiciones, sorted(posiciones), 'el orden debe seguir la jerarquia')

    def test_cuando_no_cabe_el_texto_se_prefiere_el_resumen_entero(self):
        """Media ley cortada a la mitad de un articulo es peor que una sintesis."""
        self._norma(
            'Ley 21.442', TipoNormaTransversal.LEY,
            texto='X' * 5000, resumen='Sintesis operativa de la ley.',
        )

        contexto = contexto_normativo(presupuesto_caracteres=800)
        self.assertIn('Sintesis operativa de la ley.', contexto)
        self.assertNotIn('X' * 100, contexto)

    def test_lo_que_no_cabe_ni_resumido_se_omite_completo(self):
        self._norma('Ley 21.442', TipoNormaTransversal.LEY, texto='A' * 400)
        self._norma('Circular 99', TipoNormaTransversal.CIRCULAR_MINVU, texto='B' * 5000)

        contexto = contexto_normativo(presupuesto_caracteres=700)
        self.assertIn('Ley 21.442', contexto)
        self.assertNotIn('Circular 99', contexto)

    def test_el_presupuesto_se_respeta(self):
        for i in range(5):
            self._norma(f'Norma {i}', TipoNormaTransversal.OTRA, texto='Z' * 2000)

        contexto = contexto_normativo(presupuesto_caracteres=3000)
        self.assertLessEqual(len(contexto), 3500, 'el encabezado suma, pero no puede desbordarse')

    # -- El comando de carga --------------------------------------------

    def test_declarar_deja_ver_que_falta_sin_inventar_texto(self):
        salida = StringIO()
        call_command('cargar_normativa', '--declarar', stdout=salida)

        estado = estado_del_corpus()
        self.assertGreater(estado['declaradas'], 0)
        self.assertEqual(estado['cargadas'], 0, 'declarar no debe inventar contenido')
        self.assertIn('Ley 21.442', estado['faltantes'])

    def test_el_estado_dice_de_donde_bajar_lo_que_falta(self):
        call_command('cargar_normativa', '--declarar', stdout=StringIO())
        salida = StringIO()
        call_command('cargar_normativa', '--estado', stdout=salida)

        texto = salida.getvalue()
        self.assertIn('bcn.cl', texto, 'sin la fuente nadie puede verificar que sea lo vigente')
        self.assertIn('ley-21442.txt', texto)

    def test_cargar_desde_archivos_llena_el_corpus(self):
        import os

        call_command('cargar_normativa', '--declarar', stdout=StringIO())
        carpeta = tempfile.mkdtemp(prefix='normativa_')
        with open(os.path.join(carpeta, 'ley-21442.txt'), 'w', encoding='utf-8') as fh:
            fh.write('Articulo 1. Texto oficial cargado desde archivo.')

        call_command('cargar_normativa', '--desde', carpeta, stdout=StringIO())

        norma = NormaTransversal.objects.get(identificador='Ley 21.442')
        self.assertTrue(norma.cargada)
        self.assertIn('Texto oficial cargado desde archivo', contexto_normativo())

    def test_un_archivo_vacio_no_marca_la_norma_como_cargada(self):
        import os

        call_command('cargar_normativa', '--declarar', stdout=StringIO())
        carpeta = tempfile.mkdtemp(prefix='normativa_vacia_')
        with open(os.path.join(carpeta, 'ley-21442.txt'), 'w', encoding='utf-8') as fh:
            fh.write('   \n  ')

        call_command('cargar_normativa', '--desde', carpeta, stdout=StringIO())

        self.assertIn('Ley 21.442', estado_del_corpus()['faltantes'])

    def test_toda_norma_declarada_dice_de_donde_sale_su_texto(self):
        """Una norma sin procedencia no sirve para fundar una sancion."""
        from reglamentos.management.commands.cargar_normativa import CATALOGO_ESPERADO

        for entrada in CATALOGO_ESPERADO:
            self.assertTrue(entrada['fuente_url'].startswith('https://'), entrada['identificador'])
            self.assertTrue(entrada['archivo'].endswith('.txt'), entrada['identificador'])


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class NormativaEnElAnalisisTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Marco')
        cls.admin = Usuario.objects.create_user(
            username='admin_marco', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )

    def _reglamento(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(
            '/api/reglamentos/', {'archivo_pdf': pdf_con_texto(REGLAMENTO_TEXTO)}, format='multipart',
        )
        return Reglamento.objects.get(id=respuesta.data['id'])

    def test_al_leer_un_reglamento_la_ley_va_en_el_contexto(self):
        NormaTransversal.objects.create(
            identificador='Ley 21.442', tipo=TipoNormaTransversal.LEY,
            titulo='Ley sobre Copropiedad Inmobiliaria',
            texto='Articulo 30. Las multas no podran exceder el limite que indica esta ley.',
        )
        reglamento = self._reglamento()

        capturado = {}

        def _falso(**kwargs):
            capturado.update(kwargs)
            from types import SimpleNamespace
            return SimpleNamespace(content=[SimpleNamespace(type='text', text='[]')])

        from types import SimpleNamespace
        cliente = SimpleNamespace(messages=SimpleNamespace(create=_falso))
        with override_settings(ANTHROPIC_API_KEY='sk-ant-x'):
            with patch('anthropic.Anthropic', return_value=cliente):
                self.client.post(f'/api/reglamentos/{reglamento.id}/generar-borradores-ia/')

        sistema = capturado['system']
        self.assertIn('Ley 21.442', sistema)
        self.assertIn('Articulo 30', sistema)
        self.assertIn('contradice la normativa general', sistema)

    def test_sin_corpus_el_prompt_no_menciona_normativa_general(self):
        reglamento = self._reglamento()
        capturado = {}

        def _falso(**kwargs):
            capturado.update(kwargs)
            from types import SimpleNamespace
            return SimpleNamespace(content=[SimpleNamespace(type='text', text='[]')])

        from types import SimpleNamespace
        cliente = SimpleNamespace(messages=SimpleNamespace(create=_falso))
        with override_settings(ANTHROPIC_API_KEY='sk-ant-x'):
            with patch('anthropic.Anthropic', return_value=cliente):
                respuesta = self.client.post(f'/api/reglamentos/{reglamento.id}/generar-borradores-ia/')

        self.assertEqual(respuesta.status_code, 201, 'sin corpus la extraccion funciona igual')
        self.assertNotIn('NORMATIVA GENERAL VIGENTE', capturado['system'])
