"""
Management command to initialize subscription plans.
File: subscriptions/management/commands/init_subscription_plans.py
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from subscriptions.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Initialize subscription plans'

    @transaction.atomic
    def handle(self, *args, **options):
        legacy = SubscriptionPlan.objects.filter(plan_id='').first()
        if legacy:
            replacement = 'legacy_premium_monthly'
            if SubscriptionPlan.objects.filter(plan_id=replacement).exclude(
                pk=legacy.pk
            ).exists():
                replacement = (
                    f'legacy_premium_{str(legacy.pk).replace("-", "")[:12]}'
                )
            legacy.plan_id = replacement
            legacy.is_active = False
            legacy.save(update_fields=['plan_id', 'is_active'])

        # Monthly plan
        monthly_plan, created = SubscriptionPlan.objects.update_or_create(
            plan_id='hivmeet_monthly',
            defaults={
                'name': 'Abonnement Mensuel',
                'name_en': 'Monthly Subscription',
                'name_fr': 'Abonnement Mensuel',
                'description': 'Accès complet aux fonctionnalités Premium pendant un mois',
                'description_en': 'Full access to all premium features for 1 month',
                'description_fr': 'Accès complet aux fonctionnalités Premium pendant un mois',
                'price': Decimal('7.99'),
                'currency': 'EUR',
                'billing_interval': SubscriptionPlan.INTERVAL_MONTH,
                'trial_period_days': 7,
                'unlimited_likes': True,
                'can_see_likers': True,
                'can_rewind': True,
                'monthly_boosts_count': 1,
                'daily_super_likes_count': 5,
                'media_messaging_enabled': True,
                'audio_video_calls_enabled': True,
                'is_active': True,
                'order': 1
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created monthly plan'))
        else:
            self.stdout.write(self.style.SUCCESS('Updated monthly plan'))
        
        # Annual plan
        annual_plan, created = SubscriptionPlan.objects.update_or_create(
            plan_id='hivmeet_annual',
            defaults={
                'name': 'Abonnement Annuel',
                'name_en': 'Annual Subscription',
                'name_fr': 'Abonnement Annuel',
                'description': 'Accès complet aux fonctionnalités Premium pendant un an — économisez 40 %',
                'description_en': 'Full access to all premium features for 1 year - Save 40%',
                'description_fr': 'Accès complet aux fonctionnalités Premium pendant un an — économisez 40 %',
                'price': Decimal('57.99'),
                'currency': 'EUR',
                'billing_interval': SubscriptionPlan.INTERVAL_YEAR,
                'trial_period_days': 14,
                'unlimited_likes': True,
                'can_see_likers': True,
                'can_rewind': True,
                'monthly_boosts_count': 1,
                'daily_super_likes_count': 5,
                'media_messaging_enabled': True,
                'audio_video_calls_enabled': True,
                'is_active': True,
                'order': 2
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created annual plan'))
        else:
            self.stdout.write(self.style.SUCCESS('Updated annual plan'))

        deactivated = SubscriptionPlan.objects.exclude(
            plan_id__in=('hivmeet_monthly', 'hivmeet_annual')
        ).filter(is_active=True).update(is_active=False)
        if deactivated:
            self.stdout.write(
                self.style.WARNING(
                    f'Deactivated {deactivated} non-canonical plan(s)'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('Subscription plans initialized successfully'))
