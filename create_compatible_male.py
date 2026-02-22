#!/usr/bin/env python
"""
Create a test male profile that is compatible with Marie for testing.
"""
import os
import sys
import django
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile

User = get_user_model()

def create_compatible_male():
    """Create a male profile compatible with Marie."""
    print("=" * 80)
    print("🔧 Creating Compatible Male Profile for Testing")
    print("=" * 80)
    
    email = 'thomas.compatible@test.com'
    
    # Check if already exists
    existing = User.objects.filter(email=email).first()
    if existing:
        print(f"\n⚠️  User {email} already exists, updating...")
        user = existing
    else:
        # Calculate birth_date for age 42
        today = date.today()
        birth_date = date(today.year - 42, today.month, today.day)
        
        # Create user
        user = User.objects.create(
            email=email,
            display_name='Thomas',
            birth_date=birth_date,
            is_active=True,
            email_verified=True
        )
        user.set_password('testpass123')
        user.save()
        print(f"\n✅ User created: {email}")
    
    # Create/update profile
    profile, created = Profile.objects.update_or_create(
        user=user,
        defaults={
            'gender': 'male',
            'genders_sought': ['female'],  # Seeks females
            'bio': 'Professeur d\'université. Passionné de littérature et de voyages.',
            'interests': ['reading', 'travel', 'arts'],
            'relationship_types_sought': ['long_term', 'friendship'],
            'age_min_preference': 35,  # Accepts Marie's age (39)
            'age_max_preference': 50,  # Accepts Marie's age (39)
            'distance_max_km': 50,
            'city': 'Paris',
            'country': 'France',
            'is_hidden': False,
            'allow_profile_in_discovery': True,
        }
    )
    
    if created:
        print(f"✅ Profile created")
    else:
        print(f"🔄 Profile updated")
    
    print(f"\n📋 Profile Details:")
    print(f"   Email: {email}")
    print(f"   Display name: {user.display_name}")
    print(f"   Age: {user.age}")
    print(f"   Gender: {profile.gender}")
    print(f"   Seeks: {profile.genders_sought}")
    print(f"   Age range: {profile.age_min_preference}-{profile.age_max_preference}")
    print(f"   Accepts Marie (39y)? {profile.age_min_preference <= 39 <= profile.age_max_preference}")
    
    # Check if Marie would accept this profile
    marie = User.objects.get(email='marie.claire@test.com')
    marie_profile = marie.profile
    marie_accepts = marie_profile.age_min_preference <= user.age <= marie_profile.age_max_preference
    
    print(f"   Marie accepts Thomas ({user.age}y)? {marie_accepts}")
    
    print(f"\n" + "=" * 80)
    if marie_accepts and (profile.age_min_preference <= 39 <= profile.age_max_preference):
        print("✅ Profile is fully compatible with Marie!")
    else:
        print("⚠️  Profile may not be fully compatible")
    print("=" * 80)


if __name__ == '__main__':
    create_compatible_male()
