"""
Eliminar la propia cuenta desde la app: se borran los datos personales y el
acceso, pero las denuncias quedan como registro del procedimiento.
"""

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import PermisoDenuncia, Rol, Usuario
from condominios.models import Condominio, Unidad
from multas.models import Ticket

URL = '/api/auth/me/eliminar/'


class EliminarCuentaTestCase(APITestCase):
    def setUp(self):
        self.condominio = Condominio.objects.create(nombre='Edificio Los Robles')
        self.depto = Unidad.objects.create(condominio=self.condominio, identificador='Depto 101')
        self.guardia = Usuario.objects.create_user(
            username='guardia', password='Demo12345', email='guardia@correo.cl',
            first_name='Juan', last_name='Perez', telefono='+56911111111',
            rol=Rol.FISCALIZADOR, condominio=self.condominio,
        )
        self.admin = Usuario.objects.create_user(
            username='admin1', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )

    def test_borra_datos_personales_y_conserva_la_denuncia(self):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.depto, creado_por=self.guardia,
            descripcion='Ruido', fecha_hecho=timezone.now(),
        )
        PermisoDenuncia.objects.create(usuario=self.guardia, suspendido=True)
        self.client.force_authenticate(self.guardia)

        respuesta = self.client.post(URL, {'confirmacion': 'eliminar'})

        self.assertEqual(respuesta.status_code, 204)
        self.guardia.refresh_from_db()
        self.assertFalse(self.guardia.is_active)
        self.assertEqual(self.guardia.username, f'eliminado-{self.guardia.pk}')
        self.assertEqual(self.guardia.email, '')
        self.assertEqual(self.guardia.telefono, '')
        self.assertEqual(self.guardia.get_full_name(), 'Cuenta eliminada')
        self.assertFalse(self.guardia.has_usable_password())
        self.assertFalse(PermisoDenuncia.objects.filter(usuario=self.guardia).exists())
        ticket.refresh_from_db()
        self.assertEqual(ticket.creado_por, self.guardia)

    def test_ya_no_puede_entrar(self):
        self.client.force_authenticate(self.guardia)
        self.client.post(URL, {'confirmacion': 'ELIMINAR'})
        self.client.force_authenticate(None)

        respuesta = self.client.post(
            '/api/auth/login/', {'username': 'guardia', 'password': 'Demo12345'},
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_exige_escribir_eliminar(self):
        self.client.force_authenticate(self.guardia)
        respuesta = self.client.post(URL, {'confirmacion': 'si'})
        self.assertEqual(respuesta.status_code, 400)
        self.guardia.refresh_from_db()
        self.assertTrue(self.guardia.is_active)

    def test_el_unico_administrador_no_deja_la_comunidad_sin_administrador(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(URL, {'confirmacion': 'ELIMINAR'})
        self.assertEqual(respuesta.status_code, 409)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_un_administrador_con_reemplazo_si_puede(self):
        Usuario.objects.create_user(
            username='admin2', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(URL, {'confirmacion': 'ELIMINAR'})
        self.assertEqual(respuesta.status_code, 204)

    def test_sin_sesion_no(self):
        self.assertEqual(self.client.post(URL, {'confirmacion': 'ELIMINAR'}).status_code, 401)
