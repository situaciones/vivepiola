import io

import openpyxl
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import Persona, RolOcupacion, Unidad

COLUMNAS_PLANTILLA = [
    'unidad', 'rol_ocupacion', 'nombre_completo', 'cedula_identidad',
    'domicilio', 'correo_electronico', 'telefono',
]

ROLES_VALIDOS = {choice.value for choice in RolOcupacion}


def generar_plantilla_excel():
    """Genera el archivo .xlsx de plantilla que el administrador debe completar."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Registro Copropietarios'
    ws.append(COLUMNAS_PLANTILLA)
    ws.append([
        'Depto 302', 'PROPIETARIO', 'Juana Perez Soto', '12.345.678-9',
        'Depto 302, Av. Siempre Viva 123', 'juana.perez@correo.cl', '+56912345678',
    ])
    ws.append([
        'Depto 302', 'ARRENDATARIO', 'Pedro Soto Rojas', '9.876.543-2',
        'Depto 302, Av. Siempre Viva 123', 'pedro.soto@correo.cl', '',
    ])
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

        if not unidad_id:
            errores_fila.append('unidad vacia')
        if rol not in ROLES_VALIDOS:
            errores_fila.append(f"rol_ocupacion invalido: '{rol}' (use PROPIETARIO, ARRENDATARIO u OCUPANTE)")
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
                'nombre_completo': nombre,
                'domicilio': domicilio,
                'correo_electronico': correo,
                'telefono': telefono,
                'activo': True,
            },
        )
        filas_ok += 1

    return len(filas), filas_ok, len(detalle_errores), detalle_errores
