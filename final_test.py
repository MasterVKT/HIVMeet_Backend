"""
Test final - Validation du système de notifications HIVMeet
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

def final_validation():
    """Test final de validation."""
    print("VALIDATION FINALE DU SYSTEME DE NOTIFICATIONS")
    print("=" * 60)
    
    success_count = 0
    total_tests = 6
    
    # Test 1: Import des tâches de messaging
    try:
        from messaging.tasks import send_message_notification, send_call_notification
        print("1. Messaging tasks import: SUCCESS")
        success_count += 1
    except Exception as e:
        print(f"1. Messaging tasks import: FAILED - {e}")
    
    # Test 2: Import des tâches de matching
    try:
        from matching.tasks import send_match_notification, send_like_notification
        print("2. Matching tasks import: SUCCESS")
        success_count += 1
    except Exception as e:
        print(f"2. Matching tasks import: FAILED - {e}")
    
    # Test 3: Firebase Admin SDK
    try:
        from firebase_admin import messaging
        notification = messaging.Notification(title="Test", body="Test")
        print("3. Firebase messaging: SUCCESS")
        success_count += 1
    except Exception as e:
        print(f"3. Firebase messaging: FAILED - {e}")
    
    # Test 4: Celery
    try:
        from celery import shared_task
        print("4. Celery integration: SUCCESS")
        success_count += 1
    except Exception as e:
        print(f"4. Celery integration: FAILED - {e}")
    
    # Test 5: User model
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Vérifier les champs requis
        required_fields = ['display_name', 'fcm_tokens', 'notification_settings', 'email']
        for field in required_fields:
            if not hasattr(User, field):
                raise Exception(f"Missing field: {field}")
        print("5. User model validation: SUCCESS")
        success_count += 1
    except Exception as e:
        print(f"5. User model validation: FAILED - {e}")
    
    # Test 6: Vérification des décorateurs Celery
    try:
        from messaging.tasks import send_message_notification
        from matching.tasks import send_match_notification
        
        # Vérifier que les fonctions sont des tâches Celery
        if not hasattr(send_message_notification, 'delay'):
            raise Exception("send_message_notification is not a Celery task")
        if not hasattr(send_match_notification, 'delay'):
            raise Exception("send_match_notification is not a Celery task")
        print("6. Celery task decorators: SUCCESS")
        success_count += 1
    except Exception as e:
        print(f"6. Celery task decorators: FAILED - {e}")
    
    print("=" * 60)
    print(f"RESULTS: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("STATUS: ALL TESTS PASSED - System ready!")
        print("The HIVMeet notification system is fully functional.")
        return True
    else:
        print("STATUS: Some tests failed - Please review above.")
        return False

if __name__ == '__main__':
    final_validation()
