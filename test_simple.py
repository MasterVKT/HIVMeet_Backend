import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

print("Testing messaging tasks import...")

try:
    from messaging.tasks import send_message_notification, send_call_notification
    print("SUCCESS: Messaging tasks imported successfully")
    
    from matching.tasks import send_match_notification, send_like_notification
    print("SUCCESS: Matching tasks imported successfully")
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    print(f"SUCCESS: User model imported: {User.__name__}")
    
    # Test if we can create a task without executing it
    print("SUCCESS: All imports working correctly!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()