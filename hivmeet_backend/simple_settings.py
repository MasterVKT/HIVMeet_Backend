
from pathlib import Path

SECRET_KEY = 'test-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

BASE_DIR = Path("D:\Projets\HIVMeet\env\hivmeet_backend")

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test.sqlite3',
    }
}

USE_TZ = True
LANGUAGE_CODE = 'fr'

LOGGING_CONFIG = None
