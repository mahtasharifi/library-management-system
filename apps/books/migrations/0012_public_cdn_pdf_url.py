from django.db import migrations, models


def clear_non_url_legacy_values(apps, schema_editor):
    Book = apps.get_model("books", "Book")
    Book.objects.exclude(pdf_url__startswith="http://").exclude(
        pdf_url__startswith="https://"
    ).update(pdf_url=None)


class Migration(migrations.Migration):
    dependencies = [("books", "0011_remove_book_pdf_url")]

    operations = [
        migrations.RenameField(
            model_name="book",
            old_name="pdf_storage_path",
            new_name="pdf_url",
        ),
        migrations.AlterField(
            model_name="book",
            name="pdf_url",
            field=models.URLField(
                blank=True,
                max_length=1000,
                null=True,
                verbose_name="لینک PDF در CDN",
            ),
        ),
        migrations.RunPython(clear_non_url_legacy_values, migrations.RunPython.noop),
    ]
