# Generated manually from Django's checked migration plan on 2026-10-07.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0015_kycreviewanomalyalert'),
    ]

    operations = [
        migrations.CreateModel(
            name='KycDecisionEmailDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sending', 'Sending'), ('retrying', 'Retrying'), ('sent', 'Sent'), ('failed', 'Failed'), ('suppressed', 'Suppressed')], db_index=True, default='pending', max_length=12)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('last_error_code', models.CharField(blank=True, max_length=48)),
                ('next_attempt_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('sending_started_at', models.DateTimeField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('decision', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='email_delivery', to='profiles.kycreviewdecision')),
            ],
            options={
                'db_table': 'kyc_decision_email_deliveries',
                'indexes': [models.Index(fields=['status', 'next_attempt_at'], name='kyc_decisio_status_dbe9b3_idx')],
            },
        ),
    ]
