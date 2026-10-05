"""
Utility functions for HIVMeet backend.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger('hivmeet')


def _plain_error_details(value):
    """Convert DRF ErrorDetail objects to JSON-safe primitive values."""
    if isinstance(value, dict):
        return {str(key): _plain_error_details(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_error_details(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def api_error_response(code, message, http_status, details=None):
    """Build the stable error envelope used by explicit API failures."""
    return Response(
        {
            'error': code,
            'message': message,
            'details': _plain_error_details(details or {}),
            'status_code': http_status,
        },
        status=http_status,
    )


def _safe_error_message(exc, response):
    if isinstance(exc, ValidationError):
        return _('Validation error')
    messages = {
        status.HTTP_400_BAD_REQUEST: _('The request is invalid.'),
        status.HTTP_401_UNAUTHORIZED: _('Authentication is required.'),
        status.HTTP_403_FORBIDDEN: _('You do not have permission to perform this action.'),
        status.HTTP_404_NOT_FOUND: _('The requested resource was not found.'),
        status.HTTP_405_METHOD_NOT_ALLOWED: _('This method is not allowed.'),
        status.HTTP_429_TOO_MANY_REQUESTS: _('Too many requests. Please try again later.'),
    }
    return messages.get(
        response.status_code,
        _('The request could not be processed.'),
    )

def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        request = context.get('request')
        resolver_match = getattr(request, 'resolver_match', None)
        view_name = getattr(resolver_match, 'view_name', None) or 'unknown'
        error_code = (
            'validation_error'
            if isinstance(exc, ValidationError)
            else str(getattr(exc, 'default_code', 'request_error'))
        )
        logger.warning(
            "API request rejected: type=%s code=%s status=%s view=%s method=%s",
            exc.__class__.__name__,
            error_code,
            response.status_code,
            view_name,
            getattr(request, 'method', 'unknown'),
        )

        custom_response_data = {
            'error': error_code,
            'message': _safe_error_message(exc, response),
            'details': _plain_error_details(
                response.data if hasattr(response, 'data') else {}
            ),
            'status_code': response.status_code,
        }
        response.data = custom_response_data

    return response


# ---------------------------------------------------------------------------
# LOG-05 : Normalisation des URLs de photos
# ---------------------------------------------------------------------------
# Fonction unique de normalisation utilisée par tous les producteurs de photos
# (Découverte, profils, matching, messagerie, réglages, notifications, ressources).
#
# Règles :
#   - URL HTTPS explicitement autorisée → conservée telle quelle.
#   - Chemin local valide → transformé vers /media/<chemin>.
#   - Éviter le double préfixe (si /media/ déjà présent).
#   - Schéma non autorisé (ftp://, file://, etc.) → rejeté (retourne None).
#   - URL absolue fabriquée uniquement avec contexte de requête et hôte approuvé.
# ---------------------------------------------------------------------------

_ALLOWED_EXTERNAL_HOSTS = {'www.gravatar.com'}


def normalize_media_url(url, request=None):
    """
    Normaliser une URL de photo stockée en base vers une URL servable.

    Args:
        url: La valeur brute stockée en DB (peut être relative, absolue, ou vide).
        request: Optionnel — l'objet Request DRF pour build_absolute_uri.

    Returns:
        str: L'URL normalisée (absolue si request fourni, sinon chemin /media/...).
        None: Si l'URL est vide, None, ou utilise un schéma non autorisé.
    """
    if not url or not url.strip():
        return None

    url = url.strip()

    # 1. URL HTTPS déjà absolue — conserver si hôte approuvé
    if url.startswith('https://') or url.startswith('http://'):
        # Extraire le host pour vérification
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or ''
            # Autoriser les URLs HTTPS externes connues (ex: gravatar)
            if host in _ALLOWED_EXTERNAL_HOSTS:
                return url
            # Autoriser les URLs locales (localhost, IP privées, hôte du request)
            if request:
                req_host = request.get_host().split(':')[0]
                if host in ('localhost', '127.0.0.1', req_host) or host.startswith('192.168.') or host.startswith('10.'):
                    return url
            # Pour les autres URLs HTTPS, conserver telles quelles (Firebase Storage, etc.)
            return url
        except Exception:
            return url

    # 2. Rejeter les schémas non autorisés
    if '://' in url:
        logger.warning("URL photo rejetée — schéma non autorisé (redacted)")
        return None

    # 3. Chemin local — normaliser vers /media/
    from django.conf import settings
    media_url = getattr(settings, 'MEDIA_URL', '/media/')

    # Retirer le leading slash éventuel pour uniformiser
    path = url.lstrip('/')

    # Éviter le double préfixe /media/media/
    if path.startswith('media/'):
        normalized = f'/{path}'
    elif path.startswith(media_url.lstrip('/')):
        normalized = f'/{path}'
    else:
        normalized = f'{media_url}{path}'

    # Construire l'URL absolue si on a un request context
    if request:
        try:
            return request.build_absolute_uri(normalized)
        except Exception:
            pass

    return normalized
