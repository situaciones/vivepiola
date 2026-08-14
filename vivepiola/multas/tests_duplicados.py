"""
Tests de reportes duplicados.

Varios vecinos reportando el mismo hecho es lo normal, no la excepcion. Lo que
se protege aqui es que eso no derive en varias sanciones por un solo hecho, y
que quien reporta reciba una respuesta util sin enterarse de la sancion ajena.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, TipoActo
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_dup_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ReportesDuplicadosTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre='Condominio Duplicados', plazo_descargo_dias=5, ventana_duplicados_horas=24,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 808')
        cls.otra_unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 809')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Ruidoso Del 808', cedula_identidad='66.666.666-6',
            domicilio='Depto 808', correo_electronico='ruidoso@test.local',
        )

        def usuario(username, rol, persona=None):
            return Usuario.objects.create_user(
                username=username, password='x', rol=rol, condominio=cls.condominio, persona=persona,
            )

        cls.conserje = usuario('conserje_d', Rol.FISCALIZADOR)
        cls.comite = usuario('comite_d', Rol.COMITE)
        cls.administrador = usuario('admin_d', Rol.ADMINISTRADOR)
        cls.vecino = usuario('vecino_d', Rol.RESIDENTE)
        cls.otro_vecino = usuario('otro_vecino_d', Rol.RESIDENTE)

        cls.ruido = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos nocturnos',
            articulo_referencia='Art. 15', monto=Decimal('3.00'), estado=EstadoInfraccion.ACTIVA,
        )
        cls.mascota = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='MASCOTA-01', descripcion='Mascota suelta en espacios comunes',
            articulo_referencia='Art. 4', monto=Decimal('2.00'), estado=EstadoInfraccion.ACTIVA,
        )

    def reportar(self, usuario, descripcion='Ruidos molestos a las 23:00', horas_atras=1, unidad=None):
        self.client.force_authenticate(usuario)
        objetivo = unidad or self.unidad
        cuerpo = {
            'unidad': objetivo.id,
            'descripcion': descripcion,
            'fecha_hecho': (timezone.now() - timedelta(hours=horas_atras)).isoformat(),
        }
        if objetivo == self.unidad:
            cuerpo['persona_reportada'] = self.persona.id
        respuesta = self.client.post('/api/tickets/', cuerpo)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return respuesta

    # -- La garantia central ------------------------------------------

    def test_tres_vecinos_reportan_lo_mismo_y_hay_una_sola_multa(self):
        self.reportar(self.conserje)
        self.reportar(self.vecino)
        self.reportar(self.otro_vecino)

        self.assertEqual(Multa.objects.filter(unidad=self.unidad).count(), 1,
                         'un solo hecho no puede abrir tres sanciones')
        multa = Multa.objects.get(unidad=self.unidad)
        self.assertEqual(multa.corroboraciones.count(), 2, 'los otros dos quedan como respaldo')

    def test_al_segundo_se_le_informa_la_etapa_sin_datos_del_vecino(self):
        self.reportar(self.conserje)
        respuesta = self.reportar(self.vecino)

        self.assertTrue(respuesta.data['duplicado'])
        self.assertEqual(respuesta.data['expediente_estado'], EstadoMulta.EN_REVISION)
        self.assertEqual(respuesta.data['reportes_del_hecho'], 2)
        self.assertIn('pendiente de tipificacion', respuesta.data['mensaje'])
        # Quien reporta no debe enterarse del monto ni de la persona sancionada.
        cuerpo = str(respuesta.data)
        self.assertNotIn('3.00', cuerpo)
        self.assertNotIn('Ruidoso Del 808', cuerpo)

    def test_si_ya_fue_notificado_se_informa_esa_etapa(self):
        self.reportar(self.conserje)
        multa = Multa.objects.get(unidad=self.unidad)

        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.ruido.id})
        self.client.force_authenticate(self.administrador)
        self.client.post(f'/api/multas/{multa.id}/notificar/')

        respuesta = self.reportar(self.vecino)
        self.assertTrue(respuesta.data['duplicado'])
        self.assertEqual(respuesta.data['expediente_estado'], EstadoMulta.NOTIFICADA)
        self.assertIn('ya fue notificado', respuesta.data['mensaje'].lower())

    # -- Cuando SI debe abrirse un expediente nuevo -------------------

    def test_hecho_distinto_en_la_misma_unidad_abre_su_propio_expediente(self):
        self.reportar(self.conserje, 'Ruidos molestos a las 23:00')
        self.reportar(self.vecino, 'La mascota andaba suelta en espacios comunes')
        self.assertEqual(Multa.objects.filter(unidad=self.unidad).count(), 2)

    def test_otra_unidad_no_se_agrupa(self):
        self.reportar(self.conserje)
        self.reportar(self.vecino, unidad=self.otra_unidad)
        self.assertEqual(Multa.objects.count(), 2)

    def test_fuera_de_la_ventana_abre_expediente_nuevo(self):
        self.reportar(self.conserje, horas_atras=1)
        self.reportar(self.vecino, horas_atras=72)  # tres dias antes
        self.assertEqual(Multa.objects.filter(unidad=self.unidad).count(), 2)

    def test_si_el_comite_rechazo_el_reporte_uno_nuevo_abre_expediente(self):
        self.reportar(self.conserje)
        multa = Multa.objects.get(unidad=self.unidad)
        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/rechazar/', {'motivo': 'Sin merito'})

        self.reportar(self.vecino)
        self.assertEqual(Multa.objects.filter(unidad=self.unidad).count(), 2,
                         'un hecho descartado no debe absorber reportes posteriores')

    def test_ventana_en_cero_desactiva_la_agrupacion(self):
        self.condominio.ventana_duplicados_horas = 0
        self.condominio.save(update_fields=['ventana_duplicados_horas'])
        self.reportar(self.conserje)
        self.reportar(self.vecino)
        self.assertEqual(Multa.objects.filter(unidad=self.unidad).count(), 2)

    # -- Efecto en la prueba ------------------------------------------

    def test_las_corroboraciones_quedan_selladas_en_el_acta(self):
        self.reportar(self.conserje)
        self.reportar(self.vecino)
        multa = Multa.objects.get(unidad=self.unidad)

        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.ruido.id})

        acta = multa.actas_selladas.filter(tipo_acto=TipoActo.APROBACION).first()
        corroboraciones = acta.manifiesto['corroboraciones']
        self.assertEqual(len(corroboraciones), 1)
        self.assertEqual(corroboraciones[0]['reportado_por'], 'vecino_d')

        # La cadena sigue integra con la corroboracion adentro.
        respuesta = self.client.get(f'/api/multas/{multa.id}/verificar-integridad/')
        self.assertTrue(respuesta.data['integra'])

    def test_el_comite_ve_los_reportes_de_respaldo(self):
        self.reportar(self.conserje)
        self.reportar(self.vecino)
        multa = Multa.objects.get(unidad=self.unidad)

        self.client.force_authenticate(self.comite)
        datos = self.client.get(f'/api/multas/{multa.id}/').data
        self.assertEqual(len(datos['corroboraciones']), 1)
        self.assertEqual(datos['corroboraciones'][0]['reportado_por'], 'vecino_d')

    def test_corroboracion_anonima_no_expone_al_vecino(self):
        self.reportar(self.conserje)
        self.client.force_authenticate(self.vecino)
        self.client.post('/api/tickets/', {
            'unidad': self.unidad.id,
            'descripcion': 'Ruidos molestos a las 23:00',
            'fecha_hecho': (timezone.now() - timedelta(hours=1)).isoformat(),
            'anonimo': True,
        })
        multa = Multa.objects.get(unidad=self.unidad)

        self.client.force_authenticate(self.comite)
        datos = self.client.get(f'/api/multas/{multa.id}/').data
        self.assertEqual(datos['corroboraciones'][0]['reportado_por'], 'Denuncia anonima')
