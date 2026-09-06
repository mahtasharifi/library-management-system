from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0009_background_jobs")]

    operations = [
        migrations.AddField(
            model_name="book",
            name="pdf_storage_path",
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name="مسیر خصوصی PDF"),
        ),
        migrations.AlterField(
            model_name="book",
            name="pdf_url",
            field=models.URLField(blank=True, max_length=1000, null=True, verbose_name="لینک قدیمی PDF"),
        ),
    ]
