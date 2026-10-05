from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import PaymentTransaction, SubscriptionPlan
from .payment_gateway import MyCoolPayError
from .pricing import convert_amount


User = get_user_model()


MYCOOLPAY_TEST_SETTINGS = {
    'SECURE_SSL_REDIRECT': False,
    'MYCOOLPAY_BASE_URL': 'https://my-coolpay.com/api',
    'MYCOOLPAY_PUBLIC_KEY': 'test_public_key',
    'MYCOOLPAY_PRIVATE_KEY': 'test_private_key',
    'MYCOOLPAY_CALLBACK_ALLOWED_IPS': ('127.0.0.1',),
    'MYCOOLPAY_CALLBACK_URL': (
        'https://payments.example.test/api/v1/webhooks/payments/mycoolpay/'
    ),
    'MYCOOLPAY_SUCCESS_URL': (
        'https://payments.example.test/api/v1/subscriptions/'
        'payment-return/success/'
    ),
    'MYCOOLPAY_CANCEL_URL': (
        'https://payments.example.test/api/v1/subscriptions/'
        'payment-return/cancel/'
    ),
    'MYCOOLPAY_FAILURE_URL': (
        'https://payments.example.test/api/v1/subscriptions/'
        'payment-return/failure/'
    ),
}


def create_plan(plan_id, interval, price):
    plan, _ = SubscriptionPlan.objects.update_or_create(
        plan_id=plan_id,
        defaults={
            'name': plan_id,
            'name_en': plan_id,
            'name_fr': plan_id,
            'description': plan_id,
            'description_en': plan_id,
            'description_fr': plan_id,
            'price': price,
            'currency': 'EUR',
            'billing_interval': interval,
            'is_active': True,
        },
    )
    return plan


