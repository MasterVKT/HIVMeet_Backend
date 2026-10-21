"""Internationalisation FR/EN: français par défaut, catalogue complet et compilé."""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import translation

from .helpers import BackofficeTestCase

PO_FILE = Path(settings.BASE_DIR) / 'backoffice' / 'locale' / 'fr' / 'LC_MESSAGES' / 'django.po'
MO_FILE = PO_FILE.with_suffix('.mo')


def parse_po(path):
    """Entrées ``msgid``/``msgstr`` sur une seule ligne (hors en-tête)."""
    entries = {}
    text = path.read_text(encoding='utf-8')
    for block in text.split('\n\n'):
        msgid = re.search(r'^msgid "(.*)"$', block, re.MULTILINE)
        msgstr = re.search(r'^msgstr "(.*)"$', block, re.MULTILINE)
        if msgid and msgstr and msgid.group(1):
            entries[msgid.group(1)] = msgstr.group(1)
    return entries


class LanguageTests(BackofficeTestCase):
    def test_french_is_the_default_language(self):
        response = self.client_class().get(reverse('backoffice:login'))
        self.assertContains(response, 'lang="fr"')
        self.assertContains(response, 'Se connecter')
        self.assertContains(response, 'Mot de passe')

    def test_english_is_served_on_request(self):
        response = self.client.get(reverse('backoffice:login'))
        self.assertContains(response, 'lang="en"')
        self.assertContains(response, 'Sign in')
        self.assertNotContains(response, 'Se connecter')

    def test_generic_error_is_translated(self):
        french = self.client_class().post(reverse('backoffice:login'), {'email': 'a@b.test', 'password': 'x'})
        self.assertEqual(french.context['error'], 'Identifiants invalides ou accès non autorisé.')


class CatalogTests(SimpleTestCase):
    def test_every_message_is_translated(self):
        entries = parse_po(PO_FILE)
        self.assertGreaterEqual(len(entries), 31)
        missing = [msgid for msgid, msgstr in entries.items() if not msgstr]
        self.assertEqual(missing, [])

    def test_compiled_catalog_matches_the_po_file(self):
        self.assertTrue(MO_FILE.exists(), 'django.mo must be committed (msgfmt).')
        with translation.override('fr'):
            for msgid, msgstr in parse_po(PO_FILE).items():
                if '%(' in msgid:
                    continue  # chaînes paramétrées couvertes par les tests de rendu
                with self.subTest(msgid=msgid):
                    self.assertEqual(translation.gettext(msgid), msgstr.replace('\\"', '"'))
