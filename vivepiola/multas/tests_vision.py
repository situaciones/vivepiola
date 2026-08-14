"""
Tests del analisis de evidencia.

Tres cosas se cuidan aqui: que sin proveedor configurado el sistema siga
funcionando igual, que una foto que llega despues del reporte todavia alcance a
influir en el encuadre, y que el analisis no construya perfiles de residentes.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, Ticket
from multas.vision import PROMPT_VISION, analizar_evidencias
from reglamentos.models import EstadoInfraccion, Gravedad, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_vision_')

PNG_1PX = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c636000000200010005fe02fa0000000049454e44ae426082'
)


def _cliente_gemini(texto):
    """Doble del cliente: solo necesita models.generate_content(...).text."""
    llamadas = []

    def _generar(**kwargs):
        llamadas.append(kwargs)
        return SimpleNamespace(text=texto)

    cliente = SimpleNamespace(models=SimpleNamespace(generate_content=_generar))
    return cliente, llamadas


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class AnalisisDeEvidenciaTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre='Condominio Vision', cortesias_antes_de_multar=0,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 404')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Vera Vision', cedula_identidad='4.040.404-0',
            domicilio='Depto 404', correo_electronico='vera@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_vision', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='ESTAC-01',
            descripcion='Estacionar en zona de circulacion',
            articulo_referencia='Art. 22', monto=Decimal('3.00'),
            gravedad=Gravedad.LEVE, estado=EstadoInfraccion.ACTIVA,
        )

    def _ticket(self, descripcion='Auto mal puesto'):
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
            'descripcion': descripcion, 'fecha_hecho': timezone.now().isoformat(),
        }, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Ticket.objects.get(id=respuesta.data['id'])

    def _subir_foto(self, ticket):
        self.client.force_authenticate(self.conserje)
        imagen = SimpleUploadedFile('evidencia.png', PNG_1PX, content_type='image/png')
        return self.client.post(
            f'/api/tickets/{ticket.id}/evidencia/', {'imagen': imagen}, format='multipart',
        )

    def _subir_video(self, ticket):
        self.client.force_authenticate(self.conserje)
        video = SimpleUploadedFile('clip.mp4', b'\x00' * 2048, content_type='video/mp4')
        return self.client.post(
            f'/api/tickets/{ticket.id}/evidencia/', {'video': video}, format='multipart',
        )

    # -- Sin proveedor el sistema no cambia -----------------------------

    def test_sin_clave_no_hay_analisis_y_todo_sigue_igual(self):
        """La evidencia queda en el expediente y la sigue viendo una persona."""
        ticket = self._ticket()
        respuesta = self._subir_foto(ticket)

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.analisis_evidencia, '')
        self.assertEqual(analizar_evidencias(ticket), ('', 0))

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_si_el_proveedor_se_cae_la_denuncia_no_se_pierde(self):
        ticket = self._ticket()
        with patch('google.genai.Client', side_effect=RuntimeError('503')):
            respuesta = self._subir_foto(ticket)

        self.assertEqual(respuesta.status_code, 201, 'la evidencia se guarda igual')
        ticket.refresh_from_db()
        self.assertEqual(ticket.analisis_evidencia, '')

    # -- Que analiza ----------------------------------------------------

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_la_foto_se_analiza_y_queda_escrita_en_el_expediente(self):
        ticket = self._ticket()
        cliente, llamadas = _cliente_gemini(
            'Se observa un vehiculo detenido sobre la rampa de acceso peatonal.'
        )
        with patch('google.genai.Client', return_value=cliente):
            self._subir_foto(ticket)

        ticket.refresh_from_db()
        self.assertIn('rampa de acceso', ticket.analisis_evidencia)
        self.assertEqual(len(llamadas), 1)

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_el_video_tambien_se_manda_a_analizar(self):
        """Es la razon de usar este proveedor: ingiere el archivo completo."""
        ticket = self._ticket()
        cliente, llamadas = _cliente_gemini('Se aprecia un forcejeo en el pasillo.')
        with patch('google.genai.Client', return_value=cliente):
            self._subir_video(ticket)

        ticket.refresh_from_db()
        self.assertIn('forcejeo', ticket.analisis_evidencia)
        self.assertEqual(len(llamadas), 1)

    @override_settings(GEMINI_API_KEY='clave-de-prueba', VISION_MAX_BYTES_POR_PIEZA=100)
    def test_una_pieza_demasiado_pesada_se_omite_del_analisis(self):
        """Sigue siendo prueba en el expediente; solo no entra al analisis."""
        ticket = self._ticket()
        cliente, llamadas = _cliente_gemini('No deberia llamarse')
        with patch('google.genai.Client', return_value=cliente):
            self._subir_video(ticket)

        self.assertEqual(len(llamadas), 0)
        self.assertEqual(ticket.evidencias.count(), 1, 'la evidencia igual se guarda')

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_el_analisis_se_recorta_para_no_desbordar_el_expediente(self):
        ticket = self._ticket()
        cliente, _ = _cliente_gemini('X' * 5000)
        with override_settings(VISION_MAX_CARACTERES=200):
            with patch('google.genai.Client', return_value=cliente):
                self._subir_foto(ticket)

        ticket.refresh_from_db()
        self.assertEqual(len(ticket.analisis_evidencia), 200)

    # -- Privacidad -----------------------------------------------------

    def test_la_instruccion_prohibe_describir_a_las_personas(self):
        """
        Un sistema que anotara "hombre de 50, polera roja" estaria armando
        perfiles de residentes desde las camaras. Eso es justo lo que la
        Ley 19.628 busca evitar.
        """
        self.assertIn('PROHIBIDO', PROMPT_VISION)
        for prohibido in ('describir a las personas', 'identificarlas', 'vestimenta', 'rostro'):
            self.assertIn(prohibido, PROMPT_VISION)

    def test_la_instruccion_prohibe_calificar_la_infraccion(self):
        """Describir es un paso; decidir si hay infraccion es otro, con sus reglas."""
        self.assertIn('afirmar que se cometio una infraccion', PROMPT_VISION)
        self.assertIn('inventar lo que no se ve', PROMPT_VISION)

    # -- La foto que llega tarde igual influye --------------------------

    @override_settings(GEMINI_API_KEY='clave-de-prueba', ANTHROPIC_API_KEY='sk-ant-x')
    def test_una_foto_posterior_reevalua_el_expediente_no_cursado(self):
        """
        El reporte entra primero y la foto llega segundos despues por otra
        llamada. Sin reevaluar, la evidencia llegaba tarde para influir.
        """
        respuesta_ia = SimpleNamespace(content=[SimpleNamespace(
            type='text',
            text='{"codigo": "ESTAC-01", "confianza": 95, "fundamento": "La imagen lo confirma."}',
        )])
        anthropic_falso = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kw: respuesta_ia),
        )
        # El reporte inicial no calza con nada: queda esperando.
        vacio = SimpleNamespace(content=[SimpleNamespace(
            type='text', text='{"codigo": null, "confianza": 0, "fundamento": "Sin datos."}',
        )])
        with patch('anthropic.Anthropic', return_value=SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kw: vacio),
        )):
            ticket = self._ticket(descripcion='Algo raro en el estacionamiento')

        multa = Multa.objects.get(ticket=ticket)
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)

        cliente, _ = _cliente_gemini('Un vehiculo ocupa la zona de circulacion demarcada.')
        with patch('google.genai.Client', return_value=cliente):
            with patch('anthropic.Anthropic', return_value=anthropic_falso):
                self._subir_foto(ticket)

        multa.refresh_from_db()
        self.assertEqual(multa.infraccion, self.infraccion, 'la foto permitio encuadrarlo')
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertIn('se analizo la evidencia', ' '.join(
            multa.historial.values_list('comentario', flat=True)
        ).lower())

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_un_expediente_ya_notificado_no_se_reabre_con_una_foto(self):
        """No se puede cambiar una sancion ya comunicada al residente."""
        ticket = self._ticket()
        multa = Multa.objects.get(ticket=ticket)
        multa.estado = EstadoMulta.NOTIFICADA
        multa.fecha_notificacion = timezone.now()
        multa.save(update_fields=['estado', 'fecha_notificacion'])

        cliente, _ = _cliente_gemini('Descripcion tardia de la escena.')
        with patch('google.genai.Client', return_value=cliente):
            self._subir_foto(ticket)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        ticket.refresh_from_db()
        self.assertIn(
            'Descripcion tardia', ticket.analisis_evidencia,
            'igual queda guardado para quien resuelva despues',
        )

    @override_settings(GEMINI_API_KEY='clave-de-prueba')
    def test_lo_que_se_ve_va_separado_de_lo_que_alguien_escribio(self):
        """Si la foto contradice el relato, esa contradiccion es informacion."""
        from multas.clasificador import clasificar_con_ia

        ticket = self._ticket()
        ticket.analisis_evidencia = 'La zona esta despejada y demarcada.'
        ticket.save(update_fields=['analisis_evidencia'])

        capturado = {}

        def _crear(**kwargs):
            capturado.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(
                type='text', text='{"codigo": null, "confianza": 0, "fundamento": ""}',
            )])

        with override_settings(ANTHROPIC_API_KEY='sk-ant-x'):
            with patch('anthropic.Anthropic', return_value=SimpleNamespace(
                messages=SimpleNamespace(create=_crear),
            )):
                clasificar_con_ia(ticket, [self.infraccion])

        enviado = capturado['messages'][0]['content']
        self.assertIn('observado_en_la_evidencia', enviado)
        self.assertIn('despejada', enviado)
