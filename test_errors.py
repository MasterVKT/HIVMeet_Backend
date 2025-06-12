import os
import sys
import django
import traceback

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

print("Setting up Django...")
try:
    django.setup()
    print("Django setup successful")
except Exception as e:
    print(f"Django setup failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\nTesting messaging tasks...")
try:
    from messaging.tasks import send_message_notification, send_call_notification
    print("✓ Messaging tasks imported successfully")
    
    # Test function signatures
    import inspect
    
    sig = inspect.signature(send_message_notification)
    print(f"✓ send_message_notification signature: {sig}")
    
    sig = inspect.signature(send_call_notification)
    print(f"✓ send_call_notification signature: {sig}")
    
except Exception as e:
    print(f"✗ Error importing messaging tasks: {e}")
    traceback.print_exc()

print("\nTesting matching tasks...")
try:
    from matching.tasks import send_match_notification, send_like_notification
    print("✓ Matching tasks imported successfully")
    
    import inspect
    
    sig = inspect.signature(send_match_notification)
    print(f"✓ send_match_notification signature: {sig}")
    
    sig = inspect.signature(send_like_notification)
    print(f"✓ send_like_notification signature: {sig}")
    
except Exception as e:
    print(f"✗ Error importing matching tasks: {e}")
    traceback.print_exc()

print("\nTesting Firebase integration...")
try:
    import firebase_admin
    from firebase_admin import messaging
    print("✓ Firebase Admin SDK imported")
    
    # Test creating a simple notification object
    notification = messaging.Notification(
        title="Test Title",
        body="Test Body"
    )
    print("✓ Firebase notification object created successfully")
    
except Exception as e:
    print(f"✗ Error with Firebase: {e}")
    traceback.print_exc()

print("\nTesting Celery integration...")
try:
    from celery import shared_task
    print("✓ Celery imported successfully")
    
    # Test creating a simple task
    @shared_task
    def test_task():
        return "test"
    
    print("✓ Celery task decorator works")
    
except Exception as e:
    print(f"✗ Error with Celery: {e}")
    traceback.print_exc()

print("\nAll tests completed!")
