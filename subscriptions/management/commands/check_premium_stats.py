"""
Management command to check premium subscription statistics.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from authentication.models import User
from subscriptions.models import Subscription, Transaction


class Command(BaseCommand):
    help = 'Display premium subscription statistics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json'],
            default='table',
            help='Output format (table or json)'
        )
    
    def handle(self, *args, **options):
        # Basic statistics
        total_users = User.objects.count()
        premium_users = User.objects.filter(is_premium=True).count()
        
        # Active subscriptions
        active_subscriptions = Subscription.objects.filter(
            status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING]
        ).count()
        
        # Subscription breakdown by status
        subscription_stats = Subscription.objects.values('status').annotate(
            count=Count('id')
        )
        
        # Revenue statistics
        total_revenue = Transaction.objects.filter(
            type=Transaction.TYPE_PURCHASE,
            status=Transaction.STATUS_SUCCEEDED
        ).aggregate(
            total=Count('amount')
        )['total'] or 0
        
        # Monthly revenue (current month)
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue = Transaction.objects.filter(
            type=Transaction.TYPE_PURCHASE,
            status=Transaction.STATUS_SUCCEEDED,
            created_at__gte=current_month
        ).count()
        
        # Conversion rate
        conversion_rate = (premium_users / total_users * 100) if total_users > 0 else 0
        
        if options['format'] == 'json':
            import json
            data = {
                'total_users': total_users,
                'premium_users': premium_users,
                'active_subscriptions': active_subscriptions,
                'conversion_rate': round(conversion_rate, 2),
                'subscription_breakdown': {
                    stat['status']: stat['count'] for stat in subscription_stats
                },
                'total_transactions': total_revenue,
                'monthly_transactions': monthly_revenue,
                'generated_at': timezone.now().isoformat()
            }
            self.stdout.write(json.dumps(data, indent=2))
        else:
            # Table format
            self.stdout.write(self.style.SUCCESS('=== PREMIUM SUBSCRIPTION STATISTICS ==='))
            self.stdout.write(f"Total users: {total_users}")
            self.stdout.write(f"Premium users: {premium_users}")
            self.stdout.write(f"Active subscriptions: {active_subscriptions}")
            self.stdout.write(f"Conversion rate: {conversion_rate:.2f}%")
            
            self.stdout.write("\n--- Subscription Status Breakdown ---")
            for stat in subscription_stats:
                self.stdout.write(f"{stat['status']}: {stat['count']}")
            
            self.stdout.write(f"\nTotal transactions: {total_revenue}")
            self.stdout.write(f"Monthly transactions: {monthly_revenue}")
            
            self.stdout.write(self.style.SUCCESS(f"\nGenerated at: {timezone.now()}"))
