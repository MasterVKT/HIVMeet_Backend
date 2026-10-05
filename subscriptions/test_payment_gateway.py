from datetime import date, timedelta
from decimal import Decimal

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from profiles.models import KycAttempt

from .models import (
    PaymentTransaction,
    Subscription,
    SubscriptionPlan,
    Transaction,
)
from .payment_gateway import (
    MyCoolPayAmbiguousError,
    MyCoolPayError,
    MyCoolPayPaylinkClient,
    apply_provider_status,
    callback_signature,
    initiate_payment,
    is_mycoolpay_callback_flow_configured,
    is_mycoolpay_payment_flow_configured,
    reconcile_payment_if_due,
)


User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MYCOOLPAY_BASE_URL='https://my-coolpay.com/api',
    MYCOOLPAY_PUBLIC_KEY='test_public_key',
    MYCOOLPAY_PRIVATE_KEY='test_private_key',
    MYCOOLPAY_CALLBACK_ALLOWED_IPS=('127.0.0.1',),
    MYCOOLPAY_CALLBACK_URL=(
        'https://payments.example.test/api/v1/webhooks/payments/mycoolpay/'
    ),
    MYCOOLPAY_SUCCESS_URL=(
        'https://payments.example.test/api/v1/subscriptions/'
        'payment-return/success/'
    ),
    MYCOOLPAY_CANCEL_URL=(
        'https://payments.example.test/api/v1/subscriptions/'
        'payment-return/cancel/'
    ),
    MYCOOLPAY_FAILURE_URL=(
        'https://payments.example.test/api/v1/subscriptions/'
        'payment-return/failure/'
    ),
)
class PaymentGatewayTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='payer@example.com',
            password='test-pass',
            display_name='Payer',
            birth_date=date(1990, 1, 1),
        )
        self.plan = SubscriptionPlan.objects.create(
            plan_id='premium_monthly',
            name='Premium',
            name_en='Premium',
            name_fr='Premium',
            description='Premium',
            description_en='Premium',
            description_fr='Premium',
            price=Decimal('5000.00'),
            currency='XAF',
            billing_interval=SubscriptionPlan.INTERVAL_MONTH,
        )
        KycAttempt.objects.create(
            user=self.user,
            status=KycAttempt.VERIFIED,
            is_open=False,
            expires_at=timezone.now() + timedelta(days=1),
        )

    def _provider_payload(self, payment, status='SUCCESS'):
        payload = {
            'application': 'test_public_key',
            'app_transaction_ref': payment.app_transaction_ref,
            'operator_transaction_ref': 'operator-ref',
            'transaction_ref': payment.provider_transaction_ref,
            'transaction_type': 'PAYIN',
            'transaction_amount': 5000,
            'transaction_fees': 0,
            'transaction_currency': 'XAF',
            'transaction_operator': 'CM_OM',
            'transaction_status': status,
            'transaction_reason': 'HIVMeet Premium',
            'transaction_message': None,
            'customer_phone_number': '699009900',
        }
        payload['signature'] = callback_signature(payload, 'test_private_key')
        return payload

    def test_merchant_reference_exists_before_provider_call(self):
        test_case = self

        class FakeClient:
            def create_paylink(self, payment, phone_number, language):
                test_case.assertTrue(
                    PaymentTransaction.objects.filter(id=payment.id).exists()
                )
                return {
                    'status': 'success',
                    'transaction_ref': 'provider-ref',
                    'payment_url': (
                        'https://my-coolpay.com/payment/checkout/provider-ref'
                    ),
                }

        payment = initiate_payment(
            user=self.user,
            plan=self.plan,
            phone_number='699009900',
            language='fr',
            client=FakeClient(),
        )

        self.assertEqual(payment.status, PaymentTransaction.STATUS_PENDING)
        self.assertEqual(payment.provider_transaction_ref, 'provider-ref')

    def test_paylink_client_uses_the_documented_endpoint_and_flat_payload(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
        )

        class FakeResponse:
            status_code = 201

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    'status': 'success',
                    'transaction_ref': 'provider-ref',
                    'payment_url': (
                        'https://my-coolpay.com/payment/checkout/provider-ref'
                    ),
                }

        class FakeSession:
            def post(self, url, json, headers, timeout):
                self.url = url
                self.payload = json
                self.headers = headers
                return FakeResponse()

        session = FakeSession()
        MyCoolPayPaylinkClient(session=session).create_paylink(
            payment,
            phone_number='699009900',
            language='fr',
        )

        self.assertEqual(
            session.url,
            'https://my-coolpay.com/api/test_public_key/paylink',
        )
        self.assertEqual(
            set(session.payload),
            {
                'transaction_amount',
                'transaction_currency',
                'transaction_reason',
                'app_transaction_ref',
                'customer_phone_number',
                'customer_name',
                'customer_email',
                'customer_lang',
            },
        )
        self.assertEqual(
            session.payload['app_transaction_ref'],
            payment.app_transaction_ref,
        )
        self.assertEqual(session.payload['transaction_amount'], 5000.0)
        self.assertEqual(
            session.headers,
            {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
        )

    def test_status_client_uses_the_documented_check_status_endpoint(self):
        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    'status': 'success',
                    'transaction_ref': 'provider-ref',
                    'transaction_status': 'PENDING',
                }

        class FakeSession:
            def get(self, url, headers, timeout):
                self.url = url
                self.headers = headers
                self.timeout = timeout
                return FakeResponse()

        session = FakeSession()
        result = MyCoolPayPaylinkClient(session=session).check_status(
            'provider-ref'
        )

        self.assertEqual(
            session.url,
            (
                'https://my-coolpay.com/api/test_public_key/'
                'checkStatus/provider-ref'
            ),
        )
        self.assertEqual(session.headers, {'Accept': 'application/json'})
        self.assertEqual(result['transaction_status'], 'PENDING')

    def test_status_reference_is_path_encoded(self):
        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {'status': 'success', 'transaction_status': 'PENDING'}

        class FakeSession:
            def get(self, url, headers, timeout):
                self.url = url
                return FakeResponse()

        session = FakeSession()
        MyCoolPayPaylinkClient(session=session).check_status('ref/with spaces')

        self.assertTrue(session.url.endswith('checkStatus/ref%2Fwith%20spaces'))

    def test_ambiguous_paylink_response_keeps_one_recoverable_payment(self):
        class TimeoutSession:
            def post(self, *args, **kwargs):
                raise requests.ReadTimeout('provider detail must stay internal')

        payment = initiate_payment(
            user=self.user,
            plan=self.plan,
            phone_number='699009900',
            language='fr',
            idempotency_key='ambiguous-checkout',
            client=MyCoolPayPaylinkClient(session=TimeoutSession()),
        )

        self.assertEqual(payment.status, PaymentTransaction.STATUS_CREATED)
        self.assertIsNone(payment.provider_transaction_ref)
        self.assertEqual(payment.provider_message, 'provider_response_unknown')
        self.assertEqual(PaymentTransaction.objects.count(), 1)

        payload = self._provider_payload(payment)
        payload['transaction_ref'] = 'provider-late-callback'
        payload['signature'] = callback_signature(payload, 'test_private_key')
        apply_provider_status(payment.id, payload)

        payment.refresh_from_db()
        self.assertEqual(
            payment.provider_transaction_ref,
            'provider-late-callback',
        )
        self.assertTrue(payment.is_fulfilled)

    def test_provider_503_is_ambiguous_and_does_not_invite_a_duplicate(self):
        class UnavailableResponse:
            status_code = 503

            def raise_for_status(self):
                error = requests.HTTPError('temporarily unavailable')
                error.response = self
                raise error

            def json(self):
                return {'status': 'error'}

        class UnavailableSession:
            def post(self, *args, **kwargs):
                return UnavailableResponse()

        with self.assertRaises(MyCoolPayAmbiguousError):
            MyCoolPayPaylinkClient(
                session=UnavailableSession(),
            ).create_paylink(
                PaymentTransaction.objects.create(
                    user=self.user,
                    plan=self.plan,
                    amount=self.plan.price,
                    currency='XAF',
                ),
                phone_number='699009900',
                language='fr',
            )

    def test_late_callback_cannot_rebind_an_existing_provider_reference(self):
        PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            provider_transaction_ref='already-bound-provider-ref',
        )
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_CREATED,
        )
        payload = self._provider_payload(payment)
        payload['transaction_ref'] = 'already-bound-provider-ref'

        with self.assertRaises(MyCoolPayError):
            apply_provider_status(payment.id, payload)

        payment.refresh_from_db()
        self.assertIsNone(payment.provider_transaction_ref)
        self.assertFalse(payment.is_fulfilled)

    def test_success_fulfillment_is_idempotent(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='provider-ref',
        )
        payload = self._provider_payload(payment)

        apply_provider_status(payment.id, payload)
        apply_provider_status(payment.id, payload)

        payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertTrue(payment.is_fulfilled)
        self.assertTrue(self.user.is_premium)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_success_callback_records_payment_but_never_activates_premium_without_kyc(self):
        KycAttempt.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='expired-kyc-provider-ref',
        )

        apply_provider_status(payment.id, self._provider_payload(payment))

        payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.STATUS_SUCCESS)
        self.assertFalse(payment.is_fulfilled)
        self.assertIsNotNone(payment.paid_at)
        self.assertFalse(self.user.is_premium)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    def test_webhook_rejects_bad_signature_and_accepts_valid_callback(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='provider-ref',
        )
        payload = self._provider_payload(payment)
        client = APIClient()
        url = reverse('api:mycoolpay-webhook')

        invalid = dict(payload, signature='invalid')
        response = client.post(
            url,
            payload,
            format='json',
            secure=True,
            REMOTE_ADDR='203.0.113.10',
        )
        self.assertEqual(response.status_code, 403)

        response = client.post(
            url,
            invalid,
            format='json',
            secure=True,
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(response.status_code, 403)

        wrong_amount = dict(payload, transaction_amount=1)
        wrong_amount['signature'] = callback_signature(
            wrong_amount,
            'test_private_key',
        )
        response = client.post(
            url,
            wrong_amount,
            format='json',
            secure=True,
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_premium)

        response = client.post(
            url,
            payload,
            format='json',
            secure=True,
            REMOTE_ADDR='127.0.0.1',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'OK')
        self.assertTrue(
            PaymentTransaction.objects.get(id=payment.id).is_fulfilled
        )

    @override_settings(MYCOOLPAY_TRUSTED_PROXY_IPS=('10.10.10.10',))
    def test_webhook_trusts_forwarded_ip_only_from_configured_proxy(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='proxy-provider-ref',
        )
        payload = self._provider_payload(payment)
        client = APIClient()
        url = reverse('api:mycoolpay-webhook')

        spoofed = client.post(
            url,
            payload,
            format='json',
            REMOTE_ADDR='203.0.113.10',
            HTTP_X_FORWARDED_FOR='127.0.0.1',
        )
        self.assertEqual(spoofed.status_code, 403)

        proxied = client.post(
            url,
            payload,
            format='json',
            REMOTE_ADDR='10.10.10.10',
            HTTP_X_FORWARDED_FOR='127.0.0.1, 10.10.10.10',
        )
        self.assertEqual(proxied.status_code, 200)

    def test_conflicting_terminal_callback_cannot_change_payment(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='terminal-provider-ref',
        )
        apply_provider_status(
            payment.id,
            self._provider_payload(payment, status='CANCELED'),
        )

        with self.assertRaises(MyCoolPayError):
            apply_provider_status(
                payment.id,
                self._provider_payload(payment, status='SUCCESS'),
            )

        payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.STATUS_CANCELED)
        self.assertFalse(self.user.is_premium)

    def test_fulfillment_rejects_inconsistent_provider_fields(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='provider-ref',
        )
        base_payload = self._provider_payload(payment)
        invalid_fields = {
            'app_transaction_ref': 'another-merchant-reference',
            'transaction_ref': 'another-provider-reference',
            'transaction_type': 'PAYOUT',
            'transaction_amount': 1,
            'transaction_currency': 'EUR',
        }

        for field, invalid_value in invalid_fields.items():
            with self.subTest(field=field):
                payload = dict(base_payload, **{field: invalid_value})
                with self.assertRaises(MyCoolPayError):
                    apply_provider_status(payment.id, payload)

        payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.STATUS_PENDING)
        self.assertFalse(self.user.is_premium)

    def test_payment_status_is_scoped_to_its_owner(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='private-provider-ref',
        )
        other_user = User.objects.create_user(
            email='other@example.com',
            password='test-pass',
            display_name='Other',
            birth_date=date(1990, 1, 1),
        )
        client = APIClient()
        client.force_authenticate(user=other_user)

        response = client.get(
            reverse(
                'api:subscriptions:payment-status',
                kwargs={'payment_id': payment.id},
            ),
            secure=True,
        )

        self.assertEqual(response.status_code, 404)

    def test_payment_status_includes_fulfilled_subscription_period(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='provider-status-details',
        )
        apply_provider_status(payment.id, self._provider_payload(payment))
        client = APIClient()
        client.force_authenticate(user=self.user)

        response = client.get(
            reverse(
                'api:subscriptions:payment-status',
                kwargs={'payment_id': payment.id},
            ),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['fulfilled'])
        self.assertEqual(
            response.data['subscription']['plan_id'],
            self.plan.plan_id,
        )
        self.assertEqual(
            response.data['subscription']['subscription_id'],
            payment.provider_transaction_ref,
        )
        self.assertIsNotNone(
            response.data['subscription']['current_period_start']
        )
        self.assertIsNotNone(
            response.data['subscription']['current_period_end']
        )

    def test_payment_return_urls_only_emit_ux_signals(self):
        cases = {
            'payment-return-success': 'success',
            'payment-return-cancel': 'cancelled',
            'payment-return-failure': 'failed',
        }
        for route_name, signal in cases.items():
            with self.subTest(route_name=route_name):
                response = APIClient().get(
                    reverse(f'api:subscriptions:{route_name}')
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response['Location'],
                    f'hivmeet://payment/result?status={signal}',
                )
                self.assertIn('no-store', response['Cache-Control'])

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_premium)

    @override_settings(MYCOOLPAY_SUCCESS_URL='http://unsafe.example.test/success')
    def test_flow_configuration_requires_exact_https_return_urls(self):
        self.assertTrue(is_mycoolpay_payment_flow_configured())
        self.assertFalse(is_mycoolpay_callback_flow_configured())

    @override_settings(
        MYCOOLPAY_FAILURE_URL=(
            'https://another.test.example/api/v1/subscriptions/'
            'payment-return/failure/'
        ),
    )
    def test_flow_configuration_requires_one_backend_origin(self):
        self.assertTrue(is_mycoolpay_payment_flow_configured())
        self.assertFalse(is_mycoolpay_callback_flow_configured())

    def test_complete_https_flow_configuration_is_available(self):
        self.assertTrue(is_mycoolpay_payment_flow_configured())
        self.assertTrue(is_mycoolpay_callback_flow_configured())

    @override_settings(
        MYCOOLPAY_PRIVATE_KEY='',
        MYCOOLPAY_CALLBACK_URL='',
        MYCOOLPAY_SUCCESS_URL='',
        MYCOOLPAY_CANCEL_URL='',
        MYCOOLPAY_FAILURE_URL='',
    )
    def test_polling_only_checkout_needs_no_callback_secret(self):
        self.assertTrue(is_mycoolpay_payment_flow_configured())
        self.assertFalse(is_mycoolpay_callback_flow_configured())

    def test_created_provider_status_remains_pending(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='created-provider-ref',
        )

        provider_payload = self._provider_payload(payment, status='CREATED')
        provider_payload['transaction_operator'] = ''
        result = apply_provider_status(payment.id, provider_payload)

        self.assertEqual(result.status, PaymentTransaction.STATUS_PENDING)
        self.assertFalse(result.is_fulfilled)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_premium)

    def test_terminal_provider_status_requires_known_operator(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='missing-operator-provider-ref',
        )
        provider_payload = self._provider_payload(payment, status='SUCCESS')
        provider_payload['transaction_operator'] = ''

        with self.assertRaisesMessage(
            MyCoolPayError,
            'Unexpected transaction operator',
        ):
            apply_provider_status(payment.id, provider_payload)

        payment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.STATUS_PENDING)
        self.assertFalse(payment.is_fulfilled)
        self.assertFalse(self.user.is_premium)

    def test_mobile_and_worker_checks_claim_one_provider_poll(self):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref='claimed-provider-ref',
        )
        test_case = self

        class FakeClient:
            calls = 0

            def check_status(self, provider_transaction_ref):
                self.calls += 1
                return test_case._provider_payload(payment, status='PENDING')

        client = FakeClient()
        _, first_attempted = reconcile_payment_if_due(
            payment.id,
            client=client,
            min_interval_seconds=60,
        )
        _, second_attempted = reconcile_payment_if_due(
            payment.id,
            client=client,
            min_interval_seconds=60,
        )

        self.assertTrue(first_attempted)
        self.assertFalse(second_attempted)
        self.assertEqual(client.calls, 1)
