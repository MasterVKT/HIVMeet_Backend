from django.db import migrations, models
from django.db.models import Count, Q


def require_reconciled_interactions(apps, schema_editor):
    InteractionHistory = apps.get_model('matching', 'InteractionHistory')
    active_rewound = InteractionHistory.objects.filter(
        is_revoked=False,
        rewound_at__isnull=False,
    ).count()
    duplicate_pairs = (
        InteractionHistory.objects.filter(is_revoked=False)
        .values('user_id', 'target_user_id')
        .annotate(active_count=Count('id'))
        .filter(active_count__gt=1)
        .count()
    )
    if active_rewound or duplicate_pairs:
        raise RuntimeError(
            'Interaction history has not been reconciled. Apply migration 0005, '
            'run reconcile_interaction_history --dry-run and --apply with a private '
            'report, then retry migration 0006. '
            f'active_rewound={active_rewound}, duplicate_pairs={duplicate_pairs}.'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('matching', '0005_interaction_rewound_at'),
    ]

    operations = [
        migrations.RunPython(require_reconciled_interactions, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='interactionhistory',
            name='unique_active_interaction',
        ),
        migrations.AddConstraint(
            model_name='interactionhistory',
            constraint=models.UniqueConstraint(
                condition=Q(is_revoked=False),
                fields=('user', 'target_user'),
                name='unique_active_interaction_pair',
            ),
        ),
    ]

