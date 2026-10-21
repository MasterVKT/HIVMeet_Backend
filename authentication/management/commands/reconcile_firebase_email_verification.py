"""Synchronise local email-verification flags from Firebase safely."""
from django.core.management.base import BaseCommand

from authentication.models import User


class Command(BaseCommand):
    help = (
        'Compare local email-verification flags with Firebase. Dry-run by '
        'default; --apply updates only existing local accounts.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Persist discrepancies after the dry-run totals have been reviewed.',
        )
        parser.add_argument(
            '--limit', type=int,
            help='Inspect at most this many accounts (useful for a controlled rollout).',
        )

    def handle(self, *args, **options):
        # Import lazily so ``manage.py help`` remains usable when Firebase
        # credentials are intentionally absent in an isolated test setup.
        from hivmeet_backend.firebase_service import firebase_service

        queryset = User.objects.exclude(firebase_uid__isnull=True).exclude(firebase_uid='')
        if options['limit'] is not None:
            queryset = queryset.order_by('id')[:max(options['limit'], 0)]

        totals = {
            'scanned': 0,
            'unchanged': 0,
            'discrepancies': 0,
            'updated': 0,
            'missing_firebase_identity': 0,
            'lookup_errors': 0,
        }
        for user in queryset.iterator():
            totals['scanned'] += 1
            try:
                firebase_user = firebase_service.get_user(user.firebase_uid)
            except Exception:
                # Intentionally aggregate only: no UID, e-mail, or exception
                # text is written to command output.
                totals['lookup_errors'] += 1
                continue

            firebase_email = str(getattr(firebase_user, 'email', '')).strip().lower()
            if not firebase_email or firebase_email != user.email.lower():
                totals['missing_firebase_identity'] += 1
                continue

            firebase_verified = getattr(firebase_user, 'email_verified', False) is True
            if user.email_verified == firebase_verified:
                totals['unchanged'] += 1
                continue

            totals['discrepancies'] += 1
            if options['apply']:
                user.email_verified = firebase_verified
                user.save(update_fields=['email_verified', 'updated_at'])
                totals['updated'] += 1

        mode = 'applied' if options['apply'] else 'dry-run'
        self.stdout.write(
            self.style.SUCCESS(
                '{} email-verification reconciliation: {}'.format(
                    mode,
                    ', '.join(f'{key}={value}' for key, value in totals.items()),
                )
            )
        )
