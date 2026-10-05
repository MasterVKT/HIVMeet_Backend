import logging

from django.test import SimpleTestCase

from hivmeet_backend.logging_privacy import PrivacyRedactionFilter, redact_log_text


class PrivacyLoggingTests(SimpleTestCase):
    def test_redacts_identifiers_profile_fields_urls_and_coordinates(self):
        raw = (
            "user=alice@example.com "
            "id=8b1a9953-c461-4f36-9c2b-2a2f9c379f10 "
            "display_name=Alice location=Douala latitude=4.0511 "
            "photo_url=https://cdn.example.test/private/alice.jpg?token=secret "
            "callback=https://api.example.test/payment/result "
            "phone=+237699887766"
        )

        redacted = redact_log_text(raw)

        for secret in (
            'alice@example.com',
            '8b1a9953-c461-4f36-9c2b-2a2f9c379f10',
            'Alice',
            'Douala',
            '4.0511',
            '/private/alice.jpg',
            '/payment/result',
            '+237699887766',
        ):
            self.assertNotIn(secret, redacted)
        self.assertIn('<email:', redacted)
        self.assertIn('<id:', redacted)
        self.assertIn('<url:api.example.test>', redacted)

    def test_redacts_bare_jwt_or_bearer_token(self):
        jwt = (
            'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.'
            'dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        )
        redacted = redact_log_text(f'Authorization: Bearer {jwt}')

        self.assertNotIn(jwt, redacted)
        self.assertIn('<token:redacted>', redacted)

    def test_filter_redacts_interpolated_logging_arguments(self):
        record = logging.LogRecord(
            name='hivmeet.test',
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='Authenticated user=%s',
            args=('alice@example.com',),
            exc_info=None,
        )

        self.assertTrue(PrivacyRedactionFilter().filter(record))
        self.assertNotIn('alice@example.com', record.getMessage())
        self.assertEqual(record.args, ())

    def test_filter_redacts_exception_text_before_formatter_uses_it(self):
        try:
            raise ValueError(
                'profile 8b1a9953-c461-4f36-9c2b-2a2f9c379f10 '
                'for alice@example.com'
            )
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name='hivmeet.test',
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg='operation failed',
            args=(),
            exc_info=exc_info,
        )
        PrivacyRedactionFilter().filter(record)

        self.assertNotIn('alice@example.com', record.exc_text)
        self.assertNotIn(
            '8b1a9953-c461-4f36-9c2b-2a2f9c379f10',
            record.exc_text,
        )
