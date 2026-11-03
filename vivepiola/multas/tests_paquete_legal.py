"""
Ajustes a la orientacion legal recibida (Ley 21.442 y datos personales):

- la notificacion trae el contenido minimo: hecho con fecha y hora, pruebas,
  calificacion, plazo y el derecho a ir al Juzgado de Policia Local;
- la advertencia automatica lo dice y ofrece revision humana, y no agrava
  otra sancion mientras corre su plazo;
- el Comite gradua el monto solo dentro del rango del reglamento, y la
  reincidencia a lo mas dobla la multa;
- la exportacion a gastos comunes dice en que unidad va cada monto.
"""

import csv
import io
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from gastos_comunes.utils import exportar_multas_firmes
from multas.models import EstadoMulta, EvidenciaFoto, Multa, Ticket
from multas.services import notificar_multa, verificar_reincidencia
from reglamentos.models import EstadoInfraccion, Gravedad, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='sinconflicto_paquete_legal_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class PaqueteLegalTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Edificio Norma', cortesias_antes_de_multar=0)
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 808')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Rosa Norma', cedula_identidad='9.999.999-9',
            domicilio='Depto 808', correo_electronico='rosa@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_n', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.comite = Usuario.objects.create_user(
            username='comite_n', password='x', rol=Rol.COMITE, condominio=cls.condominio,
        )
        cls.ruido = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('1.00'), monto_minimo=Decimal('0.50'),
            monto_maximo=Decimal('2.00'), gravedad=Gravedad.GRAVE, factor_reincidencia=Decimal('2.00'),
            estado=EstadoInfraccion.ACTIVA,
        )

    def _multa(self, estado=EstadoMulta.EN_REVISION, cortesia=False, dias_atras=1):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, persona_reportada=self.persona,
            creado_por=self.conserje, descripcion='Musica a todo volumen', ubicacion='Piso 8',
            fecha_hecho=timezone.now() - timedelta(days=dias_atras),
        )
        return Multa.objects.create(
            condominio=self.condominio, ticket=ticket, unidad=self.unidad, persona_infractor=self.persona,
            estado=estado, infraccion=self.ruido,
            monto=Decimal('0.00') if cortesia else Decimal('1.00'),
            monto_sin_cortesia=Decimal('1.00') if cortesia else None,
            fecha_notificacion=timezone.now() - timedelta(days=dias_atras) if estado != EstadoMulta.EN_REVISION else None,
        )

    # -- Contenido minimo de la notificacion --------------------------------

    def test_la_notificacion_trae_los_siete_elementos(self):
        multa = self._multa()
        EvidenciaFoto.objects.create(ticket=multa.ticket, imagen='evidencias/x.jpg', sha256='0' * 64)
        multa.estado = EstadoMulta.APROBADA
        multa.aprobada_por = self.comite
        multa.save()
        notificar_multa(multa, usuario=None)

        cuerpo = mail.outbox[-1].body
        self.assertIn('Depto 808', cuerpo)                       # 1. unidad
        self.assertIn('El hecho se registro el', cuerpo)          # 2. fecha y hora
        self.assertIn('Piso 8', cuerpo)
        self.assertIn('1 fotografia(s)', cuerpo)                  # 3. pruebas
        self.assertIn('personal de Edificio Norma', cuerpo)
        self.assertIn('Art. 15', cuerpo)                          # 4. articulo
        self.assertIn('Calificacion de la falta: grave', cuerpo)  # 5. calificacion y monto
        self.assertIn('1.00', cuerpo)
        self.assertIn('dias habiles', cuerpo)                     # 6. plazo
        self.assertIn('Juzgado de Policia Local', cuerpo)         # 7. a quien reclamar
        self.assertIn('3 meses', cuerpo)
        self.assertNotIn('automatizada', cuerpo, 'esta multa la aprobo el Comite')

    def test_la_advertencia_automatica_lo_dice_y_ofrece_revision(self):
        multa = self._multa(cortesia=True)
        notificar_multa(multa, usuario=None)
        cuerpo = mail.outbox[-1].body
        self.assertIn('emitida de forma automatizada', cuerpo)
        self.assertIn('pedir que una persona', cuerpo)

    # -- La advertencia no agrava mientras corre su plazo --------------------

    def test_la_advertencia_vigente_no_cuenta_para_reincidencia(self):
        self._multa(EstadoMulta.NOTIFICADA, cortesia=True, dias_atras=3)
        es_reincidencia, _, _ = verificar_reincidencia(self.unidad, self.ruido)
        self.assertFalse(es_reincidencia)

    def test_la_advertencia_cerrada_si_cuenta(self):
        self._multa(EstadoMulta.CORTESIA, cortesia=True, dias_atras=30)
        es_reincidencia, _, _ = verificar_reincidencia(self.unidad, self.ruido)
        self.assertTrue(es_reincidencia)

    # -- Monto dentro del rango del reglamento ------------------------------

    def _aprobar(self, multa, monto):
        self.client.force_authenticate(self.comite)
        return self.client.post(f'/api/multas/{multa.id}/aprobar/', {
            'infraccion_id': self.ruido.id, 'monto': monto,
        }, format='json', SERVER_NAME='localhost')

    def test_el_comite_gradua_dentro_del_rango(self):
        multa = self._multa()
        r = self._aprobar(multa, '1.50')
        self.assertEqual(r.status_code, 200, r.data)
        multa.refresh_from_db()
        self.assertEqual(multa.monto, Decimal('1.50'))

    def test_fuera_del_rango_se_rechaza(self):
        multa = self._multa()
        r = self._aprobar(multa, '5.00')
        self.assertEqual(r.status_code, 400)
        self.assertIn('entre 0.50 y 2.00', r.data['detail'])
        self.assertFalse(multa.votos_aprobacion.exists(), 'un voto invalido no queda registrado')

    def test_la_reincidencia_a_lo_mas_dobla(self):
        self.ruido.factor_reincidencia = Decimal('3.00')
        self.ruido.save(update_fields=['factor_reincidencia'])
        self._multa(EstadoMulta.FIRME, dias_atras=20)
        multa = self._multa()
        self.assertEqual(self._aprobar(multa, '1.00').status_code, 200)
        multa.refresh_from_db()
        self.assertEqual(multa.monto, Decimal('2.00'), 'el factor 3 se topa en el doble')

    # -- Exportacion con su unidad -------------------------------------------

    def test_la_exportacion_dice_la_unidad_de_cada_monto(self):
        uf = self._multa(EstadoMulta.FIRME)
        pesos = InfraccionCatalogo.objects.create(
            condominio=self.condominio, codigo='BASURA', descripcion='Basura', articulo_referencia='Art. 18',
            monto=Decimal('20000'), unidad_monto='CLP', estado=EstadoInfraccion.ACTIVA,
        )
        clp = self._multa(EstadoMulta.FIRME)
        clp.infraccion = pesos
        clp.monto = Decimal('20000')
        clp.save()

        lote = exportar_multas_firmes(self.condominio, '2026-11', None)
        filas = list(csv.DictReader(io.StringIO(lote.archivo_csv.read().decode('utf-8-sig'))))
        unidades = {int(f['multa_id']): f['unidad_monto'] for f in filas}
        self.assertEqual(unidades, {uf.id: 'UF', clp.id: 'CLP'})
        self.assertEqual(lote.totales_por_unidad(), {'UF': Decimal('1.00'), 'CLP': Decimal('20000.00')})
