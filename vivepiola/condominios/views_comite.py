"""El Administrador registra la designacion del Comite y sigue sus accesos."""

import json

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Rol
from accounts.permissions import EsAdministrador, UsuarioAsignado

from .comite import (
    DesignacionInvalida, designar_comite, estado_comite, motivo_no_elegible, reenviar_acceso,
)
from .models import MiembroComite, Persona


class EstadoComiteView(APIView):
    """
    GET: el Comite vigente, sus miembros y que les falta. Lo ven todos los de
    la comunidad (el Comite lo usa para saber si esta habilitado), pero los
    correos solo el Administrador.
    """

    permission_classes = [UsuarioAsignado]

    def get(self, request):
        if not request.user.condominio_id:
            return Response({'detail': 'Su cuenta no esta asociada a una comunidad.'}, status=400)
        estado = estado_comite(request.user.condominio)
        if request.user.rol != Rol.ADMINISTRADOR:
            for m in estado['miembros']:
                m.pop('correo', None)
        return Response(estado)


class ElegiblesComiteView(APIView):
    """GET: las personas del registro que pueden integrar el Comite, y las que no con su motivo."""

    permission_classes = [EsAdministrador]

    def get(self, request):
        filas = []
        personas = Persona.objects.filter(condominio_id=request.user.condominio_id).select_related('unidad')
        for p in personas:
            filas.append({
                'id': p.id,
                'nombre': p.nombre_completo,
                'unidad': p.unidad.identificador,
                'rol_ocupacion': p.get_rol_ocupacion_display(),
                'motivo_no_elegible': motivo_no_elegible(p),
            })
        return Response(filas)


class DesignarComiteView(APIView):
    """
    POST (multipart): acta (PDF), fecha_asamblea, vigente_hasta, personas
    (lista de ids, como JSON o repetida), cargos (JSON {id: cargo}, opcional).
    Reemplaza la designacion anterior.
    """

    permission_classes = [EsAdministrador]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        from datetime import date

        condominio = request.user.condominio
        if condominio is None:
            raise ValidationError({'detail': 'Su cuenta no esta asociada a una comunidad.'})
        acta = request.FILES.get('acta')
        if acta is None:
            raise ValidationError({'acta': 'Adjunta el acta de la asamblea en PDF.'})
        if not acta.name.lower().endswith('.pdf'):
            raise ValidationError({'acta': 'El acta debe ser un PDF.'})
        try:
            fecha_asamblea = date.fromisoformat(request.data.get('fecha_asamblea', ''))
            vigente_hasta = date.fromisoformat(request.data.get('vigente_hasta', ''))
        except ValueError:
            raise ValidationError({'detail': 'Indica la fecha de la asamblea y el termino del mandato.'})

        ids = request.data.getlist('personas') if hasattr(request.data, 'getlist') else request.data.get('personas', [])
        if len(ids) == 1 and str(ids[0]).startswith('['):
            ids = json.loads(ids[0])
        try:
            ids = [int(i) for i in ids]
        except (TypeError, ValueError):
            raise ValidationError({'personas': 'Lista de personas invalida.'})
        personas = list(Persona.objects.filter(id__in=ids).select_related('unidad', 'condominio'))
        if len(personas) != len(set(ids)):
            raise ValidationError({'personas': 'Alguna persona elegida no existe en el registro.'})

        try:
            cargos = {int(k): str(v) for k, v in json.loads(request.data.get('cargos') or '{}').items()}
        except (ValueError, AttributeError):
            cargos = {}

        try:
            designar_comite(
                condominio, acta=acta, fecha_asamblea=fecha_asamblea, vigente_hasta=vigente_hasta,
                personas=personas, usuario=request.user, cargos=cargos,
                notas=(request.data.get('notas') or '')[:255],
            )
        except DesignacionInvalida as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(estado_comite(condominio), status=201)


class ReenviarAccesoComiteView(APIView):
    permission_classes = [EsAdministrador]

    def post(self, request, pk):
        miembro = get_object_or_404(
            MiembroComite.objects.select_related('persona__unidad', 'persona__condominio'),
            pk=pk, designacion__condominio_id=request.user.condominio_id, designacion__activa=True,
        )
        try:
            reenviar_acceso(miembro, request.user)
        except DesignacionInvalida as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(estado_comite(request.user.condominio))
