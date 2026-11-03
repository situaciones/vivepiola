"""
Ninguna multa con cobro sale sin la aprobacion de la mayoria del Comite.

La Ley 21.442 (art. 2 N.5 y 17) deja la imposicion de multas en el Comite. Lo
que se verifica aqui: hace falta la mitad mas uno de sus integrantes, solo
suman los votos por la misma salida, nadie vota dos veces y quien es parte del
caso no vota ni bloquea la decision.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, Ticket, TipoActo
from multas.services import votos_requeridos_aprobacion
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_aprobacion_')


def _persona(condominio, unidad, nombre, rut):
    return Persona.objects.create(
        condominio=condominio, unidad=unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
        nombre_completo=nombre, cedula_identidad=rut, domicilio=unidad.identificador,
        correo_electronico=f'{rut[:2]}@test.local',
    )


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class _BaseComite(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Edificio Mayoria', cortesias_antes_de_multar=0)
        cls.d101 = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 101')
        cls.d202 = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 202')
        cls.vecino = _persona(cls.condominio, cls.d101, 'Pedro Vecino', '11.111.111-1')
        cls.miembro_p = _persona(cls.condominio, cls.d202, 'Ana Comite', '22.222.222-2')
        cls.ana = Usuario.objects.create_user(
            username='ana_m', password='x', rol=Rol.COMITE, condominio=cls.condominio, persona=cls.miembro_p,
        )
        cls.bruno = Usuario.objects.create_user(username='bruno_m', password='x', rol=Rol.COMITE, condominio=cls.condominio)
        cls.carla = Usuario.objects.create_user(username='carla_m', password='x', rol=Rol.COMITE, condominio=cls.condominio)
        cls.guardia = Usuario.objects.create_user(
            username='guardia_m', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.ruido = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('1.00'), estado=EstadoInfraccion.ACTIVA,
        )
        cls.basura = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='BASURA', descripcion='Basura fuera del shaft',
            articulo_referencia='Art. 18', monto=Decimal('0.50'), estado=EstadoInfraccion.ACTIVA,
        )

    def _multa(self, unidad=None, persona=None):
        unidad = unidad or self.d101
        persona = persona or self.vecino
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=unidad, persona_reportada=persona,
            creado_por=self.guardia, descripcion='Musica fuerte', fecha_hecho=timezone.now() - timedelta(hours=2),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=unidad, persona_infractor=persona,
            estado=EstadoMulta.EN_REVISION, infraccion=self.ruido, monto=Decimal('1.00'),
        )

    def _votar(self, usuario, multa, infraccion=None, accion='aprobar', **extra):
        self.client.force_authenticate(usuario)
        datos = {'motivo': 'No hay prueba suficiente'} if accion == 'rechazar' else {
            'infraccion_id': (infraccion or self.ruido).id,
        }
        datos.update(extra)
        return self.client.post(f'/api/multas/{multa.id}/{accion}/', datos, format='json', SERVER_NAME='localhost')



class AprobacionComiteTestCase(_BaseComite):
    def test_con_tres_integrantes_hacen_falta_dos_votos(self):
        multa = self._multa()
        self.assertEqual(votos_requeridos_aprobacion(multa), 2)

        r = self._votar(self.ana, multa)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['resultado_votacion'])
        self.assertEqual(r.data['aprobacion_comite']['votos_aprobar'], 1)
        self.assertEqual(r.data['aprobacion_comite']['mi_voto'], 'APROBAR')
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION, 'un voto no basta')

        r = self._votar(self.bruno, multa)
        self.assertEqual(r.data['resultado_votacion'], 'APROBADA')
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.APROBADA)
        self.assertEqual(multa.actas_selladas.filter(tipo_acto=TipoActo.VOTO_APROBACION).count(), 2)
        acta = multa.actas_selladas.get(tipo_acto=TipoActo.APROBACION)
        self.assertEqual(acta.manifiesto['extra']['votos'], 2)

    def test_votos_por_salidas_distintas_no_suman(self):
        multa = self._multa()
        self._votar(self.ana, multa, self.ruido)
        r = self._votar(self.bruno, multa, self.basura)
        self.assertIsNone(r.data['resultado_votacion'])
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)

        r = self._votar(self.carla, multa, self.basura)
        self.assertEqual(r.data['resultado_votacion'], 'APROBADA')
        multa.refresh_from_db()
        self.assertEqual(multa.infraccion, self.basura, 'se aplica lo que voto la mayoria')
        self.assertEqual(multa.monto, Decimal('0.50'))

    def test_la_mayoria_tambien_decide_no_aplicarla(self):
        multa = self._multa()
        self._votar(self.ana, multa, accion='rechazar')
        r = self._votar(self.bruno, multa, accion='rechazar')
        self.assertEqual(r.data['resultado_votacion'], 'RECHAZADA')
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.RECHAZADA)

    def test_nadie_vota_dos_veces(self):
        multa = self._multa()
        self._votar(self.ana, multa)
        r = self._votar(self.ana, multa)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Ya votaste', r.data['detail'])

    def test_quien_es_parte_no_vota_ni_bloquea(self):
        # La multa es de la unidad de Ana: votan Bruno y Carla, y bastan los dos.
        multa = self._multa(self.d202, self.miembro_p)
        self.assertEqual(votos_requeridos_aprobacion(multa), 2)
        self.assertEqual(self._votar(self.ana, multa).status_code, 403)

        Usuario.objects.filter(id=self.carla.id).update(is_active=False)
        self.assertEqual(votos_requeridos_aprobacion(multa), 1, 'si solo queda uno habilitado, basta el')

    def test_sin_aprobacion_no_se_puede_notificar(self):
        multa = self._multa()
        self._votar(self.ana, multa)
        admin = Usuario.objects.create_user(
            username='admin_m', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.client.force_authenticate(admin)
        r = self.client.post(f'/api/multas/{multa.id}/notificar/', SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class DerivacionTestCase(_BaseComite):
    """Si nadie del Comite puede decidir, la administracion lo deriva."""

    def test_se_deriva_cuando_todos_son_parte(self):
        Usuario.objects.filter(id__in=[self.bruno.id, self.carla.id]).update(is_active=False)
        multa = self._multa(self.d202, self.miembro_p)  # la unidad de Ana, unica del Comite
        admin = Usuario.objects.create_user(
            username='admin_d', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.client.force_authenticate(admin)
        r = self.client.get(f'/api/multas/{multa.id}/', SERVER_NAME='localhost')
        self.assertTrue(r.data['sin_comite_habilitado'])
        r = self.client.post(f'/api/multas/{multa.id}/derivar/', {'destino': 'JPL'}, format='json',
                             SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 200, r.data)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.DERIVADA)
        self.assertTrue(multa.actas_selladas.filter(tipo_acto=TipoActo.DERIVACION).exists())

    def test_no_se_deriva_si_alguien_puede_decidir(self):
        multa = self._multa()
        admin = Usuario.objects.create_user(
            username='admin_d2', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.client.force_authenticate(admin)
        r = self.client.post(f'/api/multas/{multa.id}/derivar/', {'destino': 'JPL'}, format='json',
                             SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class LibroActasTestCase(_BaseComite):
    def test_el_libro_trae_los_votos_y_la_aprobacion(self):
        multa = self._multa()
        self._votar(self.ana, multa)
        self._votar(self.bruno, multa)
        from multas.services import generar_libro_actas_pdf
        from django.utils import timezone as tz
        hoy = tz.localdate()
        pdf = generar_libro_actas_pdf(self.condominio, hoy, hoy, self.ana)
        self.assertTrue(pdf.startswith(b'%PDF'))

        self.client.force_authenticate(self.ana)
        r = self.client.get('/api/multas/libro-actas/', SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_el_residente_no_lo_descarga(self):
        vecino = Usuario.objects.create_user(
            username='vecino_l', password='x', rol=Rol.RESIDENTE, condominio=self.condominio,
        )
        self.client.force_authenticate(vecino)
        r = self.client.get('/api/multas/libro-actas/', SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 403)
