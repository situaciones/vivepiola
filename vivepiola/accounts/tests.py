"""
Tests del ingreso universal con Google y del flujo de invitacion delegada.

Se ejercitan con el modo simulado de Google (credencial "mock:correo"), que es
el mismo camino que recorre un ID token real una vez verificado: lo unico que
cambia es de donde sale el correo.
"""

from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import EstadoInvitacion, Invitacion, Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad


@override_settings(GOOGLE_OAUTH_CLIENT_ID='', GOOGLE_OAUTH_MOCK=True)
class IngresoGoogleTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Comunidad RBAC')
        cls.otra = Condominio.objects.create(nombre='Comunidad Ajena')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 404')
        cls.administrador = Usuario.objects.create_user(
            username='admin_rbac', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )

    def _entrar_con_google(self, correo, codigo=''):
        return self.client.post('/api/auth/google/', {'credential': f'mock:{correo}', 'codigo': codigo})

    # -- Registro sin invitacion --------------------------------------

    def test_registro_sin_invitacion_queda_pendiente_y_sin_acceso(self):
        respuesta = self._entrar_con_google('desconocido@gmail.com')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['rol'], Rol.PENDIENTE)
        self.assertIsNone(respuesta.data['condominio_id'])

        usuario = Usuario.objects.get(email='desconocido@gmail.com')
        self.assertFalse(usuario.has_usable_password())  # solo entra por Google

        # Con rol PENDIENTE ve su perfil pero ningun modulo del flujo.
        self.client.force_authenticate(usuario)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        for ruta in ('/api/multas/', '/api/tickets/', '/api/condominios/', '/api/novedades/'):
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)

    def test_credencial_invalida_en_modo_simulado(self):
        respuesta = self.client.post('/api/auth/google/', {'credential': 'token-real-no-valido'})
        self.assertEqual(respuesta.status_code, 400)

    # -- Invitacion delegada del Administrador ------------------------

    def test_administrador_invita_y_el_invitado_entra_con_su_rol(self):
        self.client.force_authenticate(self.administrador)
        respuesta = self.client.post('/api/invitaciones/', {
            'correo': 'vecina@gmail.com', 'unidad': self.unidad.id, 'rol_sugerido': Rol.RESIDENTE,
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('vecina@gmail.com', mail.outbox[0].to)

        self.client.force_authenticate(None)
        ingreso = self._entrar_con_google('vecina@gmail.com')
        self.assertEqual(ingreso.data['rol'], Rol.RESIDENTE)
        self.assertEqual(ingreso.data['condominio_id'], self.condominio.id)

        invitacion = Invitacion.objects.get(correo='vecina@gmail.com')
        self.assertEqual(invitacion.estado, EstadoInvitacion.ACEPTADA)
        self.assertIsNotNone(invitacion.aceptada_en)

    def test_invitacion_vincula_la_ficha_de_persona_por_correo(self):
        persona = Persona.objects.create(
            condominio=self.condominio, unidad=self.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Marta Copropietaria', cedula_identidad='44.444.444-4',
            domicilio='Depto 404', correo_electronico='marta@gmail.com',
        )
        self.client.force_authenticate(self.administrador)
        self.client.post('/api/invitaciones/', {'correo': 'marta@gmail.com', 'rol_sugerido': Rol.RESIDENTE})

        self.client.force_authenticate(None)
        self._entrar_con_google('marta@gmail.com')
        self.assertEqual(Usuario.objects.get(email='marta@gmail.com').persona_id, persona.id)

    def test_administrador_no_puede_invitar_administradores(self):
        self.client.force_authenticate(self.administrador)
        respuesta = self.client.post('/api/invitaciones/', {
            'correo': 'otro@gmail.com', 'rol_sugerido': Rol.ADMINISTRADOR,
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('rol_sugerido', respuesta.data)

    def test_invitacion_revocada_no_asigna_rol(self):
        self.client.force_authenticate(self.administrador)
        creada = self.client.post('/api/invitaciones/', {'correo': 'tarde@gmail.com', 'rol_sugerido': Rol.COMITE})
        self.client.post(f"/api/invitaciones/{creada.data['id']}/revocar/")

        self.client.force_authenticate(None)
        ingreso = self._entrar_con_google('tarde@gmail.com')
        self.assertEqual(ingreso.data['rol'], Rol.PENDIENTE)

    # -- Codigo Unico de Comunidad ------------------------------------

    def test_codigo_de_comunidad_asocia_pero_deja_pendiente(self):
        self.condominio.refresh_from_db()
        codigo = self.condominio.codigo_comunidad
        self.assertTrue(codigo, 'el condominio debe nacer con su codigo unico')

        ingreso = self._entrar_con_google('vecino.codigo@gmail.com', codigo=codigo)
        self.assertEqual(ingreso.data['rol'], Rol.PENDIENTE)
        self.assertEqual(ingreso.data['condominio_id'], self.condominio.id)

    def test_codigo_solo_visible_para_el_administrador(self):
        residente = Usuario.objects.create_user(
            username='res_rbac', password='x', rol=Rol.RESIDENTE, condominio=self.condominio,
        )
        self.client.force_authenticate(residente)
        datos = self.client.get('/api/condominios/').data
        fila = (datos['results'] if isinstance(datos, dict) else datos)[0]
        self.assertIsNone(fila['codigo_comunidad'])

        self.client.force_authenticate(self.administrador)
        datos = self.client.get('/api/condominios/').data
        fila = (datos['results'] if isinstance(datos, dict) else datos)[0]
        self.assertEqual(fila['codigo_comunidad'], self.condominio.codigo_comunidad)

    # -- Confirmacion del rol final -----------------------------------

    def test_administrador_confirma_rol_de_cuenta_pendiente(self):
        self.condominio.refresh_from_db()
        self._entrar_con_google('porconfirmar@gmail.com', codigo=self.condominio.codigo_comunidad)
        pendiente = Usuario.objects.get(email='porconfirmar@gmail.com')

        self.client.force_authenticate(self.administrador)
        listado = self.client.get('/api/usuarios/pendientes/')
        self.assertEqual(listado.status_code, 200)
        self.assertIn(pendiente.id, [u['id'] for u in listado.data])

        respuesta = self.client.post(
            f'/api/usuarios/{pendiente.id}/asignar-rol/', {'rol': Rol.FISCALIZADOR},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.rol, Rol.FISCALIZADOR)
        # Ya asignado, accede a los modulos que su rol habilita.
        self.client.force_authenticate(pendiente)
        self.assertEqual(self.client.get('/api/tickets/').status_code, 200)

    def test_administrador_no_toca_cuentas_de_otra_comunidad(self):
        ajeno = Usuario.objects.create_user(
            username='ajeno', password='x', rol=Rol.PENDIENTE, condominio=self.otra,
        )
        self.client.force_authenticate(self.administrador)
        respuesta = self.client.post(f'/api/usuarios/{ajeno.id}/asignar-rol/', {'rol': Rol.RESIDENTE})
        self.assertEqual(respuesta.status_code, 403)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.rol, Rol.PENDIENTE)
