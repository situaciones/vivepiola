"""
Tests del encuadre automatico de la denuncia.

El sistema tipifica solo cuando el encuadre es solido. La advertencia sin
cobro se notifica de inmediato; la multa con cobro queda propuesta hasta que
la apruebe la mayoria del Comite (Ley 21.442). Lo que se verifica aqui es
donde estan los limites de ese automatismo y que nada se pierde cuando no puede.
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

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_curse_')


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
            email='comite@test.local',
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

    def _aprobar_y_notificar(self, multa):
        self.client.force_authenticate(self.comite)
        r = self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.ruido.id})
        self.assertEqual(r.status_code, 200, r.data)
        administrador = Usuario.objects.create_user(
            username=f'admin_curse_{multa.id}', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.client.force_authenticate(administrador)
        mail.outbox = []
        r = self.client.post(f'/api/multas/{multa.id}/notificar/')
        self.assertEqual(r.status_code, 200, r.data)
        multa.refresh_from_db()
        return multa

    # -- Con encuadre solido, la propuesta llega lista al Comite ---------

    def test_con_encuadre_solido_la_multa_con_cobro_espera_al_comite(self):
        """La Ley 21.442 deja la imposicion de multas en el Comite: no sale sola."""
        multa = self._denunciar(confianza=85)

        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertEqual(multa.infraccion, self.ruido, 'la propuesta llega lista')
        self.assertEqual(multa.monto, Decimal('3.00'))
        self.assertIsNone(multa.fecha_notificacion)
        self.assertIn('Falta la aprobacion del Comite', multa.historial.first().comentario)
        self.assertFalse(multa.actas_selladas.filter(tipo_acto=TipoActo.CURSE_AUTOMATICO).exists())

        self.assertNotIn('nora@test.local', [d for m in mail.outbox for d in m.to])
        avisos = [m for m in mail.outbox if 'Multa por aprobar' in m.subject]
        self.assertEqual(len(avisos), 1)
        self.assertIn('no se notifica ni se cobra', avisos[0].body)

    def test_aprobada_por_el_comite_la_notificacion_lo_dice(self):
        multa = self._aprobar_y_notificar(self._denunciar(confianza=85))
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertEqual(multa.aprobada_por, self.comite)
        self.assertIn('ha aprobado', mail.outbox[0].body)

    def test_la_advertencia_sin_cobro_si_sale_sola(self):
        """Una advertencia no es una multa con cobro: se notifica de inmediato."""
        self.condominio.cortesias_antes_de_multar = 1
        self.condominio.save()
        multa = self._denunciar(confianza=85)

        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertEqual(multa.monto, Decimal('0.00'))
        self.assertIsNone(multa.aprobada_por)
        self.assertNotIn('ha aprobado', mail.outbox[0].body)
        acta = multa.actas_selladas.get(tipo_acto=TipoActo.CURSE_AUTOMATICO)
        self.assertEqual(acta.manifiesto['extra']['confianza_propuesta'], 85)
        self.assertEqual(acta.manifiesto['extra']['origen_propuesta'], 'IA')
        self.assertTrue(acta.manifiesto['extra']['es_cortesia'])

    def test_el_residente_apela_y_el_comite_resuelve(self):
        multa = self._aprobar_y_notificar(self._denunciar(confianza=85))
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

    # -- Lo que NO se cursa solo ---------------------------------------

    def test_bajo_el_umbral_de_confianza_espera_tipificacion_humana(self):
        multa = self._denunciar(confianza=55)

        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertEqual(len(mail.outbox), 0, 'nadie puede ser notificado con un encuadre debil')
        self.assertIn('exige al menos', multa.historial.first().comentario)

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
        self.condominio.cortesias_antes_de_multar = 1  # la advertencia es lo que se notifica solo
        self.condominio.save()
        with patch('multas.services.EmailMessage.send', side_effect=OSError('SMTP caido')):
            multa = self._denunciar(confianza=95)

        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION, 'una falla tecnica no borra la denuncia')
        self.assertIn('No se pudo notificar', multa.historial.first().comentario)

    def test_el_umbral_es_configurable(self):
        with override_settings(CURSE_CONFIANZA_MINIMA={'LEVE': 50, 'GRAVE': 80, 'GRAVISIMA': 90}):
            multa = self._denunciar(confianza=55)
        self.assertIn('Propuesta lista', multa.historial.first().comentario)
