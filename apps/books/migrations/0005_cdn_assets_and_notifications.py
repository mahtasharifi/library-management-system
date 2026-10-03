import os
from urllib.parse import quote

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


CDN_LIBRARY_URL = "https://legacy-files.example.com/library/"


def migrate_legacy_asset_urls(apps, schema_editor):
    Book = apps.get_model('books', 'Book')
    for book in Book.objects.all().iterator():
        cover_value = str(book.cover or '').strip()
        pdf_value = str(book.download_link or book.book_file or '').strip()

        if cover_value:
            book.cover_url = (
                cover_value
                if cover_value.startswith(('http://', 'https://'))
                else f"{CDN_LIBRARY_URL}/Cover/{quote(os.path.basename(cover_value))}"
            )
        if pdf_value:
            book.pdf_url = (
                pdf_value
                if pdf_value.startswith(('http://', 'https://'))
                else f"{CDN_LIBRARY_URL}/PDF/{quote(os.path.basename(pdf_value))}"
            )
        book.save(update_fields=['cover_url', 'pdf_url'])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('books', '0004_category_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='cover_url',
            field=models.URLField(blank=True, max_length=1000, null=True, verbose_name='لینک جلد در CDN'),
        ),
        migrations.AddField(
            model_name='book',
            name='pdf_url',
            field=models.URLField(blank=True, max_length=1000, null=True, verbose_name='لینک فایل PDF در CDN'),
        ),
        migrations.AddField(
            model_name='bookrequest',
            name='admin_read_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان مشاهده مدیر'),
        ),
        migrations.AddField(
            model_name='bookrequest',
            name='admin_response',
            field=models.TextField(blank=True, null=True, verbose_name='پاسخ مدیر'),
        ),
        migrations.AddField(
            model_name='bookrequest',
            name='responded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان پاسخ'),
        ),
        migrations.AddField(
            model_name='bookrequest',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='digital_book_requests', to=settings.AUTH_USER_MODEL, verbose_name='کاربر'),
        ),
        migrations.AddField(
            model_name='message',
            name='admin_read_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان مشاهده مدیر'),
        ),
        migrations.AddField(
            model_name='message',
            name='admin_response',
            field=models.TextField(blank=True, null=True, verbose_name='پاسخ مدیر'),
        ),
        migrations.AddField(
            model_name='message',
            name='responded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان پاسخ'),
        ),
        migrations.AddField(
            model_name='message',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='library_messages', to=settings.AUTH_USER_MODEL, verbose_name='کاربر'),
        ),
        migrations.AddField(
            model_name='physicalbookrequest',
            name='admin_read_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان مشاهده مدیر'),
        ),
        migrations.AddField(
            model_name='physicalbookrequest',
            name='admin_response',
            field=models.TextField(blank=True, null=True, verbose_name='پاسخ مدیر'),
        ),
        migrations.AddField(
            model_name='physicalbookrequest',
            name='responded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان پاسخ'),
        ),
        migrations.AddField(
            model_name='physicalbookrequest',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='physical_book_requests', to=settings.AUTH_USER_MODEL, verbose_name='کاربر'),
        ),
        migrations.CreateModel(
            name='UserNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('read', 'مشاهده شد'), ('answered', 'پاسخ داده شد'), ('approved', 'تأیید شد'), ('rejected', 'رد شد'), ('info', 'اطلاع‌رسانی')], default='info', max_length=20, verbose_name='نوع اعلان')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان')),
                ('message', models.TextField(verbose_name='متن اعلان')),
                ('related_type', models.CharField(blank=True, max_length=40, verbose_name='نوع رکورد مرتبط')),
                ('related_id', models.PositiveBigIntegerField(blank=True, null=True, verbose_name='شناسه رکورد مرتبط')),
                ('is_read', models.BooleanField(default=False, verbose_name='خوانده شده توسط کاربر')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='library_notifications', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'اعلان کاربر',
                'verbose_name_plural': 'اعلان‌های کاربران',
                'ordering': ['-created_at'],
            },
        ),
        migrations.RunPython(migrate_legacy_asset_urls, migrations.RunPython.noop),
        migrations.RemoveField(model_name='category', name='description'),
        migrations.RemoveField(model_name='book', name='book_file'),
        migrations.RemoveField(model_name='book', name='cover'),
        migrations.RemoveField(model_name='book', name='download_link'),
        migrations.RemoveField(model_name='book', name='has_pdf'),
        migrations.RemoveField(model_name='book', name='has_physical'),
        migrations.AlterField(
            model_name='book',
            name='physical_available',
            field=models.PositiveIntegerField(default=0, verbose_name='تعداد موجود'),
        ),
        migrations.AlterField(
            model_name='book',
            name='physical_count',
            field=models.PositiveIntegerField(default=0, verbose_name='تعداد کل نسخه فیزیکی'),
        ),
    ]
