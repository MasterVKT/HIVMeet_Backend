import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

try:
    from resources.services import ResourceService
    print("SUCCESS: ResourceService imported")
except Exception as e:
    print(f"ERROR: {e}")

try:
    from matching.services import MatchingService
    print("SUCCESS: MatchingService imported")
except Exception as e:
    print(f"ERROR: {e}")
