#!/usr/bin/env python
"""
Test script to validate the discovery API endpoint.
Tests the actual endpoint response format and data completeness.
"""
import os
import sys
import django
import json

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

def get_test_user_token():
    """Get or create a test user and return their auth token."""
    email = 'test_discovery@test.com'
    user = User.objects.filter(email=email).first()
    
    if not user:
        print(f"❌ Test user {email} not found. Please create a test user first.")
        return None
    
    # Generate JWT token
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), user

def test_discovery_endpoint():
    """Test the actual discovery API endpoint."""
    print("=" * 80)
    print("🧪 Testing Discovery API Endpoint")
    print("=" * 80)
    
    # Get test user and token
    token, user = get_test_user_token()
    if not token:
        return False
    
    print(f"\n📝 Using test user: {user.email}")
    
    # Create API client
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    # Call the discovery endpoint
    print("\n📤 Calling GET /api/v1/discovery/profiles?page=1")
    response = client.get('/api/v1/discovery/profiles/', {'page': 1})
    
    print(f"📥 Response status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Expected 200, got {response.status_code}")
        print(f"Response: {response.data}")
        return False
    
    data = response.json()
    
    # Validate response structure
    print("\n✓ Response structure validation:")
    required_fields = ['count', 'results']
    for field in required_fields:
        if field in data:
            print(f"   ✅ {field}: {data[field] if not isinstance(data[field], list) else f'{len(data[field])} items'}")
        else:
            print(f"   ❌ Missing field: {field}")
            return False
    
    results = data.get('results', [])
    
    if not results:
        print(f"\n⚠️  No profiles returned. Response: {json.dumps(data, indent=2)}")
        return True  # Not necessarily an error
    
    print(f"\n📋 Validating {len(results)} profile(s):")
    
    all_valid = True
    for i, profile in enumerate(results[:3]):  # Check first 3
        print(f"\n   Profile {i+1}:")
        
        # Check display_name
        display_name = profile.get('display_name')
        if not display_name or not str(display_name).strip():
            print(f"      ❌ display_name is empty!")
            all_valid = False
        else:
            print(f"      ✅ display_name: '{display_name}'")
        
        # Check photos
        photos = profile.get('photos')
        if not isinstance(photos, list):
            print(f"      ❌ photos is not a list!")
            all_valid = False
        elif not photos:
            print(f"      ❌ photos is empty!")
            all_valid = False
        else:
            print(f"      ✅ photos: {len(photos)} URL(s)")
            for j, photo_url in enumerate(photos[:2]):  # Check first 2
                if isinstance(photo_url, str):
                    print(f"         ✅ Photo {j+1}: {photo_url[:60]}...")
                else:
                    print(f"         ❌ Photo {j+1} is not a string: {photo_url}")
                    all_valid = False
        
        # Check other fields
        for field in ['user_id', 'age', 'bio', 'city', 'country', 'interests', 'is_verified', 'is_online']:
            value = profile.get(field)
            if value is None:
                print(f"      ⚠️  {field}: None")
            else:
                print(f"      ✅ {field}: {str(value)[:50]}..." if len(str(value)) > 50 else f"      ✅ {field}: {value}")
    
    print("\n" + "=" * 80)
    if all_valid:
        print("✅ Discovery API is working correctly!")
    else:
        print("❌ Some validation checks failed!")
    print("=" * 80)
    
    return all_valid


if __name__ == '__main__':
    success = test_discovery_endpoint()
    sys.exit(0 if success else 1)
