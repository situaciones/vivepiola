"""
Tests de la reunion con el residente y de la resolucion por acuerdo.

Un formulario no siempre alcanza: hay explicaciones que se entienden hablando.
Y en comunidades donde el reglamento lo exige, resolver una apelacion no puede
ser cosa de quien entre primero al sistema.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import (
    Descargo, EstadoMulta, EstadoReunion, ModalidadReunion, Multa, OrigenAntecedente,
    ResolucionDescargo, Ticket, TipoActo,
)
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_reunion_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class BaseApelacionTestCase(APITestCase):
    quorum = 1

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre=f'Condominio Q{cls.quorum}', plazo_descargo_dias=5, plazo_resolucion_dias=15,
            quorum_resolucion_apelacion=cls.quorum,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 505')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Rosa Reune', cedula_identidad='5.050.505-0',
            domicilio='Depto 505', correo_electronico='rosa@test.local',
        )
        cls.residente = Usuario.objects.create_user(
            username=f'rosa{cls.quorum}', password='x', rol=Rol.RESIDENTE,
            condominio=cls.condominio, persona=cls.persona,
        )
        cls.comite1 = Usuario.objects.create_user(
            username=f'comite1_q{cls.quorum}', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.comite2 = Usuario.objects.create_user(
            username=f'comite2_q{cls.quorum}', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('6.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _apelada(self):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Ruido', fecha_hecho=timezone.now(),
        )
        multa = Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, infraccion=self.infraccion,
            monto=Decimal('6.00'), estado=EstadoMulta.CON_DESCARGO,
            fecha_notificacion=timezone.now(), fecha_acuse=timezone.now(),
            fecha_limite_descargo=timezone.now() + timedelta(days=5),
        )
        Descargo.objects.create(
            multa=multa, presentado_por=self.residente, texto='Quiero explicarlo en persona',
            fecha_limite_resolucion=timezone.now() + timedelta(days=15),
        )
        return multa


class ReunionConElResidenteTestCase(BaseApelacionTestCase):
    def test_el_comite_cita_al_residente_y_queda_la_convocatoria(self):
        multa = self._apelada()
        cuando = timezone.now() + timedelta(days=7)

        self.client.force_authenticate(self.comite1)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/convocar-reunion/',
            {
                'modalidad': ModalidadReunion.ONLINE,
                'fecha_propuesta': cuando.isoformat(),
                'lugar_o_enlace': 'https://meet.example.cl/apelacion-505',
            }, format='json',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data['estado'], EstadoReunion.PROPUESTA)
        self.assertEqual(respuesta.data['modalidad'], ModalidadReunion.ONLINE)

    def test_citar_extiende_el_plazo_que_tiene_el_comite(self):
        """Escuchar mejor no puede contar como demora del propio organo."""
        multa = self._apelada()
        limite_original = multa.descargo.fecha_limite_resolucion
        cuando = timezone.now() + timedelta(days=20)  # despues del vencimiento

        self.client.force_authenticate(self.comite1)
        self.client.post(
            f'/api/multas/{multa.id}/convocar-reunion/',
            {
                'modalidad': ModalidadReunion.PRESENCIAL,
                'fecha_propuesta': cuando.isoformat(),
                'lugar_o_enlace': 'Sala de reuniones del condominio',
            }, format='json',
        )

        multa.descargo.refresh_from_db()
        self.assertGreater(multa.descargo.fecha_limite_resolucion, limite_original)
        self.assertGreater(multa.descargo.fecha_limite_resolucion, cuando)

    def test_no_se_cita_a_una_reunion_en_el_pasado(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/convocar-reunion/',
            {
                'modalidad': ModalidadReunion.ONLINE,
                'fecha_propuesta': (timezone.now() - timedelta(days=1)).isoformat(),
                'lugar_o_enlace': 'https://meet.example.cl/x',
            }, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_no_se_cita_sobre_una_apelacion_ya_resuelta(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/convocar-reunion/',
            {
                'modalidad': ModalidadReunion.ONLINE,
                'fecha_propuesta': (timezone.now() + timedelta(days=2)).isoformat(),
                'lugar_o_enlace': 'https://meet.example.cl/x',
            }, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_el_residente_no_se_autoconvoca(self):
        multa = self._apelada()
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/convocar-reunion/',
            {
                'modalidad': ModalidadReunion.ONLINE,
                'fecha_propuesta': (timezone.now() + timedelta(days=2)).isoformat(),
                'lugar_o_enlace': 'https://meet.example.cl/x',
            }, format='json',
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_lo_dicho_en_la_reunion_entra_al_expediente_por_escrito(self):
        """Una explicacion de viva voz que no queda escrita, para el expediente no existio."""
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        self.client.post(
            f'/api/multas/{multa.id}/convocar-reunion/',
            {
                'modalidad': ModalidadReunion.ONLINE,
                'fecha_propuesta': (timezone.now() + timedelta(days=3)).isoformat(),
                'lugar_o_enlace': 'https://meet.example.cl/apelacion-505',
            }, format='json',
        )

        respuesta = self.client.post(
            f'/api/multas/{multa.id}/acta-reunion/',
            {
                'acta': 'La residente explico que el ruido venia del departamento de al lado.',
                'antecedentes': ['Nombre del vecino que puede confirmarlo', 'Foto del pasillo'],
            }, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['estado'], EstadoReunion.REALIZADA)

        multa.descargo.refresh_from_db()
        de_reunion = multa.descargo.antecedentes.filter(origen=OrigenAntecedente.REUNION)
        self.assertEqual(de_reunion.count(), 2)

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.REUNION_REALIZADA)
        self.assertIn('departamento de al lado', acta.manifiesto['extra']['acta'])

    def test_sin_reunion_pendiente_no_hay_acta_que_registrar(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/acta-reunion/', {'acta': 'Inventada'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)


class ResolucionSinQuorumTestCase(BaseApelacionTestCase):
    """Con quorum 1 nada cambia: resuelve quien entre primero."""

    quorum = 1

    def test_un_solo_miembro_resuelve(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)


class ResolucionPorAcuerdoTestCase(BaseApelacionTestCase):
    """Con quorum 2 la resolucion exige que dos coincidan en la MISMA salida."""

    quorum = 2

    def test_el_primer_voto_no_resuelve_pero_queda_sellado(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)

        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 202, respuesta.data)
        self.assertFalse(respuesta.data['resuelta'])
        self.assertEqual(respuesta.data['votos_coincidentes'], 1)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO, 'todavia no hay acuerdo')
        self.assertEqual(multa.actas_selladas.filter(tipo_acto=TipoActo.VOTO_RESOLUCION).count(), 1)

    def test_el_segundo_voto_coincidente_resuelve(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )

        self.client.force_authenticate(self.comite2)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)

    def test_dos_votos_distintos_no_son_un_acuerdo(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )

        self.client.force_authenticate(self.comite2)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'ACEPTADO'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 202, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(
            multa.estado, EstadoMulta.CON_DESCARGO,
            'dos personas que votan cosas distintas no resolvieron nada',
        )

    def test_un_mismo_miembro_no_alcanza_el_quorum_votando_dos_veces(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 202)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)
        self.assertEqual(multa.descargo.votos.count(), 1)

    def test_el_acuerdo_sobre_un_descuento_exige_el_mismo_porcentaje(self):
        multa = self._apelada()
        self.client.force_authenticate(self.comite1)
        self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/',
            {'resolucion': 'DESCUENTO', 'porcentaje_descuento': 50}, format='json',
        )

        self.client.force_authenticate(self.comite2)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/',
            {'resolucion': 'DESCUENTO', 'porcentaje_descuento': 30}, format='json',
        )
        self.assertEqual(respuesta.status_code, 202, 'rebajar "algo" no es un acuerdo sobre cuanto')

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)

    def test_con_el_mismo_porcentaje_si_resuelve(self):
        multa = self._apelada()
        for miembro in (self.comite1, self.comite2):
            self.client.force_authenticate(miembro)
            respuesta = self.client.post(
                f'/api/multas/{multa.id}/resolver-descargo/',
                {'resolucion': 'DESCUENTO', 'porcentaje_descuento': 50}, format='json',
            )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)
        self.assertEqual(multa.monto, Decimal('3.00'))
