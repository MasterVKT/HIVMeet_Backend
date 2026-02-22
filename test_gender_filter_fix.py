#!/usr/bin/env python
"""
Test script to validate the gender filter bug fix.
Simulates the discovery flow for a female user seeking males.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile
from matching.services import RecommendationService

User = get_user_model()

def test_gender_filter_fix():
    """Test that female users can find male profiles that seek females."""
    print("=" * 80)
    print("🧪 Testing Gender Filter Bug Fix")
    print("=" * 80)
    
    # Find or use Marie (female user seeking males)
    marie_email = 'marie.claire@test.com'
    marie = User.objects.filter(email=marie_email).first()
    
    if not marie:
        print(f"❌ Test user '{marie_email}' not found")
        print("   Please create Marie's profile first")
        return False
    
    print(f"\n📋 Test User: {marie.display_name} ({marie.email})")
    marie_profile = marie.profile
    
    print(f"   Gender: {marie_profile.gender}")
    print(f"   Seeking: {marie_profile.genders_sought}")
    print(f"   Age: {marie.age} (seeking {marie_profile.age_min_preference}-{marie_profile.age_max_preference})")
    
    # Check male profiles
    print(f"\n📊 Analyzing Male Profiles:")
    male_profiles = Profile.objects.filter(
        gender='male',
        user__is_active=True,
        user__email_verified=True
    )
    
    print(f"   Total male profiles: {male_profiles.count()}")
    
    # Check how many have genders_sought configured
    males_with_preference = male_profiles.exclude(genders_sought=[])
    males_without_preference = male_profiles.filter(genders_sought=[])
    
    print(f"   With genders_sought: {males_with_preference.count()}")
    print(f"   Without genders_sought (empty): {males_without_preference.count()}")
    
    # Show sample
    if males_with_preference.exists():
        print(f"\n   Sample male profiles with preferences:")
        for profile in males_with_preference[:3]:
            print(f"      - {profile.user.email}: seeks {profile.genders_sought}")
    
    if males_without_preference.exists():
        print(f"\n   ⚠️  Male profiles WITHOUT preferences:")
        for profile in males_without_preference[:3]:
            print(f"      - {profile.user.email}: genders_sought is EMPTY")
    
    # Test the recommendation service
    print(f"\n🔍 Testing RecommendationService.get_recommendations():")
    profiles = RecommendationService.get_recommendations(
        user=marie,
        limit=10,
        offset=0
    )
    
    print(f"\n📊 Results:")
    print(f"   Profiles returned: {len(profiles)}")
    
    if len(profiles) == 0:
        print(f"\n❌ TEST FAILED: No profiles returned!")
        print(f"   Expected: At least 1 male profile seeking females")
        print(f"   Got: 0 profiles")
        
        # Diagnostic
        print(f"\n🔍 Diagnostic:")
        if males_without_preference.count() > 0:
            print(f"   ⚠️  {males_without_preference.count()} male profiles have empty genders_sought")
            print(f"   Run: python fix_genders_sought.py")
        
        return False
    
    # Show returned profiles
    print(f"\n✅ Profiles returned:")
    for i, profile in enumerate(profiles[:5], 1):
        print(f"   {i}. {profile.user.display_name} ({profile.user.email})")
        print(f"      Gender: {profile.gender}, Seeks: {profile.genders_sought}")
        print(f"      Age: {profile.user.age}")
    
    # Validate that all returned profiles are compatible
    all_valid = True
    for profile in profiles:
        # Check if profile seeks Marie's gender
        if profile.genders_sought and 'female' not in profile.genders_sought:
            print(f"\n   ❌ {profile.user.email} does NOT seek females: {profile.genders_sought}")
            all_valid = False
    
    print(f"\n" + "=" * 80)
    if all_valid and len(profiles) > 0:
        print("✅ TEST PASSED: Gender filter is working correctly!")
        print(f"   {len(profiles)} compatible profiles found")
    else:
        print("❌ TEST FAILED: Some profiles are not compatible")
    print("=" * 80)
    
    return all_valid and len(profiles) > 0


if __name__ == '__main__':
    success = test_gender_filter_fix()
    sys.exit(0 if success else 1)
