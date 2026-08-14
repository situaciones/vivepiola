"""
Tests del camino de entrada de todo condominio nuevo:

    subir reglamento PDF -> extraer texto -> la IA sugiere borradores
    -> un humano confirma -> la infraccion queda ACTIVA y recien ahi
    puede fundamentar una multa.

Sin este camino, un condominio no puede cursar ni una sola multa. Por eso
aqui se prueba completo, incluyendo lo que pasa cuando el PDF viene mal.
"""

import io
import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, Ticket
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo, Reglamento

MEDIA_TEMP = tempfile.mkdtemp(prefix='debido_test_reglamentos_')

REGLAMENTO_TEXTO = """REGLAMENTO DE COPROPIEDAD
Art. 10 Los copropietarios deben mantener el aseo de los espacios comunes.
Art. 12 Se prohibe generar ruidos molestos entre las 22:00 y las 08:00 horas.
Art. 18 Las mascotas deben circular con correa por los espacios comunes.
Art. 25 El estacionamiento de visitas tiene un maximo de 24 horas continuas."""


def lista(respuesta):
    """El listado viene paginado o plano segun configuracion; aqui da igual."""
    datos = respuesta.data
    if isinstance(datos, dict) and 'results' in datos:
        return datos['results']
    return datos

SUGERENCIAS_IA = [
    {
        'codigo': 'RUIDO-01',
        'descripcion': 'Ruidos molestos despues de las 22:00 horas',
        'articulo_referencia': 'Art. 12',
        'monto': 1.5,
        'unidad_monto': 'UF',
        'gravedad': 'LEVE',
        'texto_fuente': 'Se prohibe generar ruidos molestos entre las 22:00 y las 08:00.',
    },
    {
        'codigo': 'MASCOTA-01',
        'descripcion': 'Mascota sin correa en espacios comunes',
        'articulo_referencia': 'Art. 18',
        'monto': 2,
        'unidad_monto': 'UF',
        'gravedad': 'GRAVE',
        'texto_fuente': 'Las mascotas deben circular con correa por los espacios comunes.',
    },
]


def pdf_con_texto(texto):
    """Un PDF real y legible, como el que sube un administrador."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    for i, linea in enumerate(texto.splitlines()):
        c.drawString(72, 720 - i * 14, linea)
    c.save()
    return SimpleUploadedFile('reglamento.pdf', buffer.getvalue(), content_type='application/pdf')


def pdf_escaneado():
    """
    Un PDF sin capa de texto: exactamente lo que produce un escaner de oficina
    al digitalizar el reglamento en papel. pdfplumber no extrae nada de aqui.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.rect(72, 500, 400, 200, fill=0)  # solo un dibujo, cero texto
    c.save()
    return SimpleUploadedFile('escaneado.pdf', buffer.getvalue(), content_type='application/pdf')