@override_settings(**MYCOOLPAY_TEST_SETTINGS)
class SubscriptionCatalogContractTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='catalog@example.com',
            password='test-pass',
            display_name='Catalogue',
            birth_date=date(1990, 1, 1),
        )
        self.user.profile.country = 'Cameroun'
        self.user.profile.save(update_fields=['country'])
        create_plan(
            'hivmeet_monthly',
            SubscriptionPlan.INTERVAL_MONTH,
            Decimal('7.99'),
        )
        create_plan(
            'hivmeet_annual',
            SubscriptionPlan.INTERVAL_YEAR,
            Decimal('57.99'),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_catalog_uses_effective_currency_and_exposes_discount(self):
        response = self.client.get(reverse('api:subscriptions:plans'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plans = {
            item['plan_id']: item
            for item in response.data['results']
        }
        monthly = plans['hivmeet_monthly']
        annual = plans['hivmeet_annual']

        self.assertEqual(monthly['currency'], 'XAF')
        self.assertEqual(
            monthly['price'],
            format(convert_amount(Decimal('7.99'), 'EUR', 'XAF'), 'f'),
        )
        self.assertEqual(monthly['base_price'], '7.99')
        self.assertEqual(monthly['base_currency'], 'EUR')
        self.assertEqual(annual['savings_percentage'], 40)
        self.assertTrue(annual['recommended'])
        self.assertTrue(annual['most_popular'])
        self.assertEqual(annual['features']['daily_rewinds_count'], 5)

    def test_manual_eur_preference_keeps_eur_catalog_prices(self):
        self.user.profile.preferred_currency = 'EUR'
        self.user.profile.save(update_fields=['preferred_currency'])

        response = self.client.get(reverse('api:subscriptions:plans'))
        plans = response.data['results']

        self.assertEqual({plan['currency'] for plan in plans}, {'EUR'})
        self.assertEqual(plans[0]['price'], '7.99')

    def test_capabilities_are_authenticated_and_never_expose_keys(self):
        url = reverse('api:subscriptions:payment-capabilities')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])
        self.assertTrue(response.data['callback_verification_available'])
        self.assertEqual(response.data['effective_currency'], 'XAF')
        self.assertNotIn('public_key', response.data)
        self.assertNotIn('private_key', response.data)

        self.client.force_authenticate(user=None)
        unauthenticated = self.client.get(url)
        self.assertIn(
            unauthenticated.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    @override_settings(MYCOOLPAY_BASE_URL='http://unsafe.example.test/api')
    def test_capabilities_reject_unsafe_provider_configuration(self):
        response = self.client.get(
            reverse('api:subscriptions:payment-capabilities')
        )

        self.assertFalse(response.data['available'])

    @override_settings(MYCOOLPAY_PRIVATE_KEY='')
    def test_capabilities_allow_secure_polling_without_callback_secret(self):
        response = self.client.get(
            reverse('api:subscriptions:payment-capabilities')
        )

        self.assertTrue(response.data['available'])
        self.assertFalse(response.data['callback_verification_available'])
        self.assertFalse(response.data['automatic_return_available'])
        self.assertEqual(response.data['confirmation_mode'], 'polling_only')

    def test_blank_plan_error_has_safe_plain_details(self):
        response = self.client.post(
            reverse('api:subscriptions:purchase'),
            {
                'plan_id': '',
                'phone_number': '699009900',
                'language': 'fr',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'validation_error')
        self.assertEqual(response.data['status_code'], 400)
        self.assertNotIn('ErrorDetail', str(response.data))


@override_settings(**MYCOOLPAY_TEST_SETTINGS)
class PurchaseIdempotencyContractTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='idempotency@example.com',
            password='test-pass',
            display_name='Idempotence',
            birth_date=date(1990, 1, 1),
        )
        create_plan(
            'hivmeet_monthly',
            SubscriptionPlan.INTERVAL_MONTH,
            Decimal('7.99'),
        )
        create_plan(
            'hivmeet_annual',
            SubscriptionPlan.INTERVAL_YEAR,
            Decimal('57.99'),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('api:subscriptions:purchase')

    @patch('subscriptions.payment_gateway.MyCoolPayPaylinkClient.create_paylink')
    def test_purchase_ignores_client_prices_and_uses_server_quote(
        self,
        create_paylink,
    ):
        self.user.profile.country = 'Cameroun'
        self.user.profile.save(update_fields=['country'])
        create_paylink.return_value = {
            'status': 'success',
            'transaction_ref': 'provider-server-quote',
            'payment_url': 'https://my-coolpay.com/payment/checkout/test',
        }

        response = self.client.post(
            self.url,
            {
                'plan_id': 'hivmeet_monthly',
                'phone_number': '699009900',
                'amount': '0.01',
                'currency': 'USD',
            },
            format='json',
        )

        payment = PaymentTransaction.objects.get(id=response.data['payment_id'])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(payment.amount, Decimal('5241'))
        self.assertEqual(payment.currency, 'XAF')

    @patch('subscriptions.payment_gateway.MyCoolPayPaylinkClient.create_paylink')
    def test_same_key_replays_one_payment_transaction(self, create_paylink):
        create_paylink.return_value = {
            'status': 'success',
            'transaction_ref': 'provider-idempotent',
            'payment_url': 'https://my-coolpay.com/payment/checkout/test',
        }
        payload = {
            'plan_id': 'hivmeet_monthly',
            'phone_number': '699009900',
            'language': 'fr',
        }
        headers = {'HTTP_IDEMPOTENCY_KEY': 'checkout-12345678'}

        first = self.client.post(self.url, payload, format='json', **headers)
        second = self.client.post(self.url, payload, format='json', **headers)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['payment_id'], second.data['payment_id'])
        self.assertTrue(second.data['idempotent_replay'])
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        create_paylink.assert_called_once()

    @patch('subscriptions.payment_gateway.MyCoolPayPaylinkClient.create_paylink')
    def test_same_key_cannot_be_reused_for_another_plan(self, create_paylink):
        create_paylink.return_value = {
            'status': 'success',
            'transaction_ref': 'provider-conflict',
            'payment_url': 'https://my-coolpay.com/payment/checkout/test',
        }
        headers = {'HTTP_IDEMPOTENCY_KEY': 'checkout-conflict'}
        first = self.client.post(
            self.url,
            {
                'plan_id': 'hivmeet_monthly',
                'phone_number': '699009900',
            },
            format='json',
            **headers,
        )
        second = self.client.post(
            self.url,
            {
                'plan_id': 'hivmeet_annual',
                'phone_number': '699009900',
            },
            format='json',
            **headers,
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.data['error'], 'idempotency_conflict')
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    def test_invalid_idempotency_header_is_rejected(self):
        response = self.client.post(
            self.url,
            {
                'plan_id': 'hivmeet_monthly',
                'phone_number': '699009900',
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='bad key',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'validation_error')
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    @override_settings(MYCOOLPAY_PUBLIC_KEY='')
    def test_unconfigured_payment_uses_stable_error_envelope(self):
        response = self.client.post(
            self.url,
            {
                'plan_id': 'hivmeet_monthly',
                'phone_number': '699009900',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error'], 'payment_not_configured')
        self.assertEqual(response.data['details'], {})
        self.assertEqual(response.data['status_code'], 503)

    @patch('subscriptions.payment_gateway.MyCoolPayPaylinkClient.create_paylink')
    def test_provider_failure_uses_stable_error_envelope(self, create_paylink):
        create_paylink.side_effect = MyCoolPayError('provider secret detail')
        response = self.client.post(
            self.url,
            {
                'plan_id': 'hivmeet_monthly',
                'phone_number': '699009900',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data['error'], 'payment_provider_unavailable')
        self.assertNotIn('provider secret detail', str(response.data))
        self.assertEqual(response.data['status_code'], 502)


class SubscriptionCatalogIntegrityTest(TestCase):
    def test_fixed_parity_rounds_xaf_to_a_whole_franc(self):
        self.assertEqual(
            convert_amount(Decimal('7.99'), 'EUR', 'XAF'),
            Decimal('5241'),
        )
        self.assertEqual(
            convert_amount(Decimal('5241'), 'XAF', 'EUR'),
            Decimal('7.99'),
        )

    def test_database_rejects_empty_plan_id(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_plan(
                    '',
                    SubscriptionPlan.INTERVAL_MONTH,
                    Decimal('1.00'),
                )

    def test_init_command_keeps_only_canonical_plans_active(self):
        legacy = create_plan(
            'legacy_extra',
            SubscriptionPlan.INTERVAL_MONTH,
            Decimal('9.99'),
        )

        call_command('init_subscription_plans', stdout=StringIO())

        legacy.refresh_from_db()
        self.assertFalse(legacy.is_active)
        active_ids = set(
            SubscriptionPlan.objects.filter(is_active=True).values_list(
                'plan_id', flat=True
            )
        )
        self.assertEqual(
            active_ids,
            {'hivmeet_monthly', 'hivmeet_annual'},
        )
