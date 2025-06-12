"""
Management command to initialize subscription plans.
File: subscriptions/management/commands/init_subscription_plans.py
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _
from subscriptions.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Initialize subscription plans'

    def handle(self, *args, **options):
        # Monthly plan
        monthly_plan, created = SubscriptionPlan.objects.update_or_create(
            plan_id='hivmeet_monthly',
            defaults={
                'name': 'Abonnement Mensuel',
                'name_en': 'Monthly Subscription',
                'name_fr': 'Abonnement Mensuel',
                'description': 'Accès complet à toutes les fonctionnalités premium pendant 1 mois',
                'description_en': 'Full access to all premium features for 1 month',
                'description_fr': 'Accès complet à toutes les fonctionnalités premium pendant 1 mois',
                'price': 7.99,
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
                'description': 'Accès complet à toutes les fonctionnalités premium pendant 1 an - Économisez 40%',
                'description_en': 'Full access to all premium features for 1 year - Save 40%',
                'description_fr': 'Accès complet à toutes les fonctionnalités premium pendant 1 an - Économisez 40%',
                'price': 57.99,
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
        
        self.stdout.write(self.style.SUCCESS('Subscription plans initialized successfully'))