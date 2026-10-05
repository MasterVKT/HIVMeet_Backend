"""Dispatch bounded, idempotent private-media migration batches."""

from django.core.management.base import BaseCommand

from profiles.tasks import migrate_legacy_profile_photos


class Command(BaseCommand):
    help = 'Enqueue a bounded batch that copies, verifies, switches and deletes legacy profile photos.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=100)

    def handle(self, *args, **options):
        batch_size = max(1, min(options['batch_size'], 1000))
        result = migrate_legacy_profile_photos.delay(batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(
            f'Legacy profile-photo migration batch dispatched: {result.id}',
        ))
