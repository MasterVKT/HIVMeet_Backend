# Additive attachment metadata contract. Existing media rows remain readable.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0004_message_global_deletion'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='media_duration_ms',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Media duration in milliseconds'),
        ),
        migrations.AddField(
            model_name='message',
            name='media_file_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Media file name'),
        ),
        migrations.AddField(
            model_name='message',
            name='media_mime_type',
            field=models.CharField(blank=True, max_length=100, verbose_name='Media MIME type'),
        ),
        migrations.AddField(
            model_name='message',
            name='media_size_bytes',
            field=models.PositiveBigIntegerField(blank=True, null=True, verbose_name='Media size in bytes'),
        ),
    ]
