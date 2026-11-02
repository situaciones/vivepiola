"""
El Comite nace de una designacion con acta: solo quien la integra, dentro de
su mandato, puede tomar las decisiones que la ley reserva al Comite.
"""

import tempfile
from datetime import date, timedelta

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import EstadoInvitacion, Invitacion, Rol, Usuario
from condominios.models import Condominio, DesignacionComite, Persona, Unidad
from reglamentos.models import InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_test_media_')


def _acta():
    return SimpleUploadedFile('acta.pdf', b'%PDF-1.4 acta', content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class DesignacionComiteTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.condominio = Condominio.objects.create(nombre='Edificio Los Robles')
        self.admin = Usuario.objects.create_user(
            username='admin1', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.personas = []
        for i in range(1, 5):
            unidad = Unidad.objects.create(condominio=self.condominio, identificador=f'Depto {i}01')
            self.personas.append(Persona.objects.create(
                condominio=self.condominio, unidad=unidad, rol_ocupacion='PROPIETARIO',
                nombre_completo=f'Propietario {i}', cedula_identidad=f'{i}.111.111-1',
                domicilio=f'Depto {i}01', correo_electronico=f'dueno{i}@correo.cl',
            ))
        self.arrendatario = Persona.objects.create(
            condominio=self.condominio, unidad=self.personas[0].unidad, rol_ocupacion='ARRENDATARIO',
            nombre_completo='Arrendatario', cedula_identidad='9.999.999-9', domicilio='Depto 101',
            correo_electronico='arrienda@correo.cl',
        )
        # El primero ya tiene cuenta como residente.
        self.vecino = Usuario.objects.create_user(
            username='dueno1', password='x', email='dueno1@correo.cl', rol=Rol.RESIDENTE,
            condominio=self.condominio, persona=self.personas[0],
        )
        self.infraccion = InfraccionCatalogo.objects.create(
            condominio=self.condominio, codigo='R-1', descripcion='Ruidos molestos', monto=1,
        )

    def _designar(self, personas=None, desde=None, hasta=None):
        hoy = timezone.localdate()
        self.client.force_authenticate(self.admin)
        return self.client.post('/api/comite/designar/', {
            'acta': _acta(),
            'fecha_asamblea': (desde or hoy - timedelta(days=10)).isoformat(),
            'vigente_hasta': (hasta or hoy + timedelta(days=365)).isoformat(),
            'personas': [p.id for p in (personas or self.personas[:3])],
        }, format='multipart')

    def _confirmar_infraccion(self, quien):
        quien.refresh_from_db()  # el rol cambia al designar; la sesion real lo relee en cada pedido
        self.client.force_authenticate(quien)
        return self.client.post(f'/api/infracciones/{self.infraccion.id}/confirmar/')

    # -- Designar --------------------------------------------------------

    def test_designa_y_da_acceso_a_cada_miembro(self):
        respuesta = self._designar()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.vecino.refresh_from_db()
        self.assertEqual(self.vecino.rol, Rol.COMITE)
        # Los dos sin cuenta reciben el enlace para activar su acceso.
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            Invitacion.objects.filter(rol_sugerido=Rol.COMITE, estado=EstadoInvitacion.PENDIENTE).count(), 2,
        )
        estados = sorted(m['estado'] for m in respuesta.data['miembros'])
        self.assertEqual(estados, ['ACTIVO', 'INVITADO', 'INVITADO'])
        self.assertTrue(respuesta.data['vigente'])

    def test_exige_el_minimo_de_miembros(self):
        respuesta = self._designar(personas=self.personas[:2])
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('al menos 3', respuesta.data['detail'])
        self.assertFalse(DesignacionComite.objects.exists())

    def test_un_arrendatario_no_puede_integrarlo(self):
        respuesta = self._designar(personas=self.personas[:2] + [self.arrendatario])
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('Arrendatario no es propietaria', respuesta.data['detail'])

    def test_el_mandato_no_puede_pasar_el_maximo(self):
        hoy = timezone.localdate()
        respuesta = self._designar(desde=hoy, hasta=date(hoy.year + 4, 1, 1))
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('3 anos', respuesta.data['detail'])

    def test_exige_el_acta(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post('/api/comite/designar/', {
            'fecha_asamblea': '2026-01-01', 'vigente_hasta': '2027-01-01',
            'personas': [p.id for p in self.personas[:3]],
        }, format='multipart')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('acta', respuesta.data)

    def test_ya_no_se_invita_comite_suelto(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post('/api/invitaciones/', {'correo': 'x@correo.cl', 'rol_sugerido': Rol.COMITE})
        self.assertEqual(respuesta.status_code, 400)

    def test_los_miembros_salientes_vuelven_a_residente(self):
        self._designar()
        self.assertEqual(self._designar(personas=self.personas[1:4]).status_code, 201)
        self.vecino.refresh_from_db()
        self.assertEqual(self.vecino.rol, Rol.RESIDENTE)
        self.assertEqual(DesignacionComite.objects.filter(activa=True).count(), 1)

    def test_reenviar_acceso_a_quien_no_lo_activo(self):
        estado = self._designar().data
        sin_activar = next(m for m in estado['miembros'] if m['estado'] == 'INVITADO')
        mail.outbox.clear()
        respuesta = self.client.post(f'/api/comite/miembros/{sin_activar["id"]}/reenviar/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    # -- Quien puede decidir ---------------------------------------------

    def test_un_miembro_vigente_decide(self):
        self._designar()
        self.assertEqual(self._confirmar_infraccion(self.vecino).status_code, 200)

    def test_el_comite_que_no_integra_la_designacion_no_decide(self):
        self._designar()
        intruso = Usuario.objects.create_user(
            username='intruso', password='x', rol=Rol.COMITE, condominio=self.condominio,
        )
        respuesta = self._confirmar_infraccion(intruso)
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn('No integra el Comite', respuesta.data['detail'])

    def test_con_el_mandato_vencido_nadie_decide(self):
        hoy = timezone.localdate()
        self._designar(desde=hoy - timedelta(days=400), hasta=hoy - timedelta(days=1))
        respuesta = self._confirmar_infraccion(self.vecino)
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn('vencio', respuesta.data['detail'])

    def test_comunidad_sin_designacion_sigue_como_antes(self):
        antiguo = Usuario.objects.create_user(
            username='antiguo', password='x', rol=Rol.COMITE, condominio=self.condominio,
        )
        self.assertEqual(self._confirmar_infraccion(antiguo).status_code, 200)
        self.client.force_authenticate(self.admin)
        estado = self.client.get('/api/comite/').data
        self.assertTrue(estado['sin_designacion'])
        self.assertTrue(estado['alertas'])

    def test_quien_activa_su_acceso_queda_en_el_comite_y_decide(self):
        self._designar()
        invitacion = Invitacion.objects.get(correo='dueno2@correo.cl', estado=EstadoInvitacion.PENDIENTE)
        self.client.force_authenticate(None)
        respuesta = self.client.post(f'/api/auth/invitacion/{invitacion.codigo}/', {
            'first_name': 'Dueno', 'username': 'dueno2', 'password': 'Robles-del-201',
        })
        self.assertEqual(respuesta.status_code, 201)
        nuevo = Usuario.objects.get(username='dueno2')
        self.assertEqual(nuevo.rol, Rol.COMITE)
        self.assertEqual(nuevo.persona, self.personas[1])
        self.assertEqual(self._confirmar_infraccion(nuevo).status_code, 200)

    def test_avisa_si_los_activos_no_alcanzan_el_quorum(self):
        self.condominio.quorum_resolucion_apelacion = 2
        self.condominio.save()
        estado = self._designar().data
        self.assertEqual(estado['activos'], 1)
        self.assertTrue(any('quorum' in a for a in estado['alertas']))
