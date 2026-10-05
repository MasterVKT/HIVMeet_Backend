"""
Tests pour normalize_media_url (LOG-05).

Valide tous les cas de normalisation d'URL de photo :
- URL HTTPS externe approuvée (gravatar) → conservée
- URL HTTPS locale → conservée
- Chemin local sans préfixe (profile_photos/...) → /media/profile_photos/...
- Chemin local avec /media/ déjà présent → conservé
- Chemin local avec leading slash (/profile_photos/...) → /media/profile_photos/...
- URL vide/None → None
- Schéma non autorisé (ftp://) → None
- Double préfixe évité (/media/media/...)
"""
import os
import django
from django.test import TestCase, RequestFactory

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.test_settings')
django.setup()

from hivmeet_backend.utils import normalize_media_url


class NormalizeMediaUrlTest(TestCase):
    """Tests unitaires pour normalize_media_url (LOG-05)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/api/v1/test/')

    def test_empty_url_returns_none(self):
        """URL vide retourne None."""
        self.assertIsNone(normalize_media_url(''))
        self.assertIsNone(normalize_media_url(None))
        self.assertIsNone(normalize_media_url('   '))

    def test_https_gravatar_url_preserved(self):
        """URL HTTPS gravatar conservée telle quelle."""
        url = 'https://www.gravatar.com/avatar/abc123?d=identicon&s=400'
        result = normalize_media_url(url, self.request)
        self.assertEqual(result, url)

    def test_https_firebase_url_preserved(self):
        """URL HTTPS Firebase Storage conservée."""
        url = 'https://firebasestorage.googleapis.com/v0/b/bucket/o/photos%2Ftest.jpg'
        result = normalize_media_url(url, self.request)
        self.assertEqual(result, url)

    def test_relative_path_normalized_to_media(self):
        """Chemin relatif sans préfixe → /media/<chemin>."""
        url = 'profile_photos/female_28_1756679314.jpg'
        result = normalize_media_url(url)
        self.assertEqual(result, '/media/profile_photos/female_28_1756679314.jpg')

    def test_relative_path_with_leading_slash_normalized(self):
        """Chemin avec leading slash → /media/<chemin> (pas /profile_photos/)."""
        url = '/profile_photos/male_28_1756679165.jpg'
        result = normalize_media_url(url)
        self.assertEqual(result, '/media/profile_photos/male_28_1756679165.jpg')

    def test_already_media_prefixed_preserved(self):
        """Chemin déjà préfixé /media/ → conservé."""
        url = '/media/profile_photos/test.jpg'
        result = normalize_media_url(url)
        self.assertEqual(result, '/media/profile_photos/test.jpg')

    def test_media_without_leading_slash_no_double_prefix(self):
        """Chemin media/... sans slash → /media/... sans double préfixe."""
        url = 'media/profile_photos/test.jpg'
        result = normalize_media_url(url)
        self.assertEqual(result, '/media/profile_photos/test.jpg')

    def test_unauthorized_scheme_rejected(self):
        """Schéma non autorisé (ftp://) → None."""
        url = 'ftp://evil.server/photos/test.jpg'
        result = normalize_media_url(url)
        self.assertIsNone(result)

    def test_file_scheme_rejected(self):
        """Schéma file:// → None."""
        url = 'file:///etc/passwd'
        result = normalize_media_url(url)
        self.assertIsNone(result)

    def test_absolute_url_with_request_context(self):
        """Avec request context, l'URL devient absolue."""
        url = 'profile_photos/test.jpg'
        result = normalize_media_url(url, self.request)
        self.assertTrue(result.startswith('http://'))
        self.assertIn('/media/profile_photos/test.jpg', result)

    def test_none_url_returns_none(self):
        """None retourne None."""
        self.assertIsNone(normalize_media_url(None))

    def test_external_https_url_without_request_preserved(self):
        """URL HTTPS externe sans request → conservée."""
        url = 'https://storage.googleapis.com/bucket/photos/test.jpg'
        result = normalize_media_url(url)
        self.assertEqual(result, url)