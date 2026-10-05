import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import subscriptions.models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('subscriptions', '0002_add_modification_transaction_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('app_transaction_ref', models.CharField(default=subscriptions.models.generate_payment_reference, editable=False, max_length=100, unique=True)),
                ('provider_transaction_ref', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(max_length=3)),
                ('status', models.CharField(choices=[('CREATED', 'Created'), ('PENDING', 'Pending'), ('SUCCESS', 'Success'), ('CANCELED', 'Canceled'), ('FAILED', 'Failed')], default='CREATED', max_length=10)),
                ('payment_url', models.URLField(blank=True, max_length=500)),
                ('provider_message', models.CharField(blank=True, max_length=255)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('fulfilled_at', models.DateTimeField(blank=True, null=True)),
                ('last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_transactions', to='subscriptions.subscriptionplan')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'subscription_payment_transactions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='paymenttransaction',
            index=models.Index(fields=['user', '-created_at'], name='subscriptio_user_id_b5a1c4_idx'),
        ),
        migrations.AddIndex(
            model_name='paymenttransaction',
            index=models.Index(fields=['status', 'created_at'], name='subscriptio_status_fe5971_idx'),
        ),
    ]
