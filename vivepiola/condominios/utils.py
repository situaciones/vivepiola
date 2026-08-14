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
    # Los titulos se marcan con TITULO en vez de por numero de fila: la lista
    # de indices fijos que habia antes ponia negrita en la linea equivocada
    # apenas se agregaba un renglon en el medio.
    TITULO = object()
    for fila in [
        (TITULO, 'COMO LLENAR ESTA PLANILLA', ''),
        (None, '', ''),
        (None, 'Una fila por PERSONA, no por departamento.', ''),
        (None, 'Si un depto tiene propietario y arrendatario, van dos filas con la misma unidad.', ''),
        (None, '', ''),
        (TITULO, 'COLUMNA', 'QUE VA / REGLAS'),
        (None, 'unidad', 'Ej: Depto 302, Estacionamiento 12'),
        (None, 'rol_ocupacion', 'Titulo con que ocupa: ' + ', '.join(sorted(ROLES_VALIDOS))),
        (None, 'nombre_completo', 'Nombre y apellidos'),
        (None, 'cedula_identidad', 'RUT con guion. Ej: 12.345.678-9'),
        (None, 'domicilio', 'Direccion de la unidad'),
        (None, 'correo_electronico', 'OBLIGATORIO: es el canal legal de notificacion'),
        (None, 'telefono', 'Opcional. +569XXXXXXXX. Habilita el aviso por WhatsApp'),
        (None, 'permanencia',
         'Opcional. PERMANENTE (por defecto) o TRANSITORIO (hospedaje temporal, estadia corta). '
         'Marcar TRANSITORIO hace que la notificacion se copie al propietario.'),
        (None, 'vinculo_copropietario',
         'Opcional. CONYUGE, CONVIVIENTE_CIVIL o FAMILIAR. Si ocupa por vinculo con el dueño, '
         'la notificacion tambien se le copia a el.'),
        (None, '', ''),
        (TITULO, 'QUIEN PAGA', ''),
        (None, 'El PROPIETARIO es el obligado al pago ante la comunidad.', ''),
        (None, 'Si multan al arrendatario, el cargo igual se emite a nombre del dueño de la unidad.', ''),
        (None, 'Por eso cada unidad deberia tener su propietario registrado.', ''),
        (None, '', ''),
        (TITULO, 'A QUIEN LE LLEGA LA NOTIFICACION', ''),
        (None, 'La notificacion legal va al correo del infractor. Ademas se copia al propietario cuando:', ''),
        (None, '   - la persona es TRANSITORIO: puede haberse ido antes de que venza el plazo de descargo.', ''),
        (None, '   - la persona ocupa por vinculo con el dueño (conyuge, conviviente civil, familiar).', ''),
        (None, 'En los demas casos no se copia a nadie mas.', ''),
        (None, 'Por eso conviene llenar estas dos columnas: son las que definen a quien le llega.', ''),
        (None, '', ''),
        (TITULO, 'ERRORES QUE RECHAZAN LA FILA', ''),
        (None, 'Correo vacio o mal escrito', 'Sin correo no se puede notificar y la multa queda bloqueada'),
        (None, 'rol_ocupacion fuera de la lista', 'En mayusculas y sin acentos'),
        (None, 'Falta nombre, cedula, domicilio o unidad', 'Todos obligatorios'),
        (None, '', ''),
        (None, 'El sistema valida fila por fila: importa las correctas e informa cuales fallaron.', ''),
        (None, 'Puedes volver a subir el archivo corregido: las personas ya cargadas se actualizan.', ''),
    ]:
        marca, columna_a, columna_b = fila
        guia.append([columna_a, columna_b])
        if marca is TITULO:
            for celda in guia[guia.max_row]:
                celda.font = openpyxl.styles.Font(bold=True)
    guia.column_dimensions['A'].width = 62
    guia.column_dimensions['B'].width = 62

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


# Nombre interno -> encabezados aceptados, en orden de preferencia. Los alias
# existen porque el administrador rara vez usa la plantilla tal cual: renombra
# "correo_electronico" a "correo", "cedula_identidad" a "cedula", etc.
ALIAS_COLUMNAS = {
    'unidad': ('unidad',),
    'rol_ocupacion': ('rol_ocupacion', 'rol'),
    'nombre_completo': ('nombre_completo', 'nombre'),
    'cedula_identidad': ('cedula_identidad', 'cedula'),
    'domicilio': ('domicilio',),
    'correo_electronico': ('correo_electronico', 'correo', 'email'),
    'telefono': ('telefono',),
    'permanencia': ('permanencia',),
    'vinculo_copropietario': ('vinculo_copropietario', 'vinculo'),
}

