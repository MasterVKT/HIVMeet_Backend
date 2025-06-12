#!/usr/bin/env python
import os
import sys
import traceback

# Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

try:
    import django
    print("✓ Django imported")
    django.setup()
    print("✓ Django setup completed")
except Exception as e:
    print(f"✗ Django setup failed: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    print(f"✓ User model: {User}")
except Exception as e:
    print(f"✗ User model import failed: {e}")
    traceback.print_exc()

try:
    from resources.services import ResourceService
    print("✓ ResourceService imported successfully")
except Exception as e:
    print(f"✗ ResourceService import failed: {e}")
    traceback.print_exc()

try:
    from matching.services import MatchingService
    print("✓ MatchingService imported successfully")
except Exception as e:
    print(f"✗ MatchingService import failed: {e}")
    traceback.print_exc()

print("Test completed.")
