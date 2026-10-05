# Distinguish idempotent rewinds from ordinary interaction-history revocations.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0004_match_participant_seen_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='interactionhistory',
            name='rewound_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Rewound at'),
        ),
    ]
