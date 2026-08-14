from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from accounts.permissions import UsuarioAsignado
from rest_framework.response import Response

from accounts.models import Rol
from accounts.permissions import (
    EsAdministrador, EsComite, EsDenunciante, EsFiscalizadorOComiteOAdministrador, EsResidente,
)

from reglamentos.models import EstadoInfraccion, InfraccionCatalogo

from .contencion import (
    SinAutoridad, TransicionInvalida, ejecutar_contencion, escalar_medidas_vencidas,
    levantar_contencion, otorgar_delegacion, ratificar_contencion, revocar_delegacion,
)
from .models import (
    CanalNotificacion, Delegacion, Descargo, EstadoMulta, EstadoTicket, EvidenciaFoto,
    MedidaInmediata, Multa, Ticket, TipoActo,
)
from .sellado import procesar_evidencia, sellar_acto, verificar_expediente
from .serializers import (
    AprobarMultaSerializer, DelegacionSerializer, DescargoSerializer, EjecutarMedidaSerializer,
    EvidenciaFotoSerializer, LevantarMedidaSerializer, MedidaInmediataSerializer, MultaSerializer,
    OtorgarDelegacionSerializer, PresentarDescargoSerializer, RechazarMultaSerializer,
    ResolverDescargoSerializer, TicketSerializer,
)
from .services import (
    ETAPA_PARA_DENUNCIANTE, actualizar_multas_vencidas, aplicar_monto_con_reincidencia,
    buscar_expediente_abierto, cursar_multa_automatica, generar_audit_trail_pdf,
    notificar_multa, proponer_infraccion, registrar_acuse, registrar_historial,
    resolver_descargo,
)


