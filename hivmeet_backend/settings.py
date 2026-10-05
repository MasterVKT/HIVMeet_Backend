"""
Django settings for HIVMeet backend project.
"""

from pathlib import Path
from datetime import timedelta
import os
from decouple import config, Csv
import dj_database_url
from hivmeet_backend.kyc_runtime import (
    validate_kyc_runtime_gate,
    validate_private_storage_runtime_gate,
)

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-your-secret-key-here')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default='True') == 'True'

# KYC permissions are mandatory in this codebase. A production process must
# therefore fail before serving traffic unless an authorised deploy supplies
# the explicit legal/DPO approval gate and its non-sensitive reference.
HIVMEET_DEPLOYMENT_ENVIRONMENT = config(
    'HIVMEET_DEPLOYMENT_ENVIRONMENT',
    default='development' if DEBUG else 'production',
).strip().lower()
KYC_SOCIAL_ACCESS_ENFORCEMENT = config(
    'KYC_SOCIAL_ACCESS_ENFORCEMENT',
    default='enforced' if DEBUG else 'disabled',
).strip().lower()
KYC_PRODUCTION_LEGAL_APPROVAL = config(
    'KYC_PRODUCTION_LEGAL_APPROVAL', default=False, cast=bool,
)
KYC_PRODUCTION_LEGAL_APPROVAL_REFERENCE = config(
    'KYC_PRODUCTION_LEGAL_APPROVAL_REFERENCE', default='',
).strip()
validate_kyc_runtime_gate(
    deployment_environment=HIVMEET_DEPLOYMENT_ENVIRONMENT,
    enforcement_mode=KYC_SOCIAL_ACCESS_ENFORCEMENT,
    legal_approval=KYC_PRODUCTION_LEGAL_APPROVAL,
    legal_approval_reference=KYC_PRODUCTION_LEGAL_APPROVAL_REFERENCE,
)

# Production readiness gate: an empty city catalogue would make manual location unusable.
GEONAMES_CATALOG_REQUIRED = config('GEONAMES_CATALOG_REQUIRED', default=not DEBUG, cast=bool)

# Secure default.  A controlled rollout can temporarily set this to False
# while the registration client is being distributed, then must turn it back
# on to reject Firebase-only account creation.
HIVMEET_REQUIRE_EXPLICIT_REGISTRATION = config(
    'HIVMEET_REQUIRE_EXPLICIT_REGISTRATION', default=True, cast=bool,
)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,10.0.2.2,0.0.0.0,192.168.1.118,*', cast=Csv())

# Application definition
INSTALLED_APPS = [
    # Daphne ASGI server (must be first)
    'daphne',
    
    # Local apps (must be before Django apps when using custom User model)
    'authentication',
    
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',
    'channels',
    # 'rosetta',
    
    # Other local apps (to be added)
    'profiles',
    'matching',
    'messaging',
    # 'verification',
    'subscriptions',
    'resources',
    'notifications',
]

AUTH_USER_MODEL = 'authentication.User'


# Authentication backends
AUTHENTICATION_BACKENDS = [
    'authentication.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Frontend URL for email links
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'hivmeet_backend.security.RateLimitMiddleware',  # Middleware de limitation de debit
    'subscriptions.middleware.PremiumRequiredMiddleware',
    'hivmeet_backend.middleware.PremiumStatusMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
]

if DEBUG:
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
    INSTALLED_APPS += ['debug_toolbar']

ROOT_URLCONF = 'hivmeet_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

WSGI_APPLICATION = 'hivmeet_backend.wsgi.application'

