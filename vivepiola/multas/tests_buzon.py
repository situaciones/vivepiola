"""
Tests del buzon del residente y de la apelacion por enlace firmado.

El derecho a defenderse no puede depender de saber usar un software. Por eso
los tres canales —app, correo y WhatsApp— llevan al mismo enlace, y desde ahi
se puede ver el caso, descargar el documento y apelar sin crear cuenta.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, ResolucionDescargo, Ticket, TipoActo
from multas.services import enlace_acuse, notificar_multa, token_acuse
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_buzon_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class BuzonDelResidenteTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre='Condominio Buzon', plazo_descargo_dias=5, cortesias_antes_de_multar=0,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 606')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Bruno Buzon', cedula_identidad='6.060.606-0',
            domicilio='Depto 606', correo_electronico='bruno@test.local', telefono='+56966666666',
        )
        cls.administrador = Usuario.objects.create_user(
            username='admin_buzon', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_buzon', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('5.00'),
            texto_fuente='Se prohiben los ruidos entre las 22:00 y las 08:00.',
            estado=EstadoInfraccion.ACTIVA,
        )

    def _notificada(self):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Fiesta a las 3 de la manana', fecha_hecho=timezone.now(),
        )
        multa = Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, infraccion=self.infraccion,
            monto=Decimal('5.00'), estado=EstadoMulta.APROBADA,
        )
        mail.outbox = []
        notificar_multa(multa, self.administrador)
        multa.refresh_from_db()
        return multa

    # -- El buzon muestra el caso completo ------------------------------

    def test_sin_sesion_se_ve_todo_lo_que_el_residente_debe_saber(self):
        multa = self._notificada()
        self.client.force_authenticate(None)

        respuesta = self.client.get(f'/api/notificaciones/acuse/{token_acuse(multa)}/')
        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.data
        self.assertEqual(datos['unidad'], 'Depto 606')
        self.assertEqual(datos['infraccion'], 'Ruidos molestos')
        self.assertEqual(datos['articulo'], 'Art. 15')
        self.assertIn('22:00', datos['texto_norma'], 'debe poder leer la norma que le aplican')
        self.assertIn('Fiesta', datos['hecho'])
        self.assertEqual(datos['plazo_dias'], 5)

    def test_no_se_expone_quien_reporto(self):
        """El anonimato del denunciante es parte del diseño, y aqui es donde
        mas tentador seria filtrarlo."""
        multa = self._notificada()
        respuesta = self.client.get(f'/api/notificaciones/acuse/{token_acuse(multa)}/')

        cuerpo = str(respuesta.data)
        self.assertNotIn('creado_por', cuerpo)
        self.assertNotIn('admin_buzon', cuerpo)

    def test_el_buzon_dice_que_puede_hacer_en_este_momento(self):
        multa = self._notificada()
        respuesta = self.client.get(f'/api/notificaciones/acuse/{token_acuse(multa)}/')

        acciones = respuesta.data['acciones']
        self.assertTrue(acciones['puede_acusar'])
        self.assertTrue(acciones['puede_apelar'])
        self.assertTrue(acciones['tiene_documento'])

    # -- El documento se puede volver a descargar -----------------------

    def test_el_pdf_se_descarga_cuantas_veces_haga_falta(self):
        """No depende de haber guardado el correo."""
        multa = self._notificada()
        url = f'/api/notificaciones/documento/{token_acuse(multa)}/'

        for _ in range(3):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta['Content-Type'], 'application/pdf')
            self.assertTrue(respuesta.content.startswith(b'%PDF'))

    def test_un_enlace_adulterado_no_entrega_el_documento(self):
        multa = self._notificada()
        respuesta = self.client.get(f'/api/notificaciones/documento/{token_acuse(multa)}xx/')
        self.assertEqual(respuesta.status_code, 404)

    # -- Apelar sin cuenta ----------------------------------------------

    def test_se_apela_desde_el_enlace_sin_iniciar_sesion(self):
        multa = self._notificada()
        self.client.force_authenticate(None)

        respuesta = self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/',
            {'texto': 'Ese dia no estaba en el departamento'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)
        self.assertEqual(multa.descargo.texto, 'Ese dia no estaba en el departamento')
        self.assertIsNone(multa.descargo.presentado_por, 'llego por el enlace, sin sesion')

    def test_apelar_cuenta_como_acuse_si_no_lo_habia_hecho(self):
        """Seria absurdo rechazarle la defensa a quien la esta ejerciendo."""
        multa = self._notificada()
        self.assertIsNone(multa.fecha_acuse)

        self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/',
            {'texto': 'No fui yo'}, format='json',
        )

        multa.refresh_from_db()
        self.assertIsNotNone(multa.fecha_acuse)
        self.assertIsNotNone(multa.fecha_limite_descargo)

    def test_la_apelacion_por_enlace_queda_sellada_con_su_via(self):
        multa = self._notificada()
        self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/',
            {'texto': 'Mi version'}, format='json',
        )

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.DESCARGO_PRESENTADO)
        self.assertEqual(acta.manifiesto['extra']['via'], 'enlace_de_notificacion')
        self.assertEqual(acta.auth_metodo, 'enlace_firmado')

    def test_una_apelacion_vacia_se_rechaza(self):
        multa = self._notificada()
        respuesta = self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/', {'texto': '   '}, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_no_se_apela_dos_veces_por_el_mismo_caso(self):
        multa = self._notificada()
        token = token_acuse(multa)
        self.client.post(f'/api/notificaciones/apelar/{token}/', {'texto': 'Una'}, format='json')

        respuesta = self.client.post(
            f'/api/notificaciones/apelar/{token}/', {'texto': 'Otra'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('Ya presentaste', respuesta.data['detail'])

    def test_vencido_el_plazo_ya_no_se_apela(self):
        multa = self._notificada()
        multa.fecha_acuse = timezone.now() - timedelta(days=30)
        multa.fecha_limite_descargo = timezone.now() - timedelta(days=1)
        multa.save(update_fields=['fecha_acuse', 'fecha_limite_descargo'])

        respuesta = self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/', {'texto': 'Tarde'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('plazo', respuesta.data['detail'].lower())

    def test_el_comite_resuelve_igual_una_apelacion_llegada_por_enlace(self):
        """Da lo mismo por donde entro: es una apelacion como cualquier otra."""
        multa = self._notificada()
        self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/',
            {'texto': 'No fui yo'}, format='json',
        )

        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/',
            {'resolucion': 'ACEPTADO', 'comentario': 'Tiene razon'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.ANULADA)
        self.assertEqual(multa.descargo.resolucion, ResolucionDescargo.ACEPTADO)

    def test_despues_de_apelar_el_buzon_muestra_la_apelacion_y_su_estado(self):
        multa = self._notificada()
        self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/',
            {'texto': 'Mi defensa'}, format='json',
        )

        respuesta = self.client.get(f'/api/notificaciones/acuse/{token_acuse(multa)}/')
        self.assertEqual(respuesta.data['apelacion']['texto'], 'Mi defensa')
        self.assertEqual(respuesta.data['apelacion']['resolucion'], ResolucionDescargo.PENDIENTE)
        self.assertFalse(respuesta.data['acciones']['puede_apelar'], 'ya no puede apelar de nuevo')

    # -- Los tres canales llevan al mismo lugar -------------------------

    def test_el_correo_lleva_al_buzon_y_lo_explica(self):
        multa = self._notificada()
        cuerpo = mail.outbox[0].body

        self.assertIn('/acuse/', cuerpo)
        self.assertIn('presentar su apelacion', cuerpo)
        self.assertIn('sin crear ninguna cuenta', cuerpo)

    @override_settings(
        TWILIO_ACCOUNT_SID='ACtest', TWILIO_AUTH_TOKEN='tok',
        TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
    )
    def test_el_whatsapp_lleva_al_mismo_buzon_y_no_a_una_pagina_con_login(self):
        """
        Antes apuntaba a /m/<id>, que exige iniciar sesion: justo la barrera
        que deja fuera a quien hay que alcanzar por WhatsApp.
        """
        from types import SimpleNamespace
        from unittest.mock import patch

        multa = self._notificada()
        with patch('multas.services.requests.post', return_value=SimpleNamespace(status_code=201)) as post:
            from multas.services import enviar_notificacion_whatsapp
            enviar_notificacion_whatsapp(multa)

        cuerpo = post.call_args.kwargs['data']['Body']
        self.assertIn('/acuse/', cuerpo)
        self.assertNotIn(f'/m/{multa.id}', cuerpo)
        self.assertIn('apelar', cuerpo)

    def test_el_enlace_es_unico_por_multa(self):
        primera = self._notificada()
        segunda = self._notificada()
        self.assertNotEqual(enlace_acuse(primera), enlace_acuse(segunda))

        # Y el de una no sirve para operar sobre la otra.
        respuesta = self.client.get(f'/api/notificaciones/acuse/{token_acuse(primera)}/')
        self.assertEqual(respuesta.data['multa_id'], primera.id)
