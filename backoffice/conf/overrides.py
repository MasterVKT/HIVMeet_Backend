"""Réglages propres au back-office, appliqués par-dessus ceux de l'application.

``apply(globals())`` est appelé par ``backoffice.conf.settings`` (exécution) et
``backoffice.conf.settings_test`` (tests) *après* l'import des réglages de base.
Rien ici n'est jamais importé par ``hivmeet_backend.settings`` : l'application
existante reste strictement inchangée.
"""

from __future__ import annotations

from pathlib import Path

from decouple import Csv, config

# Applications de l'API qui n'ont pas lieu d'être dans le processus back-office.
# - daphne : fournit un runserver ASGI propre à l'API ;
# - corsheaders / drf_yasg : surface API (CORS, Swagger) ;
# - debug_toolbar : incompatible avec la CSP stricte ;
# - django.contrib.admin : l'admin Django n'est pas monté ici (repli superuser
#   uniquement dans le processus de l'API, inchangé).
REMOVED_APPS = frozenset({
    'daphne',
    'corsheaders',
    'drf_yasg',
    'debug_toolbar',
    'django.contrib.admin',
})

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'backoffice.middleware.BackofficeSecurityMiddleware',
]


def apply(namespace: dict) -> None:
    """Modifie ``namespace`` (les globals du module de settings appelant)."""
    base_dir = Path(namespace['BASE_DIR'])
    debug = bool(namespace['DEBUG'])

    namespace['INSTALLED_APPS'] = [
        app for app in namespace['INSTALLED_APPS'] if app not in REMOVED_APPS
    ] + ['backoffice']
    namespace['MIDDLEWARE'] = list(MIDDLEWARE)
    namespace['ROOT_URLCONF'] = 'backoffice.conf.urls'
    namespace['WSGI_APPLICATION'] = 'backoffice.conf.wsgi.application'

    # Cookies distincts de ceux de l'API, limités au chemin du back-office.
    namespace['SESSION_COOKIE_NAME'] = 'bo_sessionid'
    namespace['SESSION_COOKIE_PATH'] = '/backoffice/'
    namespace['SESSION_COOKIE_SAMESITE'] = 'Strict'
    namespace['SESSION_COOKIE_HTTPONLY'] = True
    namespace['SESSION_COOKIE_SECURE'] = not debug
    namespace['CSRF_COOKIE_NAME'] = 'bo_csrftoken'
    namespace['CSRF_COOKIE_PATH'] = '/backoffice/'
    namespace['CSRF_COOKIE_SAMESITE'] = 'Strict'
    namespace['CSRF_COOKIE_HTTPONLY'] = True
    namespace['CSRF_COOKIE_SECURE'] = not debug
    namespace['CSRF_TRUSTED_ORIGINS'] = config(
        'BACKOFFICE_CSRF_TRUSTED_ORIGINS', default='', cast=Csv(),
    )
    namespace['LANGUAGE_COOKIE_NAME'] = 'bo_language'
    namespace['SESSION_SAVE_EVERY_REQUEST'] = True
    namespace['X_FRAME_OPTIONS'] = 'DENY'

    # Derrière un proxy TLS (nginx) : opt-in explicite.
    if config('BACKOFFICE_TRUST_PROXY_SSL_HEADER', default=False, cast=bool):
        namespace['SECURE_PROXY_SSL_HEADER'] = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Fichiers statiques propres (collectstatic séparé de l'API).
    namespace['STATICFILES_DIRS'] = []
    namespace['STATIC_ROOT'] = Path(config(
        'BACKOFFICE_STATIC_ROOT', default=str(base_dir / 'staticfiles_backoffice'),
    ))

    # Paramètres du back-office (secondes).
    namespace['BACKOFFICE_IDLE_SECONDS'] = config('BACKOFFICE_IDLE_SECONDS', default=900, cast=int)
    namespace['BACKOFFICE_MAX_SESSION_SECONDS'] = config(
        'BACKOFFICE_MAX_SESSION_SECONDS', default=28800, cast=int,
    )
    namespace['BACKOFFICE_PENDING_SECONDS'] = config('BACKOFFICE_PENDING_SECONDS', default=300, cast=int)
    namespace['BACKOFFICE_STEP_UP_SECONDS'] = config('BACKOFFICE_STEP_UP_SECONDS', default=300, cast=int)
    namespace['BACKOFFICE_LOCKOUT_WINDOW_SECONDS'] = config(
        'BACKOFFICE_LOCKOUT_WINDOW_SECONDS', default=900, cast=int,
    )
    namespace['BACKOFFICE_LOGIN_ACCOUNT_LIMIT'] = config(
        'BACKOFFICE_LOGIN_ACCOUNT_LIMIT', default=5, cast=int,
    )
    namespace['BACKOFFICE_LOGIN_IP_LIMIT'] = config('BACKOFFICE_LOGIN_IP_LIMIT', default=20, cast=int)
    # X-Forwarded-For n'est lu que si un proxy de confiance l'ajoute en dernier.
    namespace['BACKOFFICE_TRUST_X_FORWARDED_FOR'] = config(
        'BACKOFFICE_TRUST_X_FORWARDED_FOR', default=False, cast=bool,
    )
