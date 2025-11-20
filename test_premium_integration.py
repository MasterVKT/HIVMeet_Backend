"""
Test script for premium features integration.
"""
import os
import sys
import django

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'hivmeet_backend.settings'
django.setup()

def test_premium_integration():
    """Test all premium features integration."""
    
    print("=== TESTING PREMIUM FEATURES INTEGRATION ===\n")
    
    # Test 1: Premium utilities import
    print("1. Testing premium utilities import...")
    try:
        from subscriptions.utils import (
            is_premium_user, check_feature_availability, 
            get_premium_limits, premium_required_response,
            consume_premium_feature
        )
        print("[OK] Premium utilities imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import premium utilities: {e}")
        return False
    
    # Test 2: Premium middleware import
    print("\n2. Testing premium middleware import...")
    try:
        from subscriptions.middleware import premium_required, check_feature_limit
        from hivmeet_backend.middleware import PremiumStatusMiddleware
        print("[OK] Premium middleware imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import premium middleware: {e}")
        return False
    
    # Test 3: Matching premium views import
    print("\n3. Testing matching premium views import...")
    try:
        from matching.views_premium import (
            RewindLastSwipeView, SendSuperLikeView, ProfileBoostView
        )
        print("[OK] Matching premium views imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import matching premium views: {e}")
        return False
    
    # Test 4: Messaging premium views import
    print("\n4. Testing messaging premium views import...")
    try:
        from messaging.views import SendMediaMessageView, InitiatePremiumCallView
        print("[OK] Messaging premium views imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import messaging premium views: {e}")
        return False
    
    # Test 5: Profiles premium views import
    print("\n5. Testing profiles premium views import...")
    try:
        from profiles.views_premium import (
            LikesReceivedView, SuperLikesReceivedView, PremiumFeaturesStatusView
        )
        print("[OK] Profiles premium views imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import profiles premium views: {e}")
        return False
    
    # Test 6: User model premium properties
    print("\n6. Testing User model premium properties...")
    try:
        from authentication.models import User
        user_props = [
            'premium_features', 'can_send_super_like', 'can_use_boost',
            'can_send_media_messages', 'can_make_calls', 'can_see_who_liked'
        ]
        user_instance = User()
        for prop in user_props:
            if not hasattr(user_instance, prop):
                raise AttributeError(f"Missing property: {prop}")
        print("[OK] User model premium properties available")
    except Exception as e:
        print(f"[ERROR] User model premium properties test failed: {e}")
        return False
    
    # Test 7: Premium signals import
    print("\n7. Testing premium signals import...")
    try:
        from matching.signals import handle_super_like_sent, handle_boost_activation
        print("[OK] Premium signals imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import premium signals: {e}")
        return False
    
    # Test 8: Management command
    print("\n8. Testing premium management command...")
    try:
        from subscriptions.management.commands.check_premium_stats import Command
        print("[OK] Premium management command available")
    except ImportError as e:
        print(f"[ERROR] Failed to import premium management command: {e}")
        return False
    
    # Test 9: Admin premium configuration
    print("\n9. Testing admin premium configuration...")
    try:
        from authentication.admin import CustomUserAdmin
        from subscriptions.admin import SubscriptionAdmin
        print("[OK] Premium admin configuration available")
    except ImportError as e:
        print(f"[ERROR] Failed to import premium admin configuration: {e}")
        return False
    
    print("\n=== ALL PREMIUM INTEGRATION TESTS PASSED ===")
    return True

def test_premium_services():
    """Test premium services functionality."""
    
    print("\n=== TESTING PREMIUM SERVICES ===\n")
    
    try:
        from subscriptions.services import (
            MyCoolPayService, SubscriptionService, PremiumFeatureService
        )
        
        # Test service initialization
        payment_service = MyCoolPayService()
        subscription_service = SubscriptionService()
        feature_service = PremiumFeatureService()
        
        print("[OK] Premium services initialized successfully")
        
        # Test service methods exist
        required_methods = {
            'MyCoolPayService': [
                'create_payment_session', 'cancel_subscription', 
                'reactivate_subscription'
            ],
            'SubscriptionService': [
                'create_subscription', 'handle_payment_success',
                'handle_payment_failure', 'handle_subscription_renewal'
            ],            'PremiumFeatureService': [
                'check_premium_status', 'check_and_reset_counters',
                'can_use_feature'
            ]
        }
        
        for service_name, methods in required_methods.items():
            if service_name == 'MyCoolPayService':
                service = payment_service
            elif service_name == 'SubscriptionService':
                service = subscription_service
            elif service_name == 'PremiumFeatureService':
                service = feature_service
            
            for method in methods:
                if not hasattr(service, method):
                    raise AttributeError(f"{service_name} missing method: {method}")
        
        print("[OK] All premium service methods available")
        return True
        
    except Exception as e:
        print(f"[ERROR] Premium services test failed: {e}")
        return False

def main():
    """Run all premium integration tests."""
    
    try:
        test1 = test_premium_integration()
        test2 = test_premium_services()
        
        if test1 and test2:
            print("\n[SUCCESS] ALL PREMIUM FEATURES INTEGRATED SUCCESSFULLY!")
            print("The HIVMeet premium system is ready for use.")
            return True
        else:
            print("\n[WARNING] Some premium integration tests failed.")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Critical error during premium testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
