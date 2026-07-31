import csv
import io

from django.core.files.base import ContentFile
from django.db import transaction

from multas.models import EstadoMulta, Multa

from .models import CargoGastoComun, LoteExportacion


@transaction.atomic
def exportar_multas_firmes(condominio, periodo, usuario):
    """
    Toma todas las multas FIRME del condominio que aun no han sido exportadas
    y las agrupa en un lote de gastos comunes (CSV), marcandolas EXPORTADA.
    Solo procede sobre multas sin apelaciones/descargos pendientes.
    """
    multas_firmes = Multa.objects.filter(condominio=condominio, estado=EstadoMulta.FIRME)

    if not multas_firmes.exists():
        return None

    lote, _ = LoteExportacion.objects.get_or_create(
        condominio=condominio, periodo=periodo, defaults={'generado_por': usuario},
    )

    for multa in multas_firmes:
        descripcion = f'Multa #{multa.id} - {multa.infraccion.descripcion if multa.infraccion else ""}'
        CargoGastoComun.objects.create(
            lote=lote, multa=multa, unidad=multa.unidad, monto=multa.monto, descripcion=descripcion,
        )
        multa.estado = EstadoMulta.EXPORTADA
        multa.save(update_fields=['estado'])

    # El CSV se regenera con TODOS los cargos del lote: si el administrador
    # exporta dos veces en el mismo periodo, el archivo debe seguir completo.
    cargos = lote.cargos.select_related('unidad', 'multa__persona_infractor').all()
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    # El cobro va a nombre del PROPIETARIO: la Ley 21.442 lo hace obligado
    # principal al pago aunque el infractor haya sido quien ocupa la unidad.
    # El infractor se conserva aparte para que el cargo sea explicable.
    escritor.writerow([
        'unidad', 'obligado_al_pago', 'cedula_obligado',
        'infractor', 'cedula_infractor', 'concepto', 'monto', 'multa_id',
    ])
    total = 0
    for cargo in cargos:
        infractor = cargo.multa.persona_infractor
        obligado = cargo.unidad.propietario or infractor  # sin dueño en el registro, responde el infractor
        escritor.writerow([
            cargo.unidad.identificador,
            obligado.nombre_completo if obligado else '',
            obligado.cedula_identidad if obligado else '',
            infractor.nombre_completo if infractor else '',
            infractor.cedula_identidad if infractor else '',
            cargo.descripcion,
            cargo.monto,
            cargo.multa_id,
        ])
        total += cargo.monto

    lote.total_monto = total
    lote.archivo_csv.save(
        f'gastos_comunes_{condominio.id}_{periodo}.csv',
        ContentFile(buffer.getvalue().encode('utf-8-sig')),
        save=False,
    )
    lote.save()
    return lote
