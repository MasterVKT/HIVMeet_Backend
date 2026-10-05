"""
Test configuration for HIVMeet backend.
File: hivmeet_backend/test_settings.py
"""
import os

# The host may set DEBUG=False globally. Supply the in-memory broker before
# importing the base settings so Django's production safety gate does not make
# the isolated test configuration impossible to load.
os.environ.setdefault('CELERY_BROKER_URL', 'memory://')
os.environ.setdefault('HIVMEET_DEPLOYMENT_ENVIRONMENT', 'test')

from .settings import *

# Override settings for testing
DEBUG = False
TESTING = True
GEONAMES_CATALOG_REQUIRED = False
SECURE_SSL_REDIRECT = False
TEST_RUNNER = 'hivmeet_backend.test_runner.HIVMeetDiscoverRunner'

# Test database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('HIVMEET_TEST_DB_NAME', 'hivmeet_test'),
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'NAME': os.environ.get('HIVMEET_TEST_DB_NAME', 'hivmeet_test'),
        }
    }
}

# Use in-memory cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Keep tests hermetic and deterministic when a local Redis service is absent.
# Production continues to use the Redis channel layer declared in settings.py.
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
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
PROFILE_PHOTO_STORAGE = 'local'
KYC_STORAGE_BACKEND = 'memory'
KYC_STORAGE_BUCKET = 'test-kyc-private'
KYC_STORAGE_KMS_KEY = 'projects/test/locations/test/keyRings/test/cryptoKeys/test'
KYC_DOCUMENT_RETENTION_DAYS = 1
KYC_QUARANTINE_RETENTION_HOURS = 1
KYC_ANTIVIRUS_BACKEND = 'test'
PROFILE_MEDIA_STORAGE_BACKEND = 'memory'
PROFILE_MEDIA_PRIVATE_BUCKET = 'test-profile-private'
PROFILE_MEDIA_KMS_KEY = 'projects/test/locations/test/keyRings/test/cryptoKeys/profile-media'
PROFILE_MEDIA_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PROFILE_MEDIA_MAX_IMAGE_PIXELS = 1_000_000

# Email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Celery configuration for testing
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# ``memory://`` is a broker transport, not a Celery result backend.  Eager
# tasks still resolve ``app.backend`` when their result is stored, so use the
# supported in-process cache backend to keep data-export tests isolated.
CELERY_RESULT_BACKEND = 'cache+memory://'

# Security settings for testing
SECRET_KEY = 'test-secret-key-for-testing-only'
ALLOWED_HOSTS = ['*']

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'privacy': {
            '()': 'hivmeet_backend.logging_privacy.PrivacyRedactionFilter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['privacy'],
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

# Fast hasher for tests to keep suite deterministic and quick
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Rate limiting disabled for tests
RATELIMIT_ENABLE = False

# MyCoolPay test credentials
MYCOOLPAY_PUBLIC_KEY = 'test_public_key'
MYCOOLPAY_PRIVATE_KEY = 'test_private_key'
MYCOOLPAY_BASE_URL = 'https://my-coolpay.com/api'
MYCOOLPAY_CALLBACK_ALLOWED_IPS = ('127.0.0.1',)
MYCOOLPAY_TRUSTED_PROXY_IPS = ('10.10.10.10',)
MYCOOLPAY_CALLBACK_URL = (
    'https://api.test.hivmeet.example/api/v1/webhooks/payments/mycoolpay/'
)
MYCOOLPAY_SUCCESS_URL = (
    'https://api.test.hivmeet.example/api/v1/subscriptions/'
    'payment-return/success/'
)
MYCOOLPAY_CANCEL_URL = (
    'https://api.test.hivmeet.example/api/v1/subscriptions/'
    'payment-return/cancel/'
)
MYCOOLPAY_FAILURE_URL = (
    'https://api.test.hivmeet.example/api/v1/subscriptions/'
    'payment-return/failure/'
)
MYCOOLPAY_PAYMENT_HOSTS = ('my-coolpay.com',)
MYCOOLPAY_ALLOWED_OPERATORS = ('MCP', 'CM_MOMO', 'CM_OM', 'CARD')
MYCOOLPAY_ENABLED_CURRENCIES = ('XAF', 'EUR')
MYCOOLPAY_DEFAULT_CURRENCY = 'XAF'
MYCOOLPAY_STATUS_MIN_INTERVAL_SECONDS = 5
MYCOOLPAY_RECONCILIATION_MIN_AGE_SECONDS = 60
MYCOOLPAY_RECONCILIATION_MAX_AGE_HOURS = 168
MYCOOLPAY_RECONCILIATION_BATCH_SIZE = 100
