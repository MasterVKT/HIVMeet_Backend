"""Add the chronological global-message-deletion marker."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0003_message_idempotency_and_unread_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='is_deleted_for_everyone',
            field=models.BooleanField(default=False, verbose_name='Deleted for everyone'),
        ),
        migrations.AddField(
            model_name='message',
            name='deleted_for_everyone_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Deleted for everyone at'),
        ),
    ]
