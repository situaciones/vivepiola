"""
Tests del correo de notificacion: asunto con la comunidad, "Responder" a la
administracion y version HTML con boton, sin perder el texto plano legal.
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
from multas.models import Multa
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

from .correo_html import html_correo

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_test_media_')


@override_settings(
    MEDIA_ROOT=MEDIA_TEMP,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://sinconflicto.cl',
)
class CorreoNotificacionTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Sin cortesias: se prueba primero la multa con monto.
        cls.condominio = Condominio.objects.create(
            nombre='Edificio Los Robles', cortesias_antes_de_multar=0,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 101')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Ana <b>Perez</b>', cedula_identidad='11.111.111-1',
            domicilio='Depto 101', correo_electronico='ana@test.local',
        )

        def usuario(username, rol, email=''):
            return Usuario.objects.create_user(
                username=username, password='x', rol=rol, condominio=cls.condominio, email=email,
            )

        cls.fiscalizador = usuario('fisca', Rol.FISCALIZADOR)
        cls.comite = usuario('comite', Rol.COMITE)
        cls.administrador = usuario('admin1', Rol.ADMINISTRADOR, 'administracion@losrobles.cl')
        usuario('admin_sin_correo', Rol.ADMINISTRADOR)
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos nocturnos',
            articulo_referencia='Art. 15', monto=Decimal('2.00'), unidad_monto='UF',
            estado=EstadoInfraccion.ACTIVA,
        )

    def _notificar(self):
        self.client.force_authenticate(self.fiscalizador)
        ticket = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
            'descripcion': 'Musica a todo volumen a las 3 am',
            'fecha_hecho': (timezone.now() - timedelta(hours=1)).isoformat(),
        }).data
        multa = Multa.objects.get(ticket_id=ticket['id'])
        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.infraccion.id})
        self.client.force_authenticate(self.administrador)
        self.assertEqual(self.client.post(f'/api/multas/{multa.id}/notificar/').status_code, 200)
        return multa, mail.outbox[-1]

    def test_el_asunto_lleva_el_nombre_de_la_comunidad(self):
        multa, correo = self._notificar()
        self.assertEqual(correo.subject, f'Notificacion de multa #{multa.id} - Edificio Los Robles')

    def test_responder_llega_a_la_administracion_de_la_comunidad(self):
        _, correo = self._notificar()
        self.assertEqual(correo.reply_to, ['administracion@losrobles.cl'])
        self.assertIn('notificaciones@', correo.from_email)

    def test_trae_html_con_boton_al_caso_y_conserva_el_texto_legal(self):
        multa, correo = self._notificar()
        html, tipo = correo.alternatives[0]
        self.assertEqual(tipo, 'text/html')
        self.assertIn('Ver mi caso y confirmar recepcion', html)
        self.assertIn('https://sinconflicto.cl/acuse/', html)
        self.assertIn('2.00 UF', html)
        # El texto plano sigue completo: es la constancia legal.
        self.assertIn('/acuse/', correo.body)
        self.assertIn('canal legal', correo.body)
        self.assertEqual(correo.attachments[0][0], f'notificacion_{multa.id}.pdf')

    def test_el_html_escapa_lo_que_viene_del_caso(self):
        _, correo = self._notificar()
        html = correo.alternatives[0][0]
        self.assertNotIn('<b>Perez</b>', html)
        self.assertIn('&lt;b&gt;Perez&lt;/b&gt;', html)

    def test_sin_administracion_con_correo_sale_sin_direccion_de_respuesta(self):
        Usuario.objects.filter(rol=Rol.ADMINISTRADOR).update(email='')
        _, correo = self._notificar()
        self.assertEqual(correo.reply_to, [])


class HtmlCorreoTestCase(APITestCase):
    def test_un_enlace_malicioso_en_el_boton_no_rompe_el_atributo(self):
        html = html_correo(
            comunidad='X', titulo='T', parrafos=['a', 'b'],
            boton=('Abrir', 'https://x.cl/"><script>alert(1)</script>'),
        )
        self.assertNotIn('<script>', html)
