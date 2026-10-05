from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


User = get_user_model()


class ProfileCurrencyPreferenceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='currency@example.com',
            password='test-pass',
            display_name='Currency',
            birth_date=date(1990, 1, 1),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('api:profiles:my-profile')

    def test_auto_currency_uses_country_without_precise_location(self):
        self.user.profile.country = 'Gabon'
        self.user.profile.latitude = None
        self.user.profile.longitude = None
        self.user.profile.save(
            update_fields=['country', 'latitude', 'longitude']
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['preferred_currency'], 'AUTO')
        self.assertEqual(response.data['effective_currency'], 'XAF')

    def test_preference_can_be_updated_and_returns_effective_currency(self):
        response = self.client.patch(
            self.url,
            {'preferred_currency': 'EUR'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['preferred_currency'], 'EUR')
        self.assertEqual(response.data['effective_currency'], 'EUR')

    def test_unsupported_currency_is_rejected_with_safe_error(self):
        response = self.client.patch(
            self.url,
            {'preferred_currency': 'USD'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'validation_error')
        self.assertNotIn('ErrorDetail', str(response.data))

    @override_settings(
        MYCOOLPAY_ENABLED_CURRENCIES=('EUR',),
        MYCOOLPAY_DEFAULT_CURRENCY='EUR',
    )
    def test_auto_falls_back_to_an_enabled_merchant_currency(self):
        self.user.profile.country = 'Cameroon'
        self.user.profile.save(update_fields=['country'])

        response = self.client.get(self.url)

        self.assertEqual(response.data['preferred_currency'], 'AUTO')
        self.assertEqual(response.data['effective_currency'], 'EUR')
