"""
Test script for DailyLikesService.

This script tests the implementation of the daily likes counter fix.
"""
import os
import sys
import django

# Setup Django with test settings to avoid env issues
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['DEBUG'] = 'True'  # Force DEBUG to True for testing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.test_settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from matching.daily_likes_service import DailyLikesService
from matching.models import Like, InteractionHistory
from authentication.models import User
from profiles.models import Profile

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def test_daily_likes_service():
    """Test the DailyLikesService implementation."""
    print_header("TEST: DailyLikesService Implementation")
    
    # Get or create a test user
    try:
        # Try to get Marie (test user)
        test_user = User.objects.filter(email__icontains='marie').first()
        if not test_user:
            test_user = User.objects.filter(email__icontains='test').first()
        if not test_user:
            test_user = User.objects.first()
        
        if not test_user:
            print("❌ No users found in database. Please run population scripts first.")
            return False
        
        print(f"✅ Using test user: {test_user.email}")
        
    except Exception as e:
        print(f"❌ Error getting test user: {e}")
        return False
    
    # Test 1: Initial status
    print_header("TEST 1: Initial Status")
    try:
        status = DailyLikesService.get_status_summary(test_user)
        print(f"Status Summary: {status}")
        
        # Check that the values are valid
        assert status is not None, "Status should not be None"
        assert 'daily_likes_remaining' in status, "Should have daily_likes_remaining"
        assert 'super_likes_remaining' in status, "Should have super_likes_remaining"
        assert 'is_premium' in status, "Should have is_premium"
        assert 'reset_at' in status, "Should have reset_at"
        
        print(f"✅ Initial status retrieved successfully")
        print(f"   - daily_likes_remaining: {status['daily_likes_remaining']}")
        print(f"   - super_likes_remaining: {status['super_likes_remaining']}")
        print(f"   - is_premium: {status['is_premium']}")
        print(f"   - daily_likes_limit: {status['daily_likes_limit']}")
        
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Count likes today
    print_header("TEST 2: Count Likes Today")
    try:
        likes_today = DailyLikesService.count_likes_today(test_user)
        super_likes_today = DailyLikesService.count_super_likes_today(test_user)
        
        print(f"✅ Likes counted successfully")
        print(f"   - Likes sent today: {likes_today}")
        print(f"   - Super likes sent today: {super_likes_today}")
        
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Get likes remaining
    print_header("TEST 3: Get Likes Remaining")
    try:
        likes_remaining = DailyLikesService.get_likes_remaining(test_user)
        super_likes_remaining = DailyLikesService.get_super_likes_remaining(test_user)
        
        print(f"✅ Likes remaining calculated")
        print(f"   - Likes remaining: {likes_remaining}")
        print(f"   - Super likes remaining: {super_likes_remaining}")
        
        # Validate the value is in expected range
        if status['is_premium']:
            assert likes_remaining == -1, f"Premium user should have unlimited likes (-1), got {likes_remaining}"
            print(f"   ✓ Premium user correctly shows unlimited (-1)")
        else:
            assert 0 <= likes_remaining <= 10, f"Free user should have 0-10 likes, got {likes_remaining}"
            print(f"   ✓ Free user correctly shows {likes_remaining}/10 likes")
        
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Can user like
    print_header("TEST 4: Can User Like Check")
    try:
        can_like, error_msg = DailyLikesService.can_user_like(test_user)
        print(f"✅ Can user like check")
        print(f"   - can_like: {can_like}")
        print(f"   - error_msg: {error_msg}")
        
        if can_like:
            print(f"   ✓ User can still like")
        else:
            print(f"   ✓ User has reached daily limit")
            
    except Exception as e:
        print(f"❌ Test 4 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Get next reset time
    print_header("TEST 5: Next Reset Time")
    try:
        reset_time = DailyLikesService.get_next_reset_time()
        print(f"✅ Next reset time calculated")
        print(f"   - Reset at: {reset_time}")
        
        # Validate it's in the future
        assert reset_time > timezone.now(), "Reset time should be in the future"
        print(f"   ✓ Reset time is in the future")
        
    except Exception as e:
        print(f"❌ Test 5 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 6: Log status
    print_header("TEST 6: Log Status")
    try:
        DailyLikesService.log_status(test_user, "TEST_CONTEXT")
        print(f"✅ Log status executed (check logs for output)")
        
    except Exception as e:
        print(f"❌ Test 6 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print_header("ALL TESTS PASSED ✅")
    return True


def test_integration_with_views():
    """Test that the views use DailyLikesService correctly."""
    print_header("TEST: View Integration Check")
    
    try:
        # Import views to check they can be loaded
        from matching import views_discovery
        
        # Check that DailyLikesService is imported in views
        assert hasattr(views_discovery, 'DailyLikesService'), "DailyLikesService should be imported in views"
        
        print(f"✅ DailyLikesService is properly imported in views_discovery")
        
        # Check the endpoint exists
        assert hasattr(views_discovery, 'get_interaction_status'), "get_interaction_status endpoint should exist"
        assert hasattr(views_discovery, 'like_profile'), "like_profile endpoint should exist"
        assert hasattr(views_discovery, 'dislike_profile'), "dislike_profile endpoint should exist"
        assert hasattr(views_discovery, 'superlike_profile'), "superlike_profile endpoint should exist"
        
        print(f"✅ All required endpoints exist")
        print(f"   - get_interaction_status")
        print(f"   - like_profile")
        print(f"   - dislike_profile")
        print(f"   - superlike_profile")
        
        return True
        
    except Exception as e:
        print(f"❌ View integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  HIVMeet Daily Likes Counter Fix - Test Suite")
    print("=" * 60)
    
    # Run tests
    test1_passed = test_daily_likes_service()
    test2_passed = test_integration_with_views()
    
    # Summary
    print_header("TEST SUMMARY")
    print(f"DailyLikesService Tests: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"View Integration Tests:   {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    all_passed = test1_passed and test2_passed
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
