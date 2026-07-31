"""Tests de la carga del registro de copropietarios (Excel/CSV)."""

import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Permanencia, Persona, RolOcupacion, Unidad
from gastos_comunes.utils import exportar_multas_firmes
from multas.models import EstadoMulta, Multa, Ticket
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

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

    # -- Titulos de la Ley 21.442 y permanencia ------------------------

    def test_importa_usufructuario_y_comodatario(self):
        contenido = (
            'unidad,rol_ocupacion,nombre_completo,cedula_identidad,domicilio,correo_electronico,telefono\n'
            'Depto 601,USUFRUCTUARIO,Carla Usufructo,18.111.222-3,Depto 601,carla.u@test.cl,\n'
            'Depto 602,COMODATARIO,Dario Comodato,19.111.222-3,Depto 602,dario.c@test.cl,\n'
        )
        respuesta = self.importar(contenido)
        self.assertEqual(respuesta.data['filas_ok'], 2, respuesta.data['detalle_errores'])
        self.assertEqual(
            Persona.objects.get(cedula_identidad='18.111.222-3').rol_ocupacion, RolOcupacion.USUFRUCTUARIO,
        )

    def test_la_permanencia_es_independiente_del_titulo(self):
        contenido = (
            'unidad,rol_ocupacion,nombre_completo,cedula_identidad,domicilio,correo_electronico,telefono,permanencia\n'
            'Depto 701,ARRENDATARIO,Fija Larga,21.111.222-3,Depto 701,fija@test.cl,,PERMANENTE\n'
            'Depto 702,ARRENDATARIO,Turista Corta,22.111.222-3,Depto 702,turista@test.cl,,TRANSITORIO\n'
        )
        self.importar(contenido)
        self.assertEqual(
            Persona.objects.get(cedula_identidad='21.111.222-3').permanencia, Permanencia.PERMANENTE,
        )
        self.assertEqual(
            Persona.objects.get(cedula_identidad='22.111.222-3').permanencia, Permanencia.TRANSITORIO,
        )

    def test_permanencia_por_defecto_si_la_columna_no_viene(self):
        self.importar(CSV_VALIDO)  # el CSV clasico no trae la columna
        self.assertEqual(
            Persona.objects.get(cedula_identidad='10.111.222-3').permanencia, Permanencia.PERMANENTE,
        )

    def test_permanencia_invalida_rechaza_la_fila(self):
        contenido = (
            'unidad,rol_ocupacion,nombre_completo,cedula_identidad,domicilio,correo_electronico,telefono,permanencia\n'
            'Depto 801,PROPIETARIO,Mala Permanencia,23.111.222-3,Depto 801,mala@test.cl,,A VECES\n'
        )
        respuesta = self.importar(contenido)
        self.assertEqual(respuesta.data['filas_error'], 1)
        self.assertIn('permanencia invalida', respuesta.data['detalle_errores'][0]['errores'][0])

    def test_registra_el_vinculo_con_el_copropietario(self):
        contenido = (
            'unidad,rol_ocupacion,nombre_completo,cedula_identidad,domicilio,correo_electronico,telefono,permanencia,vinculo_copropietario\n'
            'Depto 901,OCUPANTE,Conyuge Del Dueno,24.111.222-3,Depto 901,conyuge@test.cl,,PERMANENTE,CONYUGE\n'
        )
        respuesta = self.importar(contenido)
        self.assertEqual(respuesta.data['filas_ok'], 1, respuesta.data['detalle_errores'])
        self.assertEqual(
            Persona.objects.get(cedula_identidad='24.111.222-3').vinculo_copropietario, 'CONYUGE',
        )


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ObligadoAlPagoTestCase(APITestCase):
    """
    La Ley 21.442 hace al copropietario obligado principal al pago: si multan
    al arrendatario, el cargo del gasto comun igual se emite a nombre del dueño.
    """

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Cobro')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 500')
        cls.dueno = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Elena Propietaria', cedula_identidad='10.000.000-1',
            domicilio='Depto 500', correo_electronico='elena@test.local',
        )
        cls.arrendatario = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.ARRENDATARIO,
            nombre_completo='Fabian Arrendatario', cedula_identidad='20.000.000-2',
            domicilio='Depto 500', correo_electronico='fabian@test.local',
        )
        cls.admin = Usuario.objects.create_user(
            username='admin_cobro', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('3.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _multa_firme(self, infractor):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=infractor,
            descripcion='Hecho', fecha_hecho=timezone.now(),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=infractor, infraccion=self.infraccion,
            monto=Decimal('3.00'), estado=EstadoMulta.FIRME,
        )

    def test_la_unidad_conoce_a_su_propietario(self):
        self.assertEqual(self.unidad.propietario, self.dueno)

    def test_el_cobro_va_al_dueno_aunque_multen_al_arrendatario(self):
        self._multa_firme(self.arrendatario)
        lote = exportar_multas_firmes(self.condominio, '2026-07', self.admin)

        contenido = lote.archivo_csv.read().decode('utf-8-sig')
        encabezado, fila = contenido.strip().splitlines()[:2]

        self.assertIn('obligado_al_pago', encabezado)
        self.assertIn('Elena Propietaria', fila, 'el cargo debe emitirse al dueño de la unidad')
        self.assertIn('10.000.000-1', fila)
        # El infractor se conserva para que el cargo sea explicable.
        self.assertIn('Fabian Arrendatario', fila)

    def test_sin_propietario_registrado_responde_el_infractor(self):
        self.dueno.delete()
        self._multa_firme(self.arrendatario)
        lote = exportar_multas_firmes(self.condominio, '2026-08', self.admin)
        self.assertIn('Fabian Arrendatario', lote.archivo_csv.read().decode('utf-8-sig'))
