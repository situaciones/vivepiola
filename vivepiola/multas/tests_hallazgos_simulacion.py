"""
Lo que mostro la simulacion de una comunidad nueva:

- al apelar, el Comite se entera por correo (no solo en el resumen diario);
- al resolver, el residente recibe la decision por correo;
- un miembro del Comite no decide sobre su propia unidad, y eso no deja la
  apelacion sin quorum;
- la alerta de un auto se dirige a la unica persona de su unidad.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad, Vehiculo
from multas.models import Descargo, EstadoMulta, Multa, Ticket
from multas.services import quorum_efectivo, token_acuse
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_hallazgos_')


def _persona(condominio, unidad, nombre, rut, correo):
    return Persona.objects.create(
        condominio=condominio, unidad=unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
        nombre_completo=nombre, cedula_identidad=rut, domicilio=unidad.identificador,
        correo_electronico=correo,
    )


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class HallazgosSimulacionTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Edificio Los Robles', quorum_resolucion_apelacion=2)
        cls.d302 = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 302')
        cls.d401 = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 401')
        cls.d501 = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 501')
        cls.matias = _persona(cls.condominio, cls.d302, 'Matias Herrera', '18.765.432-7', 'matias@test.local')
        cls.javiera_p = _persona(cls.condominio, cls.d401, 'Javiera Castro', '15.678.904-1', 'javiera@test.local')
        cls.luis_p = _persona(cls.condominio, cls.d501, 'Luis Navarro', '16.789.015-2', 'luis@test.local')
        cls.javiera = Usuario.objects.create_user(
            username='javiera_h', password='x', rol=Rol.COMITE, condominio=cls.condominio,
            email='javiera@test.local', persona=cls.javiera_p,
        )
        cls.luis = Usuario.objects.create_user(
            username='luis_h', password='x', rol=Rol.COMITE, condominio=cls.condominio,
            email='luis@test.local', persona=cls.luis_p,
        )
        cls.guardia = Usuario.objects.create_user(
            username='guardia_h', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
            email='guardia@test.local',
        )
        cls.sofia = Usuario.objects.create_user(
            username='sofia_h', password='x', rol=Rol.RESIDENTE, condominio=cls.condominio,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='BASURA', descripcion='Basura fuera del shaft',
            articulo_referencia='Art. 18', monto=Decimal('0.50'), estado=EstadoInfraccion.ACTIVA,
        )

    def _multa(self, unidad, persona, estado=EstadoMulta.NOTIFICADA):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=unidad, persona_reportada=persona,
            creado_por=self.guardia, descripcion='Basura en el pasillo',
            fecha_hecho=timezone.now() - timedelta(days=1),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=unidad, persona_infractor=persona,
            estado=estado, infraccion=self.infraccion, monto=Decimal('0.50'),
            fecha_notificacion=timezone.now(),
        )

    def _con_descargo(self, unidad, persona):
        multa = self._multa(unidad, persona, EstadoMulta.CON_DESCARGO)
        Descargo.objects.create(
            multa=multa, texto='No fui yo', fecha_limite_resolucion=timezone.now() + timedelta(days=15),
        )
        return multa

    # -- Apelacion: aviso al Comite ----------------------------------------

    def test_apelar_desde_el_enlace_avisa_al_comite_habilitado(self):
        multa = self._multa(self.d501, self.luis_p)  # la multa es de Luis, del Comite
        r = self.client.post(
            f'/api/notificaciones/apelar/{token_acuse(multa)}/', {'texto': 'El auto no era mio'},
            format='json', SERVER_NAME='localhost',
        )
        self.assertEqual(r.status_code, 201, r.content)
        avisos = [m for m in mail.outbox if 'Nueva apelacion' in m.subject]
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0].to, ['javiera@test.local'])  # Luis no decide su propio caso
        self.assertIn('Depto 501', avisos[0].subject)
        self.assertNotIn('El auto no era mio', avisos[0].body)  # el texto se lee en la app

    # -- Resolucion: aviso al residente -------------------------------------

    def test_resolver_le_avisa_al_residente_con_el_detalle(self):
        self.condominio.quorum_resolucion_apelacion = 1
        self.condominio.save()
        multa = self._con_descargo(self.d302, self.matias)
        self.client.force_authenticate(self.javiera)
        r = self.client.post(f'/api/multas/{multa.id}/resolver-descargo/', {
            'resolucion': 'DESCUENTO', 'porcentaje_descuento': 50,
            'comentario': 'Las camaras no permiten identificar a quien dejo las bolsas.',
        }, format='json', SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 200, r.content)
        correo = [m for m in mail.outbox if 'Resolucion de su apelacion' in m.subject]
        self.assertEqual(len(correo), 1)
        self.assertEqual(correo[0].to, ['matias@test.local'])
        self.assertIn('50%', correo[0].body)
        self.assertIn('de 0.50 a 0.25', correo[0].body)
        self.assertIn('Las camaras no permiten', correo[0].body)

    def test_rechazo_explica_que_va_a_gastos_comunes(self):
        self.condominio.quorum_resolucion_apelacion = 1
        self.condominio.save()
        multa = self._con_descargo(self.d302, self.matias)
        self.client.force_authenticate(self.javiera)
        self.client.post(f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'},
                         format='json', SERVER_NAME='localhost')
        cuerpo = [m for m in mail.outbox if 'Resolucion' in m.subject][0].body
        self.assertIn('queda firme', cuerpo)
        self.assertIn('gastos comunes', cuerpo)

    # -- Conflicto de interes -----------------------------------------------

    def test_un_miembro_no_resuelve_el_caso_de_su_propia_unidad(self):
        multa = self._con_descargo(self.d501, self.luis_p)
        self.client.force_authenticate(self.luis)
        r = self.client.post(f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'ACEPTADO'},
                             format='json', SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 403)
        self.assertIn('propia unidad', r.json()['detail'])
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)

    def test_el_conflicto_no_deja_la_apelacion_sin_quorum(self):
        # Quorum 2, pero solo Javiera puede decidir: con su voto alcanza.
        multa = self._con_descargo(self.d501, self.luis_p)
        self.assertEqual(quorum_efectivo(multa), 1)
        self.client.force_authenticate(self.javiera)
        r = self.client.post(f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'},
                             format='json', SERVER_NAME='localhost')
        self.assertEqual(r.status_code, 200, r.content)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)

    def test_sin_conflicto_se_mantiene_el_quorum_de_la_comunidad(self):
        multa = self._con_descargo(self.d302, self.matias)
        self.assertEqual(quorum_efectivo(multa), 2)

    # -- Alerta: responsable del auto ---------------------------------------

    def _alerta(self, patente):
        self.client.force_authenticate(self.sofia)
        return self.client.post('/api/alertas/', {
            'tipo': 'SALIDA_BLOQUEADA', 'patente': patente, 'descripcion': 'No puedo salir',
        }, SERVER_NAME='localhost')

    def test_la_alerta_se_dirige_a_la_unica_persona_de_la_unidad(self):
        Vehiculo.objects.create(condominio=self.condominio, unidad=self.d501, patente='PRTZ88')
        self.assertEqual(self._alerta('PRTZ88').status_code, 201)
        ticket = Ticket.objects.filter(unidad=self.d501).latest('id')
        self.assertEqual(ticket.persona_reportada, self.luis_p)

    def test_con_varias_personas_no_se_adivina_el_responsable(self):
        _persona(self.condominio, self.d302, 'Ana Morales', '11.223.344-5', 'ana@test.local')
        Vehiculo.objects.create(condominio=self.condominio, unidad=self.d302, patente='GHTR45')
        self.assertEqual(self._alerta('GHTR45').status_code, 201)
        ticket = Ticket.objects.filter(unidad=self.d302).latest('id')
        self.assertIsNone(ticket.persona_reportada)
