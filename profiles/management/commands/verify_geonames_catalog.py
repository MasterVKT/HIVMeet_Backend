from django.core.management.base import BaseCommand, CommandError
from profiles.catalog import catalog_is_healthy


class Command(BaseCommand):
    help = 'Fail unless the versioned GeoNames populated-place catalogue is healthy.'

    def handle(self, *args, **options):
        if not catalog_is_healthy():
            raise CommandError('GeoNames catalogue is missing, empty, or lacks a verified release manifest.')
        self.stdout.write(self.style.SUCCESS('GeoNames catalogue is healthy.'))
