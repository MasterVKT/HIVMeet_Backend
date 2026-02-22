#!/usr/bin/env python
"""
Script to create an active Subscription for the test user to enable super like.
The super like endpoint requires an active subscription with status='active'.
"""
import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
sys.path.insert(0, 'D:\\Projets\\HIVMeet\\env\\hivmeet_backend')

django.setup()

from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, SubscriptionPlan
from profiles.models import Profile

User = get_user_model()

def fix_superlike():
    """Create active subscription for Marie (test user) to enable super like."""
    
    # Get the test user
    user = User.objects.filter(email='marie.claire@test.com').first()
    if not user:
        print("❌ User not found: marie.claire@test.com")
        return False
    
    print(f"✅ Found user: {user.email}")
    
    # Get or create the profile
    profile = Profile.objects.filter(user=user).first()
    if not profile:
        print("❌ Profile not found for user")
        return False
    
    print(f"✅ Found profile: {profile.id}")
    
    # Get the premium subscription plan (or any active plan)
    premium_plan = SubscriptionPlan.objects.filter(
        is_active=True
    ).first()
    
    if not premium_plan:
        # Create a basic premium plan
        print("⚠️  No active subscription plan found, creating Premium plan...")
        premium_plan = SubscriptionPlan.objects.create(
            name='Premium',
            name_en='Premium',
            name_fr='Premium',
            is_active=True,
            price=9.99,
            currency='EUR',
            billing_interval='monthly',
            trial_period_days=7,
            unlimited_likes=True,
            monthly_boosts_count=10,
            daily_super_likes_count=3,
            audio_video_calls_enabled=True,
            media_messaging_enabled=True,
            can_see_likers=True,
            can_rewind=True,
        )
        print(f"✅ Created premium plan: {premium_plan.name}")
    else:
        print(f"✅ Using subscription plan: {premium_plan.name}")
    
    # Check for existing active subscription
    existing_subscription = Subscription.objects.filter(
        user=user,
        status='active'
    ).first()
    
    if existing_subscription:
        print(f"⚠️  User already has active subscription: {existing_subscription.id}")
        return True
    
    # Create new subscription
    now = timezone.now()
    subscription = Subscription.objects.create(
        user=user,
        plan=premium_plan,
        status='active',
        current_period_start=now,
        current_period_end=now + timedelta(days=365),  # Valid for 1 year
        auto_renew=True,
    )
    
    print(f"✅ Created active subscription:")
    print(f"   - ID: {subscription.id}")
    print(f"   - Plan: {premium_plan.name}")
    print(f"   - Status: {subscription.status}")
    print(f"   - Valid until: {subscription.current_period_end}")
    print()
    print("🎉 Super like should now work without 400 error!")
    
    return True

if __name__ == '__main__':
    try:
        fix_superlike()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
