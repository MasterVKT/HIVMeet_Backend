"""Verify the Phase-2 private-storage deployment gate without exposing objects."""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from profiles.private_storage import (
    PrivateStorageUnavailable,
    private_object_storage,
    private_storage_configuration_errors,
)


class Command(BaseCommand):
    help = 'Verify private KYC and profile-media bucket configuration, UBLA, CMEK and IAM.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scope', choices=['kyc', 'profile', 'all'], default='all',
        )

    def handle(self, *args, **options):
        scopes = ['kyc', 'profile'] if options['scope'] == 'all' else [options['scope']]
        failures = []
        if options['scope'] == 'all':
            if settings.KYC_STORAGE_BUCKET == settings.PROFILE_MEDIA_PRIVATE_BUCKET:
                failures.append('scopes:buckets_not_distinct')
            if settings.KYC_STORAGE_KMS_KEY == settings.PROFILE_MEDIA_KMS_KEY:
                failures.append('scopes:cmek_keys_not_distinct')
        for scope in scopes:
            configuration_errors = private_storage_configuration_errors(scope)
            if configuration_errors:
                failures.extend(f'{scope}:{code}' for code in configuration_errors)
                continue
            try:
                policy_errors = private_object_storage.verify_bucket_policy(scope)
            except PrivateStorageUnavailable:
                failures.append(f'{scope}:storage_unavailable')
                continue
            failures.extend(f'{scope}:{code}' for code in policy_errors)
        if failures:
            raise CommandError('Private storage gate failed: ' + ', '.join(failures))
        self.stdout.write(self.style.SUCCESS('Private storage gate passed.'))
