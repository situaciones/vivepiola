"""
Banco de pruebas del clasificador de denuncias.

Pasa un set de reportes tipicos de condominio por el clasificador y muestra
que propone cada uno, con que confianza y por que. Sirve para dos cosas:

  1. Comparar el agente con IA contra el respaldo por terminos (que tanto
     aporta pagar por el modelo).
  2. Calibrar: si el modelo se equivoca seguido, casi siempre el problema
     esta en como estan redactadas las infracciones del catalogo.

Uso:
    manage.py probar_clasificador --sembrar     # crea un catalogo de ejemplo
    manage.py probar_clasificador               # usa el catalogo existente
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from condominios.models import Condominio
from multas.clasificador import clasificar_con_ia, clasificar_por_coincidencia
from reglamentos.models import EstadoInfraccion, Gravedad, InfraccionCatalogo

# Catalogo de ejemplo, redactado como suele venir un reglamento real.
CATALOGO_EJEMPLO = [
    ('RUIDO-01', 'Ruidos molestos que perturben la tranquilidad entre las 22:00 y las 08:00', 'Art. 15', '3', Gravedad.GRAVE),
    ('MASCOTA-01', 'Mascota sin correa o sin supervision en espacios comunes', 'Art. 4', '2', Gravedad.LEVE),
    ('ESTAC-01', 'Uso indebido de estacionamiento de visitas por residentes', 'Art. 22', '2', Gravedad.LEVE),
    ('BASURA-01', 'Disposicion de residuos fuera del horario o del lugar habilitado', 'Art. 18', '1', Gravedad.LEVE),
    ('FACHADA-01', 'Alteracion de fachada o instalaciones exteriores sin autorizacion', 'Art. 9', '5', Gravedad.GRAVISIMA),
    ('COMUNES-01', 'Uso de espacios comunes fuera del horario reglamentario', 'Art. 27', '2', Gravedad.LEVE),
    ('HUMO-01', 'Fumar en espacios comunes cerrados', 'Art. 31', '2', Gravedad.GRAVE),
]

# Casos redactados como los escribe un conserje, NO como los dice el reglamento:
# ahi esta la prueba. 'esperado' es el codigo correcto segun criterio humano.
CASOS = [
    ('El perro del 707 andaba suelto por el pasillo del segundo piso', 'MASCOTA-01'),
    ('Fiesta con musica a todo volumen hasta las 3 de la madrugada', 'RUIDO-01'),
    ('El auto del 302 lleva toda la semana en el espacio para visitas', 'ESTAC-01'),
    ('Dejaron bolsas tiradas en el pasillo a las 11 de la noche', 'BASURA-01'),
    ('Pusieron una reja nueva en el balcon sin avisar a nadie', 'FACHADA-01'),
    ('Un señor estaba con cigarro adentro del ascensor', 'HUMO-01'),
    ('Habia gente en la piscina pasadas las 12 de la noche', 'COMUNES-01'),
    ('Se solicita cambiar la ampolleta quemada del pasillo del piso 3', None),  # no es infraccion
]


class Command(BaseCommand):
    help = 'Corre reportes de ejemplo por el clasificador y muestra que propone cada uno.'

    def add_arguments(self, parser):
        parser.add_argument('--condominio', type=int, help='ID del condominio (por defecto, el primero).')
        parser.add_argument('--sembrar', action='store_true', help='Crea el catalogo de ejemplo si falta.')

    def handle(self, *args, **opciones):
        condominio = (
            Condominio.objects.filter(id=opciones['condominio']).first()
            if opciones.get('condominio') else Condominio.objects.first()
        )
        if condominio is None:
            self.stderr.write('No hay condominios. Corre primero: manage.py seed_demo')
            return

        if opciones['sembrar']:
            creadas = 0
            for codigo, desc, art, monto, gravedad in CATALOGO_EJEMPLO:
                _, nueva = InfraccionCatalogo.objects.get_or_create(
                    condominio=condominio, codigo=codigo,
                    defaults={
                        'descripcion': desc, 'articulo_referencia': art,
                        'monto': Decimal(monto), 'unidad_monto': 'UF',
                        'gravedad': gravedad, 'estado': EstadoInfraccion.ACTIVA,
                    },
                )
                creadas += 1 if nueva else 0
            self.stdout.write(f'Catalogo de ejemplo: {creadas} infracciones nuevas.\n')

        activas = list(InfraccionCatalogo.objects.filter(
            condominio=condominio, estado=EstadoInfraccion.ACTIVA,
        ))
        if not activas:
            self.stderr.write('El condominio no tiene infracciones ACTIVAS. Usa --sembrar.')
            return

        con_ia = bool(settings.ANTHROPIC_API_KEY)
        self.stdout.write(f'Comunidad: {condominio.nombre}')
        self.stdout.write(f'Catalogo activo: {len(activas)} infracciones')
        self.stdout.write(f'Modo: {"AGENTE CON IA + respaldo" if con_ia else "SOLO RESPALDO (sin ANTHROPIC_API_KEY)"}\n')

        aciertos_ia = aciertos_resp = 0
        for descripcion, esperado in CASOS:
            ticket = SimpleNamespace(
                descripcion=descripcion,
                ubicacion='',
                fecha_hecho=timezone.now() - timedelta(hours=1),
                unidad=SimpleNamespace(identificador='Depto 707'),
            )

            resp_inf, resp_conf, _ = clasificar_por_coincidencia(ticket, activas)
            resp_codigo = resp_inf.codigo if resp_inf else None
            resp_ok = resp_codigo == esperado
            aciertos_resp += 1 if resp_ok else 0

            self.stdout.write(f'- "{descripcion}"')
            self.stdout.write(f'   esperado    : {esperado or "ninguna (no es infraccion)"}')
            self.stdout.write(
                f'   respaldo    : {resp_codigo or "ninguna":<12} {"OK" if resp_ok else "FALLA"} (confianza {resp_conf})'
            )

            if con_ia:
                try:
                    ia_inf, ia_conf, ia_fund = clasificar_con_ia(ticket, activas)
                    ia_codigo = ia_inf.codigo if ia_inf else None
                    ia_ok = ia_codigo == esperado
                    aciertos_ia += 1 if ia_ok else 0
                    self.stdout.write(
                        f'   agente IA   : {ia_codigo or "ninguna":<12} {"OK" if ia_ok else "FALLA"} (confianza {ia_conf})'
                    )
                    self.stdout.write(f'   fundamento  : {ia_fund}')
                except Exception as exc:
                    self.stdout.write(f'   agente IA   : ERROR ({exc})')
            self.stdout.write('')

        total = len(CASOS)
        self.stdout.write(f'RESULTADO  respaldo por terminos: {aciertos_resp}/{total}')
        if con_ia:
            self.stdout.write(f'           agente con IA      : {aciertos_ia}/{total}')
        else:
            self.stdout.write(
                '           agente con IA      : no evaluado (configura ANTHROPIC_API_KEY y repite)'
            )
