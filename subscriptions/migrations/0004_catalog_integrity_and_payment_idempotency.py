from decimal import Decimal

from django.db import migrations, models


CANONICAL_PLAN_IDS = ('hivmeet_monthly', 'hivmeet_annual')


def normalize_subscription_catalog(apps, schema_editor):
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')

    legacy = SubscriptionPlan.objects.filter(plan_id='').first()
    if legacy is not None:
        replacement = 'legacy_premium_monthly'
        if SubscriptionPlan.objects.filter(plan_id=replacement).exclude(
            pk=legacy.pk
        ).exists():
            replacement = f'legacy_premium_{str(legacy.pk).replace("-", "")[:12]}'
        legacy.plan_id = replacement
        legacy.is_active = False
        legacy.save(update_fields=['plan_id', 'is_active'])

    plans = (
        {
            'plan_id': 'hivmeet_monthly',
            'name': 'Abonnement Mensuel',
            'name_en': 'Monthly Subscription',
            'name_fr': 'Abonnement Mensuel',
            'description': 'Accès complet aux fonctionnalités Premium pendant un mois',
            'description_en': 'Full access to Premium features for one month',
            'description_fr': 'Accès complet aux fonctionnalités Premium pendant un mois',
            'price': Decimal('7.99'),
            'currency': 'EUR',
            'billing_interval': 'month',
            'trial_period_days': 7,
            'order': 1,
        },
        {
            'plan_id': 'hivmeet_annual',
            'name': 'Abonnement Annuel',
            'name_en': 'Annual Subscription',
            'name_fr': 'Abonnement Annuel',
            'description': 'Accès complet aux fonctionnalités Premium pendant un an — économisez 40 %',
            'description_en': 'Full access to Premium features for one year — save 40%',
            'description_fr': 'Accès complet aux fonctionnalités Premium pendant un an — économisez 40 %',
            'price': Decimal('57.99'),
            'currency': 'EUR',
            'billing_interval': 'year',
            'trial_period_days': 14,
            'order': 2,
        },
    )

    common_features = {
        'unlimited_likes': True,
        'can_see_likers': True,
        'can_rewind': True,
        'monthly_boosts_count': 1,
        'daily_super_likes_count': 5,
        'media_messaging_enabled': True,
        'audio_video_calls_enabled': True,
        'is_active': True,
    }
    for plan in plans:
        plan_id = plan.pop('plan_id')
        SubscriptionPlan.objects.update_or_create(
            plan_id=plan_id,
            defaults={**plan, **common_features},
        )

    SubscriptionPlan.objects.exclude(
        plan_id__in=CANONICAL_PLAN_IDS
    ).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0003_paymenttransaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymenttransaction',
            name='idempotency_key',
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name='paymenttransaction',
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=('user', 'idempotency_key'),
                name='unique_payment_idempotency_key_per_user',
            ),
        ),
        migrations.RunPython(
            normalize_subscription_catalog,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='subscriptionplan',
            constraint=models.CheckConstraint(
                check=models.Q(('plan_id', ''), _negated=True),
                name='subscription_plan_id_not_empty',
            ),
        ),
    ]
