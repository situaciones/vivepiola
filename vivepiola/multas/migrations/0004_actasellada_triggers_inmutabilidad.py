"""
Triggers de inmutabilidad para ActaSellada (segundo anillo de defensa).

El primer anillo es la aplicacion (no expone UPDATE); este anillo aborta a
nivel de motor cualquier UPDATE/DELETE, incluso lanzado por consola o por un
ORM futuro. El tercer anillo (produccion) es un usuario de conexion con solo
INSERT/SELECT sobre esta tabla y el anclaje externo del hash-raiz.
"""

from django.db import migrations


SQL_CREAR = """
CREATE TRIGGER acta_sellada_bloquear_update
BEFORE UPDATE ON multas_actasellada
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ActaSellada es inmutable: UPDATE bloqueado por trigger';
;;
CREATE TRIGGER acta_sellada_bloquear_delete
BEFORE DELETE ON multas_actasellada
FOR EACH ROW
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ActaSellada es inmutable: DELETE bloqueado por trigger';
"""

SQL_ELIMINAR = """
DROP TRIGGER IF EXISTS acta_sellada_bloquear_update;
DROP TRIGGER IF EXISTS acta_sellada_bloquear_delete;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('multas', '0003_evidenciafoto_anclaje_fisico_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[s.strip() for s in SQL_CREAR.split(';;')],
            reverse_sql=SQL_ELIMINAR,
        ),
    ]
