from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad, Vertical
from reglamentos.models import EstadoInfraccion, Gravedad, InfraccionCatalogo

VOCABULARIO_CONSTRUCCION = {
    'organizacion': 'Obra',
    'unidad': 'Subcontratista',
    'multa': 'No conformidad',
    'multa_plural': 'No conformidades',
    'reporte_corto': 'Nuevo hallazgo',
    'nuevo_reporte': 'Nuevo hallazgo de terreno',
    'persona_reportada': 'Responsable del subcontratista',
    'residente': 'Contratista responsable',
    'descargo': 'Reclamacion',
    'descargo_min': 'reclamacion',
    'multa_min': 'no conformidad',
    'catalogo': 'Catalogo de no conformidades',
    'infraccion': 'No conformidad tipificada',
    'contencion': 'Paralizacion',
    'contencion_titulo': 'Paralizacion de faena',
    'contenciones': 'Paralizaciones',
    'rol_FISCALIZADOR': 'Supervisor de terreno (ITO)',
    'rol_COMITE': 'Administrador de contrato',
    'rol_ADMINISTRADOR': 'Oficina tecnica',
    'rol_RESIDENTE': 'Contratista',

    # --- Portal del infractor (Contratista) ---
    'mis_multas': 'Mis no conformidades',
    'mis_multas_sub': 'Consulta las no conformidades de tu subcontrato con su evidencia y presenta reclamaciones dentro del plazo contractual.',
    'presentar_descargo': 'Presentar reclamacion',
    'descargo_placeholder': 'Escribe tu reclamacion...',
    'tu_descargo': 'Tu reclamacion:',
    'ver_notificacion_pdf': 'Ver aviso de no conformidad (PDF)',
    'por_que_falta': '¿Por que es una no conformidad?',
    'por_que_falta_texto': 'El contrato de obra la tipifica como no conformidad',
    'semaforo_verde_titulo': 'Subcontrato al dia',
    'semaforo_verde_detalle': 'No registras no conformidades activas. Estandar de obra cumplido.',
    'semaforo_ambar_titulo': 'Tienes un proceso en curso',
    'semaforo_ambar_detalle': 'Hay una no conformidad en tramite o con plazo de reclamacion abierto. Revisa los detalles mas abajo.',
    'semaforo_rojo_titulo': 'Tienes no conformidades firmes',
    'semaforo_rojo_detalle': 'Una o mas no conformidades quedaron firmes y seran descontadas de tus estados de pago.',
    'countdown_texto': 'para presentar reclamaciones',
    'countdown_vencido': 'Plazo de reclamacion vencido',

    # --- Gestion (Oficina tecnica) ---
    'registro_titulo': 'Registro de subcontratistas',
    'registro_sub': 'Individualiza a los subcontratistas y sus responsables con el correo legal de notificacion.',

    # Terminos server-side (correo + PDF)
    'organizacion_cap': 'Obra',
    'unidad_cap': 'Subcontratista',
    'multa_cap': 'No conformidad',
    'sujeto_cap': 'Responsable del subcontratista',
    'organo_sancionador': 'Administrador de contrato',
    'destino_cobro': 'estados de pago del contrato',

    # Frases completas (i18n clave-por-frase)
    'notificacion_asunto': 'Aviso de No Conformidad #{numero} - {org_nombre}',
    'notificacion_cuerpo': (
        'Se le notifica que el Administrador de contrato de {org_nombre} ha aprobado '
        'una No Conformidad asociada al subcontratista {unidad_id} por el hallazgo '
        '"{infraccion}" (Clausula {articulo}).'
    ),
    'pdf_titulo': 'Aviso de No Conformidad N° {numero}',
    'pdf_aviso_descargo': (
        'El subcontratista dispone de un plazo de {dias} dias corridos desde esta '
        'notificacion, hasta el {fecha_limite}, para presentar su reclamacion ante el '
        'Administrador de contrato. Transcurrido el plazo sin reclamacion, la No Conformidad '
        'quedara firme y se incorporara como descuento en los estados de pago del contrato.'
    ),
}


