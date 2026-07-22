"""Tests de la carga del registro de copropietarios (Excel/CSV)."""

import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, Unidad

MEDIA_TEMP = tempfile.mkdtemp(prefix='debido_test_media_')

CSV_VALIDO = (
    'unidad,rol_ocupacion,nombre_completo,cedula_identidad,domicilio,correo_electronico,telefono\n'
    'Depto 301,PROPIETARIO,Ana Rojas,10.111.222-3,Depto 301,ana@test.cl,+56911111111\n'
    'Depto 301,ARRENDATARIO,Luis Diaz,12.333.444-5,Depto 301,luis@test.cl,\n'
    'Depto 402,OCUPANTE,Mario Vera,14.555.666-7,Depto 402,mario@test.cl,\n'
)

CSV_CON_ERRORES = (
    'unidad,rol_ocupacion,nombre_completo,cedula_identidad,domicilio,correo_electronico,telefono\n'
    'Depto 501,PROPIETARIO,Carla Munoz,15.111.222-3,Depto 501,carla@test.cl,\n'
    'Depto 502,DUENO,Rol Invalido,16.111.222-3,Depto 502,rol@test.cl,\n'
    'Depto 503,OCUPANTE,Sin Correo,17.111.222-3,Depto 503,correo-invalido,\n'
)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ImportacionRegistroTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Import')
        cls.administrador = Usuario.objects.create_user(
            username='admin_import', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.residente = Usuario.objects.create_user(
            username='residente_import', password='x', rol=Rol.RESIDENTE, condominio=cls.condominio,
        )

    def importar(self, contenido, usuario=None):
        self.client.force_authenticate(usuario or self.administrador)
        archivo = SimpleUploadedFile('registro.csv', contenido.encode('utf-8'), content_type='text/csv')
        return self.client.post('/api/registro/importar/', {'archivo': archivo}, format='multipart')

    def test_importacion_valida_crea_unidades_y_personas(self):
        respuesta = self.importar(CSV_VALIDO)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['filas_ok'], 3)
        self.assertEqual(respuesta.data['filas_error'], 0)
        self.assertEqual(Unidad.objects.filter(condominio=self.condominio).count(), 2)
        self.assertEqual(Persona.objects.filter(condominio=self.condominio).count(), 3)

    def test_importacion_reporta_filas_invalidas_sin_abortar(self):
        respuesta = self.importar(CSV_CON_ERRORES)
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.data['filas_ok'], 1)
        self.assertEqual(respuesta.data['filas_error'], 2)
        self.assertEqual(respuesta.data['estado'], 'CON_ERRORES')
        errores = {e['fila'] for e in respuesta.data['detalle_errores']}
        self.assertEqual(errores, {3, 4})

    def test_reimportar_actualiza_sin_duplicar(self):
        self.importar(CSV_VALIDO)
        respuesta = self.importar(CSV_VALIDO)
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Persona.objects.filter(condominio=self.condominio).count(), 3)

    def test_solo_administrador_importa(self):
        respuesta = self.importar(CSV_VALIDO, usuario=self.residente)
        self.assertEqual(respuesta.status_code, 403)
