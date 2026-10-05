from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import User
from profiles.catalog import CATALOG_VERSION, catalog_is_healthy, file_sha256, sync_cities, sync_countries
from profiles.models import GeoCatalogRelease, GeoCity, GeoCountry


class ProfileAndCatalogContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email='profile-phase4@example.test', password='password', display_name='Owner',
            birth_date=date(1990, 1, 1),
        )
        self.owner.profile.gender = 'male'
        self.owner.profile.gender_confirmation_required = False
        self.owner.profile.save()
        self.client.force_authenticate(self.owner)
        self.country = GeoCountry.objects.create(
            code='CM', geonames_id=2233387, name='Cameroon', name_fr='Cameroun',
            search_name='cm cameroon cameroun', catalog_version='test',
        )
        self.city = GeoCity.objects.create(
            geonames_id=2220957, country=self.country, name='Douala', ascii_name='Douala',
            search_name='douala', latitude=Decimal('4.0511000'), longitude=Decimal('9.7679000'),
            population=1000000, catalog_version='test',
        )

    def test_unconfirmed_gender_is_never_recommended_until_selected(self):
        from matching.services import RecommendationService

        self.owner.email_verified = True
        self.owner.save(update_fields=['email_verified'])
        target = User.objects.create_user(
            email='unconfirmed-phase4@example.test', password='password',
            display_name='Target', birth_date=date(1991, 1, 1), email_verified=True,
        )
        # The signal makes gender blank/confirmation-required.  Even if a stale
        # legacy flag says discoverable, the recommendation query is defensive.
        target.profile.allow_profile_in_discovery = True
        target.profile.save(update_fields=['allow_profile_in_discovery'])
        initial = RecommendationService.get_recommendations(self.owner)
        self.assertNotIn(target.profile, initial)
        target.profile.gender = 'female'
        target.profile.gender_confirmation_required = False
        target.profile.save()
        selected = RecommendationService.get_recommendations(self.owner)
        self.assertIn(target.profile, selected)

    def test_sought_gender_accepts_one_value_or_everyone_only(self):
        rejected = self.client.patch('/api/v1/user-profiles/me/', {
            'genders_sought': ['male', 'female'],
        }, format='json')
        self.assertEqual(rejected.status_code, 400)
        accepted = self.client.patch('/api/v1/user-profiles/me/', {
            'genders_sought': ['female'],
        }, format='json')
        self.assertEqual(accepted.status_code, 200)
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.genders_sought, ['female'])

    def test_gender_is_immutable_after_explicit_confirmation(self):
        response = self.client.patch('/api/v1/user-profiles/me/', {'gender': 'female'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'gender_immutable')
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.gender, 'male')

    def test_atomic_profile_and_location_does_not_partially_save(self):
        self.owner.profile.bio = 'Before'
        self.owner.profile.save()
        response = self.client.put('/api/v1/user-profiles/me/complete/', {
            'profile': {'bio': 'After'},
            'location': {'location_enabled': False, 'city_id': 999999999},
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.bio, 'Before')

    def test_automatic_location_quantizes_coordinates_to_seven_decimals(self):
        response = self.client.put('/api/v1/user-profiles/me/complete/', {
            'profile': {},
            'location': {
                'location_enabled': True,
                'latitude': '4.052000049',
                'longitude': '9.768000149',
                'accuracy_m': 8,
            },
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.latitude, Decimal('4.0520000'))
        self.assertEqual(self.owner.profile.longitude, Decimal('9.7680001'))

    def test_verified_geonames_archive_records_manifest_and_is_searchable(self):
        sync_countries()
        with TemporaryDirectory() as directory:
            archive = Path(directory) / 'cities500.zip'
            row = '987654\t?bolowa\tEbolowa\t\t2.9000000\t11.1500000\tP\tPPLA\tCM\t\t\t\t\t\t1000\t\t\t\t\n'
            with ZipFile(archive, 'w') as zip_file:
                zip_file.writestr('cities500.txt', row)
            count = sync_cities(archive, expected_sha256=file_sha256(archive))
        self.assertEqual(count, 1)
        self.assertTrue(GeoCatalogRelease.objects.filter(catalog_version=CATALOG_VERSION).exists())
        self.assertTrue(catalog_is_healthy())
        response = self.client.get('/api/v1/user-profiles/geo/cities/?country=CM&q=ebolowa')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row['name'] == '?bolowa' for row in response.data['results']))
