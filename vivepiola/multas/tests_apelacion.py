"""
Tests de la apelacion como proceso, no como formulario de una sola vez.

Dos cosas se protegen aqui: que el residente pueda seguir aportando prueba
mientras su caso siga abierto, y que el plazo obligue tambien al Comite. Una
apelacion que se responde cuando alguien se acuerda no es debido proceso.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import (
    Descargo, EstadoMulta, Multa, OrigenAntecedente, ResolucionDescargo, Ticket, TipoActo,
)
from multas.resumenes import resumen_para_comite
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_apela_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ApelacionConAntecedentesTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre='Condominio Apela', plazo_descargo_dias=5, plazo_resolucion_dias=15,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 202')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Ana Apela', cedula_identidad='2.020.202-0',
            domicilio='Depto 202', correo_electronico='ana@test.local',
        )
        cls.residente = Usuario.objects.create_user(
            username='ana', password='x', rol=Rol.RESIDENTE,
            condominio=cls.condominio, persona=cls.persona,
        )
        cls.otro_residente = Usuario.objects.create_user(
            username='otro', password='x', rol=Rol.RESIDENTE, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_apela', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('3.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def _notificada(self):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            descripcion='Ruido', fecha_hecho=timezone.now(),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad,
            persona_infractor=self.persona, infraccion=self.infraccion,
            monto=Decimal('3.00'), estado=EstadoMulta.NOTIFICADA,
            fecha_notificacion=timezone.now(), fecha_acuse=timezone.now(),
            fecha_limite_descargo=timezone.now() + timedelta(days=5),
        )

    def _apelar(self, multa):
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/descargo/', {'texto': 'No fui yo'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        multa.refresh_from_db()
        return multa.descargo

    # -- El plazo obliga tambien al Comite ------------------------------

    def test_al_apelar_arranca_el_plazo_que_tiene_el_comite(self):
        descargo = self._apelar(self._notificada())

        self.assertIsNotNone(descargo.fecha_limite_resolucion)
        esperado = descargo.fecha_presentacion + timedelta(days=15)
        self.assertAlmostEqual(descargo.fecha_limite_resolucion, esperado, delta=timedelta(minutes=1))
        self.assertFalse(descargo.resolucion_vencida)

    def test_una_apelacion_sin_responder_a_tiempo_queda_marcada(self):
        descargo = self._apelar(self._notificada())
        descargo.fecha_limite_resolucion = timezone.now() - timedelta(days=1)
        descargo.save(update_fields=['fecha_limite_resolucion'])

        descargo.refresh_from_db()
        self.assertTrue(descargo.resolucion_vencida)

    def test_una_apelacion_ya_resuelta_no_figura_vencida(self):
        descargo = self._apelar(self._notificada())
        descargo.fecha_limite_resolucion = timezone.now() - timedelta(days=1)
        descargo.resolucion = ResolucionDescargo.RECHAZADO
        descargo.save(update_fields=['fecha_limite_resolucion', 'resolucion'])

        self.assertFalse(descargo.resolucion_vencida, 'ya se respondio, aunque haya sido tarde')

    def test_el_resumen_del_comite_avisa_del_plazo_vencido_como_urgente(self):
        descargo = self._apelar(self._notificada())
        descargo.fecha_limite_resolucion = timezone.now() - timedelta(days=2)
        descargo.save(update_fields=['fecha_limite_resolucion'])

        resumen = resumen_para_comite(self.condominio)

        self.assertTrue(resumen['urgente'])
        self.assertTrue(any('VENCIDO' in p for p in resumen['puntos']), resumen['puntos'])

    def test_el_resumen_no_marca_urgencia_cuando_esta_en_plazo(self):
        self._apelar(self._notificada())
        resumen = resumen_para_comite(self.condominio)

        self.assertFalse(resumen['urgente'])
        self.assertTrue(any('por resolver' in p for p in resumen['puntos']), resumen['puntos'])

    # -- Antecedente adicional -----------------------------------------

    def test_el_residente_suma_prueba_despues_de_haber_apelado(self):
        """Una boleta o un certificado pueden llegar dias despues."""
        multa = self._notificada()
        self._apelar(multa)

        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/antecedente/',
            {'texto': 'Boleta que prueba que estaba fuera de la ciudad'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.descargo.antecedentes.count(), 1)
        antecedente = multa.descargo.antecedentes.first()
        self.assertEqual(antecedente.origen, OrigenAntecedente.RESIDENTE)
        self.assertEqual(antecedente.aportado_por, self.residente)

    def test_se_puede_adjuntar_un_archivo_al_antecedente(self):
        multa = self._notificada()
        self._apelar(multa)

        archivo = SimpleUploadedFile('boleta.pdf', b'%PDF-1.4 contenido', content_type='application/pdf')
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/antecedente/',
            {'texto': 'Boleta adjunta', 'archivo_adjunto': archivo}, format='multipart',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(respuesta.data['archivo_adjunto'])

    def test_el_antecedente_queda_sellado_en_el_expediente(self):
        multa = self._notificada()
        self._apelar(multa)
        self.client.force_authenticate(self.residente)
        self.client.post(
            f'/api/multas/{multa.id}/antecedente/', {'texto': 'Prueba nueva'}, format='json',
        )

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.ANTECEDENTE_APORTADO)
        self.assertEqual(acta.manifiesto['extra']['texto'], 'Prueba nueva')
        self.assertEqual(acta.manifiesto['extra']['origen'], OrigenAntecedente.RESIDENTE)

    def test_no_se_aportan_antecedentes_sin_haber_apelado(self):
        multa = self._notificada()
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/antecedente/', {'texto': 'Algo'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('apelacion', respuesta.data['detail'])

    def test_despues_de_resuelta_el_expediente_esta_cerrado(self):
        """Agregarle piezas a un caso ya resuelto lo falsearia."""
        multa = self._notificada()
        self._apelar(multa)

        self.client.force_authenticate(self.comite)
        self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )

        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/antecedente/', {'texto': 'Tarde'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('cerrado', respuesta.data['detail'])

    def test_nadie_aporta_prueba_al_expediente_de_otro(self):
        """
        Da 404 y no 403: a un vecino ajeno ni siquiera se le confirma que ese
        expediente existe. Saber quien tiene multas ya es informacion.
        """
        multa = self._notificada()
        self._apelar(multa)

        self.client.force_authenticate(self.otro_residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/antecedente/', {'texto': 'Me meto'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 404)
        multa.refresh_from_db()
        self.assertEqual(multa.descargo.antecedentes.count(), 0)

    def test_el_comite_ve_los_antecedentes_al_resolver(self):
        multa = self._notificada()
        self._apelar(multa)
        self.client.force_authenticate(self.residente)
        self.client.post(
            f'/api/multas/{multa.id}/antecedente/', {'texto': 'Estaba de viaje'}, format='json',
        )

        self.client.force_authenticate(self.comite)
        respuesta = self.client.get(f'/api/multas/{multa.id}/')
        antecedentes = respuesta.data['descargo']['antecedentes']

        self.assertEqual(len(antecedentes), 1)
        self.assertEqual(antecedentes[0]['texto'], 'Estaba de viaje')
        self.assertIn('fecha_limite_resolucion', respuesta.data['descargo'])