# ASGI application for WebSocket support
ASGI_APPLICATION = 'hivmeet_backend.asgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='postgresql://postgres:postgres@localhost:5432/hivmeet_db')
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# Par defaut FR, mais `LocaleMiddleware` respecte `Accept-Language`
LANGUAGE_CODE = 'fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Languages supported
LANGUAGES = [
    ('fr', 'Francais'),
    ('en', 'English'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
#MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Local media is permitted for profile photos only while developing. A
# production deployment must use the explicitly configured object provider.
PROFILE_PHOTO_STORAGE = config(
    'PROFILE_PHOTO_STORAGE',
    default='local' if DEBUG else 'firebase',
)

# Private KYC and profile-media storage.  These values identify infrastructure
# only; credentials remain workload-identity / service-account material outside
# the repository.  There is deliberately no production fallback to local or a
# public Firebase bucket.
KYC_STORAGE_BACKEND = config(
    'KYC_STORAGE_BACKEND', default='memory' if DEBUG else 'gcs',
).strip().lower()
KYC_STORAGE_BUCKET = config('KYC_STORAGE_BUCKET', default='').strip()
KYC_STORAGE_KMS_KEY = config('KYC_STORAGE_KMS_KEY', default='').strip()
PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT = config(
    'PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT', default='',
).strip()
KYC_STORAGE_UPLOAD_TTL_SECONDS = config(
    'KYC_STORAGE_UPLOAD_TTL_SECONDS', default=1800, cast=int,
)
KYC_QUARANTINE_RETENTION_HOURS = config(
    'KYC_QUARANTINE_RETENTION_HOURS', default=24, cast=int,
)
# A legal/DPO-approved value is mandatory outside development and test.
KYC_DOCUMENT_RETENTION_DAYS = config(
    'KYC_DOCUMENT_RETENTION_DAYS', default=0, cast=int,
)
KYC_ANTIVIRUS_BACKEND = config(
    'KYC_ANTIVIRUS_BACKEND', default='test' if DEBUG else 'disabled',
).strip().lower()
KYC_CLAMAV_BINARY = config('KYC_CLAMAV_BINARY', default='clamscan').strip()
KYC_SCAN_TIMEOUT_SECONDS = config('KYC_SCAN_TIMEOUT_SECONDS', default=30, cast=int)
KYC_MAX_IMAGE_PIXELS = config('KYC_MAX_IMAGE_PIXELS', default=24_000_000, cast=int)
KYC_MAX_PDF_PAGES = config('KYC_MAX_PDF_PAGES', default=25, cast=int)
KYC_MAX_PDF_OBJECTS = config('KYC_MAX_PDF_OBJECTS', default=5_000, cast=int)

PROFILE_MEDIA_STORAGE_BACKEND = config(
    'PROFILE_MEDIA_STORAGE_BACKEND', default='memory' if DEBUG else 'gcs',
).strip().lower()
PROFILE_MEDIA_PRIVATE_BUCKET = config('PROFILE_MEDIA_PRIVATE_BUCKET', default='').strip()
PROFILE_MEDIA_KMS_KEY = config('PROFILE_MEDIA_KMS_KEY', default='').strip()
PROFILE_MEDIA_MAX_UPLOAD_BYTES = config(
    'PROFILE_MEDIA_MAX_UPLOAD_BYTES', default=5 * 1024 * 1024, cast=int,
)
PROFILE_MEDIA_MAX_IMAGE_PIXELS = config(
    'PROFILE_MEDIA_MAX_IMAGE_PIXELS', default=25_000_000, cast=int,
)
validate_private_storage_runtime_gate(
    deployment_environment=HIVMEET_DEPLOYMENT_ENVIRONMENT,
    kyc_storage_backend=KYC_STORAGE_BACKEND,
    profile_media_storage_backend=PROFILE_MEDIA_STORAGE_BACKEND,
    kyc_bucket=KYC_STORAGE_BUCKET,
    profile_media_bucket=PROFILE_MEDIA_PRIVATE_BUCKET,
    kyc_kms_key=KYC_STORAGE_KMS_KEY,
    profile_media_kms_key=PROFILE_MEDIA_KMS_KEY,
    runtime_service_account=PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT,
    kyc_document_retention_days=KYC_DOCUMENT_RETENTION_DAYS,
    antivirus_backend=KYC_ANTIVIRUS_BACKEND,
    kyc_storage_upload_ttl_seconds=KYC_STORAGE_UPLOAD_TTL_SECONDS,
    kyc_quarantine_retention_hours=KYC_QUARANTINE_RETENTION_HOURS,
    kyc_scan_timeout_seconds=KYC_SCAN_TIMEOUT_SECONDS,
    kyc_max_image_pixels=KYC_MAX_IMAGE_PIXELS,
    kyc_max_pdf_pages=KYC_MAX_PDF_PAGES,
    kyc_max_pdf_objects=KYC_MAX_PDF_OBJECTS,
    profile_media_max_upload_bytes=PROFILE_MEDIA_MAX_UPLOAD_BYTES,
    profile_media_max_image_pixels=PROFILE_MEDIA_MAX_IMAGE_PIXELS,
    kyc_clamav_binary=KYC_CLAMAV_BINARY,
)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'EXCEPTION_HANDLER': 'hivmeet_backend.utils.custom_exception_handler',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS settings - Configuration pour Flutter et developpement
CORS_ALLOW_ALL_ORIGINS = True  # Temporaire pour diagnostic/developpement
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8080',
    'http://10.0.2.2:8000',
    'http://127.0.0.1:8000',
    'http://0.0.0.0:8000',

]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-firebase-token',  # Pour Flutter Firebase
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH', 
    'POST',
    'PUT',
]

# Permettre toutes les origines pour Flutter (developpement)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://10\.0\.2\..*",      # Emulateur Android
    r"^http://127\.0\.0\.1:.*",   # Localhost
    r"^http://localhost:.*",      # Localhost alternative
]

