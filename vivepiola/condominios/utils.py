import io

import openpyxl
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import Permanencia, Persona, RolOcupacion, Unidad, VinculoCopropietario

COLUMNAS_PLANTILLA = [
    'unidad', 'rol_ocupacion', 'nombre_completo', 'cedula_identidad',
    'domicilio', 'correo_electronico', 'telefono', 'permanencia', 'vinculo_copropietario',
]

ROLES_VALIDOS = {choice.value for choice in RolOcupacion}
PERMANENCIAS_VALIDAS = {choice.value for choice in Permanencia}
VINCULOS_VALIDOS = {choice.value for choice in VinculoCopropietario}


def generar_plantilla_excel():
    """
    Plantilla .xlsx para el administrador.

    Va sin filas de ejemplo a proposito: una plantilla con datos de muestra
    termina importando personas ficticias al registro. Los ejemplos y las
    reglas viven en la hoja de instrucciones.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Registro Copropietarios'
    ws.append(COLUMNAS_PLANTILLA)
    ws.freeze_panes = 'A2'
    for i, ancho in enumerate([16, 16, 30, 18, 38, 30, 18, 16, 22], start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = ancho
    for celda in ws[1]:
        celda.font = openpyxl.styles.Font(bold=True, color='FFFFFF')
        celda.fill = openpyxl.styles.PatternFill('solid', fgColor='111827')

    guia = wb.create_sheet('Instrucciones')
    for fila in [
        ('COMO LLENAR ESTA PLANILLA', ''),
        ('', ''),
        ('Una fila por PERSONA, no por departamento.', ''),
        ('Si un depto tiene propietario y arrendatario, van dos filas con la misma unidad.', ''),
        ('', ''),
        ('COLUMNA', 'QUE VA / REGLAS'),
        ('unidad', 'Ej: Depto 302, Estacionamiento 12'),
        ('rol_ocupacion', 'Titulo con que ocupa: ' + ', '.join(sorted(ROLES_VALIDOS))),
        ('nombre_completo', 'Nombre y apellidos'),
        ('cedula_identidad', 'RUT con guion. Ej: 12.345.678-9'),
        ('domicilio', 'Direccion de la unidad'),
        ('correo_electronico', 'OBLIGATORIO: es el canal legal de notificacion'),
        ('telefono', 'Opcional. +569XXXXXXXX. Habilita el aviso por WhatsApp'),
        ('permanencia', 'Opcional. PERMANENTE (por defecto) o TRANSITORIO (hospedaje temporal)'),
        ('vinculo_copropietario', 'Opcional. CONYUGE, CONVIVIENTE_CIVIL o FAMILIAR'),
        ('', ''),
        ('QUIEN PAGA', ''),
        ('El PROPIETARIO es el obligado al pago ante la comunidad.', ''),
        ('Si multan al arrendatario, el cargo igual se emite a nombre del dueño de la unidad.', ''),
        ('Por eso cada unidad deberia tener su propietario registrado.', ''),
        ('', ''),
        ('ERRORES QUE RECHAZAN LA FILA', ''),
        ('Correo vacio o mal escrito', 'Sin correo no se puede notificar y la multa queda bloqueada'),
        ('rol_ocupacion fuera de la lista', 'En mayusculas y sin acentos'),
        ('Falta nombre, cedula, domicilio o unidad', 'Todos obligatorios'),
        ('', ''),
        ('El sistema valida fila por fila: importa las correctas e informa cuales fallaron.', ''),
        ('Puedes volver a subir el archivo corregido: las personas ya cargadas se actualizan.', ''),
    ]:
        guia.append(list(fila))
    guia.column_dimensions['A'].width = 62
    guia.column_dimensions['B'].width = 62
    for numero in (1, 6, 17, 22):
        guia.cell(row=numero, column=1).font = openpyxl.styles.Font(bold=True)
        guia.cell(row=numero, column=2).font = openpyxl.styles.Font(bold=True)

    wb.active = 0
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _leer_filas(archivo):
    """Soporta .xlsx y .csv; devuelve lista de dicts normalizados por encabezado."""
    nombre = archivo.name.lower()
    if nombre.endswith('.csv'):
        import csv
        texto = archivo.read().decode('utf-8-sig')
        lector = csv.DictReader(io.StringIO(texto))
        filas = [
            {(k or '').strip().lower(): (v or '').strip() for k, v in fila.items()}
            for fila in lector
        ]
        return filas

    wb = openpyxl.load_workbook(archivo, data_only=True)
    ws = wb.active
    filas_raw = list(ws.iter_rows(values_only=True))
    if not filas_raw:
        return []
    encabezados = [str(c).strip().lower() if c else '' for c in filas_raw[0]]
    filas = []
    for fila in filas_raw[1:]:
        if all(c is None or str(c).strip() == '' for c in fila):
            continue
        registro = {encabezados[i]: (str(fila[i]).strip() if fila[i] is not None else '') for i in range(len(encabezados))}
        filas.append(registro)
    return filas


def importar_registro_copropietarios(condominio, archivo):
    """
    Procesa el archivo subido, validando cada fila de forma independiente.
    Devuelve (filas_totales, filas_ok, filas_error, detalle_errores).
    """
    filas = _leer_filas(archivo)
    filas_ok = 0
    detalle_errores = []

    for numero, fila in enumerate(filas, start=2):
        errores_fila = []

        unidad_id = (fila.get('unidad') or '').strip()
        rol = (fila.get('rol_ocupacion') or fila.get('rol') or '').strip().upper()
        nombre = (fila.get('nombre_completo') or fila.get('nombre') or '').strip()
        cedula = (fila.get('cedula_identidad') or fila.get('cedula') or '').strip()
        domicilio = (fila.get('domicilio') or '').strip()
        correo = (fila.get('correo_electronico') or fila.get('correo') or fila.get('email') or '').strip()
        telefono = (fila.get('telefono') or '').strip()
        # Columnas opcionales: si vienen vacias se asume permanencia y sin vinculo.
        permanencia = (fila.get('permanencia') or '').strip().upper() or Permanencia.PERMANENTE
        vinculo = (fila.get('vinculo_copropietario') or fila.get('vinculo') or '').strip().upper()

        if not unidad_id:
            errores_fila.append('unidad vacia')
        if rol not in ROLES_VALIDOS:
            errores_fila.append(
                f"rol_ocupacion invalido: '{rol}' (use {', '.join(sorted(ROLES_VALIDOS))})"
            )
        if permanencia not in PERMANENCIAS_VALIDAS:
            errores_fila.append(
                f"permanencia invalida: '{permanencia}' (use PERMANENTE o TRANSITORIO)"
            )
        if vinculo and vinculo not in VINCULOS_VALIDOS:
            errores_fila.append(
                f"vinculo_copropietario invalido: '{vinculo}' (use CONYUGE, CONVIVIENTE_CIVIL o FAMILIAR)"
            )
        if not nombre:
            errores_fila.append('nombre_completo vacio')
        if not cedula:
            errores_fila.append('cedula_identidad vacia')
        if not domicilio:
            errores_fila.append('domicilio vacio')
        if not correo:
            errores_fila.append('correo_electronico vacio')
        else:
            try:
                validate_email(correo)
            except ValidationError:
                errores_fila.append(f"correo_electronico invalido: '{correo}'")

        if errores_fila:
            detalle_errores.append({'fila': numero, 'errores': errores_fila})
            continue

        unidad, _ = Unidad.objects.get_or_create(condominio=condominio, identificador=unidad_id)
        Persona.objects.update_or_create(
            condominio=condominio,
            unidad=unidad,
            cedula_identidad=cedula,
            defaults={
                'rol_ocupacion': rol,
                'permanencia': permanencia,
                'vinculo_copropietario': vinculo,
                'nombre_completo': nombre,
                'domicilio': domicilio,
                'correo_electronico': correo,
                'telefono': telefono,
                'activo': True,
            },
        )
        filas_ok += 1

    return len(filas), filas_ok, len(detalle_errores), detalle_errores
