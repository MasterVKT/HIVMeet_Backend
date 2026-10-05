from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import PaymentTransaction, SubscriptionPlan
from .tasks import reconcile_pending_mycoolpay_payments


User = get_user_model()


@override_settings(
    MYCOOLPAY_RECONCILIATION_MIN_AGE_SECONDS=60,
    MYCOOLPAY_RECONCILIATION_MAX_AGE_HOURS=24,
    MYCOOLPAY_RECONCILIATION_BATCH_SIZE=2,
)
class PaymentReconciliationTaskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='reconciliation@example.com',
            password='test-pass',
            display_name='Reconciliation',
            birth_date=date(1990, 1, 1),
        )
        self.plan = SubscriptionPlan.objects.create(
            plan_id='reconciliation_monthly',
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

    def _pending(self, reference, *, age):
        payment = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            amount=self.plan.price,
            currency='XAF',
            status=PaymentTransaction.STATUS_PENDING,
            provider_transaction_ref=reference,
        )
        PaymentTransaction.objects.filter(id=payment.id).update(
            created_at=timezone.now() - age,
        )
        return payment

    @patch('subscriptions.tasks.reconcile_mycoolpay_payment.delay')
    def test_dispatches_only_recoverable_pending_payments(self, delay):
        eligible = self._pending('eligible', age=timedelta(minutes=2))
        self._pending('too-recent', age=timedelta(seconds=20))
        self._pending('too-old', age=timedelta(hours=25))
        without_reference = self._pending(
            'temporary-reference',
            age=timedelta(minutes=2),
        )
        PaymentTransaction.objects.filter(id=without_reference.id).update(
            provider_transaction_ref=None,
        )

        dispatched = reconcile_pending_mycoolpay_payments()

        self.assertEqual(dispatched, 1)
        delay.assert_called_once_with(str(eligible.id))

    @override_settings(MYCOOLPAY_RECONCILIATION_BATCH_SIZE=1)
    @patch('subscriptions.tasks.reconcile_mycoolpay_payment.delay')
    def test_dispatch_is_bounded_by_configured_batch_size(self, delay):
        self._pending('first', age=timedelta(minutes=3))
        self._pending('second', age=timedelta(minutes=2))

        dispatched = reconcile_pending_mycoolpay_payments()

        self.assertEqual(dispatched, 1)
        self.assertEqual(delay.call_count, 1)
