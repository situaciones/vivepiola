"""
Tests del video como evidencia.

Hay hechos que una imagen fija no prueba: una pelea, un choque, un perro
suelto. Lo que se cuida aqui son los dos limites: que un video no pueda
inflar el almacenamiento de la comunidad, y que no se le atribuya un anclaje
de fecha y lugar que no tiene.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EvidenciaFoto, Ticket

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_video_')

# PNG minimo valido, para no depender de un archivo en disco.
PNG_1PX = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c636000000200010005fe02fa0000000049454e44ae426082'
)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class EvidenciaEnVideoTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Video')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 111')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Vito Video', cedula_identidad='1.111.111-1',
            domicilio='Depto 111', correo_electronico='vito@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_video', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )

    def _ticket(self):
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
            'descripcion': 'Pelea en el pasillo', 'fecha_hecho': timezone.now().isoformat(),
        }, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Ticket.objects.get(id=respuesta.data['id'])

    def _subir(self, ticket, **archivos):
        self.client.force_authenticate(self.conserje)
        return self.client.post(
            f'/api/tickets/{ticket.id}/evidencia/',
            {'descripcion': 'Prueba', **archivos}, format='multipart',
        )

    def _video(self, nombre='hecho.mp4', tamano=1024):
        return SimpleUploadedFile(nombre, b'\x00' * tamano, content_type='video/mp4')

    def test_se_puede_adjuntar_un_video(self):
        ticket = self._ticket()
        respuesta = self._subir(ticket, video=self._video())

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(respuesta.data['es_video'])
        self.assertTrue(respuesta.data['video'])
        self.assertIsNone(respuesta.data['imagen'])

        evidencia = EvidenciaFoto.objects.get(id=respuesta.data['id'])
        self.assertTrue(evidencia.es_video)
        self.assertTrue(evidencia.archivo)

    def test_la_foto_sigue_funcionando_igual(self):
        ticket = self._ticket()
        imagen = SimpleUploadedFile('foto.png', PNG_1PX, content_type='image/png')
        respuesta = self._subir(ticket, imagen=imagen)

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertFalse(respuesta.data['es_video'])

    def test_el_video_se_sella_por_contenido_igual_que_la_foto(self):
        ticket = self._ticket()
        respuesta = self._subir(ticket, video=self._video())

        evidencia = EvidenciaFoto.objects.get(id=respuesta.data['id'])
        self.assertEqual(len(evidencia.sha256), 64, 'sin hash no hay prueba de que no se cambio')

    def test_al_video_no_se_le_atribuye_un_anclaje_que_no_tiene(self):
        """
        La foto trae EXIF con fecha y GPS; el video de un telefono no siempre.
        Decir que esta anclado cuando no se evaluo seria inventar prueba.
        """
        ticket = self._ticket()
        respuesta = self._subir(ticket, video=self._video())

        evidencia = EvidenciaFoto.objects.get(id=respuesta.data['id'])
        self.assertFalse(evidencia.anclaje_fisico)
        self.assertEqual(evidencia.metadatos_origen['medio'], 'video')
        self.assertEqual(evidencia.metadatos_origen['anclaje'], 'no evaluado')

    # -- Limites -------------------------------------------------------

    @override_settings(EVIDENCIA_VIDEO_MAX_MB=1)
    def test_un_video_demasiado_pesado_se_rechaza_con_el_motivo(self):
        """Sin tope, un archivo enorme se sube entero y lo paga la comunidad."""
        ticket = self._ticket()
        respuesta = self._subir(ticket, video=self._video(tamano=2 * 1024 * 1024))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('maximo es 1 MB', respuesta.data['detail'])
        self.assertEqual(EvidenciaFoto.objects.count(), 0)

    def test_un_formato_de_video_desconocido_se_rechaza(self):
        ticket = self._ticket()
        respuesta = self._subir(ticket, video=self._video(nombre='hecho.avi'))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('.avi', respuesta.data['detail'])
        self.assertIn('.mp4', respuesta.data['detail'], 'debe decir cuales si sirven')

    def test_los_formatos_que_graban_los_telefonos_se_aceptan(self):
        for nombre in ('clip.mp4', 'clip.mov', 'clip.3gp', 'clip.webm', 'clip.m4v'):
            with self.subTest(nombre=nombre):
                ticket = self._ticket()
                respuesta = self._subir(ticket, video=self._video(nombre=nombre))
                self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_no_se_admiten_dos_archivos_en_una_misma_evidencia(self):
        ticket = self._ticket()
        respuesta = self._subir(
            ticket,
            imagen=SimpleUploadedFile('foto.png', PNG_1PX, content_type='image/png'),
            video=self._video(),
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(EvidenciaFoto.objects.count(), 0)

    def test_sin_archivo_no_hay_evidencia(self):
        ticket = self._ticket()
        respuesta = self._subir(ticket)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('imagen o un video', respuesta.data['detail'])
