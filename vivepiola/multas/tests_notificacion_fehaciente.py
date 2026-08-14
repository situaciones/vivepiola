"""
Tests de la notificacion fehaciente.

Haber enviado un correo no es haber notificado. Lo que se protege aqui es que
nadie pierda su defensa por un mensaje que nunca leyo: el plazo de apelacion
arranca cuando hay constancia de recepcion, se reintenta hasta conseguirla, y
si no llega por ningun canal digital queda la via del buzon de la unidad.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import (
    CanalNotificacion, EstadoEntrega, EstadoMulta, Multa, Ticket, TipoActo,
)
from multas.services import actualizar_multas_vencidas, token_acuse
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_notif_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class NotificacionFehacienteTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Fehaciente', plazo_descargo_dias=5)
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 404')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Olga Ochenta', cedula_identidad='4.444.444-4',
            domicilio='Depto 404', correo_electronico='olga@test.local', telefono='+56944444444',
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_notif', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.administrador = Usuario.objects.create_user(
            username='admin_notif', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.residente = Usuario.objects.create_user(
            username='olga', password='x', rol=Rol.RESIDENTE,
            condominio=cls.condominio, persona=cls.persona,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('2.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _notificada(self):
        """Un expediente ya despachado, sin acuse todavia."""
        from multas.services import notificar_multa

        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Ruido nocturno', fecha_hecho=timezone.now(),
        )
        multa = Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, infraccion=self.infraccion,
            monto=Decimal('2.00'), estado=EstadoMulta.APROBADA,
        )
        mail.outbox = []
        notificar_multa(multa, self.administrador)
        multa.refresh_from_db()
        return multa

    # -- El plazo no corre por el solo hecho de enviar ------------------

    def test_al_despachar_no_hay_plazo_todavia(self):
        multa = self._notificada()

        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertIsNone(multa.fecha_acuse)
        self.assertIsNone(multa.fecha_limite_descargo)
        cuerpo = mail.outbox[0].body.lower()
        self.assertIn(
            'confirmar que lo recibio', cuerpo,
            'el correo tiene que pedir el acuse, que es lo que hace correr el plazo',
        )
        self.assertIn('presentar su apelacion', cuerpo, 'y ofrecer la defensa en el mismo lugar')

    def test_sin_acuse_la_multa_no_puede_quedar_firme_sola(self):
        """La proteccion central: nadie queda sancionado por un correo que no leyo."""
        multa = self._notificada()
        multa.fecha_notificacion = timezone.now() - timedelta(days=90)
        multa.save(update_fields=['fecha_notificacion'])

        actualizar_multas_vencidas(self.condominio)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA, 'sin acuse no empezo a correr ningun plazo')

    def test_con_acuse_el_plazo_arranca_y_luego_queda_firme(self):
        multa = self._notificada()

        respuesta = self.client.post(f'/api/notificaciones/acuse/{token_acuse(multa)}/')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertIsNotNone(multa.fecha_acuse)
        self.assertEqual(multa.canal_acuse, CanalNotificacion.EMAIL)
        esperado = multa.fecha_acuse + timedelta(days=5)
        self.assertAlmostEqual(multa.fecha_limite_descargo, esperado, delta=timedelta(seconds=5))

        multa.fecha_limite_descargo = timezone.now() - timedelta(minutes=1)
        multa.save(update_fields=['fecha_limite_descargo'])
        actualizar_multas_vencidas(self.condominio)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)

    # -- El acuse funciona sin cuenta ----------------------------------

    def test_el_enlace_muestra_de_que_multa_se_trata_sin_iniciar_sesion(self):
        multa = self._notificada()
        self.client.force_authenticate(None)

        respuesta = self.client.get(f'/api/notificaciones/acuse/{token_acuse(multa)}/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['multa_id'], multa.id)
        self.assertEqual(respuesta.data['unidad'], 'Depto 404')
        self.assertFalse(respuesta.data['ya_acusada'])
        # Consultar el enlace no puede dar por notificado a nadie: eso lo hace
        # el POST, para que ningun escaner de correo acuse recibo por la persona.
        multa.refresh_from_db()
        self.assertIsNone(multa.fecha_acuse)

    def test_un_enlace_adulterado_no_sirve(self):
        multa = self._notificada()
        respuesta = self.client.post(f'/api/notificaciones/acuse/{token_acuse(multa)}xx/')
        self.assertEqual(respuesta.status_code, 404)
        multa.refresh_from_db()
        self.assertIsNone(multa.fecha_acuse)

    def test_el_acuse_no_se_puede_repetir_para_estirar_el_plazo(self):
        multa = self._notificada()
        token = token_acuse(multa)

        self.client.post(f'/api/notificaciones/acuse/{token}/')
        multa.refresh_from_db()
        primera_fecha = multa.fecha_limite_descargo

        self.client.post(f'/api/notificaciones/acuse/{token}/')
        multa.refresh_from_db()
        self.assertEqual(multa.fecha_limite_descargo, primera_fecha)
        self.assertEqual(multa.actas_selladas.filter(tipo_acto=TipoActo.ACUSE_RECIBO).count(), 1)

    def test_abrir_la_multa_en_la_app_vale_como_acuse(self):
        multa = self._notificada()
        self.client.force_authenticate(self.residente)

        respuesta = self.client.get(f'/api/multas/{multa.id}/')
        self.assertEqual(respuesta.status_code, 200)

        multa.refresh_from_db()
        self.assertEqual(multa.canal_acuse, CanalNotificacion.APP)
        self.assertIsNotNone(multa.fecha_limite_descargo)

    def test_apelar_sin_haber_acusado_no_deja_a_nadie_sin_defensa(self):
        """Presentar la apelacion prueba que se entero: seria absurdo rechazarla."""
        multa = self._notificada()
        self.client.force_authenticate(self.residente)

        respuesta = self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'No fui yo'}, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)
        self.assertIsNotNone(multa.fecha_acuse)

    # -- Bitacora de entregas ------------------------------------------

    def test_queda_registro_de_cada_canal_por_el_que_se_intento(self):
        multa = self._notificada()

        entregas = {(e.canal, e.destino, e.estado) for e in multa.entregas.all()}
        self.assertIn((CanalNotificacion.EMAIL, 'olga@test.local', EstadoEntrega.ENVIADA), entregas)

    def test_un_canal_caido_no_impide_los_demas(self):
        with override_settings(
            TWILIO_ACCOUNT_SID='ACtest', TWILIO_AUTH_TOKEN='tok',
            TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
        ):
            with patch('multas.services.EmailMessage.send', side_effect=OSError('SMTP caido')), \
                 patch('multas.services.requests.post', return_value=SimpleNamespace(status_code=201)):
                multa = self._notificada()

        estados = {e.canal: e.estado for e in multa.entregas.all()}
        self.assertEqual(estados[CanalNotificacion.EMAIL], EstadoEntrega.FALLIDA)
        self.assertEqual(estados[CanalNotificacion.WHATSAPP], EstadoEntrega.ENVIADA)
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA, 'WhatsApp salio, la notificacion vale')

    def test_si_no_sale_ningun_canal_el_expediente_no_queda_notificado(self):
        from multas.services import notificar_multa

        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Ruido', fecha_hecho=timezone.now(),
        )
        multa = Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, infraccion=self.infraccion,
            monto=Decimal('2.00'), estado=EstadoMulta.APROBADA,
        )
        with patch('multas.services.EmailMessage.send', side_effect=OSError('SMTP caido')):
            with self.assertRaises(ValueError):
                notificar_multa(multa, self.administrador)

        multa.refresh_from_db()
        self.assertEqual(
            multa.estado, EstadoMulta.APROBADA,
            'si no salio ningun mensaje, el expediente no puede figurar como notificado',
        )

    # -- Reintentos -----------------------------------------------------

    def test_reintenta_cuando_pasaron_los_minutos_de_espera(self):
        multa = self._notificada()
        multa.entregas.update(enviada_en=timezone.now() - timedelta(minutes=10))

        call_command('reintentar_notificaciones', stdout=StringIO())

        multa.refresh_from_db()
        self.assertEqual(multa.entregas.filter(intento=2).count(), 1)

    def test_no_reintenta_antes_de_tiempo(self):
        self._notificada()  # recien enviada
        call_command('reintentar_notificaciones', stdout=StringIO())
        self.assertEqual(Multa.objects.get().entregas.filter(intento=2).count(), 0)

    def test_deja_de_reintentar_apenas_hay_acuse(self):
        multa = self._notificada()
        self.client.post(f'/api/notificaciones/acuse/{token_acuse(multa)}/')
        multa.entregas.update(enviada_en=timezone.now() - timedelta(minutes=10))

        call_command('reintentar_notificaciones', stdout=StringIO())

        multa.refresh_from_db()
        self.assertEqual(multa.entregas.filter(intento=2).count(), 0)

    def test_agotados_los_tres_intentos_avisa_que_corresponde_el_buzon(self):
        multa = self._notificada()
        for intento in (2, 3):
            multa.entregas.create(
                multa=multa, canal=CanalNotificacion.EMAIL, destino='olga@test.local', intento=intento,
            )
        multa.entregas.update(enviada_en=timezone.now() - timedelta(minutes=30))

        salida = StringIO()
        call_command('reintentar_notificaciones', stdout=salida)

        texto = salida.getvalue()
        self.assertIn('constancia en el buzon', texto)
        self.assertIn('Depto 404', texto)
        multa.refresh_from_db()
        self.assertEqual(multa.entregas.filter(intento=4).count(), 0, 'no puede pasarse del maximo')

    # -- Constancia en el buzon ----------------------------------------

    def test_la_constancia_en_el_buzon_perfecciona_la_notificacion(self):
        multa = self._notificada()
        self.client.force_authenticate(self.administrador)

        respuesta = self.client.post(
            f'/api/multas/{multa.id}/constancia-buzon/',
            {'detalle': 'Sobre dejado en el buzon del Depto 404'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.canal_acuse, CanalNotificacion.BUZON)
        self.assertIsNotNone(multa.fecha_limite_descargo)

        entrega = multa.entregas.get(canal=CanalNotificacion.BUZON)
        self.assertEqual(entrega.registrada_por, self.administrador, 'debe constar quien la dejo')
        self.assertEqual(entrega.estado, EstadoEntrega.ACUSADA)

    def test_el_residente_no_puede_dejarse_una_constancia_a_si_mismo(self):
        multa = self._notificada()
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(f'/api/multas/{multa.id}/constancia-buzon/', {}, format='json')
        self.assertEqual(respuesta.status_code, 403)

    def test_no_se_deja_constancia_de_algo_ya_recepcionado(self):
        multa = self._notificada()
        self.client.post(f'/api/notificaciones/acuse/{token_acuse(multa)}/')

        self.client.force_authenticate(self.administrador)
        respuesta = self.client.post(f'/api/multas/{multa.id}/constancia-buzon/', {}, format='json')
        self.assertEqual(respuesta.status_code, 400)

    def test_el_acuse_queda_sellado_con_su_canal_y_su_plazo(self):
        multa = self._notificada()
        self.client.post(f'/api/notificaciones/acuse/{token_acuse(multa)}/')

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.ACUSE_RECIBO)
        self.assertEqual(acta.manifiesto['extra']['canal'], CanalNotificacion.EMAIL)
        self.assertEqual(acta.manifiesto['extra']['plazo_descargo_dias'], 5)
        self.assertTrue(acta.manifiesto['extra']['fecha_limite_descargo'])