# Celery Configuration
# Note: Les settings effectifs sont définis plus bas (ligne ~421) avec
# config() pour permettre l'override via variables d'environnement.
# En dev, CELERY_TASK_ALWAYS_EAGER=True exécute les tasks dans le process
# Django — le cache LocMemCache est donc partagé avec le ConversationConsumer.
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'expire-kyc-upload-intents': {
        'task': 'profiles.tasks.expire_kyc_upload_intents',
        'schedule': crontab(minute='*/5'),
    },
    'purge-due-kyc-documents': {
        'task': 'profiles.tasks.purge_due_kyc_documents',
        'schedule': crontab(minute='*/10'),
    },
    'expire-verified-kyc-attempts': {
        'task': 'profiles.tasks.expire_verified_kyc_attempts',
        'schedule': crontab(minute='*/15'),
    },
    'reconcile-pending-mycoolpay-payments': {
        'task': 'subscriptions.tasks.reconcile_pending_mycoolpay_payments',
        'schedule': crontab(minute='*/5'),
    },
    'check-subscription-expirations': {
        'task': 'subscriptions.tasks.check_subscription_expirations',
        'schedule': crontab(minute=0),  # Every hour
    },
    'send-expiration-reminders': {
        'task': 'subscriptions.tasks.send_expiration_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'reset-daily-counters': {
        'task': 'subscriptions.tasks.reset_daily_counters',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'reset-monthly-counters': {
        'task': 'subscriptions.tasks.reset_monthly_counters',
        'schedule': crontab(hour=0, minute=30),  # Daily at 00:30
    },
    'clean-old-webhook-events': {
        'task': 'subscriptions.tasks.clean_old_webhook_events',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),  # Weekly on Monday at 2 AM
    },
}

# Firebase configuration

# Configuration Firebase (restaurer chemin original)
FIREBASE_CREDENTIALS_PATH = config(
    'FIREBASE_CREDENTIALS_PATH', 
    default=str(BASE_DIR / 'credentials' / 'hivmeet_firebase_credentials.json')
)

FIREBASE_STORAGE_BUCKET = config(
    'FIREBASE_STORAGE_BUCKET', 
    default='hivmeet-f76f8.firebasestorage.app'
)

# Email configuration
EMAIL_BACKEND = config(
    'EMAIL_BACKEND', 
    default='django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL', 
    default='HIVMeet <noreply@hivmeet.com>'
)
EMAIL_SUBJECT_PREFIX = '[HIVMeet] '

# MyCoolPay Paylink configuration. Secrets stay server-side.
MYCOOLPAY_PUBLIC_KEY = config('MYCOOLPAY_PUBLIC_KEY', default='')
MYCOOLPAY_PRIVATE_KEY = config('MYCOOLPAY_PRIVATE_KEY', default='')
MYCOOLPAY_BASE_URL = config(
    'MYCOOLPAY_BASE_URL',
    default='https://my-coolpay.com/api',
)
MYCOOLPAY_CALLBACK_URL = config('MYCOOLPAY_CALLBACK_URL', default='').strip()
MYCOOLPAY_SUCCESS_URL = config('MYCOOLPAY_SUCCESS_URL', default='').strip()
MYCOOLPAY_CANCEL_URL = config('MYCOOLPAY_CANCEL_URL', default='').strip()
MYCOOLPAY_FAILURE_URL = config('MYCOOLPAY_FAILURE_URL', default='').strip()
MYCOOLPAY_CALLBACK_ALLOWED_IPS = tuple(
    value.strip()
    for value in config(
        'MYCOOLPAY_CALLBACK_ALLOWED_IPS',
        default='',
    ).split(',')
    if value.strip()
)
MYCOOLPAY_TRUSTED_PROXY_IPS = tuple(
    value.strip()
    for value in config('MYCOOLPAY_TRUSTED_PROXY_IPS', default='').split(',')
    if value.strip()
)
MYCOOLPAY_PAYMENT_HOSTS = tuple(
    value.strip().lower()
    for value in config(
        'MYCOOLPAY_PAYMENT_HOSTS',
        default='my-coolpay.com',
    ).split(',')
    if value.strip()
)
MYCOOLPAY_ALLOWED_OPERATORS = tuple(
    value.strip()
    for value in config(
        'MYCOOLPAY_ALLOWED_OPERATORS',
        default='MCP,CM_MOMO,CM_OM,CARD',
    ).split(',')
    if value.strip()
)
MYCOOLPAY_CONNECT_TIMEOUT = config(
    'MYCOOLPAY_CONNECT_TIMEOUT', default=5, cast=int
)
MYCOOLPAY_READ_TIMEOUT = config(
    'MYCOOLPAY_READ_TIMEOUT', default=20, cast=int
)
MYCOOLPAY_ENABLED_CURRENCIES = tuple(
    value.strip().upper()
    for value in config(
        'MYCOOLPAY_ENABLED_CURRENCIES',
        default='XAF,EUR',
    ).split(',')
    if value.strip()
)
MYCOOLPAY_DEFAULT_CURRENCY = config(
    'MYCOOLPAY_DEFAULT_CURRENCY',
    default='XAF',
).strip().upper()
MYCOOLPAY_STATUS_MIN_INTERVAL_SECONDS = config(
    'MYCOOLPAY_STATUS_MIN_INTERVAL_SECONDS', default=5, cast=int
)
MYCOOLPAY_RECONCILIATION_MIN_AGE_SECONDS = config(
    'MYCOOLPAY_RECONCILIATION_MIN_AGE_SECONDS', default=60, cast=int
)
MYCOOLPAY_RECONCILIATION_MAX_AGE_HOURS = config(
    'MYCOOLPAY_RECONCILIATION_MAX_AGE_HOURS', default=168, cast=int
)
MYCOOLPAY_RECONCILIATION_BATCH_SIZE = config(
    'MYCOOLPAY_RECONCILIATION_BATCH_SIZE', default=100, cast=int
)

