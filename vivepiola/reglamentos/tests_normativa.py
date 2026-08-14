"""
Tests del corpus normativo transversal.

Lo que se protege aqui es que el corpus pueda crecer sin encarecer ni degradar
las consultas: se busca el pasaje pertinente en vez de mandarle la ley entera
al modelo. Y que cada fragmento viaje con su cita, porque un fundamento que
dice "segun la ley" sin decir cual articulo no sostiene una sancion.

Ninguno sale a la red: los embeddings se sustituyen por un doble determinista.
"""

import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from django.core.management import call_command
from django.test import override_settings
from io import StringIO
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio
from reglamentos.fuentes import FuenteIlegible, extraer_texto, trocear
from reglamentos.models import Reglamento
from reglamentos.normativa import (
    FragmentoNormativo, FuenteNormativa, TipoFuente, buscar_normativa,
    contexto_normativo, estado_del_corpus, indexar_fuente,
)
from reglamentos.tests import REGLAMENTO_TEXTO, pdf_con_texto

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_corpus_')

LEY_DEMO = """LEY 21.442 SOBRE COPROPIEDAD INMOBILIARIA

Articulo 1. La presente ley regula el regimen de copropiedad inmobiliaria.

Articulo 12. Las mascotas deberan circular con correa por los espacios comunes
y sus duenos responderan de los danos que causen.

Articulo 30. Las multas que aplique el comite no podran exceder de cinco
unidades de fomento por cada infraccion cometida.

Articulo 45. El plazo para reclamar de una multa sera de cinco dias habiles
contados desde la notificacion."""


def _doble_embeddings(mapa=None):
    """
    Sustituye la API de embeddings por vectores deterministas.

    Cada texto se convierte segun que palabras clave contiene. No pretende
    imitar un modelo real: solo permite verificar que se recupera el fragmento
    correcto y no otro.
    """
    claves = ['mascota', 'correa', 'multa', 'unidad', 'plazo', 'reclamar', 'copropiedad']

    def _vector(texto):
        bajo = texto.lower()
        v = np.array([1.0 if c in bajo else 0.0 for c in claves], dtype=np.float32)
        if not v.any():
            v[0] = 0.01
        return v / np.linalg.norm(v)

    def _embed_content(model=None, contents=None, config=None):
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=_vector(t).tolist()) for t in contents],
        )

    return SimpleNamespace(models=SimpleNamespace(embed_content=_embed_content))


