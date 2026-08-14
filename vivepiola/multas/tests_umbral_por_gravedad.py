"""
Tests del umbral de confianza escalonado por gravedad.

La confianza y la gravedad responden preguntas distintas: una dice "entendi
bien que paso" y la otra "cuanto pesa equivocarse". Combinarlas significa que
mientras mas caro sea el error, mas certeza se exige antes de notificar sin
que una persona haya mirado el caso.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa
from multas.services import confianza_minima_para, puede_cursarse_sola
from reglamentos.models import EstadoInfraccion, Gravedad, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_umbral_')


def _respuesta_ia(codigo, confianza):
    texto = f'{{"codigo": "{codigo}", "confianza": {confianza}, "fundamento": "Encuadre."}}'
    return SimpleNamespace(content=[SimpleNamespace(type='text', text=texto)])


@override_settings(MEDIA_ROOT=MEDIA_TEMP, ANTHROPIC_API_KEY='sk-ant-de-prueba')
class UmbralPorGravedadTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Cupo 0 para que la cortesia no tape lo que se mide aqui.
        cls.condominio = Condominio.objects.create(
            nombre='Condominio Umbral', cortesias_antes_de_multar=0,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 808')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Ulises Umbral', cedula_identidad='8.080.808-0',
            domicilio='Depto 808', correo_electronico='ulises@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_um', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.leve = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='LEVE-01', descripcion='Basura fuera de horario',
            articulo_referencia='Art. 10', monto=Decimal('1.00'),
            gravedad=Gravedad.LEVE, estado=EstadoInfraccion.ACTIVA,
        )
        cls.grave = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='GRAVE-01', descripcion='Danos en espacios comunes',
            articulo_referencia='Art. 20', monto=Decimal('8.00'),
            gravedad=Gravedad.GRAVE, estado=EstadoInfraccion.ACTIVA,
        )
        cls.gravisima = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='GRAVISIMA-01', descripcion='Riesgo electrico',
            articulo_referencia='Art. 30', monto=Decimal('30.00'),
            gravedad=Gravedad.GRAVISIMA, estado=EstadoInfraccion.ACTIVA,
        )

    def _denunciar(self, codigo, confianza, dias_atras=0):
        mail.outbox = []
        self.client.force_authenticate(self.conserje)
        cuando = timezone.now() - timedelta(days=dias_atras, hours=1)
        cliente = SimpleNamespace(messages=SimpleNamespace(
            create=lambda **kw: _respuesta_ia(codigo, confianza),
        ))
        with patch('anthropic.Anthropic', return_value=cliente):
            respuesta = self.client.post('/api/tickets/', {
                'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
                'descripcion': f'Hecho {codigo} {dias_atras}', 'fecha_hecho': cuando.isoformat(),
            }, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Multa.objects.get(ticket_id=respuesta.data['id'])

    # -- El umbral sube con lo que pesa la falta ------------------------

    def test_cada_gravedad_tiene_su_propia_exigencia(self):
        self.assertEqual(confianza_minima_para(self.leve), 65)
        self.assertEqual(confianza_minima_para(self.grave), 80)
        self.assertEqual(confianza_minima_para(self.gravisima), 90)

    def test_una_confianza_que_alcanza_para_la_leve_no_alcanza_para_la_grave(self):
        """El mismo 70 de confianza decide distinto segun lo que este en juego."""
        leve = self._denunciar('LEVE-01', confianza=70, dias_atras=20)
        self.assertEqual(leve.estado, EstadoMulta.NOTIFICADA)

        grave = self._denunciar('GRAVE-01', confianza=70, dias_atras=10)
        self.assertEqual(grave.estado, EstadoMulta.EN_REVISION)
        self.assertIn('exige al menos 80', grave.historial.first().comentario)

    def test_una_confianza_que_alcanza_para_la_grave_no_alcanza_para_la_gravisima(self):
        grave = self._denunciar('GRAVE-01', confianza=85, dias_atras=20)
        self.assertEqual(grave.estado, EstadoMulta.NOTIFICADA)

        gravisima = self._denunciar('GRAVISIMA-01', confianza=85, dias_atras=10)
        self.assertEqual(gravisima.estado, EstadoMulta.EN_REVISION)
        self.assertIn('exige al menos 90', gravisima.historial.first().comentario)

    def test_con_certeza_alta_hasta_la_gravisima_se_cursa_sola(self):
        multa = self._denunciar('GRAVISIMA-01', confianza=95)
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertEqual(multa.monto, Decimal('30.00'), 'una gravisima no recibe cortesia')

    def test_el_motivo_explica_la_gravedad_y_no_solo_el_numero(self):
        """Quien lea el expediente tiene que entender por que se detuvo."""
        multa = self._denunciar('GRAVISIMA-01', confianza=70)
        comentario = multa.historial.first().comentario

        self.assertIn('gravisima', comentario)
        self.assertIn('70 de confianza', comentario)
        self.assertIn('exige al menos 90', comentario)

    def test_una_gravedad_puede_exigir_siempre_revision_humana(self):
        """Un umbral sobre 100 es inalcanzable: equivale a nunca automatico."""
        with override_settings(CURSE_CONFIANZA_MINIMA={'LEVE': 65, 'GRAVE': 80, 'GRAVISIMA': 101}):
            multa = self._denunciar('GRAVISIMA-01', confianza=100)
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)

    # -- El respaldo por terminos nunca sanciona solo -------------------

    @override_settings(ANTHROPIC_API_KEY='')
    def test_el_respaldo_por_terminos_no_cursa_aunque_baje_el_umbral(self):
        """
        Antes esta garantia dependia de que el respaldo topara en 60 y el
        umbral fuera 70: una coincidencia numerica que se rompia en silencio
        si alguien bajaba el umbral. Ahora se bloquea por origen.
        """
        with override_settings(CURSE_CONFIANZA_MINIMA={'LEVE': 1, 'GRAVE': 1, 'GRAVISIMA': 1}):
            self.client.force_authenticate(self.conserje)
            respuesta = self.client.post('/api/tickets/', {
                'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
                'descripcion': 'Basura fuera de horario en el pasillo',
                'fecha_hecho': timezone.now().isoformat(),
            }, format='json')
            multa = Multa.objects.get(ticket_id=respuesta.data['id'])

        self.assertEqual(multa.propuesta_origen, 'COINCIDENCIA')
        self.assertEqual(
            multa.estado, EstadoMulta.EN_REVISION,
            'el respaldo existe para no caerse sin IA, no para sancionar por calzar palabras',
        )
        self.assertIn('no sanciona por si solo', multa.historial.first().comentario)

    def test_sin_propuesta_de_ninguna_clase_tampoco_se_cursa(self):
        multa = self._denunciar('INEXISTENTE-99', confianza=99)
        procede, motivo = puede_cursarse_sola(multa, 99)

        self.assertFalse(procede)
        self.assertIn('no calza con ninguna infraccion', motivo)
