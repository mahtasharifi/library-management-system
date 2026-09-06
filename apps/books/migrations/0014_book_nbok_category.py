from django.db import migrations, models
import django.db.models.deletion


def _column_names(connection, cursor, table_name):
    return {
        column.name
        for column in connection.introspection.get_table_description(cursor, table_name)
    }


def add_nbok_book_columns(apps, schema_editor):
    """Add NBOK columns without a physical FK constraint.

    The production database originated from a legacy MySQL schema.  Some
    installations reject a new cross-table FK even though the ORM relation is
    valid.  Keep the Django relation, but make the database change deliberately
    constraint-free and idempotent so a retry after a failed ALTER TABLE is safe.
    """
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    table = "books"

    with connection.cursor() as cursor:
        columns = _column_names(connection, cursor, table)

    if "nbok_category_id" not in columns:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} ADD COLUMN {quote('nbok_category_id')} BIGINT NULL"
        )

    if "nbok_category_level" not in columns:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} ADD COLUMN {quote('nbok_category_level')} VARCHAR(2) NULL"
        )


def remove_nbok_book_columns(apps, schema_editor):
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    table = "books"

    with connection.cursor() as cursor:
        columns = _column_names(connection, cursor, table)

    # Drop level first; neither column has a physical FK constraint in this migration.
    if "nbok_category_level" in columns:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} DROP COLUMN {quote('nbok_category_level')}"
        )

    with connection.cursor() as cursor:
        columns = _column_names(connection, cursor, table)

    if "nbok_category_id" in columns:
        schema_editor.execute(
            f"ALTER TABLE {quote(table)} DROP COLUMN {quote('nbok_category_id')}"
        )


class Migration(migrations.Migration):
    dependencies = [("books", "0013_nbok")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_nbok_book_columns, remove_nbok_book_columns),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="book",
                    name="nbok_category",
                    field=models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="books",
                        to="books.nbokentry",
                        verbose_name="دسته‌بندی",
                    ),
                ),
                migrations.AddField(
                    model_name="book",
                    name="nbok_category_level",
                    field=models.CharField(blank=True, max_length=2, null=True),
                ),
            ],
        ),
    ]