@override_settings(GEMINI_API_KEY='clave-de-prueba', NORMATIVA_DIMENSIONES=7)
class CorpusNormativoTestCase(APITestCase):
    def _fuente(self, identificador='Ley 21.442', tipo=TipoFuente.LEY, texto=LEY_DEMO, vigente=True):
        fuente = FuenteNormativa.objects.create(
            identificador=identificador, tipo=tipo, titulo=f'Titulo de {identificador}',
            vigente=vigente, url_fuente='https://www.bcn.cl/ejemplo',
        )
        with patch('google.genai.Client', return_value=_doble_embeddings()):
            indexar_fuente(fuente, texto=texto)
        return fuente

    # -- Troceado por articulo ------------------------------------------

    def test_se_trocea_por_articulo_y_no_por_largo_fijo(self):
        """El articulo es la unidad que se cita; partirlo lo vuelve inutilizable."""
        piezas = trocear(LEY_DEMO)
        referencias = [r for r, _ in piezas]

        self.assertIn('Art. 12', referencias)
        self.assertIn('Art. 30', referencias)
        self.assertIn('Art. 45', referencias)

    def test_cada_fragmento_queda_completo(self):
        piezas = dict(trocear(LEY_DEMO))
        self.assertIn('correa', piezas['Art. 12'])
        # El salto de linea del texto legal parte la frase: se normaliza.
        self.assertIn('cinco unidades de fomento', ' '.join(piezas['Art. 30'].split()))

    def test_un_texto_sin_articulado_igual_se_trocea(self):
        """Una circular o un folleto no numeran articulos y tambien deben entrar."""
        piezas = trocear('Instrucciones generales. ' * 60)
        self.assertTrue(piezas)
        self.assertTrue(all(r.startswith('Seccion') for r, _ in piezas))

    def test_un_articulo_larguisimo_se_parte_pero_conserva_su_referencia(self):
        largo = 'Articulo 7. ' + ('Contenido extenso. ' * 400)
        piezas = trocear(largo)
        self.assertGreater(len(piezas), 1)
        self.assertTrue(all(r.startswith('Art. 7') for r, _ in piezas))

    # -- Indexado --------------------------------------------------------

    def test_indexar_deja_los_fragmentos_buscables(self):
        fuente = self._fuente()

        self.assertTrue(fuente.indexada)
        self.assertGreaterEqual(fuente.total_fragmentos, 4)
        self.assertEqual(
            fuente.fragmentos.filter(vector__isnull=True).count(), 0,
            'un fragmento sin vector no se puede encontrar',
        )

    def test_reindexar_reemplaza_y_no_acumula(self):
        """Una norma actualizada no puede convivir con su version vieja."""
        fuente = self._fuente()
        antes = fuente.total_fragmentos

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            indexar_fuente(fuente, texto=LEY_DEMO)

        self.assertEqual(fuente.total_fragmentos, antes)

    def test_sin_clave_se_indexa_igual_pero_no_es_buscable(self):
        fuente = FuenteNormativa.objects.create(
            identificador='Ley sin clave', tipo=TipoFuente.LEY, titulo='X',
        )
        with override_settings(GEMINI_API_KEY=''):
            indexar_fuente(fuente, texto=LEY_DEMO)

        self.assertGreater(fuente.total_fragmentos, 0)
        self.assertEqual(fuente.fragmentos.filter(vector__isnull=False).count(), 0)
        self.assertEqual(buscar_normativa('mascota'), [])

    # -- Busqueda: lo preciso en la fuente precisa -----------------------

    def test_se_recupera_el_articulo_pertinente_y_no_la_ley_entera(self):
        """El corazon del diseño: buscar, no memorizar."""
        self._fuente()

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            resultados = buscar_normativa('el perro andaba suelto sin correa')

        self.assertTrue(resultados)
        self.assertEqual(resultados[0]['cita'], 'Ley 21.442, Art. 12')
        self.assertIn('correa', resultados[0]['texto'])

    def test_una_consulta_sobre_plazos_trae_el_articulo_de_plazos(self):
        self._fuente()

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            resultados = buscar_normativa('cuanto plazo hay para reclamar')

        self.assertEqual(resultados[0]['cita'], 'Ley 21.442, Art. 45')

    def test_cada_fragmento_viaja_con_su_cita(self):
        """Un fundamento que dice "segun la ley" no sostiene una sancion."""
        self._fuente()

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            contexto = contexto_normativo('mascota sin correa')

        self.assertIn('[Ley 21.442, Art. 12]', contexto)
        self.assertIn('Cita SIEMPRE la referencia', contexto)

    def test_no_se_traen_fragmentos_poco_pertinentes(self):
        """Traer ruido es peor que no traer nada: le da al modelo de donde
        agarrarse para fundamentar cualquier cosa."""
        self._fuente()

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            resultados = buscar_normativa('un tema totalmente ajeno', minimo_pertinencia=0.9)

        self.assertEqual(resultados, [])

    def test_se_respeta_el_tope_de_fragmentos(self):
        self._fuente()

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            resultados = buscar_normativa('multa unidad plazo mascota', k=2)

        self.assertLessEqual(len(resultados), 2)

    def test_una_fuente_derogada_deja_de_consultarse(self):
        fuente = self._fuente()
        fuente.vigente = False
        fuente.save(update_fields=['vigente'])

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            self.assertEqual(buscar_normativa('mascota sin correa'), [])

    def test_a_igual_pertinencia_manda_la_jerarquia(self):
        """Entre una ley y un folleto que dicen lo mismo, se cita la ley."""
        self._fuente('Folleto MINVU', TipoFuente.FOLLETO, texto=LEY_DEMO)
        self._fuente('Ley 21.442', TipoFuente.LEY, texto=LEY_DEMO)

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            resultados = buscar_normativa('mascota con correa')

        self.assertTrue(resultados[0]['cita'].startswith('Ley 21.442'))

    def test_si_el_servicio_de_embeddings_se_cae_no_se_interrumpe_nada(self):
        self._fuente()
        with patch('google.genai.Client', side_effect=RuntimeError('503')):
            self.assertEqual(buscar_normativa('mascota'), [])

    def test_sin_corpus_no_hay_contexto_y_el_sistema_sigue(self):
        self.assertEqual(contexto_normativo('cualquier cosa'), '')

    # -- Estado y comando -----------------------------------------------

    def test_el_estado_distingue_cargado_de_indexado(self):
        self._fuente()
        e = estado_del_corpus()

        self.assertEqual(e['fuentes'], 1)
        self.assertEqual(e['indexadas'], 1)
        self.assertEqual(e['sin_indexar'], [])
        self.assertEqual(e['fragmentos'], e['fragmentos_con_vector'])

    def test_el_comando_avisa_cuando_faltan_vectores(self):
        fuente = FuenteNormativa.objects.create(
            identificador='Ley 21.442', tipo=TipoFuente.LEY, titulo='X',
        )
        with override_settings(GEMINI_API_KEY=''):
            indexar_fuente(fuente, texto=LEY_DEMO)

        salida = StringIO()
        call_command('cargar_normativa', '--estado', stdout=salida)
        self.assertIn('falta GEMINI_API_KEY', salida.getvalue())

    def test_se_carga_una_carpeta_completa(self):
        import os

        carpeta = tempfile.mkdtemp(prefix='corpus_')
        with open(os.path.join(carpeta, 'Ley 21.442.txt'), 'w', encoding='utf-8') as fh:
            fh.write(LEY_DEMO)

        with patch('google.genai.Client', return_value=_doble_embeddings()):
            call_command('cargar_normativa', '--desde', carpeta, stdout=StringIO())

        fuente = FuenteNormativa.objects.get(identificador='Ley 21.442')
        self.assertTrue(fuente.indexada, 'el nombre del archivo es como se cita')


