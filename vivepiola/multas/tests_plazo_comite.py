"""
Plazo del Comite para resolver una apelacion.

Regla de la comunidad: antes de vencer se avisa como urgente; si vence sin
respuesta, la multa no queda detenida para siempre, pasa a cobro, y el
residente recibe un correo que le dice que va a gastos comunes porque el
Comite no respondio.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import Descargo, EstadoMulta, Multa, ResolucionDescargo, Ticket, TipoActo
from multas.resumenes import resumen_para_administracion, resumen_para_comite
from multas.services import firmar_apelaciones_sin_respuesta
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_plazo_comite_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class PlazoComiteTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Edificio Plazos')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 404')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Vecino Apelante', cedula_identidad='44.444.444-4',
            domicilio='Depto 404', correo_electronico='apelante@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_p', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        Usuario.objects.create_user(
            username='comite_p', password='x', rol=Rol.COMITE, condominio=cls.condominio,
            email='comite@test.local',
        )
        Usuario.objects.create_user(
            username='admin_p', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
            email='admin@test.local',
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('2.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _apelacion(self, vence_en, cortesia=False):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            creado_por=self.conserje, descripcion='Ruidos',
            fecha_hecho=timezone.now() - timedelta(days=20),
        )
        multa = Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, estado=EstadoMulta.CON_DESCARGO, infraccion=self.infraccion,
            monto=Decimal('0.00') if cortesia else Decimal('2.00'),
            monto_sin_cortesia=Decimal('2.00') if cortesia else None,
        )
        Descargo.objects.create(
            multa=multa, texto='No fui yo', fecha_limite_resolucion=timezone.now() + vence_en,
        )
        return multa

    # -- Antes de vencer: urgente ------------------------------------------

    def test_antes_de_vencer_el_comite_recibe_un_aviso_urgente(self):
        multa = self._apelacion(timedelta(days=2))
        resumen = resumen_para_comite(self.condominio)
        self.assertTrue(resumen['urgente'])
        texto = ' '.join(resumen['puntos'])
        self.assertIn(f'#{multa.id}', texto)
        self.assertIn('quedan firmes y se cobran', texto)

    def test_la_administracion_tambien_lo_ve_para_empujar(self):
        self._apelacion(timedelta(days=1))
        resumen = resumen_para_administracion(self.condominio)
        self.assertTrue(resumen['urgente'])
        self.assertIn('Recuerdaselo al Comite', ' '.join(resumen['puntos']))

    def test_con_tiempo_de_sobra_no_es_urgente(self):
        self._apelacion(timedelta(days=10))
        self.assertFalse(resumen_para_comite(self.condominio)['urgente'])

    # -- Al vencer: firme, a gastos comunes, y se le explica al residente ----

    def test_al_vencer_la_multa_queda_firme_y_se_avisa_al_residente(self):
        multa = self._apelacion(-timedelta(hours=1))

        cerradas = firmar_apelaciones_sin_respuesta(self.condominio)

        self.assertEqual(cerradas, [multa])
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)
        self.assertEqual(multa.descargo.resolucion, ResolucionDescargo.SIN_RESPUESTA)
        self.assertTrue(multa.actas_selladas.filter(tipo_acto=TipoActo.FIRMEZA_SIN_RESPUESTA_COMITE).exists())
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['apelante@test.local'])
        self.assertIn('no resolvio su apelacion', correo.body)
        self.assertIn('gastos comunes', correo.body)

    def test_un_aviso_de_cortesia_vencido_queda_sin_cobro(self):
        multa = self._apelacion(-timedelta(hours=1), cortesia=True)
        firmar_apelaciones_sin_respuesta(self.condominio)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CORTESIA)
        self.assertIn('sin cobro', mail.outbox[0].body)

    def test_si_no_ha_vencido_no_se_toca(self):
        multa = self._apelacion(timedelta(days=1))
        self.assertEqual(firmar_apelaciones_sin_respuesta(self.condominio), [])
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)

    def test_el_resumen_diario_cierra_los_vencidos_aunque_nadie_abra_la_app(self):
        multa = self._apelacion(-timedelta(hours=1))
        call_command('enviar_resumenes', stdout=StringIO())
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)
        self.assertTrue(any(c.to == ['apelante@test.local'] for c in mail.outbox))

    def test_queda_listo_para_exportar_a_gastos_comunes(self):
        multa = self._apelacion(-timedelta(hours=1))
        firmar_apelaciones_sin_respuesta(self.condominio)
        self.assertTrue(Multa.objects.filter(id=multa.id, estado=EstadoMulta.FIRME).exists())
        self.assertIn('lista', ' '.join(resumen_para_administracion(self.condominio)['puntos']))
