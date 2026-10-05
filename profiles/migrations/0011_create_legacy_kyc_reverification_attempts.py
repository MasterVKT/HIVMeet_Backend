from django.db import migrations


def create_legacy_reverification_attempts(apps, schema_editor):
    """Create non-verifying attempts without trusting legacy document paths."""
    Verification = apps.get_model('profiles', 'Verification')
    KycAttempt = apps.get_model('profiles', 'KycAttempt')

    for verification in Verification.objects.all().only('user_id').iterator():
        KycAttempt.objects.get_or_create(
            user_id=verification.user_id,
            is_open=True,
            defaults={
                'status': 'not_started',
                'origin': 'legacy_projection',
                'consent_version': '',
                'challenge_hash': '',
                'challenge_nonce': '',
                'challenge_idempotency_key': '',
            },
        )


def reverse_legacy_reverification_attempts(apps, schema_editor):
    """Remove only untouched migration-owned attempts on a controlled rollback."""
    KycAttempt = apps.get_model('profiles', 'KycAttempt')
    KycAttempt.objects.filter(
        origin='legacy_projection',
        status='not_started',
        consent_version='',
        challenge_hash='',
        challenge_nonce='',
        challenge_idempotency_key='',
        submitted_at__isnull=True,
        reviewed_at__isnull=True,
        expires_at__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0010_kycattempt_kycauditevent_kycdocument_kycuploadintent_and_more'),
    ]

    operations = [
        migrations.RunPython(
            create_legacy_reverification_attempts,
            reverse_legacy_reverification_attempts,
        ),
    ]
