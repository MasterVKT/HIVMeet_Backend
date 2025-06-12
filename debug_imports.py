import os
import sys

print("Python path:")
for path in sys.path:
    print(f"  {path}")

print(f"\nCurrent working directory: {os.getcwd()}")
print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")

try:
    import django
    print(f"Django version: {django.get_version()}")
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
    django.setup()
    
    print("Django setup successful")
    
    # Test imports
    from django.contrib.auth import get_user_model
    print("✓ User model imported successfully")
    
    from celery import shared_task
    print("✓ Celery imported successfully")
    
    import firebase_admin
    print("✓ Firebase Admin SDK imported successfully")
    
    from messaging.tasks import send_message_notification
    print("✓ Messaging tasks imported successfully")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
