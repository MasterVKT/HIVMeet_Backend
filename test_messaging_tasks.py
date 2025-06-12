#!/usr/bin/env python
"""
Test script to check messaging tasks import and functionality.
"""
import os
import sys
import django

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

# Setup Django
django.setup()

def test_imports():
    """Test importing messaging tasks."""
    try:
        from messaging.tasks import send_message_notification, send_call_notification
        print("✓ Successfully imported messaging tasks")
        return True
    except ImportError as e:
        print(f"✗ Failed to import messaging tasks: {e}")
        return False

def test_firebase_admin():
    """Test Firebase Admin SDK import."""
    try:
        import firebase_admin
        from firebase_admin import messaging
        print("✓ Successfully imported Firebase Admin SDK")
        return True
    except ImportError as e:
        print(f"✗ Failed to import Firebase Admin SDK: {e}")
        return False

def test_celery():
    """Test Celery import."""
    try:
        from celery import shared_task
        print("✓ Successfully imported Celery")
        return True
    except ImportError as e:
        print(f"✗ Failed to import Celery: {e}")
        return False

def test_user_model():
    """Test User model import."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        print(f"✓ Successfully imported User model: {User.__name__}")
        return True
    except Exception as e:
        print(f"✗ Failed to import User model: {e}")
        return False

def main():
    """Main test function."""
    print("Testing HIVMeet Backend Messaging Tasks...")
    print("=" * 50)
    
    tests = [
        test_user_model,
        test_celery,
        test_firebase_admin,
        test_imports,
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print()
    
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! Messaging tasks are ready.")
    else:
        print("✗ Some tests failed. Please check the errors above.")

if __name__ == '__main__':
    main()
