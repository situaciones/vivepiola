"""
Alerta inmediata: un vecino avisa que un auto le bloquea la salida. Se avisa
al momento a los guardias de turno y al dueno del auto, y queda un reporte
normal sobre la unidad del vehiculo para que la multa siga su curso.
"""

import tempfile
from datetime import time, timedelta
from decimal import Decimal
from io import BytesIO

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import PermisoDenuncia, Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad, Vehiculo
from condominios.utils import importar_registro_copropietarios
from multas.models import AlertaInmediata, EstadoAlerta, Multa
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_alertas_')


def _foto():
    buffer = BytesIO()
    Image.new('RGB', (20, 20), 'gray').save(buffer, 'JPEG')
    return SimpleUploadedFile('auto.jpg', buffer.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class AlertaInmediataTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.condominio = Condominio.objects.create(nombre='Edificio Alertas')
        self.mi_unidad = Unidad.objects.create(condominio=self.condominio, identificador='Casa 1')
        self.unidad_auto = Unidad.objects.create(condominio=self.condominio, identificador='Casa 7')
        yo = Persona.objects.create(
            condominio=self.condominio, unidad=self.mi_unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Ana Afectada', cedula_identidad='1.111.111-1', domicilio='Casa 1',
            correo_electronico='ana@test.local',
        )
        Persona.objects.create(
            condominio=self.condominio, unidad=self.unidad_auto, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Beto Del Auto', cedula_identidad='7.777.777-7', domicilio='Casa 7',
            correo_electronico='beto@test.local',
        )
        Vehiculo.objects.create(condominio=self.condominio, unidad=self.unidad_auto, patente='ABCD12')
        self.vecina = Usuario.objects.create_user(
            username='ana', password='x', rol=Rol.RESIDENTE, condominio=self.condominio, persona=yo,
            email='ana@test.local',
        )
        self.guardia = Usuario.objects.create_user(
            username='guardia', password='x', rol=Rol.FISCALIZADOR, condominio=self.condominio,
            email='guardia@test.local',
        )
        self.guardia_libre = Usuario.objects.create_user(
            username='guardia_libre', password='x', rol=Rol.FISCALIZADOR, condominio=self.condominio,
            email='libre@test.local',
        )
        # El segundo guardia solo trabaja de madrugada: no esta de turno ahora (en la mayoria de los casos).
        ahora = timezone.localtime().time()
        desde, hasta = (time(3, 0), time(3, 1)) if not (time(3, 0) <= ahora <= time(3, 1)) else (time(5, 0), time(5, 1))
        PermisoDenuncia.objects.create(usuario=self.guardia_libre, hora_desde=desde, hora_hasta=hasta)
        Usuario.objects.create_user(
            username='admin', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
            email='admin@test.local',
        )
        InfraccionCatalogo.objects.create(
            condominio=self.condominio, codigo='EST-01', descripcion='Vehiculo bloqueando salida de vehiculos',
            articulo_referencia='Art. 20', monto=Decimal('1.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _alertar(self, **datos):
        self.client.force_authenticate(self.vecina)
        cuerpo = {'tipo': 'SALIDA_BLOQUEADA', 'patente': 'abcd-12', 'descripcion': 'Auto frente a mi porton'}
        cuerpo.update(datos)
        return self.client.post('/api/alertas/', cuerpo, format='multipart')

    def _destinos(self):
        return {d for c in mail.outbox for d in c.to}

    def test_avisa_al_guardia_de_turno_a_la_administracion_y_al_dueno_del_auto(self):
        respuesta = self._alertar()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['unidad_vehiculo_identificador'], 'Casa 7')
        destinos = self._destinos()
        self.assertIn('guardia@test.local', destinos)
        self.assertIn('admin@test.local', destinos)
        self.assertIn('beto@test.local', destinos)
        self.assertNotIn('libre@test.local', destinos, 'el guardia fuera de turno no recibe la alerta')
        correo_dueno = next(c for c in mail.outbox if 'beto@test.local' in c.to)
        self.assertIn('ABCD12', correo_dueno.body)
        self.assertIn('muevalo de inmediato', correo_dueno.body)

    def test_deja_un_reporte_sobre_la_unidad_del_auto_para_la_multa(self):
        respuesta = self._alertar()
        alerta = AlertaInmediata.objects.get(id=respuesta.data['id'])
        self.assertIsNotNone(alerta.ticket)
        self.assertEqual(alerta.ticket.unidad, self.unidad_auto)
        self.assertTrue(Multa.objects.filter(ticket=alerta.ticket).exists())

    def test_la_foto_queda_como_evidencia_del_reporte(self):
        respuesta = self._alertar(foto=_foto())
        alerta = AlertaInmediata.objects.get(id=respuesta.data['id'])
        self.assertEqual(alerta.ticket.evidencias.count(), 1)
        self.assertTrue(alerta.ticket.evidencias.first().sha256)

    def test_patente_no_registrada_avisa_igual_sin_reporte(self):
        respuesta = self._alertar(patente='ZZZZ99')
        self.assertEqual(respuesta.status_code, 201)
        self.assertIsNone(respuesta.data['unidad_vehiculo_identificador'])
        self.assertIsNone(respuesta.data['ticket'])
        self.assertIn('guardia@test.local', self._destinos())
        aviso = next(c for c in mail.outbox if 'guardia@test.local' in c.to)
        self.assertIn('no esta registrada', aviso.body)

    def test_si_nadie_esta_de_turno_avisa_a_todos_los_guardias(self):
        PermisoDenuncia.objects.create(usuario=self.guardia, suspendido=True)
        self._alertar()
        destinos = self._destinos()
        self.assertIn('guardia@test.local', destinos)
        self.assertIn('libre@test.local', destinos)

    def test_pide_patente_o_foto(self):
        self.assertEqual(self._alertar(patente='').status_code, 400)

    def test_el_guardia_la_ve_y_la_atiende(self):
        alerta_id = self._alertar().data['id']
        mail.outbox.clear()
        self.client.force_authenticate(self.guardia)
        abiertas = self.client.get('/api/alertas/', {'estado': 'ABIERTA'}).data
        abiertas = abiertas.get('results', abiertas)
        self.assertEqual([a['id'] for a in abiertas], [alerta_id])

        respuesta = self.client.post(f'/api/alertas/{alerta_id}/atender/', {'nota': 'El dueno movio el auto'}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['estado'], EstadoAlerta.ATENDIDA)
        self.assertIn('ana@test.local', self._destinos(), 'quien aviso sabe que se atendio')

    def test_un_residente_no_atiende_ni_ve_alertas_ajenas(self):
        alerta_id = self._alertar().data['id']
        otro = Usuario.objects.create_user(username='otro', password='x', rol=Rol.RESIDENTE, condominio=self.condominio)
        self.client.force_authenticate(otro)
        lista = self.client.get('/api/alertas/').data
        self.assertEqual(len(lista.get('results', lista)), 0)
        self.assertIn(self.client.post(f'/api/alertas/{alerta_id}/atender/').status_code, (403, 404))


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class VehiculosTestCase(APITestCase):
    def setUp(self):
        self.condominio = Condominio.objects.create(nombre='Edificio Autos')
        self.unidad = Unidad.objects.create(condominio=self.condominio, identificador='Depto 1')
        self.admin = Usuario.objects.create_user(
            username='admin', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )

    def test_el_administrador_registra_y_la_patente_se_normaliza(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post('/api/vehiculos/', {'unidad': self.unidad.id, 'patente': 'ab-cd 12'})
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['patente'], 'ABCD12')
        repetida = self.client.post('/api/vehiculos/', {'unidad': self.unidad.id, 'patente': 'ABCD12'})
        self.assertEqual(repetida.status_code, 400)

    def test_un_residente_no_puede_recorrer_las_patentes(self):
        vecino = Usuario.objects.create_user(username='v', password='x', rol=Rol.RESIDENTE, condominio=self.condominio)
        self.client.force_authenticate(vecino)
        self.assertEqual(self.client.get('/api/vehiculos/').status_code, 403)

    def test_se_cargan_desde_el_excel_del_registro(self):
        csv = (
            'unidad,rol_ocupacion,nombre_completo,cedula_identidad,domicilio,correo_electronico,patentes\n'
            'Depto 1,PROPIETARIO,Ana,1.111.111-1,Depto 1,ana@test.local,"ABCD12, xy-1234"\n'
        ).encode('utf-8')
        archivo = SimpleUploadedFile('registro.csv', csv, content_type='text/csv')
        total, ok, errores, detalle = importar_registro_copropietarios(self.condominio, archivo)
        self.assertEqual((ok, errores), (1, 0), detalle)
        self.assertEqual(
            sorted(Vehiculo.objects.values_list('patente', flat=True)), ['ABCD12', 'XY1234'],
        )
