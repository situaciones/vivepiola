"""
Tests de la cortesia automatica por conteo.

El objetivo de una comunidad no es recaudar sino que la gente sepa que hay una
norma, y quien la incumple por primera vez casi siempre corrige con el aviso.
Por eso las primeras faltas se notifican sin cobro. Lo que se cuida aqui es que
esa generosidad tenga limites: no aplica a lo grave, se consume sola, y el
aviso dice con todas sus letras cuanto se habria cobrado.
"""

import tempfile
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.models import EstadoMulta, Multa, TipoActo
from multas.services import actualizar_multas_vencidas, corresponde_cortesia
from reglamentos.models import EstadoInfraccion, Gravedad, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='vivepiola_cortesia_auto_')


def _respuesta_ia(codigo, confianza=90):
    texto = f'{{"codigo": "{codigo}", "confianza": {confianza}, "fundamento": "Encuadre."}}'
    return SimpleNamespace(content=[SimpleNamespace(type='text', text=texto)])


@override_settings(MEDIA_ROOT=MEDIA_TEMP, ANTHROPIC_API_KEY='sk-ant-de-prueba')
class CortesiaAutomaticaTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(
            nombre='Condominio Cortesia Auto', cortesias_antes_de_multar=2,
        )
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 707')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Pia Primera', cedula_identidad='7.070.707-0',
            domicilio='Depto 707', correo_electronico='pia@test.local',
        )
        cls.conserje = Usuario.objects.create_user(
            username='conserje_ca', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )
        cls.ruido = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('4.00'),
            gravedad=Gravedad.LEVE, estado=EstadoInfraccion.ACTIVA,
        )
        cls.grave = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RIESGO-01', descripcion='Manipular el tablero electrico',
            articulo_referencia='Art. 30', monto=Decimal('20.00'),
            gravedad=Gravedad.GRAVISIMA, estado=EstadoInfraccion.ACTIVA,
        )
        cls.contencion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='OBRA-01', descripcion='Obra sin permiso',
            articulo_referencia='Art. 40', monto=Decimal('15.00'),
            gravedad=Gravedad.GRAVE, conlleva_contencion=True, estado=EstadoInfraccion.ACTIVA,
        )

    def _denunciar(self, codigo='RUIDO-01', descripcion='Ruido en la noche', dias_atras=0):
        """
        `dias_atras` separa los hechos en el tiempo. Hace falta porque dos
        reportes seguidos sobre la misma unidad se entienden como el MISMO
        hecho y se agrupan, en vez de abrir dos expedientes.
        """
        mail.outbox = []
        self.client.force_authenticate(self.conserje)
        cuando = timezone.now() - timedelta(days=dias_atras, hours=1)
        cliente = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: _respuesta_ia(codigo)))
        with patch('anthropic.Anthropic', return_value=cliente):
            respuesta = self.client.post('/api/tickets/', {
                'unidad': self.unidad.id, 'persona_reportada': self.persona.id,
                'descripcion': descripcion, 'fecha_hecho': cuando.isoformat(),
            }, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Multa.objects.get(ticket_id=respuesta.data['id'])

    # -- Las primeras se avisan sin cobrar ------------------------------

    def test_la_primera_falta_se_avisa_sin_cobro(self):
        multa = self._denunciar()

        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertTrue(multa.es_aviso_de_cortesia)
        self.assertEqual(multa.monto, Decimal('0.00'))
        self.assertEqual(multa.monto_sin_cortesia, Decimal('4.00'), 'se conserva lo que se habria cobrado')

    def test_el_aviso_dice_que_no_se_cobra_y_cuanto_se_evito(self):
        """Sin ese numero, "esto no se cobra" no le dice nada a nadie."""
        self._denunciar()
        cuerpo = mail.outbox[0].body

        self.assertIn('ESTE AVISO NO TIENE COBRO', cuerpo)
        self.assertIn('4.00', cuerpo)
        self.assertIn('si esta misma situacion se repite', cuerpo.lower())
        self.assertNotIn('Monto: 0.00', cuerpo)
        # No puede empezar hablando de una multa y terminar diciendo que no
        # hay cobro: quien lo lee se queda con lo primero.
        self.assertNotIn('se ha cursado una multa', cuerpo)
        self.assertIn('se registro una falta', cuerpo)

    def test_el_asunto_del_correo_no_asusta_con_una_multa_que_no_existe(self):
        self._denunciar()
        self.assertIn('sin cobro', mail.outbox[0].subject)

    def test_la_segunda_falta_todavia_es_aviso(self):
        self._denunciar(dias_atras=10)
        segunda = self._denunciar(descripcion='Ruido otra vez, otra noche', dias_atras=5)

        self.assertTrue(segunda.es_aviso_de_cortesia)
        self.assertEqual(segunda.monto, Decimal('0.00'))

    def test_la_tercera_ya_se_cobra(self):
        self._denunciar(dias_atras=10)
        self._denunciar(descripcion='Segunda vez', dias_atras=5)
        tercera = self._denunciar(descripcion='Tercera vez')

        self.assertFalse(tercera.es_aviso_de_cortesia)
        self.assertGreater(tercera.monto, Decimal('0.00'))

    def test_el_aviso_dice_cuantos_le_quedan(self):
        multa = self._denunciar()
        comentarios = ' '.join(multa.historial.values_list('comentario', flat=True))

        self.assertIn('falta numero 1', comentarios)
        self.assertIn('Le queda 1 aviso mas', comentarios)

    # -- Lo grave nunca admite cortesia ---------------------------------

    def test_una_falta_gravisima_se_cobra_desde_la_primera(self):
        """Avisar sin consecuencia frente a un riesgo real es el mensaje contrario."""
        multa = self._denunciar(codigo='RIESGO-01', descripcion='Manipulo el tablero electrico')

        self.assertFalse(multa.es_aviso_de_cortesia)
        self.assertEqual(multa.monto, Decimal('20.00'))

    def test_una_falta_que_conlleva_contencion_tampoco(self):
        multa = self._denunciar(codigo='OBRA-01', descripcion='Obra sin permiso en el departamento')

        self.assertFalse(multa.es_aviso_de_cortesia)
        self.assertEqual(multa.monto, Decimal('15.00'))

    def test_una_falta_grave_pero_no_gravisima_si_admite_cortesia(self):
        """El corte esta en GRAVISIMA, no en GRAVE: si no, la cortesia no existiria."""
        self.contencion.conlleva_contencion = False
        self.contencion.save(update_fields=['conlleva_contencion'])

        multa = self._denunciar(codigo='OBRA-01', descripcion='Obra sin permiso')
        self.assertTrue(multa.es_aviso_de_cortesia)

    # -- El cupo es de la unidad y se consume solo ----------------------

    def test_el_cupo_se_gasta_con_faltas_de_cualquier_tipo(self):
        """Dos faltas distintas gastan el cupo igual que dos iguales."""
        self._denunciar(codigo='RUIDO-01', dias_atras=10)
        multa = self._denunciar(codigo='RUIDO-01', descripcion='Otra cosa distinta', dias_atras=5)
        self.assertTrue(multa.es_aviso_de_cortesia)

        tercera = self._denunciar(descripcion='Y una tercera')
        self.assertFalse(tercera.es_aviso_de_cortesia)

    def test_una_falta_anulada_no_gasta_cupo(self):
        """Si el hecho se cayo, no puede contarle en contra a nadie."""
        primera = self._denunciar(dias_atras=10)
        primera.estado = EstadoMulta.ANULADA
        primera.save(update_fields=['estado'])

        segunda = self._denunciar(descripcion='Otra', dias_atras=5)
        procede, motivo = corresponde_cortesia(segunda)
        self.assertIn('falta numero 1', motivo, 'la anulada no deberia contarse')

    def test_con_cupo_cero_se_cobra_desde_la_primera(self):
        self.condominio.cortesias_antes_de_multar = 0
        self.condominio.save(update_fields=['cortesias_antes_de_multar'])

        multa = self._denunciar()
        self.assertFalse(multa.es_aviso_de_cortesia)
        self.assertEqual(multa.monto, Decimal('4.00'))

    # -- Como cierra un aviso -------------------------------------------

    def test_al_vencer_el_plazo_cierra_como_cortesia_y_no_como_firme(self):
        multa = self._denunciar()
        multa.fecha_acuse = timezone.now()
        multa.fecha_limite_descargo = timezone.now() - timedelta(minutes=1)
        multa.save(update_fields=['fecha_acuse', 'fecha_limite_descargo'])

        actualizar_multas_vencidas(self.condominio)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CORTESIA)
        self.assertEqual(multa.monto, Decimal('0.00'))
        self.assertIn('sin objecion y no hay cobro', multa.historial.last().comentario)

    def test_un_aviso_de_cortesia_no_entra_al_gasto_comun(self):
        from gastos_comunes.utils import exportar_multas_firmes

        multa = self._denunciar()
        multa.fecha_acuse = timezone.now()
        multa.fecha_limite_descargo = timezone.now() - timedelta(minutes=1)
        multa.save(update_fields=['fecha_acuse', 'fecha_limite_descargo'])
        actualizar_multas_vencidas(self.condominio)

        admin = Usuario.objects.create_user(
            username='admin_ca', password='x', rol=Rol.ADMINISTRADOR, condominio=self.condominio,
        )
        self.assertIsNone(exportar_multas_firmes(self.condominio, '2026-08', admin))

    def test_el_residente_puede_objetar_el_aviso_porque_le_consume_cupo(self):
        """
        No es solo informativo: gasta una de sus cortesias y acerca el cobro.
        Negarle contestarlo dejaria el tercer cobro fundado en hechos que nunca
        pudo discutir.
        """
        multa = self._denunciar()
        residente = Usuario.objects.create_user(
            username='pia', password='x', rol=Rol.RESIDENTE,
            condominio=self.condominio, persona=self.persona,
        )

        self.client.force_authenticate(residente)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/descargo/', {'texto': 'Ese dia no estaba'}, format='json',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)

    def test_mantener_el_aviso_no_lo_convierte_en_cobro(self):
        multa = self._denunciar()
        residente = Usuario.objects.create_user(
            username='pia2', password='x', rol=Rol.RESIDENTE,
            condominio=self.condominio, persona=self.persona,
        )
        comite = Usuario.objects.create_user(
            username='comite_ca', password='x', rol=Rol.COMITE, condominio=self.condominio,
        )
        self.client.force_authenticate(residente)
        self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'No fui'}, format='json')

        self.client.force_authenticate(comite)
        self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'}, format='json',
        )

        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CORTESIA)
        self.assertEqual(multa.monto, Decimal('0.00'), 'rechazar la objecion no crea un cobro')

    def test_el_curse_sella_que_fue_cortesia_y_por_que(self):
        multa = self._denunciar()

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.CURSE_AUTOMATICO)
        extra = acta.manifiesto['extra']
        self.assertTrue(extra['es_cortesia'])
        self.assertEqual(extra['monto_aplicado'], '0.00')
        self.assertEqual(extra['monto_sin_cortesia'], '4.00')
        self.assertIn('avisa sin cobrar', extra['motivo_cortesia'])
