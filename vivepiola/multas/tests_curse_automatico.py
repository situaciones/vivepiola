"""
Tests del ciclo sin filtro previo del comite.

La denuncia se tipifica y se notifica de inmediato; el residente ejerce su
defensa apelando, y el comite interviene una sola vez, al resolver. Lo que se
verifica aqui es donde estan los limites de ese automatismo: que sanciona solo
y que no, y que nada se pierde cuando no puede.
"""

import tempfile
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, TipoActo
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_curse_')


def _respuesta_ia(codigo, confianza):
    texto = f'{{"codigo": "{codigo}", "confianza": {confianza}, "fundamento": "Encuadre de prueba."}}'
    return SimpleNamespace(content=[SimpleNamespace(type='text', text=texto)])


@override_settings(MEDIA_ROOT=MEDIA_TEMP, ANTHROPIC_API_KEY='sk-ant-de-prueba')
class CurseAutomaticoTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Cupo 0: esta clase prueba el curse automatico, no la cortesia. Con
        # cupo la primera falta saldria sin cobro y taparia lo que se mide.
        cls.condominio = Condominio.objects.create(
            nombre='Condominio Curse', cortesias_antes_de_multar=0,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 909')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Nora Notificada', cedula_identidad='7.777.777-7',
            domicilio='Depto 909', correo_electronico='nora@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_curse', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_curse', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.ruido = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('3.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _denunciar(self, confianza, codigo='RUIDO-01', descripcion='Fiesta a las 3 de la manana'):
        mail.outbox = []
        self.client.force_authenticate(self.conserje)
        cliente = SimpleNamespace(messages=SimpleNamespace(
            create=lambda **kw: _respuesta_ia(codigo, confianza),
        ))
        with patch('anthropic.Anthropic', return_value=cliente):
            respuesta = self.client.post('/api/tickets/', {
                'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
                'descripcion': descripcion, 'fecha_hecho': timezone.now().isoformat(),
            }, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Multa.objects.get(ticket_id=respuesta.data['id'])

    # -- Lo que si se cursa solo ---------------------------------------

    def test_con_encuadre_solido_se_notifica_sin_pasar_por_el_comite(self):
        multa = self._denunciar(confianza=85)

        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertIsNone(multa.aprobada_por, 'el ciclo ya no tiene paso de aprobacion')
        self.assertIsNone(multa.notificada_por, 'la notificacion la emite el sistema')
        self.assertEqual(multa.infraccion, self.ruido)
        self.assertEqual(multa.monto, Decimal('3.00'))
        self.assertTrue(multa.pdf_notificacion.name)
        self.assertIsNone(
            multa.fecha_limite_descargo,
            'haber enviado no es haber notificado: el plazo arranca con el acuse',
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('nora@test.local', mail.outbox[0].to)
        self.assertIn('/acuse/', mail.outbox[0].body, 'el correo debe traer como confirmar la recepcion')

    def test_la_notificacion_no_dice_que_el_comite_aprobo_algo_que_no_vio(self):
        """
        Una notificacion legal no puede afirmar un hecho que no ocurrio. Si
        nadie aprobo, el texto dice que se curso automaticamente y ofrece la
        apelacion como contrapeso.
        """
        self._denunciar(confianza=85)
        cuerpo = mail.outbox[0].body

        self.assertNotIn('ha aprobado', cuerpo)
        self.assertIn('se ha cursado una multa', cuerpo)
        self.assertIn('automaticamente', cuerpo)
        self.assertIn('puede apelar', cuerpo)

    def test_cuando_si_hubo_aprobacion_humana_la_notificacion_lo_dice(self):
        multa = self._denunciar(confianza=40)
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)

        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.ruido.id})

        administrador = Usuario.objects.create_user(
            username='admin_curse', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.client.force_authenticate(administrador)
        mail.outbox = []
        respuesta = self.client.post(f'/api/multas/{multa.id}/notificar/')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.assertIn('ha aprobado', mail.outbox[0].body)

    def test_el_curse_automatico_queda_sellado_como_acto_del_sistema(self):
        multa = self._denunciar(confianza=85)

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.CURSE_AUTOMATICO)
        self.assertEqual(acta.manifiesto['extra']['confianza_propuesta'], 85)
        self.assertEqual(acta.manifiesto['extra']['origen_propuesta'], 'IA')
        self.assertEqual(acta.manifiesto['extra']['monto_aplicado'], '3.00')

    def test_el_residente_apela_y_el_comite_resuelve_una_sola_vez(self):
        multa = self._denunciar(confianza=85)
        residente = Usuario.objects.create_user(
            username='nora', password='x', rol=Rol.RESIDENTE,
            condominio=self.condominio, persona=self.persona,
        )

        self.client.force_authenticate(residente)
        respuesta = self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'No fui yo'})
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/',
            {'resolucion': 'DESCUENTO', 'porcentaje_descuento': 50, 'comentario': 'Primera vez'},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)
        self.assertEqual(multa.monto, Decimal('1.50'))

        actos_del_comite = multa.actas_selladas.filter(actor=self.comite).count()
        self.assertEqual(actos_del_comite, 1, 'el comite debe intervenir exactamente una vez')

    # -- Lo que NO se cursa solo ---------------------------------------

    def test_bajo_el_umbral_de_confianza_espera_tipificacion_humana(self):
        multa = self._denunciar(confianza=55)

        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertEqual(len(mail.outbox), 0, 'nadie puede ser notificado con un encuadre debil')
        self.assertIn('bajo el minimo', multa.historial.first().comentario)

    def test_el_respaldo_por_coincidencia_nunca_sanciona_solo(self):
        """
        Mide 60 como tope y el umbral es 70: el respaldo existe para que el
        sistema no se caiga sin IA, no para multar por calzar palabras.
        """
        with override_settings(ANTHROPIC_API_KEY=''):
            mail.outbox = []
            self.client.force_authenticate(self.conserje)
            respuesta = self.client.post('/api/tickets/', {
                'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
                'descripcion': 'Ruidos molestos toda la noche',
                'fecha_hecho': timezone.now().isoformat(),
            }, format='json')

        multa = Multa.objects.get(ticket_id=respuesta.data['id'])
        self.assertEqual(multa.propuesta_origen, 'COINCIDENCIA')
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertEqual(len(mail.outbox), 0)

    def test_sin_infraccion_en_el_catalogo_no_se_inventa_una(self):
        multa = self._denunciar(confianza=95, codigo='null')

        self.assertIsNone(multa.infraccion)
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertIn('no calza con ninguna infraccion', multa.historial.first().comentario)

    def test_sin_correo_del_residente_el_caso_queda_en_pausa(self):
        """Sin contacto no hay notificacion valida, y sin ella no hay plazo para apelar."""
        self.persona.correo_electronico = ''
        self.persona.save(update_fields=['correo_electronico'])

        multa = self._denunciar(confianza=95)

        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('no tiene correo registrado', multa.historial.first().comentario)

    def test_si_el_correo_falla_el_expediente_no_se_pierde(self):
        with patch('multas.services.EmailMessage.send', side_effect=OSError('SMTP caido')):
            multa = self._denunciar(confianza=95)

        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION, 'una falla tecnica no borra la denuncia')
        self.assertIn('No se pudo notificar', multa.historial.first().comentario)

    def test_el_umbral_es_configurable(self):
        with override_settings(CURSE_AUTOMATICO_CONFIANZA_MINIMA=50):
            multa = self._denunciar(confianza=55)
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
