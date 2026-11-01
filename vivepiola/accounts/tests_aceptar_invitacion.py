"""
Aceptar una invitacion creando usuario y contrasena, sin cuenta de Google:
el enlace del correo basta para crear la cuenta en la comunidad y con el rol
que eligio el Administrador.
"""

from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import EstadoInvitacion, Invitacion, Rol, Usuario
from condominios.models import Condominio, Persona, Unidad

CLAVE = 'Vecino-del-101'


class AceptarInvitacionTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # el limite por hora se cuenta en la cache
        self.condominio = Condominio.objects.create(nombre='Edificio Los Robles')
        self.depto = Unidad.objects.create(condominio=self.condominio, identificador='Depto 101')
        self.admin = Usuario.objects.create_user(
            username='admin1', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.invitacion = Invitacion.objects.create(
            condominio=self.condominio, correo='ana@correo.cl', unidad=self.depto,
            rol_sugerido=Rol.RESIDENTE, creada_por=self.admin,
        )
        self.url = f'/api/auth/invitacion/{self.invitacion.codigo}/'

    def _aceptar(self, **cambios):
        datos = {'first_name': 'Ana', 'last_name': 'Rojas', 'username': 'ana.rojas', 'password': CLAVE}
        datos.update(cambios)
        return self.client.post(self.url, datos)

    def test_muestra_a_que_comunidad_invitan(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['comunidad'], 'Edificio Los Robles')
        self.assertEqual(respuesta.data['rol'], 'Residente')
        self.assertEqual(respuesta.data['unidad'], 'Depto 101')
        self.assertEqual(respuesta.data['usuario_sugerido'], 'ana')

    def test_crea_la_cuenta_con_el_rol_y_la_comunidad_de_la_invitacion(self):
        persona = Persona.objects.create(
            condominio=self.condominio, unidad=self.depto, rol_ocupacion='PROPIETARIO',
            nombre_completo='Ana Rojas', cedula_identidad='11.111.111-1', domicilio='Depto 101',
            correo_electronico='ANA@correo.cl',
        )
        respuesta = self._aceptar()

        self.assertEqual(respuesta.status_code, 201)
        self.assertIn('access', respuesta.data)
        usuario = Usuario.objects.get(username='ana.rojas')
        self.assertEqual(usuario.email, 'ana@correo.cl')
        self.assertEqual(usuario.rol, Rol.RESIDENTE)
        self.assertEqual(usuario.condominio, self.condominio)
        self.assertEqual(usuario.persona, persona)
        self.invitacion.refresh_from_db()
        self.assertEqual(self.invitacion.estado, EstadoInvitacion.ACEPTADA)
        self.assertEqual(self.invitacion.aceptada_por, usuario)

    def test_despues_entra_con_usuario_y_contrasena(self):
        self._aceptar()
        respuesta = self.client.post('/api/auth/login/', {'username': 'ana.rojas', 'password': CLAVE})
        self.assertEqual(respuesta.status_code, 200)

    def test_la_invitacion_sirve_una_sola_vez(self):
        self._aceptar()
        respuesta = self._aceptar(username='otra.cuenta')
        self.assertEqual(respuesta.status_code, 410)
        self.assertEqual(Usuario.objects.filter(email='ana@correo.cl').count(), 1)

    def test_invitacion_vencida_o_revocada(self):
        self.invitacion.expira_en = timezone.now() - timedelta(minutes=1)
        self.invitacion.save()
        self.assertEqual(self.client.get(self.url).status_code, 410)
        self.assertEqual(self._aceptar().status_code, 410)

        self.invitacion.expira_en = timezone.now() + timedelta(days=1)
        self.invitacion.estado = EstadoInvitacion.REVOCADA
        self.invitacion.save()
        self.assertEqual(self._aceptar().status_code, 410)

    def test_codigo_inexistente(self):
        self.assertEqual(self.client.get('/api/auth/invitacion/no-existe/').status_code, 404)

    def test_contrasena_debil_se_rechaza(self):
        respuesta = self._aceptar(password='12345678')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('password', respuesta.data)
        self.assertFalse(Usuario.objects.filter(username='ana.rojas').exists())

    def test_usuario_repetido_se_rechaza(self):
        respuesta = self._aceptar(username='ADMIN1')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('username', respuesta.data)

    def test_usuario_con_espacios_se_rechaza(self):
        self.assertEqual(self._aceptar(username='ana rojas').status_code, 400)

    def test_si_el_correo_ya_tiene_cuenta_lo_manda_a_iniciar_sesion(self):
        Usuario.objects.create_user(username='ana', password='x', email='Ana@correo.cl', rol=Rol.RESIDENTE)
        self.assertEqual(self._aceptar().status_code, 409)

    def test_el_correo_de_invitacion_lleva_a_la_pagina_nueva(self):
        self.client.force_authenticate(self.admin)
        self.client.post('/api/invitaciones/', {'correo': 'luis@correo.cl', 'rol_sugerido': Rol.FISCALIZADOR})
        codigo = Invitacion.objects.get(correo='luis@correo.cl').codigo
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f'/invitacion/{codigo}', mail.outbox[0].body)
