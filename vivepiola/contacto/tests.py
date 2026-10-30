from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import SolicitudDemo

URL = '/api/contacto/demo/'
DATOS = {'nombre': 'Marta Rojas', 'correo': 'marta@administradora.cl', 'empresa': 'Edificio Los Robles'}


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CONTACTO_CORREO='ventas@sinconflicto.cl',
)
class SolicitudDemoTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # el limite por hora vive en la cache

    def test_guarda_la_solicitud_y_avisa_por_correo(self):
        respuesta = self.client.post(URL, DATOS, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        solicitud = SolicitudDemo.objects.get()
        self.assertEqual(solicitud.correo, 'marta@administradora.cl')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ventas@sinconflicto.cl'])
        self.assertIn('Edificio Los Robles', mail.outbox[0].body)

    def test_si_el_correo_falla_la_solicitud_igual_queda_guardada(self):
        with patch('contacto.views.send_mail', side_effect=OSError('smtp caido')):
            respuesta = self.client.post(URL, DATOS, format='json')
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(SolicitudDemo.objects.count(), 1)

    def test_no_exige_sesion_ni_falla_con_un_token_vencido(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer token-vencido')
        self.assertEqual(self.client.post(URL, DATOS, format='json').status_code, 201)

    def test_valida_nombre_y_correo(self):
        respuesta = self.client.post(URL, {'nombre': '', 'correo': 'no-es-correo'}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('nombre', respuesta.data)
        self.assertIn('correo', respuesta.data)
        self.assertEqual(SolicitudDemo.objects.count(), 0)

    def test_el_campo_trampa_descarta_robots_sin_delatarse(self):
        respuesta = self.client.post(URL, {**DATOS, 'sitio_web': 'http://spam.example'}, format='json')
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(SolicitudDemo.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_limite_por_hora(self):
        for _ in range(5):
            self.assertEqual(self.client.post(URL, DATOS, format='json').status_code, 201)
        self.assertEqual(self.client.post(URL, DATOS, format='json').status_code, 429)
