from django.db import migrations, models
import apps.accounts.models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_alter_userprofile_options_alter_userprofile_avatar_and_more")]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="avatar",
            field=models.ImageField(blank=True, null=True, upload_to=apps.accounts.models.avatar_upload_path, verbose_name="تصویر پروفایل"),
        ),
    ]
