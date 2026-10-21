"""WSGI du back-office : ``gunicorn backoffice.conf.wsgi``."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backoffice.conf.settings')

application = get_wsgi_application()
