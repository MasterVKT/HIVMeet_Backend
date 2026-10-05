from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import User
from profiles.models import GeoCity, GeoCountry, KycAttempt, Profile, ProfilePhoto
from profiles.photo_storage import ProfilePhotoStorageUnavailable, profile_photo_storage
from profiles.private_storage import PrivateObjectNotFound, private_object_storage
from PIL import Image


class LocationAndPhotoContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email='owner-location@example.test', password='password123',
            display_name='Owner', birth_date=date(1990, 1, 1),
        )
        self.other = User.objects.create_user(
            email='other-location@example.test', password='password123',
            display_name='Other', birth_date=date(1991, 1, 1),
        )
        self.country = GeoCountry.objects.create(
            code='CM', geonames_id=2233387, name='Cameroon', name_fr='Cameroun',
            catalog_version='test',
        )
        self.city = GeoCity.objects.create(
            geonames_id=2220957, country=self.country, name='Douala',
            ascii_name='Douala', latitude=Decimal('4.0511000'),
            longitude=Decimal('9.7679000'), population=1000000,
            catalog_version='test',
        )
        self.owner_profile = self.owner.profile
        self.other_profile = self.other.profile
        self.client.force_authenticate(self.owner)

    def _photo_bytes(self):
        image = Image.new('RGB', (16, 16), color='purple')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')
        return buffer.getvalue()

    def _photo_upload(self):
        return SimpleUploadedFile(
            'replacement.jpg',
            self._photo_bytes(),
            content_type='image/jpeg',
        )

    def _grant_active_kyc(self):
        """Give the caller the Phase-1 prerequisite for viewing another profile."""
        KycAttempt.objects.create(
            user=self.owner,
            status=KycAttempt.VERIFIED,
            is_open=False,
            expires_at=timezone.now() + timedelta(days=1),
        )

    def test_private_photo_storage_writes_opaque_main_and_thumbnail_keys(self):
        stored = profile_photo_storage.upload_image(
            image_data=self._photo_bytes(),
            owner_id=str(self.owner.pk),
        )
        self.assertNotIn(str(self.owner.pk), stored['storage_key'])
        self.assertNotIn(str(self.owner.pk), stored['thumbnail_storage_key'])
        self.assertEqual(
            private_object_storage.metadata(
                scope='profile', key=stored['storage_key'],
            ).content_type,
            'image/jpeg',
        )
        profile_photo_storage.delete_private_key(stored['storage_key'])
        profile_photo_storage.delete_private_key(stored['thumbnail_storage_key'])
        with self.assertRaises(PrivateObjectNotFound):
            private_object_storage.metadata(scope='profile', key=stored['storage_key'])

    def test_country_and_city_catalogues_are_paginated_and_localized(self):
        countries = self.client.get('/api/v1/user-profiles/geo/countries/?q=camer')
        self.assertEqual(countries.status_code, 200)
        self.assertEqual(countries.data['results'][0]['label'], 'Cameroun')
        cities = self.client.get('/api/v1/user-profiles/geo/cities/?country=CM&q=dou')
        self.assertEqual(cities.status_code, 200)
        self.assertEqual(cities.data['results'][0]['geonames_id'], self.city.pk)

    def test_manual_location_clears_precise_coordinates_and_keeps_city(self):
        self.owner_profile.latitude = Decimal('4.0511000')
        self.owner_profile.longitude = Decimal('9.7679000')
        self.owner_profile.location_updated_at = timezone.now()
        self.owner_profile.save()

        response = self.client.put('/api/v1/user-profiles/me/location/', {
            'location_enabled': False,
            'city_id': self.city.pk,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.owner_profile.refresh_from_db()
        self.assertFalse(self.owner_profile.location_enabled)
        self.assertEqual(self.owner_profile.location_mode, 'manual')
        self.assertEqual(self.owner_profile.geo_city_id, self.city.pk)
        self.assertEqual(self.owner_profile.city, 'Douala')
        self.assertEqual(self.owner_profile.country, 'Cameroon')
        self.assertIsNone(self.owner_profile.latitude)
        self.assertIsNone(self.owner_profile.longitude)

    def test_automatic_location_requires_coordinates_and_persists_accuracy(self):
        rejected = self.client.put('/api/v1/user-profiles/me/location/', {
            'location_enabled': True,
        }, format='json')
        self.assertEqual(rejected.status_code, 400)
        response = self.client.put('/api/v1/user-profiles/me/location/', {
            'location_enabled': True,
            'latitude': '4.0520000',
            'longitude': '9.7680000',
            'accuracy_m': 12,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.owner_profile.refresh_from_db()
        self.assertTrue(self.owner_profile.location_enabled)
        self.assertEqual(self.owner_profile.location_mode, 'automatic')
        self.assertEqual(self.owner_profile.location_accuracy_m, 12)
        self.assertEqual(self.owner_profile.geo_city_id, self.city.pk)
        self.assertIsNotNone(self.owner_profile.location_updated_at)

    def test_public_profile_never_contains_coordinates_and_reports_same_city(self):
        self._grant_active_kyc()
        for profile in (self.owner_profile, self.other_profile):
            profile.geo_city = self.city
            profile.city = self.city.name
            profile.country = self.country.name
            profile.latitude = None
            profile.longitude = None
            profile.location_updated_at = None
            profile.location_enabled = False
            profile.location_mode = 'manual'
            profile.save()

        response = self.client.get(f'/api/v1/user-profiles/{self.other.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('latitude', response.data)
        self.assertNotIn('longitude', response.data)
        self.assertTrue(response.data['same_city'])
        self.assertTrue(response.data['distance_estimated'])

    def test_fresh_device_positions_return_a_rounded_precise_distance(self):
        self._grant_active_kyc()
        now = timezone.now()
        self.owner_profile.latitude = Decimal('4.0511000')
        self.owner_profile.longitude = Decimal('9.7679000')
        self.owner_profile.location_updated_at = now
        self.owner_profile.location_enabled = True
        self.owner_profile.save()
        self.other_profile.latitude = Decimal('4.1511000')
        self.other_profile.longitude = Decimal('9.7679000')
        self.other_profile.location_updated_at = now
        self.other_profile.location_enabled = True
        self.other_profile.save()

        response = self.client.get(f'/api/v1/user-profiles/{self.other.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.data['distance_from_me_km'], 1)
        self.assertFalse(response.data['distance_estimated'])
        self.assertFalse(response.data['same_city'])

    def test_only_main_photo_cannot_be_deleted(self):
        photo = ProfilePhoto.objects.create(
            profile=self.owner_profile, photo_url='https://storage.googleapis.com/bucket/profiles/a/main.jpg',
            thumbnail_url='https://storage.googleapis.com/bucket/profiles/a/main-thumb.jpg', is_main=True,
        )
        response = self.client.delete(f'/api/v1/user-profiles/me/photos/{photo.pk}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(ProfilePhoto.objects.filter(pk=photo.pk).exists())

    @patch('profiles.views.profile_photo_storage.delete_private_key')
    @patch('profiles.views.profile_photo_storage.upload_image')
    def test_replacing_only_free_photo_preserves_identity_and_main_status(
        self,
        upload_image,
        delete_private_key,
    ):
        photo = ProfilePhoto.objects.create(
            profile=self.owner_profile,
            photo_url='',
            thumbnail_url='',
            storage_key='profile-media/private/old-main',
            thumbnail_storage_key='profile-media/private/old-thumbnail',
            storage_state=ProfilePhoto.PRIVATE,
            is_main=True,
            order=0,
        )
        upload_image.return_value = {
            'storage_key': 'profile-media/private/new-main',
            'thumbnail_storage_key': 'profile-media/private/new-thumbnail',
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.put(
                f'/api/v1/user-profiles/me/photos/{photo.pk}/',
                {'file': self._photo_upload()},
                format='multipart',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['photo_id'], str(photo.pk))
        photo.refresh_from_db()
        self.assertTrue(photo.is_main)
        self.assertEqual(photo.order, 0)
        self.assertFalse(photo.photo_url)
        self.assertEqual(photo.storage_key, 'profile-media/private/new-main')
        delete_private_key.assert_any_call('profile-media/private/old-main')
        delete_private_key.assert_any_call('profile-media/private/old-thumbnail')

    @patch(
        'profiles.views.profile_photo_storage.upload_image',
        side_effect=ProfilePhotoStorageUnavailable(),
    )
    def test_photo_storage_unavailability_returns_stable_503(self, _upload_image):
        response = self.client.post(
            '/api/v1/user-profiles/me/photos/',
            {'file': self._photo_upload()},
            format='multipart',
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error'], 'photo_storage_unavailable')

    def test_replacement_rejects_a_photo_owned_by_another_user(self):
        photo = ProfilePhoto.objects.create(
            profile=self.other_profile,
            photo_url='profiles/other/main/photo.jpg',
            thumbnail_url='profiles/other/thumbnails/photo.jpg',
            is_main=True,
        )
        response = self.client.put(
            f'/api/v1/user-profiles/me/photos/{photo.pk}/',
            {'file': self._photo_upload()},
            format='multipart',
        )
        self.assertEqual(response.status_code, 404)

    @patch('profiles.photo_storage.delete_legacy_profile_object', return_value=True)
    def test_deleting_a_non_last_photo_removes_both_storage_objects(self, delete_legacy):
        legacy_prefix = f'https://storage.googleapis.com/bucket/profiles/{self.owner.id}'
        main = ProfilePhoto.objects.create(
            profile=self.owner_profile,
            photo_url=f'{legacy_prefix}/main.jpg',
            thumbnail_url=f'{legacy_prefix}/main-thumb.jpg',
            is_main=True,
            legacy_source_verified=True,
        )
        removable = ProfilePhoto.objects.create(
            profile=self.owner_profile,
            photo_url=f'{legacy_prefix}/other.jpg',
            thumbnail_url=f'{legacy_prefix}/other-thumb.jpg',
            order=1,
            legacy_source_verified=True,
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(
                f'/api/v1/user-profiles/me/photos/{removable.pk}/'
            )
        self.assertEqual(response.status_code, 204)
        self.assertTrue(ProfilePhoto.objects.filter(pk=main.pk, is_main=True).exists())
        delete_legacy.assert_any_call(f'profiles/{self.owner.id}/other.jpg')
        delete_legacy.assert_any_call(f'profiles/{self.owner.id}/other-thumb.jpg')

    @patch('profiles.views.is_premium_user', return_value=False)
    def test_free_user_cannot_reorder(self, _is_premium):
        ProfilePhoto.objects.create(
            profile=self.owner_profile, photo_url='https://storage.googleapis.com/bucket/profiles/a/one.jpg',
            thumbnail_url='https://storage.googleapis.com/bucket/profiles/a/one-thumb.jpg', is_main=True,
        )
        response = self.client.put('/api/v1/user-profiles/me/photos/reorder/', {
            'photo_ids': [],
        }, format='json')
        self.assertEqual(response.status_code, 403)

    @patch('profiles.views.is_premium_user', return_value=True)
    def test_premium_reorder_is_exact_and_atomic(self, _is_premium):
        first = ProfilePhoto.objects.create(
            profile=self.owner_profile, photo_url='https://storage.googleapis.com/bucket/profiles/a/one.jpg',
            thumbnail_url='https://storage.googleapis.com/bucket/profiles/a/one-thumb.jpg', is_main=True, order=0,
        )
        second = ProfilePhoto.objects.create(
            profile=self.owner_profile, photo_url='https://storage.googleapis.com/bucket/profiles/a/two.jpg',
            thumbnail_url='https://storage.googleapis.com/bucket/profiles/a/two-thumb.jpg', order=1,
        )
        response = self.client.put('/api/v1/user-profiles/me/photos/reorder/', {
            'photo_ids': [str(second.pk), str(first.pk)],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data], [str(second.pk), str(first.pk)])
        invalid = self.client.put('/api/v1/user-profiles/me/photos/reorder/', {
            'photo_ids': [str(first.pk)],
        }, format='json')
        self.assertEqual(invalid.status_code, 409)
        self.assertEqual(
            list(ProfilePhoto.objects.filter(profile=self.owner_profile).order_by('order').values_list('id', flat=True)),
            [second.pk, first.pk],
        )
