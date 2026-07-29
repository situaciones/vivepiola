"""
Tests del resumen agrupado de pendientes.

Lo que se protege: que llegue UN aviso con todo junto, que no se repita, que
no se envie cuando no hay nada, y que cada rol reciba solo lo suyo.
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
from multas.models import EstadoMulta, Multa, Ticket
from multas.resumenes import resumen_para_administracion, resumen_para_comite
from novedades.models import EstadoNovedad, NovedadLibro, TipoNovedad
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_res_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ResumenPendientesTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Resumen')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 900')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Vecina Resumen', cedula_identidad='77.777.777-7',
            domicilio='Depto 900', correo_electronico='vecina@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_r', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_r', password='x', rol=Rol.COMITE, condominio=cls.condominio,
            email='comite@test.local', telefono='+56900000001',
        )
        cls.administrador = Usuario.objects.create_user(
            username='admin_r', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
            email='admin@test.local',
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('2.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _multa(self, estado=EstadoMulta.EN_REVISION, dias_atras=0):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            creado_por=self.conserje, descripcion='Hecho',
            fecha_hecho=timezone.now() - timedelta(days=dias_atras, hours=1),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, estado=estado, infraccion=self.infraccion,
            monto=Decimal('2.00'),
        )

    def _correr(self, **extra):
        salida = StringIO()
        call_command('enviar_resumenes', stdout=salida, **extra)
        return salida.getvalue()

    # -- Sin pendientes, silencio ------------------------------------

    def test_sin_pendientes_no_envia_nada(self):
        self._correr()
        self.assertEqual(len(mail.outbox), 0)
        self.condominio.refresh_from_db()
        self.assertIsNone(self.condominio.ultimo_resumen_enviado)

    # -- Un solo aviso con todo junto --------------------------------

    def test_un_solo_aviso_agrupa_los_casos(self):
        for _ in range(3):
            self._multa(EstadoMulta.EN_REVISION)

        self._correr()

        # Un correo al comite, no uno por caso.
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertIn('comite@test.local', correo.to)
        self.assertIn('3 casos por revisar', correo.body)
        self.assertIn('/app', correo.body)

    def test_cada_rol_recibe_solo_lo_suyo(self):
        self._multa(EstadoMulta.EN_REVISION)      # del comite
        self._multa(EstadoMulta.APROBADA)         # de la administracion

        self._correr()
        self.assertEqual(len(mail.outbox), 2)
        por_destino = {c.to[0]: c.body for c in mail.outbox}

        self.assertIn('1 caso por revisar', por_destino['comite@test.local'])
        self.assertNotIn('por notificar', por_destino['comite@test.local'])

        self.assertIn('1 multa aprobada por notificar', por_destino['admin@test.local'])
        self.assertNotIn('por revisar', por_destino['admin@test.local'])

    # -- No repetir ---------------------------------------------------

    def test_no_repite_el_aviso_el_mismo_dia(self):
        self._multa(EstadoMulta.EN_REVISION)

        self._correr()
        self.assertEqual(len(mail.outbox), 1)

        self._correr()  # segunda corrida el mismo dia
        self.assertEqual(len(mail.outbox), 1, 'no debe volver a avisar')

    def test_forzar_reenvia(self):
        self._multa(EstadoMulta.EN_REVISION)
        self._correr()
        self._correr(forzar=True)
        self.assertEqual(len(mail.outbox), 2)

    def test_vuelve_a_avisar_pasado_el_intervalo(self):
        self._multa(EstadoMulta.EN_REVISION)
        self._correr()

        self.condominio.refresh_from_db()
        self.condominio.ultimo_resumen_enviado = timezone.now() - timedelta(hours=30)
        self.condominio.save(update_fields=['ultimo_resumen_enviado'])

        self._correr()
        self.assertEqual(len(mail.outbox), 2)

    # -- Prioridades y urgencia ---------------------------------------

    def test_los_plazos_por_vencer_se_marcan_urgentes(self):
        NovedadLibro.objects.create(
            condominio=self.condominio, unidad=self.unidad, solicitante=None,
            tipo=TipoNovedad.RECLAMO, texto='Filtracion en el pasillo',
            fecha_limite_respuesta=timezone.now() + timedelta(days=1),
            estado=EstadoNovedad.PENDIENTE,
        )
        resumen = resumen_para_administracion(self.condominio)
        self.assertTrue(resumen['urgente'])
        self.assertIn('plazo legal por vencer', ' '.join(resumen['puntos']))

    def test_el_resumen_del_comite_pone_primero_lo_urgente(self):
        self._multa(EstadoMulta.EN_REVISION)
        self._multa(EstadoMulta.CON_DESCARGO, dias_atras=5)
        resumen = resumen_para_comite(self.condominio)
        self.assertEqual(resumen['total'], 2)
        self.assertIn('por revisar', resumen['puntos'][0])

    # -- Simulacion ---------------------------------------------------

    def test_simular_muestra_pero_no_envia(self):
        self._multa(EstadoMulta.EN_REVISION)
        salida = self._correr(simular=True)

        self.assertIn('1 caso por revisar', salida)
        self.assertEqual(len(mail.outbox), 0)
        self.condominio.refresh_from_db()
        self.assertIsNone(self.condominio.ultimo_resumen_enviado)
