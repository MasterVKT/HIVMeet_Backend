#!/usr/bin/env python
"""
Script to fix genders_sought for existing male profiles.
Sets genders_sought to ['female'] for male profiles that have it empty or NULL.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile

User = get_user_model()

def fix_male_profiles_genders():
    """Add genders_sought to male profiles that are missing it."""
    print("=" * 80)
    print("🔧 Fixing genders_sought for male profiles")
    print("=" * 80)
    
    # Find male profiles with empty or NULL genders_sought
    male_profiles = Profile.objects.filter(
        gender='male'
    )
    
    print(f"\n📊 Total male profiles found: {male_profiles.count()}")
    
    # Count how many need fixing
    profiles_to_fix = male_profiles.filter(genders_sought=[])
    print(f"📊 Male profiles with empty genders_sought: {profiles_to_fix.count()}")
    
    if profiles_to_fix.count() == 0:
        print("\n✅ All male profiles already have genders_sought configured!")
        return
    
    # Ask for confirmation
    print(f"\n🔧 Will set genders_sought=['female'] for {profiles_to_fix.count()} profiles")
    print("   This will make them compatible with female users seeking males")
    
    response = input("\nProceed? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Operation cancelled")
        return
    
    # Update profiles
    updated_count = 0
    for profile in profiles_to_fix:
        try:
            profile.genders_sought = ['female']
            profile.save(update_fields=['genders_sought'])
            print(f"✅ Updated: {profile.user.email} (user_id: {profile.user.id})")
            updated_count += 1
        except Exception as e:
            print(f"❌ Error updating {profile.user.email}: {e}")
    
    print(f"\n" + "=" * 80)
    print(f"✅ Successfully updated {updated_count}/{profiles_to_fix.count()} male profiles")
    print("=" * 80)
    
    # Verify the update
    print("\n🔍 Verification:")
    remaining_empty = Profile.objects.filter(
        gender='male',
        genders_sought=[]
    ).count()
    
    if remaining_empty == 0:
        print("✅ All male profiles now have genders_sought configured!")
    else:
        print(f"⚠️  {remaining_empty} male profiles still have empty genders_sought")


def show_profile_stats():
    """Show statistics about genders_sought across all profiles."""
    print("\n" + "=" * 80)
    print("📊 Profile Statistics by Gender")
    print("=" * 80)
    
    genders = ['male', 'female', 'non_binary', 'trans_male', 'trans_female', 'other']
    
    for gender in genders:
        profiles = Profile.objects.filter(gender=gender)
        count = profiles.count()
        
        if count == 0:
            continue
        
        with_preferences = profiles.exclude(genders_sought=[]).count()
        without_preferences = profiles.filter(genders_sought=[]).count()
        
        print(f"\n{gender.upper()}:")
        print(f"   Total: {count}")
        print(f"   With genders_sought: {with_preferences}")
        print(f"   Without genders_sought (empty): {without_preferences}")
        
        if with_preferences > 0:
            # Show what they seek
            sample_profiles = profiles.exclude(genders_sought=[])[:3]
            for p in sample_profiles:
                print(f"      - {p.user.email}: seeks {p.genders_sought}")


if __name__ == '__main__':
    print("\n🔍 Current state:")
    show_profile_stats()
    
    print("\n" + "=" * 80)
    fix_male_profiles_genders()
    
    print("\n🔍 Final state:")
    show_profile_stats()
