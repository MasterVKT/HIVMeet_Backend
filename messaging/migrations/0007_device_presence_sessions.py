# Server-authoritative, per-device presence sessions.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('messaging', '0006_message_edited_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='DevicePresenceSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_id', models.CharField(max_length=180, verbose_name='Session ID')),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('last_heartbeat_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('disconnected_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='presence_sessions', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={'db_table': 'device_presence_sessions'},
        ),
        migrations.AddConstraint(
            model_name='devicepresencesession',
            constraint=models.UniqueConstraint(fields=('user', 'session_id'), name='unique_device_presence_session'),
        ),
        migrations.AddIndex(
            model_name='devicepresencesession',
            index=models.Index(fields=['user', 'disconnected_at', 'last_heartbeat_at'], name='presence_user_active_idx'),
        ),
    ]
