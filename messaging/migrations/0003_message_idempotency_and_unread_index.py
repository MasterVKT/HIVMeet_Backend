"""Protect message idempotency and reconcile denormalized unread counters.

The client-id cleanup is intentionally not reversible at the business level:
the original duplicate identifiers cannot be recovered.  A rollback therefore
requires restoring the database snapshot taken before this migration, then
rolling back the application code and schema.
"""

from django.db import migrations, models
from django.db.models import Count, Q


def normalize_duplicate_client_message_ids_and_unread_counts(apps, schema_editor):
    """Make non-empty client IDs unique per match/sender without deleting data."""
    Message = apps.get_model('messaging', 'Message')
    Match = apps.get_model('matching', 'Match')

    duplicate_groups = (
        Message.objects.exclude(client_message_id='')
        .values('match_id', 'sender_id', 'client_message_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
    )
    for group in duplicate_groups.iterator():
        duplicates = Message.objects.filter(
            match_id=group['match_id'],
            sender_id=group['sender_id'],
            client_message_id=group['client_message_id'],
        ).order_by('created_at', 'id')
        # Keep the oldest message's original value.  Later duplicates retain
        # their message data but receive a deterministic, unique legacy value.
        for duplicate in duplicates[1:]:
            duplicate.client_message_id = f'legacy-{duplicate.id}'
            duplicate.save(update_fields=['client_message_id'])

    unread_by_match_and_sender = {
        (row['match_id'], row['sender_id']): row['total']
        for row in (
            Message.objects.filter(status__in=['sent', 'delivered'])
            .values('match_id', 'sender_id')
            .annotate(total=Count('id'))
        )
    }

    pending_updates = []
    for match in Match.objects.all().only('id', 'user1_id', 'user2_id').iterator():
        match.user1_unread_count = unread_by_match_and_sender.get(
            (match.id, match.user2_id), 0
        )
        match.user2_unread_count = unread_by_match_and_sender.get(
            (match.id, match.user1_id), 0
        )
        pending_updates.append(match)
        if len(pending_updates) == 500:
            Match.objects.bulk_update(
                pending_updates,
                ['user1_unread_count', 'user2_unread_count'],
            )
            pending_updates.clear()
    if pending_updates:
        Match.objects.bulk_update(
            pending_updates,
            ['user1_unread_count', 'user2_unread_count'],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0002_conversation_hidden_state'),
    ]

    operations = [
        migrations.RunPython(
            normalize_duplicate_client_message_ids_and_unread_counts,
            migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(
                fields=['match', 'sender', 'status', 'created_at', 'id'],
                name='msg_mtch_sndr_stat_created_id',
            ),
        ),
        migrations.AddConstraint(
            model_name='message',
            constraint=models.UniqueConstraint(
                condition=~Q(client_message_id=''),
                fields=('match', 'sender', 'client_message_id'),
                name='uniq_msg_match_sender_client_id',
            ),
        ),
    ]
