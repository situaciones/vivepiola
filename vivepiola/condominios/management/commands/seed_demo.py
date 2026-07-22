from django.core.management.base import BaseCommand

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from reglamentos.models import EstadoInfraccion, Gravedad, InfraccionCatalogo


class Command(BaseCommand):
    help = 'Crea datos de demostracion: un condominio con unidades, personas, usuarios de cada rol e infracciones.'

    def handle(self, *args, **options):
        condominio, _ = Condominio.objects.get_or_create(
            nombre='Condominio Los Alerces',
            defaults={'direccion': 'Av. Las Condes 1234, Santiago', 'rut': '76.123.456-7', 'plazo_descargo_dias': 5},
        )

        unidad_302, _ = Unidad.objects.get_or_create(condominio=condominio, identificador='Depto 302')
        unidad_105, _ = Unidad.objects.get_or_create(condominio=condominio, identificador='Depto 105')

        persona_302, _ = Persona.objects.update_or_create(
            condominio=condominio, unidad=unidad_302, cedula_identidad='12.345.678-9',
            defaults={
                'rol_ocupacion': RolOcupacion.PROPIETARIO,
                'nombre_completo': 'Juana Perez Soto',
                'domicilio': 'Depto 302, Av. Las Condes 1234',
                'correo_electronico': 'residente.demo@debido.local',
                'telefono': '+56912345678',
            },
        )
        Persona.objects.update_or_create(
            condominio=condominio, unidad=unidad_105, cedula_identidad='9.876.543-2',
            defaults={
                'rol_ocupacion': RolOcupacion.ARRENDATARIO,
                'nombre_completo': 'Pedro Soto Rojas',
                'domicilio': 'Depto 105, Av. Las Condes 1234',
                'correo_electronico': 'arrendatario.demo@debido.local',
                'telefono': '',
            },
        )

        usuarios = [
            ('conserje', Rol.FISCALIZADOR, None),
            ('comite', Rol.COMITE, None),
            ('administrador', Rol.ADMINISTRADOR, None),
            ('residente', Rol.RESIDENTE, persona_302),
        ]
        for username, rol, persona in usuarios:
            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={'rol': rol, 'condominio': condominio, 'persona': persona, 'email': f'{username}@debido.local'},
            )
            if creado:
                usuario.set_password('Demo12345')
                usuario.save()

        InfraccionCatalogo.objects.get_or_create(
            condominio=condominio, codigo='RUIDO-01',
            defaults={
                'descripcion': 'Ruidos molestos fuera del horario permitido (22:00 a 08:00 hrs).',
                'articulo_referencia': 'Art. 15',
                'monto': 1,
                'unidad_monto': 'UF',
                'gravedad': Gravedad.LEVE,
                'estado': EstadoInfraccion.ACTIVA,
            },
        )
        InfraccionCatalogo.objects.get_or_create(
            condominio=condominio, codigo='MASCOTA-02',
            defaults={
                'descripcion': 'No recoger los desechos de mascotas en areas comunes.',
                'articulo_referencia': 'Art. 22',
                'monto': 0.5,
                'unidad_monto': 'UF',
                'gravedad': Gravedad.LEVE,
                'estado': EstadoInfraccion.ACTIVA,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            'Datos de demo creados. Usuarios: conserje/comite/administrador/residente '
            '(contrasena: Demo12345), condominio "Condominio Los Alerces".'
        ))