class Command(BaseCommand):
    help = (
        'Crea la demo del vertical Construccion ("VIVEPIOLA Obras"): paquete de vertical con '
        'vocabulario, una obra con subcontratistas, usuarios por rol y catalogo de no '
        'conformidades (incluye hallazgos criticos que detonan paralizacion).'
    )

    def handle(self, *args, **options):
        vertical, _ = Vertical.objects.update_or_create(
            slug='construccion',
            defaults={
                'nombre': 'Construccion',
                'vocabulario': VOCABULARIO_CONSTRUCCION,
                'marco_legal_nombre': 'Contrato de construccion y bases administrativas',
                'marco_legal_texto_notificacion': (
                    'Documento emitido conforme a las clausulas de no conformidades y multas '
                    'del contrato de construccion y sus bases administrativas.'
                ),
                'plazo_descargo_dias_default': 3,
                'plazo_ratificacion_horas_default': 12,
            },
        )

        obra, _ = Condominio.objects.update_or_create(
            nombre='Obra Edificio Vista Norte — Constructora Andes',
            defaults={
                'direccion': 'Av. Los Industriales 4500, Quilicura',
                'rut': '77.888.999-0',
                'vertical': vertical,
                'plazo_descargo_dias': 3,
            },
        )

        sub_electrica, _ = Unidad.objects.get_or_create(condominio=obra, identificador='Electrica Sur SpA')
        sub_moldajes, _ = Unidad.objects.get_or_create(condominio=obra, identificador='Moldajes RM Ltda.')

        responsable, _ = Persona.objects.update_or_create(
            condominio=obra, unidad=sub_electrica, cedula_identidad='21.345.678-9',
            defaults={
                'rol_ocupacion': RolOcupacion.OCUPANTE,
                'nombre_completo': 'Marcos Riquelme (Jefe de terreno, Electrica Sur)',
                'domicilio': 'Instalacion de faena, Obra Vista Norte',
                'correo_electronico': 'contratista.demo@debido.local',
            },
        )
        Persona.objects.update_or_create(
            condominio=obra, unidad=sub_moldajes, cedula_identidad='19.876.543-2',
            defaults={
                'rol_ocupacion': RolOcupacion.OCUPANTE,
                'nombre_completo': 'Paula Fuentes (Jefa de terreno, Moldajes RM)',
                'domicilio': 'Instalacion de faena, Obra Vista Norte',
                'correo_electronico': 'moldajes.demo@debido.local',
            },
        )

        usuarios = [
            ('supervisor', Rol.FISCALIZADOR, None),
            ('admincontrato', Rol.COMITE, None),
            ('oficinatecnica', Rol.ADMINISTRADOR, None),
            ('contratista', Rol.RESIDENTE, responsable),
        ]
        for username, rol, persona in usuarios:
            usuario, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={'rol': rol, 'condominio': obra, 'persona': persona, 'email': f'{username}@debido.local'},
            )
            if creado:
                usuario.set_password('Demo12345')
                usuario.save()

        catalogo = [
            ('SEG-ALT-01', 'Trabajo en altura sin arnes ni linea de vida', 'Clausula 14.2',
             Decimal('15.00'), Gravedad.GRAVISIMA, True, 12),
            ('SEG-ELEC-02', 'Tablero electrico energizado expuesto en zona de transito', 'Clausula 14.3',
             Decimal('10.00'), Gravedad.GRAVE, True, 12),
            ('NC-CAL-03', 'Hormigonado sin liberacion de enfierradura por ITO', 'Clausula 9.5',
             Decimal('25.00'), Gravedad.GRAVE, False, 24),
        ]
        for codigo, desc, articulo, monto, gravedad, contencion, plazo in catalogo:
            InfraccionCatalogo.objects.update_or_create(
                condominio=obra, codigo=codigo,
                defaults={
                    'descripcion': desc,
                    'articulo_referencia': articulo,
                    'monto': monto,
                    'unidad_monto': 'UF',
                    'gravedad': gravedad,
                    'estado': EstadoInfraccion.ACTIVA,
                    'conlleva_contencion': contencion,
                    'plazo_ratificacion_horas': plazo,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            'Demo "VIVEPIOLA Obras" creada. Usuarios: supervisor / admincontrato / oficinatecnica / '
            'contratista (contrasena Demo12345). Misma build, otra piel.'
        ))
