"""
Tests de las capacidades incorporadas despues de la primera version, para que
el codigo cumpla lo que promete la pagina de ventas: propuesta automatica de
infraccion al denunciar, descuento parcial en la resolucion del descargo,
multiplicador automatico por reincidencia y aviso complementario por WhatsApp.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, TipoActo
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_test_media_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class CapacidadesNuevasTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Nuevo', plazo_descargo_dias=5)
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 202')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Ana Reincidente', cedula_identidad='33.333.333-3',
            domicilio='Depto 202', correo_electronico='ana@test.local', telefono='+56911112222',
        )

        def crear_usuario(username, rol, persona=None):
            return Usuario.objects.create_user(
                username=username, password='x', rol=rol, condominio=cls.condominio, persona=persona,
            )

        cls.conserje = crear_usuario('conserje2', Rol.FISCALIZADOR)
        cls.comite = crear_usuario('comite2', Rol.COMITE)
        cls.administrador = crear_usuario('admin2', Rol.ADMINISTRADOR)
        cls.residente = crear_usuario('residente2', Rol.RESIDENTE, cls.persona)

        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos nocturnos',
            articulo_referencia='Art. 15', monto=Decimal('10.00'), unidad_monto='UF',
            estado=EstadoInfraccion.ACTIVA, factor_reincidencia=Decimal('2.00'),
        )

    def _denunciar(self, descripcion='Ruidos molestos a las 23:00', dias_atras=0):
        """
        `dias_atras` separa el hecho en el tiempo: dos reportes cercanos sobre
        la misma unidad se entienden como el mismo hecho y se agrupan.
        """
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id,
            'persona_reportada': self.persona.id,
            'descripcion': descripcion,
            'fecha_hecho': (timezone.now() - timedelta(days=dias_atras, hours=1)).isoformat(),
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Multa.objects.get(ticket_id=respuesta.data['id'])

    def _aprobar_y_notificar(self, multa):
        self.client.force_authenticate(self.comite)
        self.assertEqual(
            self.client.post(
                f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.infraccion.id},
            ).status_code,
            200,
        )
        self.client.force_authenticate(self.administrador)
        self.assertEqual(self.client.post(f'/api/multas/{multa.id}/notificar/').status_code, 200)
        multa.refresh_from_db()
        return multa

    # -- Paso 3: propuesta automatica al denunciar ---------------------

    def test_denuncia_precarga_infraccion_propuesta(self):
        multa = self._denunciar('Ruidos molestos toda la noche en el 202')
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)
        self.assertEqual(multa.infraccion_id, self.infraccion.id)
        self.assertEqual(multa.monto, Decimal('10.00'))
        self.assertEqual(multa.propuesta_origen, 'COINCIDENCIA')  # sin clave de IA
        self.assertTrue(multa.propuesta_fundamento)

    def test_denuncia_sin_coincidencia_queda_sin_propuesta(self):
        multa = self._denunciar('Situacion atipica fuera del catalogo vigente')
        self.assertIsNone(multa.infraccion_id)

    # -- Paso 6: descuento parcial ------------------------------------

    def test_descargo_con_descuento_parcial(self):
        multa = self._aprobar_y_notificar(self._denunciar())
        self.client.force_authenticate(self.residente)
        self.assertEqual(
            self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'Atenuantes'}).status_code, 201,
        )

        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(f'/api/multas/{multa.id}/resolver-descargo/', {
            'resolucion': 'DESCUENTO', 'porcentaje_descuento': 30, 'comentario': 'Se acogen atenuantes',
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)
        self.assertEqual(multa.monto, Decimal('7.00'))  # 10 menos 30%
        descargo = multa.descargo
        self.assertEqual(descargo.porcentaje_descuento, 30)
        self.assertEqual(descargo.monto_original, Decimal('10.00'))

        acta = multa.actas_selladas.filter(tipo_acto=TipoActo.RESOLUCION_DESCARGO).first()
        self.assertEqual(acta.manifiesto['extra']['monto_original'], '10.00')
        self.assertEqual(acta.manifiesto['extra']['monto_final'], '7.00')

    def test_descargo_acepta_json_sin_adjunto(self):
        """Un cliente que solo manda texto no debe recibir 415 por usar JSON."""
        multa = self._aprobar_y_notificar(self._denunciar())
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/descargo/', {'texto': 'Defensa solo de texto'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_descuento_exige_porcentaje(self):
        multa = self._aprobar_y_notificar(self._denunciar())
        self.client.force_authenticate(self.residente)
        self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'x'})
        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'DESCUENTO'},
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('porcentaje_descuento', respuesta.data)

    # -- Paso 8: multiplicador por reincidencia -----------------------

    def test_reincidencia_aplica_multiplicador_del_catalogo(self):
        primera = self._aprobar_y_notificar(self._denunciar(dias_atras=3))
        self.assertEqual(primera.monto, Decimal('10.00'))

        # Otro dia: reincidir es volver a incurrir, no el mismo hecho repetido.
        segunda = self._denunciar()
        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{segunda.id}/aprobar/', {'infraccion_id': self.infraccion.id})
        segunda.refresh_from_db()

        self.assertTrue(segunda.es_reincidencia)
        self.assertEqual(segunda.monto, Decimal('20.00'))  # 10 por factor 2.00
        acta = segunda.actas_selladas.filter(tipo_acto=TipoActo.APROBACION).first()
        self.assertEqual(acta.manifiesto['extra']['factor_reincidencia_aplicado'], '2.00')

    # -- Paso 5: WhatsApp complementario ------------------------------

    def test_whatsapp_sin_credenciales_no_bloquea_la_notificacion(self):
        multa = self._aprobar_y_notificar(self._denunciar())
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)  # el correo legal sigue saliendo
        acta = multa.actas_selladas.filter(tipo_acto=TipoActo.NOTIFICACION).first()
        entregas = acta.manifiesto['extra']['entregas']
        self.assertTrue(any(e.startswith('EMAIL:') for e in entregas))
        self.assertFalse(
            any(e.startswith('WHATSAPP:') for e in entregas),
            'sin credenciales no se registra una entrega por WhatsApp que nunca salio',
        )

    @override_settings(
        TWILIO_ACCOUNT_SID='ACtest',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
    )
    def test_whatsapp_configurado_envia_al_telefono_registrado(self):
        with patch('multas.services.requests.post', return_value=Mock(status_code=201)) as mock_post:
            multa = self._aprobar_y_notificar(self._denunciar())

        self.assertTrue(mock_post.called)
        self.assertEqual(mock_post.call_args.kwargs['data']['To'], 'whatsapp:+56911112222')
        acta = multa.actas_selladas.filter(tipo_acto=TipoActo.NOTIFICACION).first()
        entregas = acta.manifiesto['extra']['entregas']
        self.assertIn('WHATSAPP:+56911112222:ENVIADA', entregas)

    @override_settings(
        TWILIO_ACCOUNT_SID='ACtest',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
        FRONTEND_URL='https://vivepiola.cl',
    )
    def test_whatsapp_lleva_al_buzon_del_residente(self):
        """
        El aviso sirve para actuar. Antes apuntaba a /m/<id>, que exige iniciar
        sesion: justo la barrera que deja fuera a quien hay que alcanzar por
        WhatsApp. Ahora lleva al buzon firmado, donde puede ver el caso,
        descargar el documento y apelar sin cuenta.
        """
        with patch('multas.services.requests.post', return_value=Mock(status_code=201)) as mock_post:
            multa = self._aprobar_y_notificar(self._denunciar())

        cuerpo = mock_post.call_args.kwargs['data']['Body']
        self.assertIn('https://vivepiola.cl/acuse/', cuerpo)
        self.assertNotIn(f'/m/{multa.id}', cuerpo)
        self.assertIn('apelar', cuerpo)
        # El link no debe cargar credenciales: los mensajes se reenvian.
        for filtracion in ('access', 'jwt', 'Bearer'):
            self.assertNotIn(filtracion, cuerpo)