# Cache configuration (Redis for production, LocMemCache for dev)
if config('USE_REDIS_CACHE', default='False') == 'True':
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# Django Channels configuration
_REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379/0')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [_REDIS_URL],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}

# Fallback in-memory channel layer for development
CHANNEL_LAYERS_FALLBACK = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}


def _redis_is_reachable(redis_url, timeout=0.2):
    """Quick TCP probe — avoids importing/constructing a real client at
    import time. Only used to pick a channel layer backend in DEBUG."""
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(redis_url)
        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or 6379
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


if DEBUG and not _redis_is_reachable(_REDIS_URL):
    # Local dev without a running Redis server: degrade to the in-process
    # channel layer instead of letting every WebSocket handshake fail with
    # `ConnectionRefusedError` (channels_redis has no built-in fallback).
    # Never applies outside DEBUG — production must fail loudly if its
    # configured Redis is unreachable.
    CHANNEL_LAYERS = CHANNEL_LAYERS_FALLBACK

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# In production, use real email service:
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = config('EMAIL_HOST')
# EMAIL_PORT = config('EMAIL_PORT', cast=int)
# EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
# EMAIL_HOST_USER = config('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'privacy': {
            '()': 'hivmeet_backend.logging_privacy.PrivacyRedactionFilter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['privacy'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'hivmeet': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# GDPR account-deletion grace period (hours)
HIVMEET_DELETION_GRACE_HOURS = config('HIVMEET_DELETION_GRACE_HOURS', default=72, cast=int)

# Additive rollout gate for the shared monthly Free allowance.  Keep disabled
# until a compatible backend migration and Flutter build are deployed together.
HIVMEET_FREE_MATCH_ACCESS_ENABLED = config(
    'HIVMEET_FREE_MATCH_ACCESS_ENABLED', default=False, cast=bool
)

# Celery configuration
# LOG-07 : comportement explicite par environnement.
#
# Politique :
#   - tests unitaires (test_settings.py) : eager déterministe (déjà configuré)
#   - dev sans broker : eager explicite, broker memory://, sans prétendre tester
#     un worker réel
#   - recette/staging : Redis accessible, worker et beat démarrés, eager=False
#   - production : URL broker via secret, eager=False, pas de fallback memory
#
# Le fallback memory:// est interdit en production car il masque les pannes
# de Redis et ne teste pas la topologie multi-process réelle.
_env_broker_url = config('CELERY_BROKER_URL', default='')
_env_is_prod = not DEBUG

if _env_broker_url:
    # URL explicite fournie via variable d'environnement (recette/prod)
    CELERY_BROKER_URL = _env_broker_url
    CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default=_env_broker_url)
    CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default='False') == 'True'
elif _env_is_prod:
    # Production sans CELERY_BROKER_URL → erreur au démarrage.
    # Ne jamais silencieusement fallback sur memory:// en production.
    raise RuntimeError(
        'CELERY_BROKER_URL est obligatoire en production (DEBUG=False). '
        'Configurer la variable d\'environnement CELERY_BROKER_URL avec '
        'l\'URL du broker Redis (ex: redis://host:6379/0).'
    )
else:
    # Dev local sans broker explicite : eager explicite + memory.
    # Ceci ne prétend PAS tester un worker réel — utiliser Redis pour la recette.
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = 'rpc://'
    CELERY_TASK_ALWAYS_EAGER = True

CELERY_TASK_EAGER_PROPAGATES = True

# Security settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
