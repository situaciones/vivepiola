"""
Tests de los distintos cuerpos normativos que rigen una comunidad.

Una comunidad no se rige por un solo texto: al reglamento de copropiedad se
suman los instructivos de estacionamientos y espacios comunes, las normas de
seguridad, la normativa ambiental y los acuerdos de asamblea, que obligan
igual. Lo que se cuida aqui es que cada uno se lea como lo que es: pedirle a
la IA que cite un articulo en un acta que no los tiene seria inventarle base
legal a una sancion.
"""

import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio
from reglamentos.models import InfraccionCatalogo, Reglamento, TipoNorma
from reglamentos.tests import REGLAMENTO_TEXTO, pdf_con_texto
from reglamentos.utils import INSTRUCCIONES_POR_TIPO

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_normas_')

ACTA_TEXTO = """ACTA DE ASAMBLEA ORDINARIA
Con fecha 12 de marzo de 2026 se reune la asamblea de copropietarios.
Acuerdo 1: se aprueba el presupuesto anual presentado por la administracion.
Acuerdo 3: se prohibe el uso del quincho despues de las 23:00 horas, bajo
sancion de 1 UF para quien incumpla.
Acuerdo 4: se toma conocimiento del informe de la comision revisora."""


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class CuerposNormativosTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Normas')
        cls.admin = Usuario.objects.create_user(
            username='admin_normas', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )

    def _subir(self, texto=REGLAMENTO_TEXTO, **extra):
        self.client.force_authenticate(self.admin)
        return self.client.post(
            '/api/reglamentos/', {'archivo_pdf': pdf_con_texto(texto), **extra}, format='multipart',
        )

    def test_por_defecto_es_el_reglamento_de_copropiedad(self):
        """Lo mas comun sigue siendo lo mas facil: no hay que elegir nada."""
        respuesta = self._subir()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['tipo'], TipoNorma.REGLAMENTO_COPROPIEDAD)

    def test_se_cargan_los_otros_cuerpos_que_obligan_igual(self):
        for tipo in (
            TipoNorma.ESTACIONAMIENTOS, TipoNorma.ESPACIOS_COMUNES,
            TipoNorma.SEGURIDAD, TipoNorma.AMBIENTAL,
        ):
            with self.subTest(tipo=tipo):
                respuesta = self._subir(tipo=tipo, titulo=f'Instructivo {tipo}')
                self.assertEqual(respuesta.status_code, 201, respuesta.data)
                self.assertEqual(respuesta.data['tipo'], tipo)

    def test_un_acta_se_cita_por_su_fecha_y_no_por_un_articulo(self):
        """
        Un acuerdo de asamblea no tiene articulos. Lo que lo identifica al
        fundar una sancion es la fecha en que la asamblea lo adopto.
        """
        respuesta = self._subir(
            texto=ACTA_TEXTO, tipo=TipoNorma.ACTA_ASAMBLEA, fecha_documento='2026-03-12',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['referencia_citable'], 'Acuerdo de asamblea del 12-03-2026')

    def test_un_acta_sin_fecha_no_finge_tenerla(self):
        respuesta = self._subir(texto=ACTA_TEXTO, tipo=TipoNorma.ACTA_ASAMBLEA)
        self.assertEqual(respuesta.data['referencia_citable'], 'Acuerdo de asamblea del s/f')

    def test_el_titulo_es_como_lo_conoce_la_comunidad(self):
        respuesta = self._subir(
            tipo=TipoNorma.ESTACIONAMIENTOS, titulo='Instructivo de estacionamientos 2026',
        )
        self.assertEqual(respuesta.data['referencia_citable'], 'Instructivo de estacionamientos 2026')

    # -- La IA lee cada documento como lo que es -----------------------

    def test_a_la_ia_se_le_dice_que_clase_de_documento_esta_leyendo(self):
        respuesta = self._subir(texto=ACTA_TEXTO, tipo=TipoNorma.ACTA_ASAMBLEA)
        reglamento = Reglamento.objects.get(id=respuesta.data['id'])

        with patch('reglamentos.views.sugerir_infracciones_desde_texto', return_value=[]) as ia:
            self.client.post(f'/api/reglamentos/{reglamento.id}/generar-borradores-ia/')

        ia.assert_called_once()
        self.assertEqual(ia.call_args.args[1], TipoNorma.ACTA_ASAMBLEA)

    def test_la_instruccion_del_acta_prohibe_inventar_articulos(self):
        instruccion = INSTRUCCIONES_POR_TIPO['ACTA_ASAMBLEA']
        self.assertIn('NUNCA un numero de articulo que no exista', instruccion)
        self.assertIn('acuerdos', instruccion)

    def test_hay_instruccion_para_cada_tipo_declarado(self):
        """Un tipo sin instruccion se leeria como si fuera un reglamento."""
        for tipo in TipoNorma.values:
            self.assertIn(tipo, INSTRUCCIONES_POR_TIPO, f'falta la instruccion de {tipo}')

    def test_la_infraccion_recuerda_de_que_documento_salio(self):
        """Sin eso no se puede explicar en que norma se funda la sancion."""
        respuesta = self._subir(
            texto=ACTA_TEXTO, tipo=TipoNorma.ACTA_ASAMBLEA, fecha_documento='2026-03-12',
        )
        reglamento = Reglamento.objects.get(id=respuesta.data['id'])

        sugerencias = [{
            'codigo': 'QUINCHO-01',
            'descripcion': 'Uso del quincho despues de las 23:00',
            'articulo_referencia': 'Acuerdo 3 de la asamblea',
            'monto': 1, 'unidad_monto': 'UF', 'gravedad': 'LEVE',
            'texto_fuente': 'se prohibe el uso del quincho despues de las 23:00 horas',
        }]
        with patch('reglamentos.views.sugerir_infracciones_desde_texto', return_value=sugerencias):
            self.client.post(f'/api/reglamentos/{reglamento.id}/generar-borradores-ia/')

        infraccion = InfraccionCatalogo.objects.get(codigo='QUINCHO-01')
        self.assertEqual(infraccion.reglamento, reglamento)
        self.assertEqual(infraccion.articulo_referencia, 'Acuerdo 3 de la asamblea')
        self.assertEqual(infraccion.monto, Decimal('1.00'))
        self.assertEqual(
            infraccion.reglamento.referencia_citable, 'Acuerdo de asamblea del 12-03-2026',
        )

    def test_conviven_varios_cuerpos_normativos_en_la_misma_comunidad(self):
        self._subir(tipo=TipoNorma.REGLAMENTO_COPROPIEDAD)
        self._subir(tipo=TipoNorma.ESTACIONAMIENTOS, titulo='Estacionamientos')
        self._subir(texto=ACTA_TEXTO, tipo=TipoNorma.ACTA_ASAMBLEA, fecha_documento='2026-03-12')

        tipos = set(
            Reglamento.objects.filter(condominio=self.condominio).values_list('tipo', flat=True)
        )
        self.assertEqual(
            tipos,
            {TipoNorma.REGLAMENTO_COPROPIEDAD, TipoNorma.ESTACIONAMIENTOS, TipoNorma.ACTA_ASAMBLEA},
        )