class TicketViewSet(viewsets.ModelViewSet):
    """
    El reporte lo puede levantar el conserje (Fiscalizador), el Comite o un
    vecino (Residente), con opcion de anonimato. Quien reporta NO define monto
    ni aprueba nada: por eso no expone accion de aprobacion aqui. Los tickets no
    se editan ni eliminan una vez creados: son evidencia del debido proceso
    (solo GET y POST).
    """

    serializer_class = TicketSerializer
    permission_classes = [UsuarioAsignado]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'agregar_evidencia'):
            return [EsDenunciante()]
        return [UsuarioAsignado()]

    def get_queryset(self):
        user = self.request.user
        qs = Ticket.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=user.condominio_id)
        if user.rol == Rol.FISCALIZADOR:
            qs = qs.filter(creado_por=user)
        elif user.rol == Rol.RESIDENTE:
            # El residente accede a la evidencia a traves de sus multas, no del listado de tickets.
            qs = qs.filter(multa__persona_infractor=user.persona)
        return qs

    def perform_create(self, serializer):
        condominio = self.request.user.condominio
        unidad = serializer.validated_data['unidad']
        persona = serializer.validated_data.get('persona_reportada')
        if unidad.condominio_id != condominio.id:
            raise ValidationError({'unidad': 'La entidad indicada no pertenece a la organizacion activa.'})
        if persona and persona.unidad_id != unidad.id:
            raise ValidationError({'persona_reportada': 'El sujeto responsable no pertenece a la entidad indicada.'})

        # El ticket nace CONVERTIDO en el mismo INSERT: todo reporte abre
        # expediente de inmediato. Antes se guardaba PENDIENTE y se sobrescribia
        # una linea despues, o sea dos escrituras por reporte para un estado
        # que ningun cliente alcanzaba a ver.
        ticket = serializer.save(
            condominio=condominio, creado_por=self.request.user,
            estado=EstadoTicket.CONVERTIDO,
        )

        # Analisis automatico: se identifica la infraccion del catalogo vigente,
        # con su origen y fundamento. Si el encuadre es solido, el expediente se
        # notifica de inmediato y el residente se defiende apelando; si no, queda
        # EN_REVISION para que lo tipifique una persona.
        sugerida, origen, confianza, fundamento = proponer_infraccion(ticket)

        # Varios vecinos suelen reportar el mismo hecho. Abrir un expediente por
        # cada reporte permitiria sancionar dos veces lo mismo, asi que el
        # segundo y siguientes se suman al expediente ya abierto: en vez de
        # duplicar la sancion, la respaldan con mas testigos.
        existente = buscar_expediente_abierto(
            condominio, ticket.unidad, ticket.fecha_hecho, sugerida,
        )
        if existente is not None:
            ticket.corrobora = existente
            ticket.save(update_fields=['corrobora'])
            registrar_historial(
                existente, existente.estado, existente.estado, self.request.user,
                f'Reporte #{ticket.id} sumado como corroboracion del mismo hecho.',
            )
            return

        multa = Multa.objects.create(
            condominio=ticket.condominio,
            ticket=ticket,
            unidad=ticket.unidad,
            persona_infractor=ticket.persona_reportada,
            estado=EstadoMulta.EN_REVISION,
            infraccion=sugerida,
            monto=sugerida.monto if sugerida else None,
            propuesta_origen=origen,
            propuesta_confianza=confianza,
            propuesta_fundamento=fundamento,
        )
        # El comite ya no hace de filtro previo: interviene una sola vez, y solo
        # si el residente apela. Lo que no se puede cursar solo queda EN_REVISION.
        cursar_multa_automatica(multa, confianza)

    def create(self, request, *args, **kwargs):
        """
        Igual que el create estandar, pero si el reporte se sumo a un expediente
        ya abierto se le explica a quien reporta en que va. Se informa la ETAPA,
        nunca el monto, la infraccion ni la persona: quien denuncia no tiene por
        que conocer la sancion de otra unidad.
        """
        respuesta = super().create(request, *args, **kwargs)
        ticket = Ticket.objects.filter(id=respuesta.data.get('id')).first()
        if ticket and ticket.corrobora_id:
            expediente = ticket.corrobora
            respuesta.data['duplicado'] = True
            respuesta.data['expediente_id'] = expediente.id
            respuesta.data['expediente_estado'] = expediente.estado
            respuesta.data['reportes_del_hecho'] = expediente.corroboraciones.count() + 1
            respuesta.data['mensaje'] = (
                f'{ETAPA_PARA_DENUNCIANTE.get(expediente.estado, "Ya fue reportado.")} '
                'Tu reporte se sumo como respaldo del caso.'
            )
        else:
            respuesta.data['duplicado'] = False
        return respuesta

    @action(detail=True, methods=['post'], url_path='evidencia', parser_classes=[MultiPartParser])
    def agregar_evidencia(self, request, pk=None):
        ticket = self.get_object()
        imagen = request.FILES.get('imagen')
        if not imagen:
            return Response({'detail': 'Debe adjuntar una imagen.'}, status=400)
        digest, metadatos, anclaje = procesar_evidencia(imagen)
        evidencia = EvidenciaFoto.objects.create(
            ticket=ticket, imagen=imagen, descripcion=request.data.get('descripcion', ''),
            sha256=digest, metadatos_origen=metadatos, anclaje_fisico=anclaje,
        )
        return Response(EvidenciaFotoSerializer(evidencia).data, status=201)


class MultaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Flujo legal de la multa. Las multas NUNCA se crean ni editan directamente:
    nacen del ticket del Fiscalizador y solo cambian de estado a traves de las
    acciones tipadas de este ViewSet, cada una restringida al rol que la
    Ley 21.442 habilita (aprobar=Comite, notificar=Administrador, etc.).
    """

    serializer_class = MultaSerializer

    def get_permissions(self):
        if self.action in ('aprobar', 'rechazar', 'resolver_descargo_view'):
            return [EsComite()]
        if self.action in ('notificar', 'constancia_buzon'):
            return [EsAdministrador()]
        if self.action == 'presentar_descargo':
            return [EsResidente()]
        return [UsuarioAsignado()]

    def get_queryset(self):
        user = self.request.user
        qs = Multa.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=user.condominio_id)
            actualizar_multas_vencidas(user.condominio)
        if user.rol == Rol.RESIDENTE:
            qs = qs.filter(persona_infractor=user.persona)
        elif user.rol == Rol.FISCALIZADOR:
            qs = qs.filter(ticket__creado_por=user)
        return qs

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        """
        Tipificacion humana de un expediente que el sistema no pudo cursar solo.

        Ya no es el paso normal: en el ciclo vigente la denuncia se notifica de
        inmediato y el comite interviene una sola vez, al resolver la apelacion.
        Aqui llegan las excepciones —el reporte no calzo con ninguna infraccion,
        la propuesta quedo bajo el umbral de confianza, o falto el correo del
        residente— para que no se pierdan sin que nadie las mire.
        """
        multa = self.get_object()
        if multa.estado != EstadoMulta.EN_REVISION:
            return Response({'detail': 'Solo se pueden tipificar expedientes en revision.'}, status=400)

        datos = AprobarMultaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        try:
            infraccion = InfraccionCatalogo.objects.get(
                id=datos.validated_data['infraccion_id'],
                condominio=multa.condominio,
                estado=EstadoInfraccion.ACTIVA,
            )
        except InfraccionCatalogo.DoesNotExist:
            return Response({'detail': 'La infraccion no existe o no esta activa en el catalogo.'}, status=400)

        if not multa.persona_infractor:
            return Response({'detail': 'Debe indicarse el sujeto responsable antes de aprobar.'}, status=400)

        estado_anterior = multa.estado
        factor_aplicado = aplicar_monto_con_reincidencia(
            multa, infraccion, monto_base=datos.validated_data.get('monto'),
        )
        multa.estado = EstadoMulta.APROBADA
        multa.aprobada_por = request.user
        multa.fecha_aprobacion = timezone.now()
        multa.save()

        registrar_historial(multa, estado_anterior, multa.estado, request.user, 'Expediente tipificado por el Comite.')
        sellar_acto(multa, TipoActo.APROBACION, request.user, extra={
            'monto_aplicado': str(multa.monto),
            'factor_reincidencia_aplicado': str(factor_aplicado),
            'agravante_sugerido': multa.agravante_sugerido,
            'multa_primera_sancion_id': multa.multa_primera_sancion_id,
        })
        return Response(MultaSerializer(multa).data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        multa = self.get_object()
        if multa.estado != EstadoMulta.EN_REVISION:
            return Response({'detail': 'Solo se pueden rechazar expedientes en revision.'}, status=400)

        datos = RechazarMultaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        estado_anterior = multa.estado
        multa.estado = EstadoMulta.RECHAZADA
        multa.motivo_rechazo = datos.validated_data['motivo']
        multa.save()

        registrar_historial(multa, estado_anterior, multa.estado, request.user, multa.motivo_rechazo)
        sellar_acto(multa, TipoActo.RECHAZO, request.user, extra={'motivo': multa.motivo_rechazo})
        return Response(MultaSerializer(multa).data)

    @action(detail=True, methods=['post'])
    def notificar(self, request, pk=None):
        """Solo el Administrador notifica: genera el PDF y lo envia al correo registrado."""
        multa = self.get_object()
        if multa.estado != EstadoMulta.APROBADA:
            return Response({'detail': 'Solo se pueden notificar expedientes aprobados.'}, status=400)

        try:
            notificar_multa(multa, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        except Exception as exc:
            return Response({'detail': f'Error generando/enviando la notificacion: {exc}'}, status=502)

        return Response(MultaSerializer(multa).data)

    def retrieve(self, request, *args, **kwargs):
        """
        Que el propio residente abra su multa vale como acuse de recibo: no hay
        constancia mas clara de que se entero que haberla ido a ver.
        """
        respuesta = super().retrieve(request, *args, **kwargs)
        multa = self.get_object()
        if (
            request.user.rol == Rol.RESIDENTE
            and multa.persona_infractor_id == request.user.persona_id
            and multa.estado == EstadoMulta.NOTIFICADA
            and not multa.fecha_acuse
        ):
            registrar_acuse(
                multa, CanalNotificacion.APP, usuario=request.user,
                detalle='El residente abrio la multa en la aplicacion.',
            )
            multa.refresh_from_db()
            return Response(MultaSerializer(multa).data)
        return respuesta

    @action(detail=True, methods=['post'], url_path='constancia-buzon')
    def constancia_buzon(self, request, pk=None):
        """
        Registra que se dejo la notificacion impresa en el buzon de la unidad.

        Es la salida cuando el residente no acusa recibo por ningun canal
        digital: agotados los intentos, alguien imprime el documento, lo deja
        en la unidad y lo registra aqui. Ese registro perfecciona la
        notificacion y recien entonces arranca el plazo de apelacion, con
        nombre y fecha de quien la dejo.
        """
        multa = self.get_object()
        if multa.estado != EstadoMulta.NOTIFICADA:
            return Response({'detail': 'Solo aplica a expedientes ya despachados.'}, status=400)
        if multa.fecha_acuse:
            return Response({'detail': 'Esta notificacion ya fue recepcionada.'}, status=400)

        registrar_acuse(
            multa, CanalNotificacion.BUZON, usuario=request.user,
            destino=multa.unidad.identificador if multa.unidad else '',
            detalle=request.data.get('detalle', '')[:500],
        )
        multa.refresh_from_db()
        return Response(MultaSerializer(multa).data)

    # El adjunto es opcional: se aceptan tanto multipart (con archivo) como
    # JSON (defensa solo de texto), para que un cliente sin archivo no reciba
    # un 415 por enviar el formato natural de la API.
    @action(
        detail=True, methods=['post'], url_path='descargo',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def presentar_descargo(self, request, pk=None):
        """El residente presenta su defensa dentro del plazo configurado."""
        multa = self.get_object()
        if multa.persona_infractor_id != request.user.persona_id:
            return Response({'detail': 'Este expediente no corresponde a su ficha de sujeto responsable.'}, status=403)
        if multa.estado != EstadoMulta.NOTIFICADA:
            return Response({'detail': 'Solo se puede presentar descargo a expedientes notificados.'}, status=400)
        # Apelar es la prueba mas fuerte de que se entero: si llega sin haber
        # acusado recibo, se registra el acuse ahora y recien ahi hay plazo que
        # medir. Al reves seria absurdo rechazarle la defensa a quien la ejerce.
        if not multa.fecha_acuse:
            registrar_acuse(
                multa, CanalNotificacion.APP, usuario=request.user,
                detalle='El residente presento su apelacion en la aplicacion.',
            )
            multa.refresh_from_db()
        if not multa.descargo_vigente:
            return Response({'detail': 'El plazo para presentar descargos ha vencido.'}, status=400)
        if hasattr(multa, 'descargo'):
            return Response({'detail': 'Ya existe un descargo presentado para este expediente.'}, status=400)

        datos = PresentarDescargoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        descargo = Descargo.objects.create(
            multa=multa,
            presentado_por=request.user,
            texto=datos.validated_data['texto'],
            archivo_adjunto=datos.validated_data.get('archivo_adjunto'),
        )

        estado_anterior = multa.estado
        multa.estado = EstadoMulta.CON_DESCARGO
        multa.save(update_fields=['estado'])
        registrar_historial(multa, estado_anterior, multa.estado, request.user, 'Descargo presentado por el residente.')
        sellar_acto(multa, TipoActo.DESCARGO_PRESENTADO, request.user, extra={
            'texto': descargo.texto,
            'archivo_adjunto': descargo.archivo_adjunto.name if descargo.archivo_adjunto else None,
        })

        return Response(DescargoSerializer(descargo).data, status=201)

    @action(detail=True, methods=['post'], url_path='resolver-descargo')
    def resolver_descargo_view(self, request, pk=None):
        """El Comite resuelve el descargo: aceptarlo anula la multa, rechazarlo la deja firme."""
        multa = self.get_object()
        if not hasattr(multa, 'descargo'):
            return Response({'detail': 'Este expediente no tiene descargo presentado.'}, status=400)
        if multa.estado != EstadoMulta.CON_DESCARGO:
            return Response({'detail': 'Solo se resuelven descargos de expedientes con descargo pendiente.'}, status=400)

        datos = ResolverDescargoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)

        resolver_descargo(
            multa.descargo, datos.validated_data['resolucion'], request.user,
            datos.validated_data.get('comentario', ''),
            porcentaje_descuento=datos.validated_data.get('porcentaje_descuento'),
        )
        return Response(MultaSerializer(multa).data)

    @action(detail=True, methods=['get'], url_path='verificar-integridad')
    def verificar_integridad(self, request, pk=None):
        """
        Recalcula la cadena de actas selladas y los hashes de los archivos de
        evidencia del expediente. Cualquier usuario con acceso al expediente
        puede auditarlo: la verificabilidad es parte de la transparencia.
        """
        multa = self.get_object()
        return Response(verificar_expediente(multa))

    @action(detail=True, methods=['get'], url_path='audit-trail')
    def audit_trail(self, request, pk=None):
        """
        La Prueba Maestra: certificado PDF de integridad del expediente,
        imprimible y presentable ante tribunales o auditorias. Accesible a
        cualquier rol con acceso al expediente (la verificabilidad es
        simetrica: tambien es la defensa del residente).
        """
        multa = self.get_object()
        try:
            pdf = generar_audit_trail_pdf(multa, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        respuesta = HttpResponse(pdf, content_type='application/pdf')
        respuesta['Content-Disposition'] = f'attachment; filename="audit_trail_expediente_{multa.id}.pdf"'
        return respuesta


class MedidaInmediataViewSet(viewsets.ModelViewSet):
    """
    Carril de contencion. El contrato de creacion es minimalista a proposito:
    el operario en terreno solo indica expediente + codigo de hallazgo +
    evidencias; es el BACKEND quien decide si ese hallazgo detona contencion
    (calificacion hecha en frio en el catalogo), quitandole al operario el
    peso de la decision juridica.
    """

    serializer_class = MedidaInmediataSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [EsFiscalizadorOComiteOAdministrador()]
        # Ratificar NO se restringe a EsComite en la capa DRF: la delegacion
        # habilita a otros roles, y la unica autoridad autoritativa es
        # _resolver_autoridad (que responde 403 SinAutoridad si nada respalda).
        if self.action == 'ratificar':
            return [UsuarioAsignado()]
        if self.action == 'levantar':
            return [EsComite()]  # levantar no es delegable en esta fase
        return [UsuarioAsignado()]

    def get_queryset(self):
        user = self.request.user
        qs = MedidaInmediata.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(multa__condominio_id=user.condominio_id)
            # Barrido perezoso: consistente con actualizar_multas_vencidas.
            escalar_medidas_vencidas(user.condominio)
        if user.rol == Rol.RESIDENTE:
            qs = qs.filter(multa__persona_infractor=user.persona)
        return qs

    def create(self, request, *args, **kwargs):
        datos = EjecutarMedidaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        payload = datos.validated_data

        try:
            multa = Multa.objects.get(
                id=payload['expediente_id'], condominio=request.user.condominio,
            )
        except Multa.DoesNotExist:
            return Response({'detail': 'El expediente no existe en la organizacion activa.'}, status=400)

        try:
            hallazgo = InfraccionCatalogo.objects.get(
                condominio=request.user.condominio,
                codigo=payload['hallazgo_codigo'],
                estado=EstadoInfraccion.ACTIVA,
            )
        except InfraccionCatalogo.DoesNotExist:
            return Response({'detail': 'El hallazgo no existe o no esta activo en el catalogo.'}, status=400)

        if not hallazgo.conlleva_contencion:
            return Response(
                {'detail': f'El hallazgo {hallazgo.codigo} no detona contencion inmediata segun el catalogo. '
                           'Registre el reporte por el carril sancionatorio normal.'},
                status=400,
            )

        evidencias = list(EvidenciaFoto.objects.filter(
            id__in=payload['evidencia_ids'], ticket=multa.ticket,
        ))
        if len(evidencias) != len(set(payload['evidencia_ids'])):
            return Response({'detail': 'Alguna evidencia no existe o no pertenece a este expediente.'}, status=400)

        medida = ejecutar_contencion(
            multa, hallazgo, request.user,
            evidencias=evidencias,
            descripcion=payload['descripcion'],
            auth_metodo=payload['auth_metodo'],
        )
        return Response(MedidaInmediataSerializer(medida, context={'request': request}).data, status=201)

    @action(detail=True, methods=['post'])
    def ratificar(self, request, pk=None):
        medida = self.get_object()
        try:
            medida = ratificar_contencion(medida, request.user)
        except SinAutoridad as exc:
            return Response({'detail': str(exc)}, status=403)
        except TransicionInvalida as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(MedidaInmediataSerializer(medida, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def levantar(self, request, pk=None):
        medida = self.get_object()
        datos = LevantarMedidaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        try:
            medida = levantar_contencion(
                medida, request.user,
                causal=datos.validated_data['causal'],
                fundamento=datos.validated_data['fundamento'],
            )
        except TransicionInvalida as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(MedidaInmediataSerializer(medida, context={'request': request}).data)


class DelegacionViewSet(viewsets.ModelViewSet):
    """
    Delegaciones tacticas de autoridad. Otorgar/revocar reservado al Comite
    (el titular que delega su propia facultad). Todos ven las de su condominio
    para trazabilidad. Sin update: una delegacion no se edita, se revoca y se
    otorga otra (nueva version).
    """

    serializer_class = DelegacionSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'revocar'):
            return [EsComite()]
        return [UsuarioAsignado()]

    def get_queryset(self):
        user = self.request.user
        qs = Delegacion.objects.all()
        if user.rol != Rol.SUPERADMIN:
            qs = qs.filter(condominio_id=user.condominio_id)
        return qs

    def create(self, request, *args, **kwargs):
        datos = OtorgarDelegacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        v = datos.validated_data
        from accounts.models import Usuario
        try:
            delegado = Usuario.objects.get(id=v['delegado_id'], condominio=request.user.condominio)
        except Usuario.DoesNotExist:
            return Response({'detail': 'El delegado no existe en la organizacion activa.'}, status=400)
        try:
            delegacion = otorgar_delegacion(
                request.user.condominio, request.user, delegado,
                acciones=v['acciones'], tope_gravedad=v['tope_gravedad'],
                vigencia_desde=v['vigencia_desde'], vigencia_hasta=v['vigencia_hasta'],
                motivo=v['motivo'],
            )
        except TransicionInvalida as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(DelegacionSerializer(delegacion).data, status=201)

    @action(detail=True, methods=['post'])
    def revocar(self, request, pk=None):
        delegacion = self.get_object()
        if delegacion.delegante_id != request.user.id:
            return Response({'detail': 'Solo el delegante puede revocar su delegacion.'}, status=403)
        return Response(DelegacionSerializer(revocar_delegacion(delegacion)).data)

    @action(detail=False, methods=['get'])
    def candidatos(self, request):
        """Usuarios de la organizacion a quienes se puede delegar (no el propio, no residentes)."""
        from accounts.models import Usuario
        qs = Usuario.objects.filter(
            condominio=request.user.condominio, is_active=True,
        ).exclude(id=request.user.id).exclude(rol=Rol.RESIDENTE)
        return Response([
            {'id': u.id, 'nombre': u.get_full_name() or u.username, 'rol': u.rol}
            for u in qs
        ])
