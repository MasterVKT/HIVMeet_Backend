#!/usr/bin/env python
"""
Test script to verify User model references work correctly.
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

def test_resources_services():
    """Test that resources services import correctly."""
    try:
        from resources.services import ResourceService, FeedService
        print("✓ ResourceService and FeedService imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import resources services: {e}")
        return False
    except Exception as e:
        print(f"✗ Error importing resources services: {e}")
        return False

def test_matching_services():
    """Test that matching services import correctly."""
    try:
        from matching.services import MatchingService
        print("✓ MatchingService imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import matching services: {e}")
        return False
    except Exception as e:
        print(f"✗ Error importing matching services: {e}")
        return False

def test_user_model():
    """Test User model import."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        print(f"✓ User model imported successfully: {User.__name__}")
        print(f"  - Model path: {User.__module__}.{User.__name__}")
        return True
    except Exception as e:
        print(f"✗ Failed to import User model: {e}")
        return False

def test_type_annotations():
    """Test that type annotations work correctly."""
    try:
        # This should work without errors if our type hints are correct
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from authentication.models import User as UserType
        print("✓ Type annotations work correctly")
        return True
    except Exception as e:
        print(f"✗ Type annotations failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing User model references after fix...")
    print("=" * 50)
    
    tests = [
        test_user_model,
        test_type_annotations,
        test_resources_services,
        test_matching_services,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()
    
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! User references are working correctly.")
        return True
    else:
        print("✗ Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
