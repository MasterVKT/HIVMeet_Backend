from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from profiles.catalog import CITY_SOURCE, file_sha256, sync_cities, sync_countries


class Command(BaseCommand):
    help = 'Synchronize a checksum-verified GeoNames country and city catalogue.'

    def add_arguments(self, parser):
        parser.add_argument('--countries-only', action='store_true')
        parser.add_argument('--source', default=str(CITY_SOURCE))
        parser.add_argument('--sha256', help='Required SHA-256 checksum of the city archive.')

    def handle(self, *args, **options):
        countries = sync_countries()
        self.stdout.write(f'{countries} countries synchronized.')
        if options['countries_only']:
            return
        if not options['sha256']:
            raise CommandError('--sha256 is required for a city catalogue import.')
        try:
            cities = sync_cities(Path(options['source']), expected_sha256=options['sha256'])
        except (FileNotFoundError, ValueError) as error:
            raise CommandError(str(error))
        self.stdout.write(self.style.SUCCESS(f'{cities} cities synchronized and verified.'))
