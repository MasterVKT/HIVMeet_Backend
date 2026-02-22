#!/usr/bin/env python
"""
Test script to validate DiscoveryProfileSerializer improvements.
Tests:
1. Display name handling (no empty values)
2. Photo URLs (returns list of strings, not objects)
3. Fallback to Gravatar when no photos exist
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile
from matching.serializers import DiscoveryProfileSerializer
from rest_framework.test import APIRequestFactory

User = get_user_model()

def test_discovery_serializer():
    """Test the DiscoveryProfileSerializer improvements."""
    print("=" * 80)
    print("🧪 Testing DiscoveryProfileSerializer")
    print("=" * 80)
    
    # Get some profiles to test
    profiles = Profile.objects.select_related('user').filter(
        user__is_active=True
    )[:3]  # Test first 3 profiles
    
    if not profiles.exists():
        print("❌ No profiles found in database. Please create test data first.")
        return False
    
    # Create a fake request for context
    factory = APIRequestFactory()
    request = factory.get('/api/v1/discovery/profiles/')
    # Add scheme and server_name to request for build_absolute_uri
    request.META['HTTP_HOST'] = 'localhost'
    request.META['wsgi.url_scheme'] = 'http'
    
    # Serialize profiles
    serializer = DiscoveryProfileSerializer(
        profiles,
        many=True,
        context={'request': request}
    )
    
    all_valid = True
    
    for i, profile_data in enumerate(serializer.data):
        print(f"\n📋 Profile {i+1}:")
        print(f"   User ID: {profile_data.get('user_id')}")
        
        # Test 1: Display name should not be empty
        display_name = profile_data.get('display_name')
        if not display_name or not str(display_name).strip():
            print(f"   ❌ Display name is empty!")
            all_valid = False
        else:
            print(f"   ✅ Display name: '{display_name}'")
        
        # Test 2: Photos should be a list
        photos = profile_data.get('photos')
        if not isinstance(photos, list):
            print(f"   ❌ Photos is not a list! Type: {type(photos)}")
            all_valid = False
        elif not photos:
            print(f"   ❌ Photos list is empty!")
            all_valid = False
        else:
            print(f"   ✅ Photos: {len(photos)} photo(s)")
            for j, photo_url in enumerate(photos):
                if isinstance(photo_url, dict):
                    print(f"      ❌ Photo {j+1} is a dict, should be string: {photo_url}")
                    all_valid = False
                elif isinstance(photo_url, str) and (photo_url.startswith('http://') or photo_url.startswith('https://') or photo_url.startswith('/')):
                    print(f"      ✅ Photo {j+1}: {photo_url[:60]}...")
                else:
                    print(f"      ❌ Photo {j+1} is not a valid URL: {photo_url}")
                    all_valid = False
        
        # Test 3: Check other required fields
        required_fields = ['age', 'bio', 'city', 'country', 'interests', 'relationship_types_sought', 'is_verified', 'is_online']
        for field in required_fields:
            value = profile_data.get(field)
            if value is None:
                print(f"   ⚠️  Field '{field}' is None")
            else:
                print(f"   ✅ {field}: {str(value)[:50]}..." if len(str(value)) > 50 else f"   ✅ {field}: {value}")
    
    print("\n" + "=" * 80)
    if all_valid:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    print("=" * 80)
    
    return all_valid


if __name__ == '__main__':
    success = test_discovery_serializer()
    sys.exit(0 if success else 1)
