#!/usr/bin/env python
"""Check the status of the remaining male profiles."""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile

User = get_user_model()

def check_profiles():
    """Check pierre and kevin profiles."""
    print("=" * 80)
    print("🔍 Checking Remaining Male Profiles")
    print("=" * 80)
    
    emails = ['pierre.martin@test.com', 'kevin.zhang@test.com']
    
    for email in emails:
        user = User.objects.filter(email=email).first()
        if not user:
            print(f"\n❌ {email} not found")
            continue
        
        profile = user.profile
        print(f"\n👤 {email}:")
        print(f"   Display name: {user.display_name}")
        print(f"   User active: {user.is_active}")
        print(f"   Email verified: {user.email_verified}")
        print(f"   Age: {user.age}")
        print(f"   Gender: {profile.gender}")
        print(f"   Seeks: {profile.genders_sought}")
        print(f"   Profile hidden: {profile.is_hidden}")
        print(f"   Allow in discovery: {profile.allow_profile_in_discovery}")
        print(f"   Age range: {profile.age_min_preference}-{profile.age_max_preference}")
        print(f"   Relationship types: {profile.relationship_types_sought}")
        
        # Check if compatible with Marie
        marie = User.objects.get(email='marie.claire@test.com')
        marie_profile = marie.profile
        
        print(f"\n   Compatibility with Marie:")
        print(f"      Marie's age ({marie.age}) in range? {profile.age_min_preference <= marie.age <= profile.age_max_preference}")
        print(f"      Profile age ({user.age}) in Marie's range? {marie_profile.age_min_preference <= user.age <= marie_profile.age_max_preference}")
        print(f"      Profile seeks Marie's gender? {marie_profile.gender in profile.genders_sought or not profile.genders_sought}")
        print(f"      Marie seeks profile's gender? {profile.gender in marie_profile.genders_sought or not marie_profile.genders_sought}")


if __name__ == '__main__':
    check_profiles()
