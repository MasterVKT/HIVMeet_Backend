#!/usr/bin/env python
import os
import sys
import django

# Temporairement remplacer la configuration de la base de données
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.simple_settings')

# Créer un fichier de settings simple avec SQLite
import pathlib
settings_content = '''
from hivmeet_backend.settings import *

# Override database to use SQLite for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}

# Disable logging for tests
LOGGING_CONFIG = None

# Disable Firebase for tests
FIREBASE_CREDENTIALS_PATH = None
'''

# Écrire le fichier de settings simple
simple_settings_path = pathlib.Path(__file__).parent / 'hivmeet_backend' / 'simple_settings.py'
with open(simple_settings_path, 'w') as f:
    f.write(settings_content)

print(f"Created simple settings: {simple_settings_path}")

# Maintenant tester
try:
    django.setup()
    print("✓ Django setup successful with SQLite")
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    print(f"✓ User model: {User}")
    
    from resources.services import ResourceService
    print("✓ ResourceService imported successfully")
    
    from matching.services import MatchingService  
    print("✓ MatchingService imported successfully")
    
    print("\n🎉 All User references are working correctly!")
    
except Exception as e:
    import traceback
    print(f"✗ Error: {e}")
    traceback.print_exc()
