"""
Tests de la confirmacion previa al cobro.

El comite no vuelve a estudiar las multas que nadie apelo: eso lo devolveria al
papel de cuello de botella. Se detienen solo aquellas donde hay una señal
concreta de que la persona pudo no haber podido defenderse, y sobre esas se
pide una confirmacion, no una revision de fondo.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import CondicionEspecial, Condominio, Persona, RolOcupacion, Unidad
from multas.models import CanalNotificacion, EstadoMulta, Multa, Ticket, TipoActo
from multas.services import actualizar_multas_vencidas, motivo_para_confirmar
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_confirma_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ConfirmacionPreviaAlCobroTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Confirma', plazo_descargo_dias=5)
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 303')
        cls.comite = Usuario.objects.create_user(
            username='comite_confirma', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.administrador = Usuario.objects.create_user(
            username='admin_confirma', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('5.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _persona(self, **extra):
        datos = dict(
            condominio=self.condominio, unidad=self.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Pedro Plazo', cedula_identidad='3.333.333-3',
            domicilio='Depto 303', correo_electronico='pedro@test.local',
        )
        datos.update(extra)
        return Persona.objects.create(**datos)

    def _vencida(self, persona, canal_acuse=CanalNotificacion.EMAIL):
        """Una multa notificada cuyo plazo ya vencio sin apelacion."""
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=persona,
            descripcion='Ruido', fecha_hecho=timezone.now() - timedelta(days=20),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=persona, infraccion=self.infraccion,
            monto=Decimal('5.00'), estado=EstadoMulta.NOTIFICADA,
            fecha_notificacion=timezone.now() - timedelta(days=15),
            fecha_acuse=timezone.now() - timedelta(days=15),
            canal_acuse=canal_acuse,
            fecha_limite_descargo=timezone.now() - timedelta(days=1),
        )

    # -- Lo normal: nadie interviene -----------------------------------

    def test_sin_señales_la_multa_queda_firme_sola(self):
        """El caso corriente: el comite no vuelve a mirar lo que nadie apelo."""
        multa = self._vencida(self._persona())

        actualizar_multas_vencidas(self.condominio)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)
        self.assertIsNotNone(multa.fecha_firme)

    # -- Cuando si se detiene ------------------------------------------

    def test_una_condicion_declarada_detiene_el_cobro(self):
        persona = self._persona(
            nombre_completo='Dolores Mayor', cedula_identidad='1.111.111-1',
            condicion_especial=CondicionEspecial.REQUIERE_APOYO,
        )
        multa = self._vencida(persona)

        actualizar_multas_vencidas(self.condominio)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.POR_CONFIRMAR)
        self.assertIsNone(multa.fecha_firme, 'no puede quedar firme antes de que alguien confirme')
        self.assertIn('apoyo para tramites digitales', multa.historial.last().comentario)

    def test_el_fallecimiento_detiene_el_cobro(self):
        persona = self._persona(
            nombre_completo='Hector Fallecido', cedula_identidad='2.222.222-2',
            condicion_especial=CondicionEspecial.FALLECIDO,
        )
        multa = self._vencida(persona)
        actualizar_multas_vencidas(self.condominio)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.POR_CONFIRMAR)

    def test_si_solo_hubo_papel_en_el_buzon_se_detiene(self):
        """
        Nadie confirmo la recepcion: la notificacion se perfecciono dejando un
        papel. Pudo estar de viaje, hospitalizada, o simplemente no verlo.
        """
        multa = self._vencida(self._persona(), canal_acuse=CanalNotificacion.BUZON)

        actualizar_multas_vencidas(self.condominio)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.POR_CONFIRMAR)
        self.assertIn('buzon', multa.historial.last().comentario)

    def test_si_la_persona_confirmo_por_si_misma_no_se_detiene(self):
        for canal in (CanalNotificacion.EMAIL, CanalNotificacion.APP):
            with self.subTest(canal=canal):
                multa = self._vencida(
                    self._persona(cedula_identidad=f'9.000.00{canal[:1]}-0'), canal_acuse=canal,
                )
                self.assertEqual(motivo_para_confirmar(multa), '')

    # -- La confirmacion en si ------------------------------------------

    def _por_confirmar(self):
        persona = self._persona(
            nombre_completo='Dolores Mayor', cedula_identidad='1.111.111-1',
            condicion_especial=CondicionEspecial.REQUIERE_APOYO,
        )
        multa = self._vencida(persona)
        actualizar_multas_vencidas(self.condominio)
        multa.refresh_from_db()
        return multa

    def test_el_comite_confirma_el_cobro_y_queda_firme(self):
        multa = self._por_confirmar()
        self.client.force_authenticate(self.comite)

        respuesta = self.client.post(
            f'/api/multas/{multa.id}/confirmar-cobro/',
            {'comentario': 'Se verifico que si pudo defenderse'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)
        self.assertEqual(multa.monto, Decimal('5.00'), 'confirmar el cobro no cambia el monto')

    def test_el_comite_puede_convertirla_en_parte_de_cortesia(self):
        multa = self._por_confirmar()
        self.client.force_authenticate(self.comite)

        respuesta = self.client.post(
            f'/api/multas/{multa.id}/confirmar-cobro/',
            {'dar_cortesia': True, 'comentario': 'No pudo apelar por la app'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CORTESIA)
        self.assertEqual(multa.monto, Decimal('0.00'))
        self.assertIn('se condonan 5.00', multa.historial.last().comentario)

    def test_la_confirmacion_queda_sellada_con_el_motivo_de_la_alerta(self):
        multa = self._por_confirmar()
        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/confirmar-cobro/', {}, format='json')

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.CONFIRMACION_PREVIA_COBRO)
        self.assertFalse(acta.manifiesto['extra']['dio_cortesia'])
        self.assertIn('apoyo para tramites digitales', acta.manifiesto['extra']['motivo_de_la_alerta'])

    def test_no_se_confirma_dos_veces(self):
        multa = self._por_confirmar()
        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/confirmar-cobro/', {}, format='json')

        respuesta = self.client.post(f'/api/multas/{multa.id}/confirmar-cobro/', {}, format='json')
        self.assertEqual(respuesta.status_code, 400)

    def test_no_se_confirma_una_multa_que_no_estaba_esperando(self):
        multa = self._vencida(self._persona())
        actualizar_multas_vencidas(self.condominio)

        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(f'/api/multas/{multa.id}/confirmar-cobro/', {}, format='json')
        self.assertEqual(respuesta.status_code, 400)

    def test_el_administrador_no_confirma_por_el_comite(self):
        multa = self._por_confirmar()
        self.client.force_authenticate(self.administrador)
        respuesta = self.client.post(f'/api/multas/{multa.id}/confirmar-cobro/', {}, format='json')
        self.assertEqual(respuesta.status_code, 403)

    # -- No se cobra lo que sigue esperando -----------------------------

    def test_una_multa_por_confirmar_no_entra_al_gasto_comun(self):
        from gastos_comunes.utils import exportar_multas_firmes

        self._por_confirmar()
        lote = exportar_multas_firmes(self.condominio, '2026-08', self.administrador)
        self.assertIsNone(lote, 'nada que cobrar mientras no se confirme')

    def test_el_comite_sigue_interviniendo_una_sola_vez(self):
        """
        La confirmacion reemplaza a la resolucion de apelacion, no se suma:
        aqui no hubo apelacion que resolver.
        """
        multa = self._por_confirmar()
        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/confirmar-cobro/', {}, format='json')

        actos_del_comite = multa.actas_selladas.filter(actor=self.comite).count()
        self.assertEqual(actos_del_comite, 1)
