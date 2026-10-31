"""
Limites del permiso de fiscalizacion: el Administrador acota cuando y sobre
que unidades reporta un Fiscalizador, y el reporte fuera de esos limites se
rechaza con un mensaje que dice cual limite fallo.
"""

import tempfile
from datetime import date, datetime, time, timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import PermisoDenuncia, Rol, Usuario
from condominios.models import Condominio, Unidad
from multas.models import Ticket

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_test_media_')

# Miercoles 5 de noviembre de 2025, 23:30 en Santiago.
MIERCOLES_NOCHE = timezone.make_aware(datetime(2025, 11, 5, 23, 30))


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class PermisoDenunciaTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Edificio Los Robles')
        cls.otro = Condominio.objects.create(nombre='Otro')
        cls.depto = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 101')
        cls.estacionamiento = Unidad.objects.create(condominio=cls.condominio, identificador='Estacionamiento 12')
        cls.ajena = Unidad.objects.create(condominio=cls.otro, identificador='Depto 9')

        def usuario(username, rol, condominio=None):
            return Usuario.objects.create_user(
                username=username, password='x', rol=rol, condominio=condominio or cls.condominio,
            )

        cls.fiscalizador = usuario('guardia', Rol.FISCALIZADOR)
        cls.residente = usuario('vecino', Rol.RESIDENTE)
        cls.administrador = usuario('admin1', Rol.ADMINISTRADOR)
        cls.admin_ajeno = usuario('admin2', Rol.ADMINISTRADOR, cls.otro)

    def _reportar(self, quien, unidad=None):
        self.client.force_authenticate(quien)
        return self.client.post('/api/tickets/', {
            'unidad': (unidad or self.depto).id,
            'descripcion': 'Ruido',
            'fecha_hecho': (timezone.now() - timedelta(minutes=10)).isoformat(),
        })

    def _limitar(self, **campos):
        unidades = campos.pop('unidades', [])
        permiso = PermisoDenuncia.objects.create(usuario=self.fiscalizador, **campos)
        permiso.unidades.set(unidades)
        return permiso

    # -- Reglas -------------------------------------------------------------

    def test_sin_limites_reporta_como_siempre(self):
        self.assertEqual(self._reportar(self.fiscalizador).status_code, 201)

    def test_suspendido_no_reporta(self):
        self._limitar(suspendido=True)
        r = self._reportar(self.fiscalizador)
        self.assertEqual(r.status_code, 403)
        self.assertIn('suspendido', r.data['detail'])
        self.assertFalse(Ticket.objects.exists())

    def test_permiso_vencido(self):
        self._limitar(vigente_hasta=timezone.localdate() - timedelta(days=1))
        r = self._reportar(self.fiscalizador)
        self.assertEqual(r.status_code, 403)
        self.assertIn('vencio', r.data['detail'])

    def test_permiso_que_aun_no_comienza(self):
        self._limitar(vigente_desde=timezone.localdate() + timedelta(days=1))
        self.assertIn('comienza', self._reportar(self.fiscalizador).data['detail'])

    def test_solo_las_unidades_asignadas(self):
        self._limitar(unidades=[self.estacionamiento])
        r = self._reportar(self.fiscalizador, self.depto)
        self.assertEqual(r.status_code, 403)
        self.assertIn('Depto 101', r.data['detail'])
        self.assertEqual(self._reportar(self.fiscalizador, self.estacionamiento).status_code, 201)

    def test_dias_y_turno_que_cruza_medianoche(self):
        permiso = self._limitar(dias=[2], hora_desde=time(22), hora_hasta=time(6))
        self.assertIsNone(permiso.motivo_rechazo(MIERCOLES_NOCHE))
        # Jueves 02:30 sigue siendo el turno del miercoles.
        self.assertIsNone(permiso.motivo_rechazo(MIERCOLES_NOCHE + timedelta(hours=3)))
        # Miercoles 02:30 es el turno del martes: no corresponde.
        self.assertIn('Miercoles', permiso.motivo_rechazo(MIERCOLES_NOCHE - timedelta(hours=21)))
        # Miercoles a las 15:00: dia correcto, fuera del turno.
        self.assertIn('horario', permiso.motivo_rechazo(MIERCOLES_NOCHE - timedelta(hours=8, minutes=30)))
        # Jueves: fuera de los dias.
        self.assertIn('Miercoles', permiso.motivo_rechazo(MIERCOLES_NOCHE + timedelta(days=1)))

    def test_turno_de_dia(self):
        permiso = self._limitar(hora_desde=time(8), hora_hasta=time(20))
        self.assertIsNotNone(permiso.motivo_rechazo(MIERCOLES_NOCHE))
        self.assertIsNone(permiso.motivo_rechazo(MIERCOLES_NOCHE - timedelta(hours=10)))

    def test_los_limites_no_afectan_a_residentes(self):
        self._limitar(suspendido=True)
        self.assertEqual(self._reportar(self.residente).status_code, 201)

    # -- API del Administrador ---------------------------------------------

    def _put(self, quien, datos, usuario=None):
        self.client.force_authenticate(quien)
        return self.client.put(
            f'/api/usuarios/{(usuario or self.fiscalizador).id}/permiso-denuncia/', datos, format='json',
        )

    def test_el_administrador_fija_y_quita_limites(self):
        r = self._put(self.administrador, {
            'vigente_hasta': '2030-12-31', 'dias': [4, 0, 0], 'hora_desde': '22:00', 'hora_hasta': '06:00',
            'unidades': [self.estacionamiento.id], 'notas': 'Turno noche',
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['permiso']['dias'], [0, 4])
        self.assertEqual(r.data['permiso']['unidades_identificadores'], ['Estacionamiento 12'])
        permiso = PermisoDenuncia.objects.get(usuario=self.fiscalizador)
        self.assertEqual(permiso.actualizado_por, self.administrador)
        self.assertEqual(permiso.vigente_hasta, date(2030, 12, 31))

        listado = self.client.get('/api/usuarios/denunciantes/').data
        self.assertEqual([f['id'] for f in listado], [self.fiscalizador.id])

        self.assertEqual(
            self.client.delete(f'/api/usuarios/{self.fiscalizador.id}/permiso-denuncia/').status_code, 204,
        )
        self.assertFalse(PermisoDenuncia.objects.exists())

    def test_el_fiscalizador_ve_sus_limites_y_no_puede_cambiarlos(self):
        self._limitar(notas='Solo noche')
        self.client.force_authenticate(self.fiscalizador)
        self.assertEqual(self.client.get('/api/auth/me/').data['permiso_denuncia']['notas'], 'Solo noche')
        self.assertEqual(self._put(self.fiscalizador, {'suspendido': False}).status_code, 403)

    def test_validaciones(self):
        self.assertEqual(self._put(self.administrador, {'dias': [7]}).status_code, 400)
        self.assertEqual(self._put(self.administrador, {'hora_desde': '22:00'}).status_code, 400)
        self.assertEqual(
            self._put(self.administrador, {'vigente_desde': '2030-01-02', 'vigente_hasta': '2030-01-01'}).status_code,
            400,
        )
        self.assertEqual(self._put(self.administrador, {'unidades': [self.ajena.id]}).status_code, 400)

    def test_otra_comunidad_o_quien_no_es_denunciante(self):
        self.assertEqual(self._put(self.admin_ajeno, {'suspendido': True}).status_code, 404)
        self.assertEqual(self._put(self.administrador, {'suspendido': True}, self.residente).status_code, 404)
