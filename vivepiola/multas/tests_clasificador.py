"""
Tests del agente clasificador de denuncias.

Ninguno sale a la red: la llamada al modelo se sustituye por un doble. Lo que
se verifica no es cuan listo es el modelo, sino las tres garantias del diseño:
propone sin decidir, no puede inventar infracciones, y su caida no interrumpe
el flujo legal.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_clasif_')


def respuesta_modelo(texto):
    """Doble de la respuesta de la API: solo necesita .content[].text."""
    return SimpleNamespace(content=[SimpleNamespace(type='text', text=texto)])


class ClienteFalso:
    """Sustituye a anthropic.Anthropic: devuelve un texto fijo o lanza."""

    def __init__(self, texto=None, error=None):
        self._texto = texto
        self._error = error
        self.mensajes_enviados = []
        self.messages = self

    def create(self, **kwargs):
        self.mensajes_enviados.append(kwargs)
        if self._error:
            raise self._error
        return respuesta_modelo(self._texto)


@override_settings(MEDIA_ROOT=MEDIA_TEMP, ANTHROPIC_API_KEY='sk-ant-de-prueba')
class ClasificadorTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Clasificador')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 707')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Luis Denunciado', cedula_identidad='55.555.555-5',
            domicilio='Depto 707', correo_electronico='luis@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje3', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite3', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.mascotas = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='MASCOTA-01',
            descripcion='Mascota sin correa en espacios comunes',
            articulo_referencia='Art. 4', monto=Decimal('2.00'), estado=EstadoInfraccion.ACTIVA,
        )
        cls.ruido = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos nocturnos',
            articulo_referencia='Art. 15', monto=Decimal('3.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _denunciar(self, descripcion):
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id,
            'persona_reportada': self.persona.id,
            'descripcion': descripcion,
            'fecha_hecho': (timezone.now() - timedelta(hours=1)).isoformat(),
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Multa.objects.get(ticket_id=respuesta.data['id'])

    def _con_cliente(self, cliente):
        return patch('anthropic.Anthropic', return_value=cliente)

    # -- Comprension semantica (lo que el respaldo no logra) -----------

    def test_ia_entiende_el_hecho_aunque_no_repita_las_palabras(self):
        """'el perro andaba suelto' no comparte terminos con 'Mascota sin correa'."""
        cliente = ClienteFalso(
            '{"codigo": "MASCOTA-01", "confianza": 90, '
            '"fundamento": "El reporte describe un animal sin control en pasillos, '
            'supuesto del Art. 4 sobre mascotas en espacios comunes."}'
        )
        with self._con_cliente(cliente):
            multa = self._denunciar('El perro del 707 andaba suelto por el pasillo')

        self.assertEqual(multa.infraccion_id, self.mascotas.id)
        self.assertEqual(multa.propuesta_origen, 'IA')
        self.assertEqual(multa.propuesta_confianza, 90)
        self.assertIn('Art. 4', multa.propuesta_fundamento)
        self.assertEqual(multa.monto, Decimal('2.00'))
        # Sigue siendo un borrador: la decision es del Comite.
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertIsNone(multa.aprobada_por)

    def test_el_catalogo_enviado_solo_trae_infracciones_activas(self):
        InfraccionCatalogo.objects.create(
            condominio=self.condominio, codigo='BORRADOR-99', descripcion='Sugerida sin confirmar',
            monto=Decimal('1.00'), estado=EstadoInfraccion.BORRADOR,
        )
        cliente = ClienteFalso('{"codigo": null, "confianza": 0, "fundamento": "Sin coincidencia."}')
        with self._con_cliente(cliente):
            self._denunciar('Un hecho cualquiera')

        enviado = cliente.mensajes_enviados[0]['messages'][0]['content']
        self.assertIn('MASCOTA-01', enviado)
        self.assertNotIn('BORRADOR-99', enviado, 'un borrador nunca debe ofrecerse como propuesta')

    # -- Garantia: no puede inventar ----------------------------------

    def test_codigo_inventado_se_descarta(self):
        cliente = ClienteFalso(
            '{"codigo": "INVENTADA-99", "confianza": 99, "fundamento": "Infraccion que no existe."}'
        )
        with self._con_cliente(cliente):
            multa = self._denunciar('Hecho con codigo alucinado')

        self.assertIsNone(multa.infraccion_id)
        self.assertEqual(multa.propuesta_origen, '')
        self.assertEqual(multa.propuesta_confianza, 0)

    def test_respuesta_ilegible_no_rompe_la_denuncia(self):
        cliente = ClienteFalso('lo siento, no puedo responder en JSON')
        with self._con_cliente(cliente):
            multa = self._denunciar('Ruidos molestos a las 3 de la manana')

        # Cae al respaldo por terminos, que si encuentra "ruidos molestos".
        self.assertEqual(multa.infraccion_id, self.ruido.id)
        self.assertEqual(multa.propuesta_origen, 'COINCIDENCIA')

    def test_ia_puede_declarar_que_ninguna_corresponde(self):
        cliente = ClienteFalso(
            '{"codigo": null, "confianza": 10, '
            '"fundamento": "El reporte no describe una conducta sancionable del reglamento."}'
        )
        with self._con_cliente(cliente):
            multa = self._denunciar('Se dejo constancia de una visita al conserje')

        self.assertIsNone(multa.infraccion_id)
        self.assertEqual(multa.propuesta_origen, 'IA')
        self.assertIn('no describe', multa.propuesta_fundamento)

    # -- Garantia: nunca bloquea el flujo legal ------------------------

    def test_api_caida_no_impide_denunciar(self):
        cliente = ClienteFalso(error=RuntimeError('502 Bad Gateway'))
        with self._con_cliente(cliente):
            multa = self._denunciar('Ruidos molestos en la noche')

        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertEqual(multa.propuesta_origen, 'COINCIDENCIA')

    @override_settings(ANTHROPIC_API_KEY='')
    def test_sin_clave_configurada_usa_el_respaldo(self):
        with patch('anthropic.Anthropic') as cliente:
            multa = self._denunciar('Ruidos molestos en la noche')
        cliente.assert_not_called()  # no se intenta llamar sin clave
        self.assertEqual(multa.propuesta_origen, 'COINCIDENCIA')

    # -- Garantia: propone, no decide ----------------------------------

    def test_el_comite_puede_cambiar_la_propuesta_al_aprobar(self):
        cliente = ClienteFalso(
            '{"codigo": "MASCOTA-01", "confianza": 80, "fundamento": "Animal suelto."}'
        )
        with self._con_cliente(cliente):
            multa = self._denunciar('El perro andaba suelto')
        self.assertEqual(multa.infraccion_id, self.mascotas.id)

        # El Comite discrepa y aprueba con otra infraccion del catalogo.
        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.ruido.id},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.infraccion_id, self.ruido.id, 'manda el Comite, no la propuesta')
        self.assertEqual(multa.monto, Decimal('3.00'))
        # El fundamento de la propuesta original queda en el expediente.
        self.assertIn('Animal suelto', multa.propuesta_fundamento)
