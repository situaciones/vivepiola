"""
Triggers de inmutabilidad para ActaSellada (segundo anillo de defensa).

El primer anillo es la aplicacion (no expone UPDATE); este anillo aborta a
nivel de motor cualquier UPDATE/DELETE, incluso lanzado por consola o por un
ORM futuro. El tercer anillo (produccion) es un usuario de conexion con solo
INSERT/SELECT sobre esta tabla y el anclaje externo del hash-raiz.

El abort es especifico del motor (MySQL usa SIGNAL, SQLite usa RAISE), por eso
se emite segun el vendor de la conexion: asi la misma garantia rige en la base
de produccion y en la base efimera de la suite de pruebas.
"""

from django.db import migrations

MENSAJE_UPDATE = 'ActaSellada es inmutable: UPDATE bloqueado por trigger'
MENSAJE_DELETE = 'ActaSellada es inmutable: DELETE bloqueado por trigger'

SQL_POR_VENDOR = {
    'mysql': [
        f"""CREATE TRIGGER acta_sellada_bloquear_update
BEFORE UPDATE ON multas_actasellada
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '{MENSAJE_UPDATE}'""",
        f"""CREATE TRIGGER acta_sellada_bloquear_delete
BEFORE DELETE ON multas_actasellada
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '{MENSAJE_DELETE}'""",
    ],
    'sqlite': [
        f"""CREATE TRIGGER acta_sellada_bloquear_update
BEFORE UPDATE ON multas_actasellada
BEGIN SELECT RAISE(ABORT, '{MENSAJE_UPDATE}'); END""",
        f"""CREATE TRIGGER acta_sellada_bloquear_delete
BEFORE DELETE ON multas_actasellada
BEGIN SELECT RAISE(ABORT, '{MENSAJE_DELETE}'); END""",
    ],
}

SQL_ELIMINAR = [
    'DROP TRIGGER IF EXISTS acta_sellada_bloquear_update',
    'DROP TRIGGER IF EXISTS acta_sellada_bloquear_delete',
]


def crear_triggers(apps, schema_editor):
    sentencias = SQL_POR_VENDOR.get(schema_editor.connection.vendor)
    if not sentencias:
        return  # motor sin soporte declarado: queda solo el anillo de aplicacion
    with schema_editor.connection.cursor() as cursor:
        for sentencia in sentencias:
            cursor.execute(sentencia)


def eliminar_triggers(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for sentencia in SQL_ELIMINAR:
            cursor.execute(sentencia)


class Migration(migrations.Migration):

    dependencies = [
        ('multas', '0003_evidenciafoto_anclaje_fisico_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_triggers, eliminar_triggers),
    ]
