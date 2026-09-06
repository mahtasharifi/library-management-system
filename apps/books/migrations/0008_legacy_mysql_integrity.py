"""Upgrade legacy MyISAM dump tables to transactional InnoDB with project FKs."""

from django.db import migrations


TABLES = [
    "django_content_type", "auth_permission", "auth_group", "auth_user",
    "auth_group_permissions", "auth_user_groups", "auth_user_user_permissions",
    "django_admin_log", "django_migrations", "django_session",
    "user_profiles", "mfa_credentials", "book_categories", "books",
    "physical_book_borrows", "physical_book_requests", "digital_book_requests",
    "library_messages", "book_questions", "book_comments", "book_ratings", "user_notifications",
]

FOREIGN_KEYS = [
    ("user_profiles", "user_id", "auth_user", "id", "CASCADE", "fk_user_profiles_user"),
    ("mfa_credentials", "user_id", "auth_user", "id", "CASCADE", "fk_mfa_credentials_user"),
    ("book_categories", "parent_id", "book_categories", "id", "SET NULL", "fk_book_categories_parent"),
    ("books", "category_id", "book_categories", "id", "SET NULL", "fk_books_category"),
    ("physical_book_borrows", "book_id", "books", "id", "CASCADE", "fk_borrows_book"),
    ("physical_book_requests", "book_id", "books", "id", "CASCADE", "fk_physical_requests_book"),
    ("physical_book_requests", "user_id", "auth_user", "id", "SET NULL", "fk_physical_requests_user"),
    ("digital_book_requests", "book_id", "books", "id", "CASCADE", "fk_digital_requests_book"),
    ("digital_book_requests", "user_id", "auth_user", "id", "SET NULL", "fk_digital_requests_user"),
    ("library_messages", "user_id", "auth_user", "id", "SET NULL", "fk_library_messages_user"),
    ("book_questions", "book_id", "books", "id", "CASCADE", "fk_questions_book"),
    ("book_comments", "book_id", "books", "id", "CASCADE", "fk_comments_book"),
    ("book_comments", "parent_id", "book_comments", "id", "CASCADE", "fk_comments_parent"),
    ("book_ratings", "book_id", "books", "id", "CASCADE", "fk_ratings_book"),
    ("book_ratings", "user_id", "auth_user", "id", "CASCADE", "fk_ratings_user"),
    ("user_notifications", "user_id", "auth_user", "id", "CASCADE", "fk_notifications_user"),
]

NULLABLE_RELATIONS = [
    ("book_categories", "parent_id", "book_categories"),
    ("books", "category_id", "book_categories"),
    ("physical_book_requests", "user_id", "auth_user"),
    ("digital_book_requests", "user_id", "auth_user"),
    ("library_messages", "user_id", "auth_user"),
    ("book_comments", "parent_id", "book_comments"),
    ("book_ratings", "user_id", "auth_user"),
]

REQUIRED_RELATIONS = [
    ("user_profiles", "user_id", "auth_user"),
    ("mfa_credentials", "user_id", "auth_user"),
    ("physical_book_borrows", "book_id", "books"),
    ("physical_book_requests", "book_id", "books"),
    ("book_questions", "book_id", "books"),
    ("book_comments", "book_id", "books"),
    ("book_ratings", "book_id", "books"),
    ("user_notifications", "user_id", "auth_user"),
]


def _table_exists(cursor, table):
    cursor.execute(
        "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        [table],
    )
    return cursor.fetchone() is not None


def _constraint_exists(cursor, name):
    cursor.execute(
        "SELECT 1 FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_NAME = %s",
        [name],
    )
    return cursor.fetchone() is not None


def upgrade_legacy_mysql_integrity(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    quote = schema_editor.connection.ops.quote_name
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            if _table_exists(cursor, table):
                cursor.execute(f"ALTER TABLE {quote(table)} ENGINE=InnoDB")

        for child, column, parent in NULLABLE_RELATIONS:
            if _table_exists(cursor, child) and _table_exists(cursor, parent):
                cursor.execute(
                    f"UPDATE {quote(child)} c LEFT JOIN {quote(parent)} p ON c.{quote(column)} = p.id "
                    f"SET c.{quote(column)} = NULL WHERE c.{quote(column)} IS NOT NULL AND p.id IS NULL"
                )

        for child, column, parent in REQUIRED_RELATIONS:
            if not (_table_exists(cursor, child) and _table_exists(cursor, parent)):
                continue
            cursor.execute(
                f"SELECT COUNT(*) FROM {quote(child)} c LEFT JOIN {quote(parent)} p "
                f"ON c.{quote(column)} = p.id WHERE p.id IS NULL"
            )
            if cursor.fetchone()[0]:
                raise RuntimeError(f"Legacy database contains orphaned required relation: {child}.{column}")

        for child, column, parent, parent_column, on_delete, name in FOREIGN_KEYS:
            if not (_table_exists(cursor, child) and _table_exists(cursor, parent)) or _constraint_exists(cursor, name):
                continue
            cursor.execute(
                f"ALTER TABLE {quote(child)} ADD CONSTRAINT {quote(name)} "
                f"FOREIGN KEY ({quote(column)}) REFERENCES {quote(parent)} ({quote(parent_column)}) "
                f"ON DELETE {on_delete}"
            )


class Migration(migrations.Migration):
    dependencies = [("books", "0007_remove_book_tags_json_book_tags_and_more"), ("accounts", "0004_alter_userprofile_table_mfacredential")]
    operations = [migrations.RunPython(upgrade_legacy_mysql_integrity, migrations.RunPython.noop)]
