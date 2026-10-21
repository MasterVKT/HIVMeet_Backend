"""Réglages d'exécution du back-office (processus séparé de l'API).

Usage : ``python manage.py runserver 8001 --settings=backoffice.conf.settings``
"""

from hivmeet_backend.settings import *  # noqa: F401,F403

from backoffice.conf.overrides import apply as _apply

_apply(globals())
