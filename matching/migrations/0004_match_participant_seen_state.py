# Generated for Phase 5 — participant-specific match badges.

from django.db import migrations, models
from django.db.models import F


def mark_existing_matches_seen(apps, schema_editor):
    """Do not turn every established match into a new badge on rollout."""
    Match = apps.get_model('matching', 'Match')
    # Keep write locks short for established installations. The migration is
    # non-atomic so each small update can commit before selecting the next
    # batch; rerunning after an interruption is safe because nulls only are
    # selected.
    for field in ('user1_seen_at', 'user2_seen_at'):
        while True:
            ids = list(
                Match.objects.filter(**{f'{field}__isnull': True})
                .order_by('pk')
                .values_list('pk', flat=True)[:1000]
            )
            if not ids:
                break
            Match.objects.filter(pk__in=ids).update(**{field: F('created_at')})


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('matching', '0003_free_match_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='user1_seen_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='User 1 seen at'),
        ),
        migrations.AddField(
            model_name='match',
            name='user2_seen_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='User 2 seen at'),
        ),
        migrations.RunPython(mark_existing_matches_seen, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='match',
            index=models.Index(
                fields=['user1', 'status', 'user1_seen_at'],
                name='match_u1_status_seen_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='match',
            index=models.Index(
                fields=['user2', 'status', 'user2_seen_at'],
                name='match_u2_status_seen_idx',
            ),
        ),
    ]
