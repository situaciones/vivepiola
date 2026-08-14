"""
Tests del parte de cortesia y de la reincidencia que lo sostiene.

Un parte de cortesia no es perdonar el hecho: es darlo por acreditado y no
cobrarlo. La diferencia importa, porque queda en el registro y hace que la
proxima falta igual ya no admita cortesia. Si no contara para la reincidencia,
se podria pedir indefinidamente por lo mismo.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from gastos_comunes.utils import exportar_multas_firmes
from multas.models import Descargo, EstadoMulta, Multa, ResolucionDescargo, Ticket
from multas.services import proponer_resoluciones, verificar_reincidencia
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_cortesia_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ParteDeCortesiaTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Cortesia', plazo_descargo_dias=5)
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 606')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Cesar Cortes', cedula_identidad='6.666.666-6',
            domicilio='Depto 606', correo_electronico='cesar@test.local',
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_cortesia', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.administrador = Usuario.objects.create_user(
            username='admin_cortesia', password='x', rol=Rol.ADMINISTRADOR, condominio=cls.condominio,
        )
        cls.residente = Usuario.objects.create_user(
            username='cesar', password='x', rol=Rol.RESIDENTE,
            condominio=cls.condominio, persona=cls.persona,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('4.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _con_descargo(self, monto=Decimal('4.00')):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Ruido', fecha_hecho=timezone.now(),
        )
        multa = Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, infraccion=self.infraccion,
            monto=monto, estado=EstadoMulta.CON_DESCARGO,
            fecha_notificacion=timezone.now(),
            fecha_limite_descargo=timezone.now() + timedelta(days=5),
        )
        Descargo.objects.create(multa=multa, presentado_por=self.residente, texto='Fue una sola vez')
        return multa

    def _resolver(self, multa, **datos):
        self.client.force_authenticate(self.comite)
        return self.client.post(f'/api/multas/{multa.id}/resolver-descargo/', datos, format='json')

    # -- Que hace un parte de cortesia ---------------------------------

    def test_la_cortesia_deja_la_falta_acreditada_pero_sin_cobro(self):
        multa = self._con_descargo()

        respuesta = self._resolver(multa, resolucion='CORTESIA', comentario='Primera vez')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CORTESIA)
        self.assertEqual(multa.monto, Decimal('0.00'))
        self.assertIsNotNone(multa.fecha_firme)
        # El monto condonado se conserva: sin ese dato no se puede explicar
        # despues de cuanto fue la cortesia que se dio.
        self.assertEqual(multa.descargo.monto_original, Decimal('4.00'))
        self.assertEqual(multa.descargo.resolucion, ResolucionDescargo.CORTESIA)

    def test_la_cortesia_no_es_lo_mismo_que_anular(self):
        cortesia = self._con_descargo()
        self._resolver(cortesia, resolucion='CORTESIA')
        anulada = self._con_descargo()
        self._resolver(anulada, resolucion='ACEPTADO')

        cortesia.refresh_from_db()
        anulada.refresh_from_db()
        self.assertEqual(cortesia.estado, EstadoMulta.CORTESIA)
        self.assertEqual(anulada.estado, EstadoMulta.ANULADA)

        # La anulada desaparece del historial sancionatorio; la cortesia no.
        hay_reincidencia, previa, _ = verificar_reincidencia(self.unidad, self.infraccion)
        self.assertTrue(hay_reincidencia)
        self.assertEqual(previa.id, cortesia.id)

    def test_un_parte_de_cortesia_no_se_cobra_en_el_gasto_comun(self):
        multa = self._con_descargo()
        self._resolver(multa, resolucion='CORTESIA')

        lote = exportar_multas_firmes(self.condominio, '2026-08', self.administrador)
        self.assertIsNone(lote, 'no hay nada que cobrar, asi que no se genera lote')
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CORTESIA, 'no pasa a EXPORTADA porque no hay que cobrar')

    def test_una_multa_firme_si_se_cobra_y_la_cortesia_no(self):
        """Con las dos en el mismo periodo, solo la firme entra al lote."""
        cortesia = self._con_descargo()
        self._resolver(cortesia, resolucion='CORTESIA')
        firme = self._con_descargo()
        self._resolver(firme, resolucion='RECHAZADO')

        lote = exportar_multas_firmes(self.condominio, '2026-08', self.administrador)
        self.assertEqual(lote.total_monto, Decimal('4.00'), 'solo el monto de la firme')

        contenido = lote.archivo_csv.read().decode('utf-8-sig')
        self.assertEqual(len(contenido.strip().splitlines()), 2, 'encabezado + una sola fila')

    def test_la_cortesia_hace_que_la_siguiente_falta_igual_ya_no_la_admita(self):
        primera = self._con_descargo()
        self._resolver(primera, resolucion='CORTESIA')

        segunda = self._con_descargo()
        opciones = {o['resolucion'] for o in proponer_resoluciones(segunda)}
        self.assertNotIn(
            ResolucionDescargo.CORTESIA, opciones,
            'ya se le dio una cortesia por esta misma infraccion',
        )

    def test_el_historial_explica_que_se_condono_y_que_no_habra_otra(self):
        multa = self._con_descargo()
        self._resolver(multa, resolucion='CORTESIA')

        comentario = multa.historial.last().comentario
        self.assertIn('PARTE DE CORTESIA', comentario)
        self.assertIn('4.00', comentario)
        self.assertIn('ya no admite cortesia', comentario)

    # -- El sistema propone, el comite decide --------------------------

    def test_sin_antecedentes_se_propone_cortesia_con_su_fundamento(self):
        multa = self._con_descargo()
        opciones = proponer_resoluciones(multa)

        cortesia = next(o for o in opciones if o['resolucion'] == ResolucionDescargo.CORTESIA)
        self.assertIn('primera vez', cortesia['fundamento'].lower())
        self.assertIn('RUIDO-01', cortesia['fundamento'])

    def test_con_antecedentes_se_propone_mantener_la_multa(self):
        previa = self._con_descargo()
        self._resolver(previa, resolucion='RECHAZADO')

        multa = self._con_descargo()
        opciones = proponer_resoluciones(multa)
        self.assertEqual(opciones[0]['resolucion'], ResolucionDescargo.RECHAZADO)
        self.assertIn('reiterada', opciones[0]['fundamento'])

    def test_anular_siempre_esta_disponible(self):
        multa = self._con_descargo()
        opciones = {o['resolucion'] for o in proponer_resoluciones(multa)}
        self.assertIn(ResolucionDescargo.ACEPTADO, opciones)

    def test_el_comite_ve_las_propuestas_por_la_api(self):
        multa = self._con_descargo()
        self.client.force_authenticate(self.comite)
        respuesta = self.client.get(f'/api/multas/{multa.id}/propuestas-resolucion/')

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertTrue(respuesta.data['opciones'])
        for opcion in respuesta.data['opciones']:
            self.assertTrue(opcion['fundamento'], 'una propuesta sin fundamento no sirve para decidir')

    def test_el_residente_no_ve_las_propuestas_del_comite(self):
        multa = self._con_descargo()
        self.client.force_authenticate(self.residente)
        respuesta = self.client.get(f'/api/multas/{multa.id}/propuestas-resolucion/')
        self.assertEqual(respuesta.status_code, 403)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ReincidenciaDeMultasCursadasSolasTestCase(APITestCase):
    """
    Las multas que se cursan solas no tienen fecha_aprobacion, porque nadie las
    aprobo. Contar solo esa fecha las dejaba fuera del historial y la
    reincidencia dejaba de detectarse justo en el camino normal del sistema.
    """

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Reinc')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 808')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Rita Reincidente', cedula_identidad='8.888.888-8',
            domicilio='Depto 808', correo_electronico='rita@test.local',
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='MASCOTA-01', descripcion='Mascota sin correa',
            articulo_referencia='Art. 4', monto=Decimal('2.00'), estado=EstadoInfraccion.ACTIVA,
            factor_reincidencia=Decimal('2.00'),
        )

    def _multa(self, estado, aprobada=False, hace_dias=1):
        cuando = timezone.now() - timedelta(days=hace_dias)
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Perro suelto', fecha_hecho=cuando,
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, infraccion=self.infraccion,
            monto=Decimal('2.00'), estado=estado,
            fecha_aprobacion=cuando if aprobada else None,
            fecha_notificacion=cuando,
        )

    def test_una_multa_cursada_sola_cuenta_como_antecedente(self):
        previa = self._multa(EstadoMulta.NOTIFICADA, aprobada=False, hace_dias=10)

        hay, primera, texto = verificar_reincidencia(self.unidad, self.infraccion)

        self.assertTrue(hay, 'sin fecha_aprobacion igual es una sancion previa')
        self.assertEqual(primera.id, previa.id)
        self.assertIn('MASCOTA-01', texto)

    def test_una_multa_tipificada_a_mano_tambien_cuenta(self):
        previa = self._multa(EstadoMulta.FIRME, aprobada=True, hace_dias=10)
        hay, primera, _ = verificar_reincidencia(self.unidad, self.infraccion)
        self.assertTrue(hay)
        self.assertEqual(primera.id, previa.id)

    def test_el_texto_distingue_una_cortesia_previa_de_una_multa_previa(self):
        self._multa(EstadoMulta.CORTESIA, aprobada=False, hace_dias=10)
        _, _, texto = verificar_reincidencia(self.unidad, self.infraccion)
        self.assertIn('parte de cortesia', texto)

    def test_fuera_de_la_ventana_legal_no_hay_reincidencia(self):
        self._multa(EstadoMulta.FIRME, aprobada=True, hace_dias=400)
        hay, _, _ = verificar_reincidencia(self.unidad, self.infraccion)
        self.assertFalse(hay)

    def test_una_multa_anulada_no_deja_antecedente(self):
        self._multa(EstadoMulta.ANULADA, aprobada=True, hace_dias=10)
        hay, _, _ = verificar_reincidencia(self.unidad, self.infraccion)
        self.assertFalse(hay)
