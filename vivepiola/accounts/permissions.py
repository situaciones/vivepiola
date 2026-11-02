"""
Permisos reutilizables en toda la app. Cada clase representa un rol de la
Ley 21.442; se combinan con permisos de objeto (misma unidad/condominio)
en las vistas especificas de cada modulo para impedir que, por ejemplo, un
Administrador presione el boton que la ley reserva solo al Comite.
"""

from rest_framework.permissions import BasePermission

from .models import Rol


def permiso_por_rol(*roles_permitidos):
    """Factory: crea una clase de permiso que exige que request.user.rol este en roles_permitidos."""

    class _PermisoRol(BasePermission):
        message = f'Esta accion esta reservada a los roles: {", ".join(roles_permitidos)}.'

        def has_permission(self, request, view):
            return bool(
                request.user
                and request.user.is_authenticated
                and (request.user.rol in roles_permitidos or request.user.rol == Rol.SUPERADMIN)
            )

    _PermisoRol.__name__ = 'Permiso_' + '_'.join(roles_permitidos)
    return _PermisoRol


def permiso_comite(*otros_roles):
    """
    Como permiso_por_rol, pero el rol COMITE solo basta si la persona integra
    el Comite designado y vigente (condominios/comite.py). Es para las
    decisiones que la ley reserva al Comite; leer no pasa por aqui.
    """

    class _PermisoComite(BasePermission):
        message = 'Esta accion esta reservada al Comite de Administracion.'

        def has_permission(self, request, view):
            from condominios.comite import motivo_sin_facultad

            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.rol in otros_roles or user.rol == Rol.SUPERADMIN:
                return True
            if user.rol != Rol.COMITE:
                return False
            motivo = motivo_sin_facultad(user)
            if motivo:
                self.message = motivo
                return False
            return True

    _PermisoComite.__name__ = 'PermisoComite_' + '_'.join(otros_roles)
    return _PermisoComite


EsFiscalizador = permiso_por_rol(Rol.FISCALIZADOR)
EsComite = permiso_comite()
EsAdministrador = permiso_por_rol(Rol.ADMINISTRADOR)
EsResidente = permiso_por_rol(Rol.RESIDENTE)
EsComiteOAdministrador = permiso_comite(Rol.ADMINISTRADOR)
EsFiscalizadorOComiteOAdministrador = permiso_por_rol(Rol.FISCALIZADOR, Rol.COMITE, Rol.ADMINISTRADOR)
# Denunciante: quien puede levantar un reporte. La Ley habilita a conserje,
# comite y a cualquier copropietario/residente (con opcion de anonimato).
EsDenunciante = permiso_por_rol(Rol.FISCALIZADOR, Rol.COMITE, Rol.RESIDENTE)
# Solo el administrador del sistema puede provisionar nuevas organizaciones.
EsSuperadmin = permiso_por_rol()


class UsuarioAsignado(BasePermission):
    """
    Autenticado Y con rol asignado. Las cuentas PENDIENTE (registro Google sin
    invitacion) solo pueden ver su perfil (/auth/me); ningun modulo del flujo.
    """

    message = 'Su cuenta esta pendiente de asignacion de rol por el Administrador de su comunidad.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.rol != Rol.PENDIENTE
        )


class MismoCondominio(BasePermission):
    """Restringe el acceso a objetos del mismo condominio que el usuario autenticado."""

    message = 'No tiene acceso a recursos de otro condominio.'

    def has_object_permission(self, request, view, obj):
        condominio_obj = getattr(obj, 'condominio', None)
        if condominio_obj is None:
            return True
        return request.user.rol == Rol.SUPERADMIN or request.user.condominio_id == condominio_obj.id
