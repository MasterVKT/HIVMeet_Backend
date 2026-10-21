# Generated manually from Django's checked migration plan on 2026-10-05.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def create_kyc_review_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ('kyc_reviewer', 'kyc_supervisor'):
        Group.objects.get_or_create(name=name)


def remove_kyc_review_groups(apps, schema_editor):
    # Do not delete a group during rollback: it may have acquired operators or
    # permissions after the migration ran.  The schema is still reversible;
    # group deprovisioning belongs to the explicit operational runbook.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0013_phase2_legacy_photo_cutover'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KycReviewAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('attempt', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review_assignment', to='profiles.kycattempt')),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='kyc_review_cases', to=settings.AUTH_USER_MODEL)),
                ('supervisor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='kyc_supervised_review_cases', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_review_assignments'},
        ),
        migrations.CreateModel(
            name='KycReviewDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('decision', models.CharField(choices=[('verified', 'Verified'), ('rejected', 'Rejected'), ('revoked', 'Revoked')], max_length=12)),
                ('reason_code', models.CharField(max_length=80)),
                ('internal_comment_ciphertext', models.TextField(blank=True)),
                ('idempotency_fingerprint', models.CharField(max_length=80, unique=True)),
                ('request_fingerprint', models.CharField(max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='decisions', to='profiles.kycreviewassignment')),
                ('attempt', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='review_decision', to='profiles.kycattempt')),
                ('decided_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='kyc_review_decisions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_review_decisions'},
        ),
        migrations.CreateModel(
            name='KycReviewerMfaAssertion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token_hash', models.CharField(max_length=256)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_reviewer_mfa_assertions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_reviewer_mfa_assertions'},
        ),
        migrations.CreateModel(
            name='KycReviewerMfaDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('secret_ciphertext', models.CharField(max_length=512)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('last_totp_counter', models.BigIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_reviewer_mfa_device', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_reviewer_mfa_devices'},
        ),
        migrations.AddIndex(model_name='kycreviewassignment', index=models.Index(fields=['reviewer', 'closed_at'], name='kyc_review__reviewe_4b2872_idx')),
        migrations.AddIndex(model_name='kycreviewassignment', index=models.Index(fields=['supervisor', 'closed_at'], name='kyc_review__supervi_42b7d5_idx')),
        migrations.AddIndex(model_name='kycreviewdecision', index=models.Index(fields=['decision', 'created_at'], name='kyc_review__decisio_7a1711_idx')),
        migrations.AddIndex(model_name='kycreviewermfaassertion', index=models.Index(fields=['user', 'expires_at'], name='kyc_reviewe_user_id_f426c1_idx')),
        migrations.RunPython(create_kyc_review_groups, remove_kyc_review_groups),
    ]
