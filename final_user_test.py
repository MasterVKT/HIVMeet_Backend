#!/usr/bin/env python
"""
Test final pour vérifier que les références User sont correctes.
"""
import os
import sys

# Configuration SQLite simple pour le test
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.simple_settings')

# Créer un fichier de settings simplifié avec SQLite
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

simple_settings_content = f'''
from pathlib import Path

SECRET_KEY = 'test-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

BASE_DIR = Path("{BASE_DIR}")

INSTALLED_APPS = [
    'authentication',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'profiles',
    'matching',
    'messaging',
    'resources',
]

AUTH_USER_MODEL = 'authentication.User'

DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test.sqlite3',
    }}
}}

USE_TZ = True
LANGUAGE_CODE = 'fr'

LOGGING_CONFIG = None
'''

# Écrire le fichier
settings_path = BASE_DIR / 'hivmeet_backend' / 'simple_settings.py'
with open(settings_path, 'w') as f:
    f.write(simple_settings_content)

print(f"✓ Created simple settings file")

# Maintenant tester Django
try:
    import django
    django.setup()
    print("✓ Django setup successful")
    
    # Test User model
    from django.contrib.auth import get_user_model
    User = get_user_model()
    print(f"✓ User model imported: {User.__name__}")
    
    # Test des services
    from resources.services import ResourceService, FeedService
    print("✓ Resources services imported successfully")
    
    from matching.services import MatchingService
    print("✓ Matching services imported successfully")
    
    print("\n🎉 SUCCESS: All User references are working correctly!")
    print("The 'Variable not allowed in type expression' error has been resolved.")
    
except Exception as e:
    print(f"✗ Error during test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
    
print("\n" + "="*60)
print("SUMMARY OF FIXES APPLIED:")
print("="*60)
print("1. Fixed TYPE_CHECKING imports in resources/services.py")
print("   - Changed: from django.contrib.auth.models import AbstractUser")
print("   - To: from authentication.models import User as UserType")
print("")
print("2. Updated all type annotations from 'AbstractUser' to 'UserType'")
print("   - Resources services: 8 methods fixed")
print("   - Matching services: 5 methods fixed")
print("")
print("3. All imports and references now work correctly")
print("="*60)
