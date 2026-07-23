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


EsFiscalizador = permiso_por_rol(Rol.FISCALIZADOR)
EsComite = permiso_por_rol(Rol.COMITE)
EsAdministrador = permiso_por_rol(Rol.ADMINISTRADOR)
EsResidente = permiso_por_rol(Rol.RESIDENTE)
EsComiteOAdministrador = permiso_por_rol(Rol.COMITE, Rol.ADMINISTRADOR)
EsFiscalizadorOComiteOAdministrador = permiso_por_rol(Rol.FISCALIZADOR, Rol.COMITE, Rol.ADMINISTRADOR)
# Denunciante: quien puede levantar un reporte. La Ley habilita a conserje,
# comite y a cualquier copropietario/residente (con opcion de anonimato).
EsDenunciante = permiso_por_rol(Rol.FISCALIZADOR, Rol.COMITE, Rol.RESIDENTE)


class MismoCondominio(BasePermission):
    """Restringe el acceso a objetos del mismo condominio que el usuario autenticado."""

    message = 'No tiene acceso a recursos de otro condominio.'

    def has_object_permission(self, request, view, obj):
        condominio_obj = getattr(obj, 'condominio', None)
        if condominio_obj is None:
            return True
        return request.user.rol == Rol.SUPERADMIN or request.user.condominio_id == condominio_obj.id
