# Generated manually from Django's checked migration plan on 2026-10-05.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0014_kycreviewassignment_kycreviewdecision_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KycReviewAnomalyAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('document_access_volume', 'Document access volume')], max_length=48)),
                ('window_started_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kyc_review_anomaly_alerts', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'kyc_review_anomaly_alerts'},
        ),
        migrations.AddConstraint(
            model_name='kycreviewanomalyalert',
            constraint=models.UniqueConstraint(fields=('actor', 'category', 'window_started_at'), name='profiles_kyc_review_anomaly_once_per_window'),
        ),
    ]
