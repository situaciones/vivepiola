"""
El Comite de Administracion como organo designado, no como un rol suelto.

Antes cualquiera a quien el Administrador le diera el rol COMITE decidia como
Comite. Ahora el Comite nace de una designacion: el acta de la asamblea, su
vigencia y los miembros elegidos desde el registro de copropietarios. Solo
quien integra la designacion vigente puede tomar las decisiones que la ley
reserva al Comite.

Compatibilidad: una comunidad que nunca registro una designacion sigue como
antes (sus cuentas COMITE deciden), pero se le avisa que falta el acta. En
cuanto registra la primera, rige solo la designacion.
"""

from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    CondicionEspecial, DesignacionComite, MiembroComite, Persona, RolOcupacion, VinculoCopropietario,
)


class DesignacionInvalida(Exception):
    """La designacion no cumple las reglas; el mensaje se muestra tal cual."""


def motivo_no_elegible(persona):
    """Por que esta persona no puede integrar el Comite; None si puede."""
    if not persona.activo:
        return 'esta dada de baja en el registro'
    if persona.condicion_especial == CondicionEspecial.FALLECIDO:
        return 'figura como fallecida en el registro'
    es_dueno = persona.rol_ocupacion == RolOcupacion.PROPIETARIO
    es_pareja = persona.vinculo_copropietario in (
        VinculoCopropietario.CONYUGE, VinculoCopropietario.CONVIVIENTE_CIVIL,
    )
    if not (es_dueno or es_pareja):
        return 'no es propietaria ni conyuge o conviviente civil de un propietario'
    if not persona.correo_electronico:
        return 'no tiene correo en el registro'
    return None


def personas_elegibles(condominio):
    return [
        p for p in Persona.objects.filter(condominio=condominio).select_related('unidad')
        if motivo_no_elegible(p) is None
    ]


def designacion_vigente(condominio, hoy=None):
    """La designacion activa, este o no dentro de su plazo (None si no hay)."""
    return (
        DesignacionComite.objects.filter(condominio=condominio, activa=True)
        .prefetch_related('miembros__persona__unidad').first()
    )


def motivo_comite_no_vigente(condominio, hoy=None):
    """
    Por que la comunidad no tiene un Comite habilitado para decidir; None si
    lo tiene. 'sin_designacion' se distingue porque es el caso de
    compatibilidad (comunidades anteriores a esta regla).
    """
    hoy = hoy or timezone.localdate()
    designacion = designacion_vigente(condominio)
    if designacion is None:
        return 'sin_designacion'
    if hoy < designacion.fecha_asamblea:
        return f'El mandato del Comite comienza el {designacion.fecha_asamblea:%d-%m-%Y}.'
    if hoy > designacion.vigente_hasta:
        return (
            f'El mandato del Comite vencio el {designacion.vigente_hasta:%d-%m-%Y}. '
            'La asamblea debe elegir uno nuevo y el Administrador registrar el acta.'
        )
    return None


def motivo_sin_facultad(usuario, hoy=None):
    """
    Por que `usuario` no puede decidir como Comite; None si puede. Se usa en
    los permisos de toda decision que la ley reserva al Comite.
    """
    from accounts.models import Rol

    if usuario.rol == Rol.SUPERADMIN:
        return None
    if usuario.rol != Rol.COMITE or not usuario.condominio_id:
        return 'Esta accion esta reservada al Comite de Administracion.'
    motivo = motivo_comite_no_vigente(usuario.condominio, hoy)
    if motivo == 'sin_designacion':
        return None  # comunidad anterior a la designacion: sigue como antes
    if motivo:
        return motivo
    designacion = designacion_vigente(usuario.condominio)
    if not usuario.persona_id or not designacion.miembros.filter(persona_id=usuario.persona_id).exists():
        return 'No integra el Comite designado en la ultima asamblea registrada.'
    return None


