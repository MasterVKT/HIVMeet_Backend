#!/usr/bin/env python
"""
Diagnostic script to check what's happening with the gender filtering.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile
from matching.models import InteractionHistory, Like, Dislike
from django.utils import timezone

User = get_user_model()

def diagnose():
    """Diagnose the gender filter issue."""
    print("=" * 80)
    print("🔍 Gender Filter Diagnostic")
    print("=" * 80)
    
    # Get Marie
    marie = User.objects.filter(email='marie.claire@test.com').first()
    if not marie:
        print("❌ Marie not found")
        return
    
    print(f"\n👤 Marie ({marie.email}):")
    print(f"   Gender: {marie.profile.gender}")
    print(f"   Seeking: {marie.profile.genders_sought}")
    print(f"   Age: {marie.age} (seeking {marie.profile.age_min_preference}-{marie.profile.age_max_preference})")
    
    # Step 1: All male profiles
    all_males = Profile.objects.filter(gender='male', user__is_active=True)
    print(f"\n📊 Step 1: All male profiles")
    print(f"   Count: {all_males.count()}")
    
    # Step 2: Exclude interactions
    interacted_ids = InteractionHistory.objects.filter(
        user=marie, is_revoked=False
    ).values_list('target_user_id', flat=True)
    
    legacy_liked_ids = Like.objects.filter(from_user=marie).values_list('to_user_id', flat=True)
    legacy_disliked_ids = Dislike.objects.filter(
        from_user=marie, expires_at__gt=timezone.now()
    ).values_list('to_user_id', flat=True)
    
    excluded_ids = set(interacted_ids) | set(legacy_liked_ids) | set(legacy_disliked_ids) | {marie.id}
    
    print(f"\n📊 Step 2: Excluded profiles")
    print(f"   Total excluded: {len(excluded_ids)}")
    print(f"   - Active interactions: {len(interacted_ids)}")
    print(f"   - Legacy likes: {len(legacy_liked_ids)}")
    print(f"   - Legacy dislikes: {len(legacy_disliked_ids)}")
    
    males_after_exclusion = all_males.exclude(user_id__in=excluded_ids)
    print(f"   Males after exclusion: {males_after_exclusion.count()}")
    
    # Show some males
    if males_after_exclusion.exists():
        print(f"\n   Available male profiles:")
        for profile in males_after_exclusion[:5]:
            print(f"      - {profile.user.email}: age {profile.user.age}, seeks {profile.genders_sought}")
    else:
        print(f"\n   ⚠️  No male profiles available after exclusion!")
        print(f"   Marie has already interacted with all male profiles")
        
        # Show who Marie has interacted with
        print(f"\n   Marie's interactions:")
        interactions = InteractionHistory.objects.filter(user=marie, is_revoked=False)[:10]
        for interaction in interactions:
            print(f"      - {interaction.target_user.email} ({interaction.interaction_type}) - {interaction.created_at}")


if __name__ == '__main__':
    diagnose()