# Se guardan en mayusculas porque son codigos, no texto libre.
CAMPOS_EN_MAYUSCULAS = ('rol_ocupacion', 'permanencia', 'vinculo_copropietario')


def _campos_de_fila(fila):
    """Extrae los campos de una fila cruda, resolviendo alias de encabezado."""
    campos = {}
    for campo, encabezados in ALIAS_COLUMNAS.items():
        valor = ''
        for encabezado in encabezados:
            valor = (fila.get(encabezado) or '').strip()
            if valor:
                break
        campos[campo] = valor.upper() if campo in CAMPOS_EN_MAYUSCULAS else valor

    # Columnas opcionales: vacias significan permanente y sin vinculo declarado.
    campos['permanencia'] = campos['permanencia'] or Permanencia.PERMANENTE
    return campos


def _errores_de_fila(campos):
    """
    Devuelve todos los problemas de una fila, no solo el primero: el
    administrador corrige el archivo una vez y no de a un error por vez.
    """
    errores = []

    for campo, mensaje in (
        ('unidad', 'unidad vacia'),
        ('nombre_completo', 'nombre_completo vacio'),
        ('cedula_identidad', 'cedula_identidad vacia'),
        ('domicilio', 'domicilio vacio'),
    ):
        if not campos[campo]:
            errores.append(mensaje)

    if campos['rol_ocupacion'] not in ROLES_VALIDOS:
        errores.append(
            f"rol_ocupacion invalido: '{campos['rol_ocupacion']}' "
            f"(use {', '.join(sorted(ROLES_VALIDOS))})"
        )
    if campos['permanencia'] not in PERMANENCIAS_VALIDAS:
        errores.append(
            f"permanencia invalida: '{campos['permanencia']}' (use PERMANENTE o TRANSITORIO)"
        )
    if campos['vinculo_copropietario'] and campos['vinculo_copropietario'] not in VINCULOS_VALIDOS:
        errores.append(
            f"vinculo_copropietario invalido: '{campos['vinculo_copropietario']}' "
            f"(use CONYUGE, CONVIVIENTE_CIVIL o FAMILIAR)"
        )

    correo = campos['correo_electronico']
    if not correo:
        errores.append('correo_electronico vacio')
    else:
        try:
            validate_email(correo)
        except ValidationError:
            errores.append(f"correo_electronico invalido: '{correo}'")

    return errores


def _guardar_persona(condominio, campos):
    """Crea o actualiza a la persona. La unidad se crea sola si no existia."""
    unidad, _ = Unidad.objects.get_or_create(
        condominio=condominio, identificador=campos['unidad'],
    )
    Persona.objects.update_or_create(
        condominio=condominio,
        unidad=unidad,
        cedula_identidad=campos['cedula_identidad'],
        defaults={
            'rol_ocupacion': campos['rol_ocupacion'],
            'permanencia': campos['permanencia'],
            'vinculo_copropietario': campos['vinculo_copropietario'],
            'nombre_completo': campos['nombre_completo'],
            'domicilio': campos['domicilio'],
            'correo_electronico': campos['correo_electronico'],
            'telefono': campos['telefono'],
            'activo': True,
        },
    )


def importar_registro_copropietarios(condominio, archivo):
    """
    Procesa el archivo subido, validando cada fila de forma independiente: una
    fila mala nunca impide importar las buenas.

    Devuelve (filas_totales, filas_ok, filas_error, detalle_errores). El numero
    de fila del detalle es el que ve el administrador en Excel, contando el
    encabezado, para que pueda ir directo a corregirla.
    """
    filas = _leer_filas(archivo)
    filas_ok = 0
    detalle_errores = []

    for numero, fila in enumerate(filas, start=2):
        campos = _campos_de_fila(fila)
        errores = _errores_de_fila(campos)
        if errores:
            detalle_errores.append({'fila': numero, 'errores': errores})
            continue
        _guardar_persona(condominio, campos)
        filas_ok += 1

    return len(filas), filas_ok, len(detalle_errores), detalle_errores