def _cuenta_de(persona):
    from accounts.models import Usuario

    cuenta = getattr(persona, 'usuario_cuenta', None)
    if cuenta is not None and cuenta.is_active:
        return cuenta
    return Usuario.objects.filter(
        condominio=persona.condominio, email__iexact=persona.correo_electronico, is_active=True,
    ).first()


def _invitar(persona, usuario):
    from accounts.models import EstadoInvitacion, Invitacion, Rol
    from accounts.views import _enviar_correo_invitacion

    Invitacion.objects.filter(
        condominio=persona.condominio, correo__iexact=persona.correo_electronico,
        estado=EstadoInvitacion.PENDIENTE,
    ).update(estado=EstadoInvitacion.REVOCADA)
    invitacion = Invitacion.objects.create(
        condominio=persona.condominio, correo=persona.correo_electronico, unidad=persona.unidad,
        rol_sugerido=Rol.COMITE, creada_por=usuario,
    )
    _enviar_correo_invitacion(invitacion)
    return invitacion


@transaction.atomic
def designar_comite(condominio, *, acta, fecha_asamblea, vigente_hasta, personas, usuario, cargos=None, notas=''):
    """
    Registra la eleccion del Comite y deja los accesos al dia:
      - quien ya tiene cuenta en la comunidad pasa a rol Comite;
      - quien no, recibe por correo el enlace para activar su acceso;
      - los miembros salientes vuelven a Residente y sus enlaces pendientes
        se revocan.
    """
    from accounts.models import EstadoInvitacion, Invitacion, Rol, Usuario

    cargos = cargos or {}
    personas = list(personas)
    if vigente_hasta < fecha_asamblea:
        raise DesignacionInvalida('El termino del mandato no puede ser anterior a la asamblea.')
    maximo = date(
        fecha_asamblea.year + settings.COMITE_DURACION_MAXIMA_ANOS, fecha_asamblea.month,
        min(fecha_asamblea.day, 28),
    )
    if vigente_hasta > maximo:
        raise DesignacionInvalida(
            f'El mandato no puede durar mas de {settings.COMITE_DURACION_MAXIMA_ANOS} anos.'
        )
    if len(set(p.id for p in personas)) < settings.COMITE_MIEMBROS_MINIMOS:
        raise DesignacionInvalida(
            f'El Comite debe tener al menos {settings.COMITE_MIEMBROS_MINIMOS} miembros.'
        )
    problemas = []
    for p in personas:
        if p.condominio_id != condominio.id:
            problemas.append(f'{p.nombre_completo} no pertenece a la comunidad')
            continue
        motivo = motivo_no_elegible(p)
        if motivo:
            problemas.append(f'{p.nombre_completo} {motivo}')
            continue
        cuenta = _cuenta_de(p)
        if cuenta and cuenta.rol in (Rol.ADMINISTRADOR, Rol.FISCALIZADOR):
            problemas.append(
                f'{p.nombre_completo} tiene cuenta como {cuenta.get_rol_display()}; '
                'una cuenta tiene un solo rol'
            )
    if problemas:
        raise DesignacionInvalida('No se puede designar: ' + '; '.join(problemas) + '.')

    DesignacionComite.objects.filter(condominio=condominio, activa=True).update(activa=False)
    designacion = DesignacionComite.objects.create(
        condominio=condominio, acta=acta, fecha_asamblea=fecha_asamblea,
        vigente_hasta=vigente_hasta, notas=notas, creada_por=usuario,
    )
    ids_personas = set()
    for p in personas:
        if p.id in ids_personas:
            continue
        ids_personas.add(p.id)
        MiembroComite.objects.create(designacion=designacion, persona=p, cargo=cargos.get(p.id, '')[:60])
        cuenta = _cuenta_de(p)
        if cuenta is None:
            _invitar(p, usuario)
            continue
        cuenta.rol = Rol.COMITE
        cuenta.persona = p
        cuenta.save(update_fields=['rol', 'persona'])

    # Salientes: cuentas Comite de la comunidad que no siguen.
    for cuenta in Usuario.objects.filter(condominio=condominio, rol=Rol.COMITE):
        if cuenta.persona_id not in ids_personas:
            cuenta.rol = Rol.RESIDENTE if cuenta.persona_id else Rol.PENDIENTE
            cuenta.save(update_fields=['rol'])
    correos_miembros = {p.correo_electronico.lower() for p in personas}
    for invitacion in Invitacion.objects.filter(
        condominio=condominio, rol_sugerido=Rol.COMITE, estado=EstadoInvitacion.PENDIENTE,
    ):
        if invitacion.correo.lower() not in correos_miembros:
            invitacion.estado = EstadoInvitacion.REVOCADA
            invitacion.save(update_fields=['estado'])
    return designacion


