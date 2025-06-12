"""
Test configuration for HIVMeet backend.
File: hivmeet_backend/test_settings.py
"""
from .settings import *
import os

# Override settings for testing
DEBUG = False
TESTING = True

# Test database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'hivmeet_test',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'NAME': 'hivmeet_test',
        }
    }
}

# Use in-memory cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Media files for testing
MEDIA_ROOT = os.path.join(BASE_DIR, 'test_media')

# Email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Celery configuration for testing
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Security settings for testing
SECRET_KEY = 'test-secret-key-for-testing-only'
ALLOWED_HOSTS = ['*']

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'hivmeet': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Password validation - simplified for tests
AUTH_PASSWORD_VALIDATORS = []

# Rate limiting disabled for tests
RATELIMIT_ENABLE = False

# MyCoolPay test credentials
MYCOOLPAY_API_KEY = 'test_api_key'
MYCOOLPAY_API_SECRET = 'test_api_secret'
MYCOOLPAY_BASE_URL = 'http://mock-mycoolpay.test'
MYCOOLPAY_WEBHOOK_SECRET = 'test_webhook_secret'