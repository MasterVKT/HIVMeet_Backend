#!/usr/bin/env python
"""
Adjust Marie's profile to make distance filter less restrictive.
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

def adjust_marie():
    """Adjust Marie's distance filter."""
    print("=" * 80)
    print("🔧 Adjusting Marie's Profile for Testing")
    print("=" * 80)
    
    marie = User.objects.get(email='marie.claire@test.com')
    profile = marie.profile
    
    print(f"\n📋 Before:")
    print(f"   Latitude: {profile.latitude}")
    print(f"   Longitude: {profile.longitude}")
    print(f"   Max distance: {profile.distance_max_km}km")
    
    # Remove GPS coordinates to disable distance filtering
    profile.latitude = None
    profile.longitude = None
    profile.save(update_fields=['latitude', 'longitude'])
    
    print(f"\n📋 After:")
    print(f"   Latitude: {profile.latitude}")
    print(f"   Longitude: {profile.longitude}")
    print(f"   Max distance: {profile.distance_max_km}km")
    
    print(f"\n✅ Distance filter disabled for Marie (no GPS coords)")


if __name__ == '__main__':
    adjust_marie()
