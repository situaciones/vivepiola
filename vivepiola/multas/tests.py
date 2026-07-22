"""
Tests del flujo legal de multas (Ley 21.442). Protegen las dos garantias
centrales del sistema: la separacion estricta de roles y el debido proceso
(estados, plazos y trazabilidad).
"""

import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from gastos_comunes.models import LoteExportacion
from multas.models import (
    ActaSellada, EstadoMedida, EstadoMulta, MedidaInmediata, Multa, Ticket, TipoActo, VotoRatificacion,
)
from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

MEDIA_TEMP = tempfile.mkdtemp(prefix='debido_test_media_')


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class FlujoLegalTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Test', plazo_descargo_dias=5)
        cls.otro_condominio = Condominio.objects.create(nombre='Otro Condominio')

        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 101')
        cls.unidad_ajena = Unidad.objects.create(condominio=cls.otro_condominio, identificador='Depto 999')

        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Residente Test', cedula_identidad='11.111.111-1',
            domicilio='Depto 101', correo_electronico='residente@test.local',
        )
        cls.otra_persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.OCUPANTE,
            nombre_completo='Vecino Test', cedula_identidad='22.222.222-2',
            domicilio='Depto 101', correo_electronico='vecino@test.local',
        )

        def crear_usuario(username, rol, persona=None):
            return Usuario.objects.create_user(
                username=username, password='x', rol=rol, condominio=cls.condominio, persona=persona,
            )

        cls.conserje = crear_usuario('conserje', Rol.FISCALIZADOR)
        cls.comite = crear_usuario('comite', Rol.COMITE)
        cls.administrador = crear_usuario('administrador', Rol.ADMINISTRADOR)
        cls.residente = crear_usuario('residente', Rol.RESIDENTE, cls.persona)

        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RUIDO-01', descripcion='Ruidos molestos',
            articulo_referencia='Art. 15', monto=Decimal('1.00'), unidad_monto='UF',
            estado=EstadoInfraccion.ACTIVA,
        )
        cls.infraccion_borrador = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='BORRADOR-01', descripcion='Sugerida por IA sin confirmar',
            monto=Decimal('2.00'), estado=EstadoInfraccion.BORRADOR, generado_por_ia=True,
        )

    def crear_ticket(self, persona=None):
        """Helper: el conserje crea un ticket valido y devuelve la multa generada."""
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id,
            'persona_reportada': (persona or self.persona).id,
            'descripcion': 'Hecho de prueba',
            'fecha_hecho': (timezone.now() - timedelta(hours=1)).isoformat(),
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return Multa.objects.get(ticket_id=respuesta.data['id'])

    def aprobar(self, multa, usuario=None, infraccion=None, esperar=200):
        self.client.force_authenticate(usuario or self.comite)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/aprobar/',
            {'infraccion_id': (infraccion or self.infraccion).id},
        )
        self.assertEqual(respuesta.status_code, esperar, respuesta.data)
        multa.refresh_from_db()
        return respuesta

    # ------------------------------------------------------------------
    # Flujo completo
    # ------------------------------------------------------------------

    def test_flujo_completo_hasta_exportacion(self):
        multa = self.crear_ticket()
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)

        # Comite aprueba
        self.aprobar(multa)
        self.assertEqual(multa.estado, EstadoMulta.APROBADA)
        self.assertEqual(multa.monto, Decimal('1.00'))

        # Administrador notifica: PDF + correo al canal legal
        self.client.force_authenticate(self.administrador)
        respuesta = self.client.post(f'/api/multas/{multa.id}/notificar/')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.NOTIFICADA)
        self.assertTrue(multa.pdf_notificacion.name)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('residente@test.local', mail.outbox[0].to)
        self.assertTrue(mail.outbox[0].attachments)

        # Residente presenta descargo dentro de plazo
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'No fui yo'})
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.CON_DESCARGO)

        # Comite rechaza el descargo -> multa firme
        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/',
            {'resolucion': 'RECHAZADO', 'comentario': 'Evidencia suficiente'},
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)

        # Administrador exporta a gastos comunes
        self.client.force_authenticate(self.administrador)
        respuesta = self.client.post('/api/gastos-comunes/exportar/', {'periodo': '2026-07'})
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.EXPORTADA)
        lote = LoteExportacion.objects.get(condominio=self.condominio, periodo='2026-07')
        self.assertEqual(lote.total_monto, Decimal('1.00'))

        # Trazabilidad completa en el historial
        estados = list(multa.historial.values_list('estado_nuevo', flat=True))
        self.assertEqual(
            estados,
            [EstadoMulta.APROBADA, EstadoMulta.NOTIFICADA, EstadoMulta.CON_DESCARGO, EstadoMulta.FIRME],
        )

    def test_descargo_aceptado_anula_multa(self):
        multa = self.crear_ticket()
        self.aprobar(multa)
        self.client.force_authenticate(self.administrador)
        self.client.post(f'/api/multas/{multa.id}/notificar/')
        self.client.force_authenticate(self.residente)
        self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'Prueba de coartada'})

        self.client.force_authenticate(self.comite)
        respuesta = self.client.post(
            f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'ACEPTADO'},
        )
        self.assertEqual(respuesta.status_code, 200)
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.ANULADA)

    # ------------------------------------------------------------------
    # Separacion de roles (el corazon legal del sistema)
    # ------------------------------------------------------------------

    def test_solo_el_comite_aprueba(self):
        multa = self.crear_ticket()
        for usuario in (self.administrador, self.conserje, self.residente):
            self.aprobar(multa, usuario=usuario, esperar=403)
        self.assertEqual(multa.estado, EstadoMulta.EN_REVISION)

    def test_solo_el_administrador_notifica(self):
        multa = self.crear_ticket()
        self.aprobar(multa)
        for usuario in (self.comite, self.conserje, self.residente):
            self.client.force_authenticate(usuario)
            respuesta = self.client.post(f'/api/multas/{multa.id}/notificar/')
            self.assertEqual(respuesta.status_code, 403)

    def test_solo_el_fiscalizador_crea_tickets(self):
        for usuario in (self.comite, self.administrador, self.residente):
            self.client.force_authenticate(usuario)
            respuesta = self.client.post('/api/tickets/', {
                'unidad': self.unidad.id,
                'descripcion': 'x',
                'fecha_hecho': timezone.now().isoformat(),
            })
            self.assertEqual(respuesta.status_code, 403)

    def test_multas_no_se_crean_ni_editan_directamente(self):
        multa = self.crear_ticket()
        self.client.force_authenticate(self.comite)
        self.assertEqual(self.client.post('/api/multas/', {'ticket': multa.ticket_id}).status_code, 405)
        self.assertEqual(self.client.patch(f'/api/multas/{multa.id}/', {'monto': '99'}).status_code, 405)
        self.assertEqual(self.client.delete(f'/api/multas/{multa.id}/').status_code, 405)

    def test_tickets_son_inmutables(self):
        multa = self.crear_ticket()
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.patch(f'/api/tickets/{multa.ticket_id}/', {'descripcion': 'alterada'})
        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(self.client.delete(f'/api/tickets/{multa.ticket_id}/').status_code, 405)

    def test_residente_no_gestiona_registro(self):
        self.client.force_authenticate(self.residente)
        respuesta = self.client.post('/api/personas/', {
            'unidad': self.unidad.id, 'rol_ocupacion': 'OCUPANTE', 'nombre_completo': 'Intruso',
            'cedula_identidad': '3-3', 'domicilio': 'x', 'correo_electronico': 'i@x.cl',
        })
        self.assertEqual(respuesta.status_code, 403)

    # ------------------------------------------------------------------
    # Debido proceso: catalogo, plazos y alcance
    # ------------------------------------------------------------------

    def test_no_se_aprueba_con_infraccion_borrador(self):
        multa = self.crear_ticket()
        respuesta = self.aprobar(multa, infraccion=self.infraccion_borrador, esperar=400)
        self.assertIn('no esta activa', respuesta.data['detail'])

    def test_ticket_no_acepta_unidad_de_otro_condominio(self):
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad_ajena.id,
            'descripcion': 'x',
            'fecha_hecho': timezone.now().isoformat(),
        })
        self.assertEqual(respuesta.status_code, 400)

    def test_fecha_hecho_no_puede_ser_futura(self):
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id,
            'descripcion': 'x',
            'fecha_hecho': (timezone.now() + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(respuesta.status_code, 400)

    def test_residente_solo_ve_sus_multas(self):
        multa_propia = self.crear_ticket(persona=self.persona)
        self.crear_ticket(persona=self.otra_persona)

        self.client.force_authenticate(self.residente)
        respuesta = self.client.get('/api/multas/')
        ids = [m['id'] for m in respuesta.data['results']]
        self.assertEqual(ids, [multa_propia.id])

    def test_descargo_fuera_de_plazo_rechazado(self):
        multa = self.crear_ticket()
        self.aprobar(multa)
        self.client.force_authenticate(self.administrador)
        self.client.post(f'/api/multas/{multa.id}/notificar/')

        multa.refresh_from_db()
        multa.fecha_limite_descargo = timezone.now() - timedelta(days=1)
        multa.save(update_fields=['fecha_limite_descargo'])

        self.client.force_authenticate(self.residente)
        respuesta = self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'tarde'})
        self.assertEqual(respuesta.status_code, 400)
        # Al consultarla, la consolidacion automatica ya la dejo FIRME,
        # por lo que el descargo tardio queda doblemente bloqueado.
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)

    def test_multa_notificada_queda_firme_al_vencer_plazo(self):
        multa = self.crear_ticket()
        self.aprobar(multa)
        self.client.force_authenticate(self.administrador)
        self.client.post(f'/api/multas/{multa.id}/notificar/')

        multa.refresh_from_db()
        multa.fecha_limite_descargo = timezone.now() - timedelta(days=1)
        multa.save(update_fields=['fecha_limite_descargo'])

        # Al listar, el sistema consolida las multas vencidas
        self.client.force_authenticate(self.comite)
        self.client.get('/api/multas/')
        multa.refresh_from_db()
        self.assertEqual(multa.estado, EstadoMulta.FIRME)

    def test_reincidencia_detectada(self):
        primera = self.crear_ticket()
        self.aprobar(primera)

        segunda = self.crear_ticket(persona=self.otra_persona)
        self.aprobar(segunda)
        self.assertTrue(segunda.es_reincidencia)
        self.assertEqual(segunda.multa_primera_sancion_id, primera.id)
        self.assertIn('Reincidencia', segunda.agravante_sugerido)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class SelladoCriptograficoTestCase(APITestCase):
    """
    Tests del sellado V2: cadena de actas, congelamiento de evidencia y de
    la norma aplicada, inmutabilidad a nivel de base de datos, y deteccion
    de manipulacion de archivos.
    """

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Sellado', plazo_descargo_dias=5)
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 501')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Residente Sellado', cedula_identidad='55.555.555-5',
            domicilio='Depto 501', correo_electronico='sellado@test.local',
        )

        def crear_usuario(username, rol, persona=None):
            return Usuario.objects.create_user(
                username=username, password='x', rol=rol, condominio=cls.condominio, persona=persona,
            )

        cls.conserje = crear_usuario('conserje_s', Rol.FISCALIZADOR)
        cls.comite = crear_usuario('comite_s', Rol.COMITE)
        cls.administrador = crear_usuario('admin_s', Rol.ADMINISTRADOR)
        cls.residente = crear_usuario('residente_s', Rol.RESIDENTE, cls.persona)

        cls.infraccion = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='SELLO-01', descripcion='Infraccion sellada',
            articulo_referencia='Art. 9', monto=Decimal('2.00'), unidad_monto='UF',
            estado=EstadoInfraccion.ACTIVA, texto_fuente='Texto original del reglamento.',
        )

    def _imagen(self, color=(120, 40, 40)):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buffer = io.BytesIO()
        Image.new('RGB', (24, 24), color).save(buffer, format='JPEG')
        return SimpleUploadedFile('evidencia.jpg', buffer.getvalue(), content_type='image/jpeg')

    def _crear_caso_con_evidencia(self):
        self.client.force_authenticate(self.conserje)
        respuesta = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id,
            'persona_reportada': self.persona.id,
            'descripcion': 'Caso sellado',
            'fecha_hecho': (timezone.now() - timedelta(hours=1)).isoformat(),
        })
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        ticket_id = respuesta.data['id']
        respuesta = self.client.post(
            f'/api/tickets/{ticket_id}/evidencia/', {'imagen': self._imagen()}, format='multipart',
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(len(respuesta.data['sha256']), 64)
        return Multa.objects.get(ticket_id=ticket_id)

    def _aprobar(self, multa):
        self.client.force_authenticate(self.comite)
        r = self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.infraccion.id})
        self.assertEqual(r.status_code, 200, r.data)
        multa.refresh_from_db()

    def _verificar(self, multa):
        self.client.force_authenticate(self.comite)
        r = self.client.get(f'/api/multas/{multa.id}/verificar-integridad/')
        self.assertEqual(r.status_code, 200)
        return r.data

    def test_flujo_completo_genera_cadena_integra(self):
        multa = self._crear_caso_con_evidencia()
        self._aprobar(multa)

        self.client.force_authenticate(self.administrador)
        self.client.post(f'/api/multas/{multa.id}/notificar/')
        self.client.force_authenticate(self.residente)
        self.client.post(f'/api/multas/{multa.id}/descargo/', {'texto': 'Mi defensa'})
        self.client.force_authenticate(self.comite)
        self.client.post(f'/api/multas/{multa.id}/resolver-descargo/', {'resolucion': 'RECHAZADO'})

        informe = self._verificar(multa)
        self.assertEqual(informe['version'], 2)
        self.assertTrue(informe['integra'])
        tipos = [a['tipo_acto'] for a in informe['actas']]
        self.assertEqual(tipos, ['APROBACION', 'NOTIFICACION', 'DESCARGO_PRESENTADO', 'RESOLUCION_DESCARGO'])
        # La cadena esta encadenada de verdad
        actas = list(ActaSellada.objects.filter(multa=multa).order_by('indice'))
        self.assertEqual(actas[0].hash_previo, ActaSellada.GENESIS)
        for anterior, siguiente in zip(actas, actas[1:]):
            self.assertEqual(siguiente.hash_previo, anterior.hash_acto)

    def test_manifiesto_congela_la_norma_aplicada(self):
        multa = self._crear_caso_con_evidencia()
        self._aprobar(multa)

        # El catalogo cambia despues de la decision
        self.infraccion.monto = Decimal('9.99')
        self.infraccion.descripcion = 'Texto alterado posteriormente'
        self.infraccion.save()

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.APROBACION)
        self.assertEqual(acta.manifiesto['norma_aplicada']['monto_base'], '2.00')
        self.assertEqual(acta.manifiesto['norma_aplicada']['descripcion'], 'Infraccion sellada')
        # Y el expediente sigue integro: el sello no depende del catalogo vivo
        self.assertTrue(self._verificar(multa)['integra'])

    def test_evidencia_posterior_queda_fuera_del_sello(self):
        multa = self._crear_caso_con_evidencia()
        self._aprobar(multa)

        # El fiscalizador agrega una segunda foto DESPUES de la aprobacion
        self.client.force_authenticate(self.conserje)
        r = self.client.post(
            f'/api/tickets/{multa.ticket_id}/evidencia/',
            {'imagen': self._imagen(color=(40, 120, 40))}, format='multipart',
        )
        self.assertEqual(r.status_code, 201)

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.APROBACION)
        self.assertEqual(len(acta.manifiesto['evidencias_visibles']), 1)
        self.assertEqual(multa.ticket.evidencias.count(), 2)
        self.assertTrue(self._verificar(multa)['integra'])

    def test_verificador_detecta_archivo_de_evidencia_alterado(self):
        multa = self._crear_caso_con_evidencia()
        self._aprobar(multa)

        evidencia = multa.ticket.evidencias.first()
        with open(evidencia.imagen.path, 'wb') as f:
            f.write(b'contenido sustituido')

        informe = self._verificar(multa)
        self.assertFalse(informe['integra'])
        self.assertFalse(informe['evidencias'][0]['integra'])

    def test_actas_inmutables_a_nivel_de_base_de_datos(self):
        from django.db import transaction
        from django.db.utils import OperationalError

        multa = self._crear_caso_con_evidencia()
        self._aprobar(multa)

        acta = multa.actas_selladas.first()
        with self.assertRaises(OperationalError):
            with transaction.atomic():
                ActaSellada.objects.filter(id=acta.id).update(auth_metodo='falsificado')
        with self.assertRaises(OperationalError):
            with transaction.atomic():
                ActaSellada.objects.filter(id=acta.id).delete()

    def test_expediente_sin_actas_es_legacy_v1(self):
        multa = self._crear_caso_con_evidencia()  # sin decisiones aun
        informe = self._verificar(multa)
        self.assertEqual(informe['version'], 1)
        self.assertFalse(informe['sellado'])
        self.assertIsNone(informe['integra'])

    # ------------------------------------------------------------------
    # Audit Trail PDF (la Prueba Maestra)
    # ------------------------------------------------------------------

    def _texto_pdf(self, contenido_pdf):
        import io
        import pdfplumber

        with pdfplumber.open(io.BytesIO(contenido_pdf)) as pdf:
            return '\n'.join(pagina.extract_text() or '' for pagina in pdf.pages)

    def test_audit_trail_certifica_inmutabilidad(self):
        multa = self._crear_caso_con_evidencia()
        self._aprobar(multa)

        self.client.force_authenticate(self.comite)
        r = self.client.get(f'/api/multas/{multa.id}/audit-trail/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

        texto = self._texto_pdf(r.content)
        self.assertIn('INMUTABILIDAD VERIFICADA', texto)
        self.assertIn('VERIFICADO', texto)
        self.assertIn('Aprobacion de la multa', texto)
        # El hash raiz impreso ancla el papel a la cadena digital
        hash_raiz = multa.actas_selladas.order_by('-indice').first().hash_acto
        self.assertIn(hash_raiz[:32], texto.replace('\n', ''))

    def test_audit_trail_delata_expediente_comprometido(self):
        multa = self._crear_caso_con_evidencia()
        self._aprobar(multa)

        evidencia = multa.ticket.evidencias.first()
        with open(evidencia.imagen.path, 'wb') as f:
            f.write(b'archivo sustituido tras el sellado')

        self.client.force_authenticate(self.comite)
        r = self.client.get(f'/api/multas/{multa.id}/audit-trail/')
        texto = self._texto_pdf(r.content)
        self.assertIn('INTEGRIDAD COMPROMETIDA', texto)
        self.assertIn('ALTERADO', texto)

    def test_audit_trail_rechaza_expedientes_legacy(self):
        multa = self._crear_caso_con_evidencia()  # sin actos sellados
        self.client.force_authenticate(self.comite)
        r = self.client.get(f'/api/multas/{multa.id}/audit-trail/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('legacy V1', r.data['detail'])


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class JerarquiasQuorumTestCase(APITestCase):
    """
    Fases 0-1 de Jerarquias Enterprise: delegacion tactica, quorum K-de-N y
    votos sellados idempotentes. Los tests de concurrencia son la especificacion
    ejecutable: definen el comportamiento determinista bajo el candado pesimista
    ANTES que la logica de negocio.
    """

    @classmethod
    def setUpTestData(cls):
        from condominios.models import Condominio, Persona, RolOcupacion, Unidad

        cls.obra = Condominio.objects.create(nombre='Obra Quorum', plazo_descargo_dias=3)
        cls.unidad = Unidad.objects.create(condominio=cls.obra, identificador='Subcontratista A')
        cls.persona = Persona.objects.create(
            condominio=cls.obra, unidad=cls.unidad, rol_ocupacion=RolOcupacion.OCUPANTE,
            nombre_completo='Jefe de terreno', cedula_identidad='30.111.222-3',
            domicilio='Faena', correo_electronico='q@test.local',
        )

        def usuario(u, rol):
            return Usuario.objects.create_user(u, password='x', rol=rol, condominio=cls.obra, email=f'{u}@t.local')

        cls.supervisor = usuario('sup_q', Rol.FISCALIZADOR)
        cls.admin_contrato = usuario('adm_contrato_q', Rol.COMITE)      # titular 1
        cls.prevencionista = usuario('prev_q', Rol.COMITE)              # titular 2
        cls.jefe_area = usuario('jefe_area_q', Rol.ADMINISTRADOR)       # candidato a delegado

        # Hallazgo GRAVE que exige quorum 2-de-N
        cls.hallazgo = InfraccionCatalogo.objects.create(
            condominio=cls.obra, codigo='SEG-ELEC', descripcion='Tablero energizado expuesto',
            articulo_referencia='Clausula 14.3', monto=Decimal('10.00'), unidad_monto='UF',
            gravedad='GRAVE', estado=EstadoInfraccion.ACTIVA,
            conlleva_contencion=True, plazo_ratificacion_horas=12, quorum_ratificacion=2,
        )

    def _medida_ejecutada(self):
        from multas.contencion import ejecutar_contencion

        ticket = Ticket.objects.create(
            condominio=self.obra, unidad=self.unidad, persona_reportada=self.persona,
            creado_por=self.supervisor, descripcion='Tablero expuesto',
            fecha_hecho=timezone.now() - timedelta(minutes=20),
        )
        multa = Multa.objects.create(
            condominio=self.obra, ticket=ticket, unidad=self.unidad, persona_infractor=self.persona,
        )
        return ejecutar_contencion(multa, self.hallazgo, self.supervisor)

    def _vencer(self, medida):
        MedidaInmediata.objects.filter(id=medida.id).update(proxima_revision=timezone.now() - timedelta(minutes=1))
        medida.refresh_from_db()

    # ------------------------------------------------------------------
    # Quorum basico
    # ------------------------------------------------------------------

    def test_quorum_2_requiere_dos_actores_distintos(self):
        from multas.contencion import ratificar_contencion

        medida = self._medida_ejecutada()
        self.assertEqual(medida.quorum_requerido, 2)

        ratificar_contencion(medida, self.admin_contrato)
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.EJECUTADA)  # 1 voto: aun NO ratificada
        self.assertTrue(medida.activa)

        ratificar_contencion(medida, self.prevencionista)
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.RATIFICADA)  # 2 votos: quorum completo

        # Actas: dos VOTO_RATIFICACION + un CONTENCION_RATIFICADA
        tipos = list(medida.multa.actas_selladas.values_list('tipo_acto', flat=True))
        self.assertEqual(tipos.count('VOTO_RATIFICACION'), 2)
        self.assertEqual(tipos.count('CONTENCION_RATIFICADA'), 1)

    # ------------------------------------------------------------------
    # ESTRESS 1 — Idempotencia: un actor fisico incrementa el quorum UNA vez
    # ------------------------------------------------------------------

    def test_idempotencia_mismo_actor_no_suma_dos_veces(self):
        """El gerente presiona 'Ratificar' en web y movil casi a la vez."""
        from multas.contencion import ratificar_contencion

        medida = self._medida_ejecutada()
        ratificar_contencion(medida, self.admin_contrato)
        ratificar_contencion(medida, self.admin_contrato)  # segundo click del MISMO actor

        self.assertEqual(VotoRatificacion.objects.filter(medida=medida).count(), 1)
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.EJECUTADA)  # sigue faltando el 2do actor

    def test_idempotencia_titular_y_su_propia_delegacion_cuentan_uno(self):
        """
        Un actor con cargo propio Y ademas una delegacion a su nombre no debe
        contar dos veces: el candado + unique(medida, actor) garantiza 1 voto
        por actor fisico, sin importar por cuantos caminos podria votar.
        """
        from multas.contencion import otorgar_delegacion, ratificar_contencion

        medida = self._medida_ejecutada()
        # El prevencionista (titular) ademas recibe una delegacion del admin
        otorgar_delegacion(
            self.obra, self.admin_contrato, self.prevencionista,
            acciones=['RATIFICAR_CONTENCION'], tope_gravedad='GRAVE',
            vigencia_desde=timezone.now() - timedelta(hours=1),
            vigencia_hasta=timezone.now() + timedelta(hours=5),
        )
        ratificar_contencion(medida, self.prevencionista)
        ratificar_contencion(medida, self.prevencionista)  # mismo actor, otra "via"
        self.assertEqual(VotoRatificacion.objects.filter(medida=medida, actor=self.prevencionista).count(), 1)

    # ------------------------------------------------------------------
    # ESTRESS 2 — Voto que completa quorum vs. Job de escalamiento
    # ------------------------------------------------------------------

    def test_job_se_aborta_cuando_el_voto_completa_el_quorum(self):
        from multas.contencion import escalar_medidas_vencidas, ratificar_contencion

        medida = self._medida_ejecutada()
        ratificar_contencion(medida, self.admin_contrato)  # primer voto

        # El plazo vence: el segundo voto y el job compiten. Simulamos que el
        # voto gana la carrera (sella la ratificacion) y LUEGO corre el job.
        self._vencer(medida)
        ratificar_contencion(medida, self.prevencionista)  # completa quorum -> RATIFICADA
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.RATIFICADA)

        # El job debe abortarse solo: la medida ya no esta EJECUTADA/EN_ESCALAMIENTO
        self.assertEqual(escalar_medidas_vencidas(self.obra), 0)
        self.assertEqual(
            medida.multa.actas_selladas.filter(tipo_acto=TipoActo.ESCALAMIENTO_POR_OMISION).count(), 0,
        )

    def test_escalamiento_no_invalida_votos_previos(self):
        """Si el job gana la carrera, el voto previo sigue contando hacia el quorum."""
        from multas.contencion import escalar_medidas_vencidas, ratificar_contencion

        medida = self._medida_ejecutada()
        ratificar_contencion(medida, self.admin_contrato)  # 1er voto (quorum 2)
        self._vencer(medida)
        self.assertEqual(escalar_medidas_vencidas(self.obra), 1)  # job gana: escala
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.EN_ESCALAMIENTO)
        self.assertTrue(medida.activa)  # FAIL-CLOSED

        # El segundo voto, ya en escalamiento, completa el quorum igual
        ratificar_contencion(medida, self.prevencionista)
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.RATIFICADA)
        self.assertEqual(VotoRatificacion.objects.filter(medida=medida).count(), 2)

    # ------------------------------------------------------------------
    # Delegacion: autoridad, techo y auditoria criptografica
    # ------------------------------------------------------------------

    def test_delegado_vota_y_el_verificador_audita_la_ventana(self):
        from multas.contencion import otorgar_delegacion, ratificar_contencion
        from multas.sellado import verificar_expediente

        medida = self._medida_ejecutada()
        otorgar_delegacion(
            self.obra, self.admin_contrato, self.jefe_area,
            acciones=['RATIFICAR_CONTENCION'], tope_gravedad='GRAVE',
            vigencia_desde=timezone.now() - timedelta(hours=1),
            vigencia_hasta=timezone.now() + timedelta(hours=5),
        )
        ratificar_contencion(medida, self.jefe_area)     # delegado
        ratificar_contencion(medida, self.admin_contrato)  # titular -> completa quorum
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.RATIFICADA)

        informe = verificar_expediente(medida.multa)
        self.assertTrue(informe['integra'])
        voto_del = next(a for a in informe['actas'] if a['tipo_acto'] == 'VOTO_RATIFICACION' and 'autoridad_detalle' in a)
        self.assertTrue(voto_del['autoridad_integra'])
        self.assertTrue(voto_del['autoridad_detalle']['ventana_cubre_ts'])
        self.assertTrue(voto_del['autoridad_detalle']['techo_gravedad_ok'])

    def test_delegado_sin_techo_para_gravisima_no_puede_votar(self):
        from multas.contencion import SinAutoridad, otorgar_delegacion, ratificar_contencion

        # Hallazgo GRAVISIMA con quorum
        hallazgo_vital = InfraccionCatalogo.objects.create(
            condominio=self.obra, codigo='SEG-ALT', descripcion='Trabajo en altura sin arnes',
            monto=Decimal('15.00'), gravedad='GRAVISIMA', estado=EstadoInfraccion.ACTIVA,
            conlleva_contencion=True, plazo_ratificacion_horas=6, quorum_ratificacion=2,
        )
        from multas.contencion import ejecutar_contencion
        ticket = Ticket.objects.create(
            condominio=self.obra, unidad=self.unidad, persona_reportada=self.persona,
            creado_por=self.supervisor, descripcion='Sin arnes', fecha_hecho=timezone.now() - timedelta(minutes=10),
        )
        multa = Multa.objects.create(condominio=self.obra, ticket=ticket, unidad=self.unidad, persona_infractor=self.persona)
        medida = ejecutar_contencion(multa, hallazgo_vital, self.supervisor)

        # Delegacion con techo GRAVE: no alcanza para GRAVISIMA (riesgo vital no se delega ad-hoc)
        otorgar_delegacion(
            self.obra, self.admin_contrato, self.jefe_area,
            acciones=['RATIFICAR_CONTENCION'], tope_gravedad='GRAVE',
            vigencia_desde=timezone.now() - timedelta(hours=1),
            vigencia_hasta=timezone.now() + timedelta(hours=5),
        )
        with self.assertRaises(SinAutoridad):
            ratificar_contencion(medida, self.jefe_area)

    def test_delegacion_vencida_no_otorga_autoridad(self):
        from multas.contencion import SinAutoridad, otorgar_delegacion, ratificar_contencion

        medida = self._medida_ejecutada()
        otorgar_delegacion(
            self.obra, self.admin_contrato, self.jefe_area,
            acciones=['RATIFICAR_CONTENCION'], tope_gravedad='GRAVE',
            vigencia_desde=timezone.now() - timedelta(hours=5),
            vigencia_hasta=timezone.now() - timedelta(hours=1),  # ya vencida
        )
        with self.assertRaises(SinAutoridad):
            ratificar_contencion(medida, self.jefe_area)


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class ContencionTestCase(APITestCase):
    """
    Tests del carril de contencion (MedidaInmediata): maquina de estados
    fail-closed, escalamiento por omision que NUNCA libera, manifiesto
    polimorfico CONTENCION, y convivencia de ambos carriles en la misma
    cadena sellada del expediente.
    """

    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Condominio Contencion', plazo_descargo_dias=5)
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Bodega 7')
        cls.persona = Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Residente Contencion', cedula_identidad='66.666.666-6',
            domicilio='Bodega 7', correo_electronico='contencion@test.local',
        )

        def crear_usuario(username, rol, persona=None, email=''):
            return Usuario.objects.create_user(
                username=username, password='x', rol=rol, condominio=cls.condominio,
                persona=persona, email=email,
            )

        cls.conserje = crear_usuario('conserje_c', Rol.FISCALIZADOR)
        cls.comite = crear_usuario('comite_c', Rol.COMITE, email='comite@test.local')
        cls.administrador = crear_usuario('admin_c', Rol.ADMINISTRADOR, email='admin@test.local')
        cls.residente = crear_usuario('residente_c', Rol.RESIDENTE, cls.persona)

        cls.hallazgo_critico = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='RIESGO-ELEC', descripcion='Riesgo electrico expuesto',
            articulo_referencia='Art. 30', monto=Decimal('5.00'), unidad_monto='UF',
            estado=EstadoInfraccion.ACTIVA, conlleva_contencion=True, plazo_ratificacion_horas=24,
        )
        cls.hallazgo_menor = InfraccionCatalogo.objects.create(
            condominio=cls.condominio, codigo='MENOR-01', descripcion='Hallazgo menor sin contencion',
            monto=Decimal('0.50'), estado=EstadoInfraccion.ACTIVA, conlleva_contencion=False,
        )

    def _crear_expediente(self):
        self.client.force_authenticate(self.conserje)
        r = self.client.post('/api/tickets/', {
            'unidad': self.unidad.id,
            'persona_reportada': self.persona.id,
            'descripcion': 'Cables expuestos sobre charco',
            'fecha_hecho': (timezone.now() - timedelta(minutes=30)).isoformat(),
        })
        self.assertEqual(r.status_code, 201, r.data)
        return Multa.objects.get(ticket_id=r.data['id'])

    def _ejecutar_medida(self, multa, codigo=None, esperar=201):
        self.client.force_authenticate(self.conserje)
        r = self.client.post('/api/medidas-inmediatas/', {
            'expediente_id': multa.id,
            'hallazgo_codigo': codigo or self.hallazgo_critico.codigo,
            'evidencia_ids': [],
            'auth_metodo': 'webauthn_dispositivo_terreno',
        }, format='json')
        self.assertEqual(r.status_code, esperar, r.data)
        return r

    def _vencer_plazo(self, medida):
        MedidaInmediata.objects.filter(id=medida.id).update(
            proxima_revision=timezone.now() - timedelta(minutes=5),
        )
        medida.refresh_from_db()

    # ------------------------------------------------------------------

    def test_hallazgo_no_critico_no_detona_contencion(self):
        multa = self._crear_expediente()
        r = self._ejecutar_medida(multa, codigo='MENOR-01', esperar=400)
        self.assertIn('no detona contencion', r.data['detail'])
        self.assertEqual(MedidaInmediata.objects.count(), 0)

    def test_ejecutar_sella_manifiesto_contencion(self):
        multa = self._crear_expediente()
        r = self._ejecutar_medida(multa)
        medida = MedidaInmediata.objects.get(id=r.data['id'])

        self.assertEqual(medida.estado, EstadoMedida.EJECUTADA)
        self.assertEqual(medida.auth_metodo_ejecucion, 'webauthn_dispositivo_terreno')

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.CONTENCION_EJECUTADA)
        m = acta.manifiesto
        self.assertEqual(m['tipo_manifiesto'], 'CONTENCION')
        # Claves obligatorias del contrato polimorfico
        self.assertIn('criticidad', m)
        self.assertIn('plazo_ratificacion_horas', m)
        self.assertIn('estado_contencion', m)
        self.assertEqual(m['criticidad']['codigo'], 'RIESGO-ELEC')
        self.assertEqual(m['auth_metodo'], 'webauthn_dispositivo_terreno')

    def test_omision_escala_y_jamas_libera(self):
        from multas.contencion import escalar_medidas_vencidas

        multa = self._crear_expediente()
        medida = MedidaInmediata.objects.get(id=self._ejecutar_medida(multa).data['id'])

        self._vencer_plazo(medida)
        self.assertEqual(escalar_medidas_vencidas(), 1)
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.EN_ESCALAMIENTO)
        self.assertEqual(medida.nivel_escalamiento, 1)
        self.assertTrue(medida.activa)  # FAIL-CLOSED: la contencion sigue viva

        self._vencer_plazo(medida)
        self.assertEqual(escalar_medidas_vencidas(), 1)
        medida.refresh_from_db()
        self.assertEqual(medida.nivel_escalamiento, 2)
        self.assertNotEqual(medida.estado, EstadoMedida.LEVANTADA)

        omisiones = multa.actas_selladas.filter(tipo_acto=TipoActo.ESCALAMIENTO_POR_OMISION)
        self.assertEqual(omisiones.count(), 2)
        self.assertIsNone(omisiones.first().actor)  # acto del sistema
        self.assertEqual(omisiones.first().auth_metodo, 'sistema')
        # La omision registra a quienes fueron notificados (presion por trazabilidad)
        self.assertIn('comite_c', omisiones.first().manifiesto['extra']['notificados'])

    def test_job_se_aborta_si_el_gerente_gano_la_carrera(self):
        from multas.contencion import escalar_medidas_vencidas

        multa = self._crear_expediente()
        medida = MedidaInmediata.objects.get(id=self._ejecutar_medida(multa).data['id'])

        self.client.force_authenticate(self.comite)
        r = self.client.post(f'/api/medidas-inmediatas/{medida.id}/ratificar/')
        self.assertEqual(r.status_code, 200, r.data)

        # El plazo "vence" despues de ratificada: el job debe abortarse solo
        self._vencer_plazo(medida)
        self.assertEqual(escalar_medidas_vencidas(), 0)
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.RATIFICADA)
        self.assertEqual(
            multa.actas_selladas.filter(tipo_acto=TipoActo.ESCALAMIENTO_POR_OMISION).count(), 0,
        )

    def test_ratificacion_tardia_registra_la_demora(self):
        from multas.contencion import escalar_medidas_vencidas

        multa = self._crear_expediente()
        medida = MedidaInmediata.objects.get(id=self._ejecutar_medida(multa).data['id'])
        self._vencer_plazo(medida)
        escalar_medidas_vencidas()

        self.client.force_authenticate(self.comite)
        r = self.client.post(f'/api/medidas-inmediatas/{medida.id}/ratificar/')
        self.assertEqual(r.status_code, 200)

        acta = multa.actas_selladas.get(tipo_acto=TipoActo.CONTENCION_RATIFICADA)
        self.assertTrue(acta.manifiesto['extra']['ratificacion_tardia'])
        self.assertEqual(acta.manifiesto['extra']['nivel_escalamiento_al_ratificar'], 1)

    def test_levantar_exige_causal_y_fundamento(self):
        multa = self._crear_expediente()
        medida = MedidaInmediata.objects.get(id=self._ejecutar_medida(multa).data['id'])

        self.client.force_authenticate(self.comite)
        r = self.client.post(f'/api/medidas-inmediatas/{medida.id}/levantar/', {'causal': 'CORREGIDA'})
        self.assertEqual(r.status_code, 400)  # sin fundamento no hay levantamiento

        r = self.client.post(f'/api/medidas-inmediatas/{medida.id}/levantar/', {
            'causal': 'CORREGIDA', 'fundamento': 'Tablero normalizado, foto adjunta al expediente.',
        })
        self.assertEqual(r.status_code, 200, r.data)
        medida.refresh_from_db()
        self.assertEqual(medida.estado, EstadoMedida.LEVANTADA)
        self.assertEqual(medida.levantada_por, self.comite)

        # Estado terminal: no se puede ratificar lo levantado
        r = self.client.post(f'/api/medidas-inmediatas/{medida.id}/ratificar/')
        self.assertEqual(r.status_code, 400)

    def test_solo_el_comite_ratifica_y_levanta(self):
        multa = self._crear_expediente()
        medida = MedidaInmediata.objects.get(id=self._ejecutar_medida(multa).data['id'])

        for usuario in (self.conserje, self.administrador, self.residente):
            self.client.force_authenticate(usuario)
            self.assertEqual(
                self.client.post(f'/api/medidas-inmediatas/{medida.id}/ratificar/').status_code, 403,
            )

    def test_escalamiento_lee_cadena_versionada_y_acumula(self):
        from condominios.models import CadenaEscalamiento, NivelEscalamiento
        from multas.contencion import escalar_medidas_vencidas

        # Cadena v1 (inactiva, quedo obsoleta) y v2 (activa) con dos niveles
        CadenaEscalamiento.objects.create(condominio=self.condominio, version=1, activa=False)
        cadena = CadenaEscalamiento.objects.create(condominio=self.condominio, version=2, activa=True)
        n1 = NivelEscalamiento.objects.create(cadena=cadena, orden=1, etiqueta='Jefatura de turno')
        n1.usuarios.add(self.administrador)
        n2 = NivelEscalamiento.objects.create(cadena=cadena, orden=2, etiqueta='Gerencia')
        n2.usuarios.add(self.comite)

        multa = self._crear_expediente()
        medida = MedidaInmediata.objects.get(id=self._ejecutar_medida(multa).data['id'])

        # Ejecucion (nivel 0): solo el nivel 1 de la cadena v2
        acta_ejec = multa.actas_selladas.get(tipo_acto=TipoActo.CONTENCION_EJECUTADA)
        self.assertEqual(acta_ejec.manifiesto['extra']['notificados'], ['admin_c'])
        self.assertEqual(acta_ejec.manifiesto['extra']['cadena_version'], 2)

        # Primera omision: acumulativo niveles 1..2, sin tope
        self._vencer_plazo(medida)
        escalar_medidas_vencidas()
        omision_1 = multa.actas_selladas.filter(tipo_acto=TipoActo.ESCALAMIENTO_POR_OMISION).first()
        self.assertEqual(omision_1.manifiesto['extra']['notificados'], ['admin_c', 'comite_c'])
        self.assertFalse(omision_1.manifiesto['extra']['tope_alcanzado'])

        # Segunda omision: supera el largo de la cadena -> tope alcanzado
        self._vencer_plazo(medida)
        escalar_medidas_vencidas()
        omision_2 = multa.actas_selladas.filter(tipo_acto=TipoActo.ESCALAMIENTO_POR_OMISION).last()
        self.assertTrue(omision_2.manifiesto['extra']['tope_alcanzado'])

    def test_pdf_usa_marco_legal_del_vertical(self):
        from condominios.models import Vertical
        from multas.services import generar_pdf_notificacion

        vertical = Vertical.objects.create(
            slug='construccion', nombre='Construccion',
            marco_legal_nombre='Contrato de obra y bases tecnicas',
            marco_legal_texto_notificacion='Documento emitido conforme a la clausula 14 del contrato de obra.',
        )
        self.condominio.vertical = vertical
        self.condominio.save(update_fields=['vertical'])

        multa = self._crear_expediente()
        self.client.force_authenticate(self.comite)
        r = self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.hallazgo_critico.id})
        self.assertEqual(r.status_code, 200, r.data)
        multa.refresh_from_db()

        pdf = generar_pdf_notificacion(multa)
        self.assertGreater(len(pdf), 500)  # PDF real generado con la plantilla del vertical

        # Limpieza para no afectar otros tests de la clase
        self.condominio.vertical = None
        self.condominio.save(update_fields=['vertical'])

    def test_ambos_carriles_conviven_en_la_misma_cadena_integra(self):
        multa = self._crear_expediente()
        medida = MedidaInmediata.objects.get(id=self._ejecutar_medida(multa).data['id'])

        # Carril sancionatorio avanza en paralelo
        self.client.force_authenticate(self.comite)
        r = self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': self.hallazgo_critico.id})
        self.assertEqual(r.status_code, 200, r.data)

        # Carril de contencion se ratifica despues
        r = self.client.post(f'/api/medidas-inmediatas/{medida.id}/ratificar/')
        self.assertEqual(r.status_code, 200)

        r = self.client.get(f'/api/multas/{multa.id}/verificar-integridad/')
        self.assertTrue(r.data['integra'])
        tipos = [a['tipo_acto'] for a in r.data['actas']]
        self.assertEqual(tipos, ['CONTENCION_EJECUTADA', 'APROBACION', 'CONTENCION_RATIFICADA'])


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class VocabularioServidorTestCase(APITestCase):
    """
    Cierre hermetico del vertical (servidor-side): correo y PDF de notificacion
    hablan el idioma del vertical de la organizacion, y los errores de la API
    son neutros (sin rastro de nicho).
    """

    @classmethod
    def setUpTestData(cls):
        from condominios.models import Vertical

        cls.vertical = Vertical.objects.create(
            slug='obras-test', nombre='Construccion Test',
            marco_legal_nombre='Contrato de obra',
            marco_legal_texto_notificacion='Emitido conforme a la clausula 14 del contrato.',
            vocabulario={
                'organizacion_cap': 'Obra',
                'unidad_cap': 'Subcontratista',
                'sujeto_cap': 'Responsable del subcontratista',
                'organo_sancionador': 'Administrador de contrato',
                'destino_cobro': 'estados de pago del contrato',
                'notificacion_asunto': 'Aviso de No Conformidad #{numero} - {org_nombre}',
                'notificacion_cuerpo': (
                    'Se le notifica que el Administrador de contrato de {org_nombre} ha aprobado '
                    'una No Conformidad asociada al subcontratista {unidad_id} por el hallazgo '
                    '"{infraccion}" (Clausula {articulo}).'
                ),
                'pdf_titulo': 'Aviso de No Conformidad N° {numero}',
                'pdf_aviso_descargo': 'Reclamacion en {dias} dias, hasta el {fecha_limite}, ante el Administrador de contrato.',
            },
        )
        cls.obra = Condominio.objects.create(nombre='Obra Vista Norte', vertical=cls.vertical, plazo_descargo_dias=3)
        cls.condo = Condominio.objects.create(nombre='Condominio Clasico', plazo_descargo_dias=5)

    def _montar(self, org):
        unidad = Unidad.objects.create(condominio=org, identificador='Electrica Sur' if org == self.obra else 'Depto 10')
        persona = Persona.objects.create(
            condominio=org, unidad=unidad, rol_ocupacion=RolOcupacion.OCUPANTE,
            nombre_completo='Marcos Riquelme', cedula_identidad='21.111.111-1',
            domicilio='Faena', correo_electronico='destino@test.local',
        )
        conserje = Usuario.objects.create_user('fisc_%s' % org.id, password='x', rol=Rol.FISCALIZADOR, condominio=org)
        comite = Usuario.objects.create_user('com_%s' % org.id, password='x', rol=Rol.COMITE, condominio=org)
        admin = Usuario.objects.create_user('adm_%s' % org.id, password='x', rol=Rol.ADMINISTRADOR, condominio=org)
        inf = InfraccionCatalogo.objects.create(
            condominio=org, codigo='X-01', descripcion='Trabajo en altura sin arnes',
            articulo_referencia='14.2', monto=Decimal('3.00'), unidad_monto='UF', estado=EstadoInfraccion.ACTIVA,
        )
        return unidad, persona, conserje, comite, admin, inf

    def _notificar(self, org):
        unidad, persona, conserje, comite, admin, inf = self._montar(org)
        self.client.force_authenticate(conserje)
        r = self.client.post('/api/tickets/', {
            'unidad': unidad.id, 'persona_reportada': persona.id, 'descripcion': 'hecho',
            'fecha_hecho': (timezone.now() - timedelta(hours=1)).isoformat(),
        })
        multa = Multa.objects.get(ticket_id=r.data['id'])
        self.client.force_authenticate(comite)
        self.client.post(f'/api/multas/{multa.id}/aprobar/', {'infraccion_id': inf.id})
        self.client.force_authenticate(admin)
        mail.outbox = []
        self.client.post(f'/api/multas/{multa.id}/notificar/')
        return mail.outbox[0]

    def test_correo_habla_el_vertical_construccion(self):
        correo = self._notificar(self.obra)
        self.assertIn('Aviso de No Conformidad', correo.subject)
        self.assertIn('Obra Vista Norte', correo.subject)
        self.assertIn('No Conformidad asociada al subcontratista Electrica Sur', correo.body)
        self.assertNotIn('multa', correo.body.lower())
        self.assertNotIn('condominio', correo.body.lower())

    def test_correo_conserva_el_nicho_original(self):
        correo = self._notificar(self.condo)
        self.assertIn('Notificacion de multa', correo.subject)
        self.assertIn('multa asociada a la unidad', correo.body)

    def test_error_api_es_neutro_sin_rastro_de_nicho(self):
        # Un conserje intenta un ticket con unidad de otra organizacion
        otra = Condominio.objects.create(nombre='Ajena')
        unidad_ajena = Unidad.objects.create(condominio=otra, identificador='X')
        _, _, conserje, _, _, _ = self._montar(self.obra)
        self.client.force_authenticate(conserje)
        r = self.client.post('/api/tickets/', {
            'unidad': unidad_ajena.id, 'descripcion': 'x', 'fecha_hecho': timezone.now().isoformat(),
        })
        self.assertEqual(r.status_code, 400)
        msg = str(r.data).lower()
        self.assertIn('organizacion activa', msg)
        self.assertNotIn('condominio', msg)