class ExtraccionDeFuentesTestCase(APITestCase):
    def test_se_lee_un_pdf(self):
        texto = extraer_texto(archivo=pdf_con_texto(REGLAMENTO_TEXTO), nombre='norma.pdf')
        self.assertIn('ruidos molestos', texto)

    def test_un_formato_desconocido_se_rechaza_con_el_motivo(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        with self.assertRaises(FuenteIlegible) as ctx:
            extraer_texto(archivo=SimpleUploadedFile('x.xyz', b'contenido'), nombre='x.xyz')
        self.assertIn('PDF, Word', str(ctx.exception))

    def test_un_escaneo_sin_texto_se_rechaza_diciendo_que_hacer(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        with self.assertRaises(FuenteIlegible) as ctx:
            extraer_texto(archivo=SimpleUploadedFile('corto.txt', b'poco'), nombre='corto.txt')
        self.assertIn('OCR', str(ctx.exception))


@override_settings(MEDIA_ROOT=MEDIA_TEMP, GEMINI_API_KEY='clave', NORMATIVA_DIMENSIONES=7)
class NormativaEnElAnalisisTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Corpus')
        cls.admin = Usuario.objects.create_user(
            username='admin_corpus', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )

    def test_al_leer_un_reglamento_se_le_manda_solo_lo_pertinente(self):
        fuente = FuenteNormativa.objects.create(
            identificador='Ley 21.442', tipo=TipoFuente.LEY, titulo='Copropiedad',
        )
        with patch('google.genai.Client', return_value=_doble_embeddings()):
            indexar_fuente(fuente, texto=LEY_DEMO)

        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(
            '/api/reglamentos/', {'archivo_pdf': pdf_con_texto(REGLAMENTO_TEXTO)}, format='multipart',
        )
        reglamento = Reglamento.objects.get(id=respuesta.data['id'])

        capturado = {}

        def _crear(**kwargs):
            capturado.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(type='text', text='[]')])

        with override_settings(ANTHROPIC_API_KEY='sk-ant-x'):
            with patch('google.genai.Client', return_value=_doble_embeddings()):
                with patch('anthropic.Anthropic', return_value=SimpleNamespace(
                    messages=SimpleNamespace(create=_crear),
                )):
                    self.client.post(f'/api/reglamentos/{reglamento.id}/generar-borradores-ia/')

        sistema = capturado['system']
        self.assertIn('NORMATIVA GENERAL DE CHILE PERTINENTE', sistema)
        self.assertIn('[Ley 21.442,', sistema)
        # No se manda la ley completa: solo los pasajes recuperados.
        self.assertLess(len(sistema), 12000)
