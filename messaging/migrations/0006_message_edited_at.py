"""Add the server-authoritative timestamp for Premium text edits."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0005_message_media_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Edited at'),
        ),
    ]