def archivo_corrupto():
    """Un archivo que dice ser PDF y no lo es (se subio el que no era)."""
    return SimpleUploadedFile('roto.pdf', b'esto no es un pdf', content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class BaseReglamentoTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Reglamento')
        cls.admin = Usuario.objects.create_user(
            username='admin_regl', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_regl', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.residente = Usuario.objects.create_user(
            username='residente_regl', password='x', rol=Rol.RESIDENTE, condominio=cls.condominio,
        )

    def subir(self, archivo, usuario=None):
        self.client.force_authenticate(usuario or self.admin)
        return self.client.post('/api/reglamentos/', {'archivo_pdf': archivo}, format='multipart')

    def generar_borradores(self, reglamento_id, sugerencias=None, usuario=None):
        self.client.force_authenticate(usuario or self.admin)
        with patch(
            'reglamentos.views.sugerir_infracciones_desde_texto',
            return_value=SUGERENCIAS_IA if sugerencias is None else sugerencias,
        ):
            return self.client.post(f'/api/reglamentos/{reglamento_id}/generar-borradores-ia/')


class CargaDeReglamentoTestCase(BaseReglamentoTestCase):
    """El primer paso: subir el PDF y extraer su texto."""

    def test_sube_el_pdf_y_extrae_el_texto(self):
        respuesta = self.subir(pdf_con_texto(REGLAMENTO_TEXTO))
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        reglamento = Reglamento.objects.get(id=respuesta.data['id'])
        self.assertEqual(reglamento.condominio, self.condominio)
        self.assertEqual(reglamento.cargado_por, self.admin)
        self.assertIn('ruidos molestos', reglamento.texto_extraido)
        self.assertTrue(reglamento.vigente, 'el reglamento recien subido es el vigente')

    def test_solo_el_administrador_sube_el_reglamento(self):
        for usuario in (self.comite, self.residente):
            respuesta = self.subir(pdf_con_texto(REGLAMENTO_TEXTO), usuario=usuario)
            self.assertEqual(respuesta.status_code, 403, f'{usuario.rol} no debe poder subir el reglamento')

    def test_un_pdf_escaneado_no_se_reporta_como_exito(self):
        """
        Si el reglamento viene escaneado (imagen, sin texto), el administrador
        tiene que enterarse AL SUBIRLO, no dos pasos despues. Si no, cree que
        el sistema quedo configurado cuando en realidad no puede operar.
        """
        respuesta = self.subir(pdf_escaneado())
        self.assertEqual(
            respuesta.status_code, 400,
            'un PDF sin texto extraible debe rechazarse al subirlo, no aceptarse en silencio',
        )
        self.assertIn('texto', str(respuesta.data).lower())
        self.assertFalse(Reglamento.objects.exists(), 'no debe quedar un reglamento inservible guardado')

    def test_un_archivo_corrupto_da_un_error_claro(self):
        respuesta = self.subir(archivo_corrupto())
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertFalse(Reglamento.objects.exists())


class BorradoresIATestCase(BaseReglamentoTestCase):
    """El segundo paso: la IA propone, nadie decide todavia."""

    def setUp(self):
        respuesta = self.subir(pdf_con_texto(REGLAMENTO_TEXTO))
        self.reglamento = Reglamento.objects.get(id=respuesta.data['id'])

    def test_la_ia_propone_y_todo_queda_en_borrador(self):
        respuesta = self.generar_borradores(self.reglamento.id)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(len(respuesta.data['borradores']), 2)

        infracciones = InfraccionCatalogo.objects.filter(condominio=self.condominio)
        self.assertEqual(infracciones.count(), 2)
        for infraccion in infracciones:
            self.assertEqual(infraccion.estado, EstadoInfraccion.BORRADOR)
            self.assertTrue(infraccion.generado_por_ia)
            self.assertTrue(infraccion.texto_fuente, 'sin cita del reglamento no hay trazabilidad')

        self.reglamento.refresh_from_db()
        self.assertTrue(self.reglamento.procesado_ia)

    def test_nunca_degrada_una_infraccion_ya_confirmada(self):
        """Una multa cursada depende de la infraccion vigente: la IA no la pisa."""
        self.generar_borradores(self.reglamento.id)
        ruido = InfraccionCatalogo.objects.get(codigo='RUIDO-01')
        ruido.estado = EstadoInfraccion.ACTIVA
        ruido.monto = Decimal('9.00')
        ruido.save()

        respuesta = self.generar_borradores(self.reglamento.id)
        self.assertIn('RUIDO-01', respuesta.data['omitidas'])

        ruido.refresh_from_db()
        self.assertEqual(ruido.estado, EstadoInfraccion.ACTIVA)
        self.assertEqual(ruido.monto, Decimal('9.00'), 'el monto confirmado por un humano no se toca')

    def test_sin_texto_extraido_avisa_en_vez_de_llamar_a_la_ia(self):
        self.reglamento.texto_extraido = ''
        self.reglamento.save(update_fields=['texto_extraido'])
        respuesta = self.generar_borradores(self.reglamento.id)
        self.assertEqual(respuesta.status_code, 400)

    def test_si_la_ia_falla_avisa_y_no_deja_basura(self):
        self.client.force_authenticate(self.admin)
        with patch(
            'reglamentos.views.sugerir_infracciones_desde_texto',
            side_effect=RuntimeError('ANTHROPIC_API_KEY no esta configurada en el .env'),
        ):
            respuesta = self.client.post(f'/api/reglamentos/{self.reglamento.id}/generar-borradores-ia/')
        self.assertEqual(respuesta.status_code, 502)
        self.assertFalse(InfraccionCatalogo.objects.exists())

    def test_un_monto_no_numerico_de_la_ia_no_rompe_el_lote(self):
        """
        La IA es un tercero: puede devolver 'cinco UF' donde se esperaba un
        numero. Eso no puede tumbar la carga completa del catalogo.
        """
        sugerencias = [
            {**SUGERENCIAS_IA[0], 'monto': 'cinco UF'},
            SUGERENCIAS_IA[1],
        ]
        respuesta = self.generar_borradores(self.reglamento.id, sugerencias=sugerencias)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(
            InfraccionCatalogo.objects.filter(codigo='MASCOTA-01').exists(),
            'una sugerencia mala no puede impedir que se carguen las buenas',
        )

    def test_no_se_meten_borradores_en_el_condominio_ajeno(self):
        otro = Condominio.objects.create(nombre='Condominio Vecino')
        intruso = Usuario.objects.create_user(
            username='admin_vecino', password='x', rol=Rol.ADMINISTRADOR, condominio=otro,
        )
        respuesta = self.generar_borradores(self.reglamento.id, usuario=intruso)
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(InfraccionCatalogo.objects.filter(condominio=otro).exists())


class ConfirmacionDelCatalogoTestCase(BaseReglamentoTestCase):
    """
    El tercer paso y el control humano obligatorio: sin confirmacion, el
    condominio no puede cursar ninguna multa.
    """

    def setUp(self):
        respuesta = self.subir(pdf_con_texto(REGLAMENTO_TEXTO))
        self.reglamento = Reglamento.objects.get(id=respuesta.data['id'])
        self.generar_borradores(self.reglamento.id)
        self.ruido = InfraccionCatalogo.objects.get(codigo='RUIDO-01')

    def test_el_comite_ve_los_borradores_que_debe_confirmar(self):
        """La app le dice al administrador 'el Comite debe confirmarlas en su panel'."""
        self.client.force_authenticate(self.comite)
        respuesta = self.client.get('/api/infracciones/?estado=BORRADOR')
        codigos = {i['codigo'] for i in lista(respuesta)}
        self.assertEqual(
            codigos, {'RUIDO-01', 'MASCOTA-01'},
            'si el Comite no ve los borradores, el catalogo nunca se activa',
        )

    def test_el_comite_confirma_una_infraccion(self):
        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(f'/api/infracciones/{self.ruido.id}/confirmar/')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        self.ruido.refresh_from_db()
        self.assertEqual(self.ruido.estado, EstadoInfraccion.ACTIVA)
        self.assertEqual(self.ruido.confirmado_por, self.comite)
        self.assertIsNotNone(self.ruido.fecha_confirmacion)

    def test_el_administrador_tambien_puede_confirmar(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(f'/api/infracciones/{self.ruido.id}/confirmar/')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.ruido.refresh_from_db()
        self.assertEqual(self.ruido.estado, EstadoInfraccion.ACTIVA)

    def test_el_comite_rechaza_un_borrador_equivocado(self):
        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(f'/api/infracciones/{self.ruido.id}/rechazar/')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.ruido.refresh_from_db()
        self.assertEqual(self.ruido.estado, EstadoInfraccion.INACTIVA)

    def test_el_residente_no_confirma_ni_ve_borradores(self):
        self.client.force_authenticate(self.residente)
        self.assertEqual(
            self.client.post(f'/api/infracciones/{self.ruido.id}/confirmar/').status_code, 403,
        )
        listado = self.client.get('/api/infracciones/')
        self.assertEqual(
            len(lista(listado)), 0,
            'el residente solo ve el catalogo vigente, y aun no hay ninguno',
        )

    def test_no_se_confirma_el_catalogo_de_otro_condominio(self):
        otro = Condominio.objects.create(nombre='Condominio Vecino')
        intruso = Usuario.objects.create_user(
            username='comite_vecino', password='x', rol=Rol.COMITE, condominio=otro,
        )
        self.client.force_authenticate(intruso)
        respuesta = self.client.post(f'/api/infracciones/{self.ruido.id}/confirmar/')
        self.assertEqual(respuesta.status_code, 404)
        self.ruido.refresh_from_db()
        self.assertEqual(self.ruido.estado, EstadoInfraccion.BORRADOR)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class CaminoCompletoHastaLaMultaTestCase(APITestCase):
    """
    La prueba que cierra el circuito: desde el PDF hasta una multa aprobada.
    Y la garantia legal: un borrador de IA nunca puede fundamentar una sancion.
    """

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Circuito')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 101')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Ines Propietaria', cedula_identidad='11.222.333-4',
            domicilio='Depto 101', correo_electronico='ines@test.local',
        )
        cls.admin = Usuario.objects.create_user(
            username='admin_circuito', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_circuito', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )

    def _multa_en_revision(self):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Ruido a las 2 de la manana', fecha_hecho=timezone.now(),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, monto=Decimal('0.00'), estado=EstadoMulta.EN_REVISION,
        )

    def test_del_pdf_a_la_multa_aprobada(self):
        # 1. El administrador sube el reglamento.
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(
            '/api/reglamentos/',
            {'archivo_pdf': pdf_con_texto(REGLAMENTO_TEXTO)},
            format='multipart',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        reglamento_id = respuesta.data['id']

        # 2. La IA propone borradores.
        with patch('reglamentos.views.sugerir_infracciones_desde_texto', return_value=SUGERENCIAS_IA):
            respuesta = self.client.post(f'/api/reglamentos/{reglamento_id}/generar-borradores-ia/')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        infraccion = InfraccionCatalogo.objects.get(codigo='RUIDO-01')

        # 3. Antes de confirmar, esa infraccion NO puede fundamentar una multa.
        multa = self._multa_en_revision()
        self.client.force_authenticate(self.comite)
        rechazo = self.client.post(
            f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': infraccion.id}, format='json',
        )
        self.assertEqual(
            rechazo.status_code, 400,
            'una sancion no puede fundarse en un borrador de IA sin revision humana',
        )

        # 4. El comite confirma: recien ahi entra al catalogo vigente.
        confirmacion = self.client.post(f'/api/infracciones/{infraccion.id}/confirmar/')
        self.assertEqual(confirmacion.status_code, 200, confirmacion.data)

        # 5. Y ahora si se puede cursar la multa.
        aprobacion = self.client.post(
            f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': infraccion.id}, format='json',
        )
        self.assertEqual(aprobacion.status_code, 200, aprobacion.data)

        multa.refresh_from_db()
        self.assertEqual(multa.infraccion, infraccion)
        self.assertEqual(multa.monto, infraccion.monto)
