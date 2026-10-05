"""Create test accounts via Firebase Admin SDK + Django backend API.
This bypasses the registration form UI which can't type special characters via adb.
"""
import os
import sys
import json
import requests

# Add the backend to path
sys.path.insert(0, r'D:\Projets\HIVMeet\env\hivmeet_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

import django
django.setup()

from django.contrib.auth import get_user_model
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, initialize_app

User = get_user_model()

# Initialize Firebase Admin if not already done
cred_path = r'D:\Projets\HIVMeet\env\hivmeet_backend\credentials\hivmeet_firebase_credentials.json'
if not os.path.exists(cred_path):
    print(f"ERROR: Firebase credentials not found at {cred_path}")
    sys.exit(1)

try:
    app = firebase_admin.get_app()
except:
    cred = credentials.Certificate(cred_path)
    app = initialize_app(cred)

BACKEND_URL = "http://127.0.0.1:8000"

def create_account(email, password, display_name, birth_date):
    """Create a Firebase user and sync with Django backend."""
    print(f"\n--- Creating account: {email} ---")
    
    # 1. Create Firebase user
    try:
        # Check if user already exists
        try:
            fb_user = firebase_auth.get_user_by_email(email)
            print(f"  Firebase user already exists: {fb_user.uid}")
        except:
            fb_user = firebase_auth.create_user(
                email=email,
                password=password,
                display_name=display_name,
            )
            print(f"  Firebase user created: {fb_user.uid}")
    except Exception as e:
        print(f"  ERROR creating Firebase user: {e}")
        return None
    
    # 2. Generate a Firebase ID token for this user
    try:
        custom_token = firebase_auth.create_custom_token(fb_user.uid)
        # Exchange custom token for ID token
        # Note: We can't easily get an ID token from a custom token without the client SDK
        # Instead, we'll use the backend's firebase-exchange endpoint with the custom token
        print(f"  Custom token generated (len={len(custom_token)})")
    except Exception as e:
        print(f"  ERROR generating custom token: {e}")
        return None
    
    # 3. Sync with Django backend via firebase-exchange
    try:
        # The backend expects a Firebase ID token, not a custom token
        # We need to verify the user exists in Django and create if not
        from profiles.models import Profile
        
        # Check if Django user exists
        try:
            user = User.objects.get(firebase_uid=fb_user.uid)
            print(f"  Django user already exists: {user.id}")
        except User.DoesNotExist:
            # Create Django user
            from datetime import datetime
            user = User.objects.create(
                firebase_uid=fb_user.uid,
                email=email,
                display_name=display_name,
                birth_date=datetime.strptime(birth_date, '%Y-%m-%d').date(),
                email_verified=False,
                is_active=True,
            )
            print(f"  Django user created: {user.id}")
            
            # Create user profile
            try:
                profile = Profile.objects.create(
                    user=user,
                    bio='',
                    gender='female',  # ALICE is female
                )
                print(f"  Profile created: {profile.id}")
            except Exception as pe:
                print(f"  Profile creation note: {pe}")
            print(f"  UserProfile created: {profile.id}")
            
    except Exception as e:
        print(f"  ERROR syncing with Django: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    print(f"  SUCCESS: {email} created")
    return fb_user.uid

# Create ALICE account
create_account(
    email="alice.hivmeet@test.local",
    password="Alice2026&",
    display_name="Alice",
    birth_date="1995-06-15",
)

# Create BOB account
create_account(
    email="bob.hivmeet@test.local",
    password="Bob2026&",
    display_name="Bob",
    birth_date="1993-03-20",
)

print("\n--- Done creating accounts ---")