def reenviar_acceso(miembro, usuario):
    if _cuenta_de(miembro.persona) is not None:
        raise DesignacionInvalida('Esta persona ya tiene su acceso activo.')
    return _invitar(miembro.persona, usuario)


def estado_comite(condominio):
    """Lo que el Administrador necesita ver del Comite, listo para la API."""
    from accounts.models import EstadoInvitacion, Invitacion, Rol

    designacion = designacion_vigente(condominio)
    motivo = motivo_comite_no_vigente(condominio)
    respuesta = {
        'designacion': None,
        'vigente': motivo is None,
        'motivo': None if motivo in (None, 'sin_designacion') else motivo,
        'sin_designacion': motivo == 'sin_designacion',
        'miembros': [],
        'activos': 0,
        'quorum': condominio.quorum_resolucion_apelacion,
        'minimo': settings.COMITE_MIEMBROS_MINIMOS,
        'alertas': [],
    }
    if designacion is None:
        respuesta['alertas'].append(
            'No hay Comite registrado. Sube el acta de la asamblea que lo eligio y elige a sus miembros.'
        )
        return respuesta

    respuesta['designacion'] = {
        'id': designacion.id,
        'fecha_asamblea': designacion.fecha_asamblea,
        'vigente_hasta': designacion.vigente_hasta,
        'acta': designacion.acta.url if designacion.acta else None,
        'notas': designacion.notas,
    }
    for m in designacion.miembros.all():
        cuenta = _cuenta_de(m.persona)
        invitacion = None
        if cuenta and cuenta.rol == Rol.COMITE:
            estado = 'ACTIVO'
            respuesta['activos'] += 1
        else:
            invitacion = Invitacion.objects.filter(
                condominio=condominio, correo__iexact=m.persona.correo_electronico,
                rol_sugerido=Rol.COMITE, estado=EstadoInvitacion.PENDIENTE,
            ).first()
            estado = 'INVITADO' if invitacion and invitacion.vigente else 'SIN_ACTIVAR'
        respuesta['miembros'].append({
            'id': m.id,
            'persona_id': m.persona_id,
            'nombre': m.persona.nombre_completo,
            'unidad': m.persona.unidad.identificador,
            'correo': m.persona.correo_electronico,
            'cargo': m.cargo,
            'estado': estado,
            'invitacion_vence': invitacion.expira_en if invitacion else None,
        })
    if motivo and motivo != 'sin_designacion':
        respuesta['alertas'].append(motivo)
    elif respuesta['activos'] < respuesta['quorum']:
        respuesta['alertas'].append(
            f'Solo {respuesta["activos"]} de los miembros activaron su acceso y el quorum es '
            f'{respuesta["quorum"]}: el Comite no puede resolver apelaciones hasta que se activen mas.'
        )
    dias = (designacion.vigente_hasta - timezone.localdate()).days
    if motivo is None and 0 <= dias <= 60:
        respuesta['alertas'].append(
            f'El mandato vence el {designacion.vigente_hasta:%d-%m-%Y}: convoca a asamblea para elegir el proximo Comite.'
        )
    return respuesta
