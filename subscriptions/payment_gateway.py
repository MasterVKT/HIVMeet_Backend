"""MyCoolPay Paylink integration and idempotent subscription fulfillment."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import ipaddress
import logging
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import PaymentTransaction
from .pricing import quote_plan


logger = logging.getLogger('hivmeet.subscriptions')


class MyCoolPayError(Exception):
    pass


class MyCoolPayConfigurationError(MyCoolPayError):
    pass


class MyCoolPayTransientError(MyCoolPayError):
    """A provider failure that can be retried by reconciliation."""


class MyCoolPayAmbiguousError(MyCoolPayTransientError):
    """The Paylink request may have reached the provider without a response."""


def _safe_https_url(value, *, expected_path=None):
    parsed = urlparse(str(value or ''))
    try:
        parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != 'https'
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return False
    if expected_path is not None and parsed.path != expected_path:
        return False
    return True


def _configured_ip_values(setting_name):
    values = getattr(settings, setting_name, ())
    if isinstance(values, str):
        values = values.split(',')
    configured = []
    for value in values:
        candidate = str(value).strip()
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        configured.append(candidate)
    return tuple(configured)


def resolve_callback_source_ip(request):
    """Resolve the provider IP without trusting arbitrary forwarded headers."""
    peer = str(request.META.get('REMOTE_ADDR', '')).strip()
    trusted_proxies = set(_configured_ip_values('MYCOOLPAY_TRUSTED_PROXY_IPS'))
    if peer not in trusted_proxies:
        return peer

    forwarded = str(request.META.get('HTTP_X_FORWARDED_FOR', ''))
    chain = [value.strip() for value in forwarded.split(',') if value.strip()]
    chain.append(peer)
    for candidate in reversed(chain):
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if candidate not in trusted_proxies:
            return candidate
    return peer


def is_mycoolpay_checkout_configured():
    public_key = getattr(settings, 'MYCOOLPAY_PUBLIC_KEY', '')
    base_url = getattr(
        settings,
        'MYCOOLPAY_BASE_URL',
        'https://my-coolpay.com/api',
    )
    parsed = urlparse(str(base_url))
    return bool(
        public_key
        and parsed.scheme == 'https'
        and parsed.hostname == 'my-coolpay.com'
        and parsed.path.rstrip('/') == '/api'
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def is_mycoolpay_callback_flow_configured():
    """Require every merchant-dashboard value needed for signed callbacks."""
    if not is_mycoolpay_checkout_configured():
        return False
    if not getattr(settings, 'MYCOOLPAY_PRIVATE_KEY', ''):
        return False
    if not _configured_ip_values('MYCOOLPAY_CALLBACK_ALLOWED_IPS'):
        return False

    configured_urls = {
        'callback': (
            getattr(settings, 'MYCOOLPAY_CALLBACK_URL', ''),
            '/api/v1/webhooks/payments/mycoolpay/',
        ),
        'success': (
            getattr(settings, 'MYCOOLPAY_SUCCESS_URL', ''),
            '/api/v1/subscriptions/payment-return/success/',
        ),
        'cancel': (
            getattr(settings, 'MYCOOLPAY_CANCEL_URL', ''),
            '/api/v1/subscriptions/payment-return/cancel/',
        ),
        'failure': (
            getattr(settings, 'MYCOOLPAY_FAILURE_URL', ''),
            '/api/v1/subscriptions/payment-return/failure/',
        ),
    }
    normalized = []
    origins = set()
    for value, expected_path in configured_urls.values():
        if not _safe_https_url(value, expected_path=expected_path):
            return False
        parsed = urlparse(str(value))
        origins.add((parsed.hostname, parsed.port or 443))
        normalized.append(str(value).rstrip('/'))
    return len(origins) == 1 and len(normalized) == len(set(normalized))


def is_mycoolpay_payment_flow_configured():
    """Allow checkout when authoritative provider polling is available.

    My-CoolPay's current ``checkStatus`` endpoint is authenticated by the
    application public key in the URL and returns the complete provider-owned
    transaction tuple.  A merchant private key is only required to verify the
    optional push callback.  Keeping checkout available in polling-only test
    environments therefore does not grant Premium from a browser redirect or
    any client-provided status: fulfillment still goes through
    :func:`apply_provider_status` after a server-to-server status check.
    """
    return is_mycoolpay_checkout_configured()


def canonical_amount(value):
    """Format an amount exactly as required by the callback signature."""
    try:
        normalized = format(Decimal(str(value)), 'f')
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MyCoolPayError('Invalid transaction amount') from exc
    if '.' in normalized:
        normalized = normalized.rstrip('0').rstrip('.')
    return normalized or '0'


def callback_signature(payload, private_key):
    raw = ''.join([
        str(payload.get('transaction_ref', '')),
        str(payload.get('transaction_type', '')),
        canonical_amount(payload.get('transaction_amount')),
        str(payload.get('transaction_currency', '')),
        str(payload.get('transaction_operator', '')),
        private_key,
    ])
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def verify_callback_signature(payload):
    private_key = getattr(settings, 'MYCOOLPAY_PRIVATE_KEY', '')
    if not private_key:
        raise MyCoolPayConfigurationError('MyCoolPay private key is not configured')
    supplied = str(payload.get('signature', ''))
    return bool(supplied) and hmac.compare_digest(
        supplied.lower(),
        callback_signature(payload, private_key).lower(),
    )


def _validated_payment_url(value):
    parsed = urlparse(str(value))
    allowed_hosts = getattr(
        settings,
        'MYCOOLPAY_PAYMENT_HOSTS',
        ('my-coolpay.com',),
    )
    if isinstance(allowed_hosts, str):
        allowed_hosts = allowed_hosts.split(',')
    allowed_hosts = {
        str(host).strip().lower() for host in allowed_hosts if str(host).strip()
    }
    if (
        parsed.scheme != 'https'
        or parsed.hostname not in allowed_hosts
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise MyCoolPayError('MyCoolPay returned an invalid payment URL')
    return parsed.geturl()


class MyCoolPayPaylinkClient:
    def __init__(self, session=None):
        self.public_key = getattr(settings, 'MYCOOLPAY_PUBLIC_KEY', '')
        self.base_url = getattr(
            settings,
            'MYCOOLPAY_BASE_URL',
            'https://my-coolpay.com/api',
        ).rstrip('/')
        self.timeout = (
            getattr(settings, 'MYCOOLPAY_CONNECT_TIMEOUT', 5),
            getattr(settings, 'MYCOOLPAY_READ_TIMEOUT', 20),
        )
        self.session = session or requests.Session()

    def _endpoint(self, suffix):
        if not is_mycoolpay_checkout_configured():
            raise MyCoolPayConfigurationError(
                'MyCoolPay checkout is not configured safely'
            )
        return f"{self.base_url}/{self.public_key}/{suffix.lstrip('/')}"

    def create_paylink(self, payment, phone_number, language='fr'):
        provider_amount = (
            int(payment.amount)
            if payment.currency == 'XAF'
            else float(payment.amount)
        )
        payload = {
            'transaction_amount': provider_amount,
            'transaction_currency': payment.currency,
            'transaction_reason': f'HIVMeet {payment.plan.get_name(language)}',
            'app_transaction_ref': payment.app_transaction_ref,
            'customer_phone_number': phone_number,
            'customer_name': payment.user.display_name,
            'customer_email': payment.user.email,
            'customer_lang': language if language in {'fr', 'en'} else 'fr',
        }
        try:
            response = self.session.post(
                self._endpoint('paylink'),
                json=payload,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                timeout=self.timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MyCoolPayAmbiguousError(
                'MyCoolPay Paylink response is unknown'
            ) from exc
        try:
            response.raise_for_status()
            data = response.json()
        except requests.HTTPError as exc:
            response_status = getattr(exc.response, 'status_code', None)
            if response_status == 429 or (
                response_status is not None and response_status >= 500
            ):
                raise MyCoolPayAmbiguousError(
                    'MyCoolPay Paylink response is unknown'
                ) from exc
            raise MyCoolPayError('MyCoolPay rejected the payment link') from exc
        except ValueError as exc:
            raise MyCoolPayAmbiguousError(
                'MyCoolPay Paylink response is unknown'
            ) from exc
        except requests.RequestException as exc:
            raise MyCoolPayError('Unable to create the payment link') from exc

        if response.status_code != 201 or not isinstance(data, dict):
            raise MyCoolPayAmbiguousError(
                'MyCoolPay Paylink response is unknown'
            )
        if data.get('status') != 'success' or not data.get('transaction_ref'):
            raise MyCoolPayAmbiguousError(
                'MyCoolPay Paylink response is unknown'
            )
        try:
            data['payment_url'] = _validated_payment_url(data.get('payment_url'))
        except MyCoolPayError as exc:
            raise MyCoolPayAmbiguousError(
                'MyCoolPay Paylink response is unknown'
            ) from exc
        return data

    def check_status(self, provider_transaction_ref):
        encoded_reference = quote(str(provider_transaction_ref), safe='')
        try:
            response = self.session.get(
                self._endpoint(f'checkStatus/{encoded_reference}'),
                headers={'Accept': 'application/json'},
                timeout=self.timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MyCoolPayTransientError(
                'Unable to reach MyCoolPay status service'
            ) from exc
        try:
            response.raise_for_status()
            data = response.json()
        except requests.HTTPError as exc:
            response_status = getattr(exc.response, 'status_code', None)
            if response_status == 429 or (
                response_status is not None and response_status >= 500
            ):
                raise MyCoolPayTransientError(
                    'MyCoolPay status service is temporarily unavailable'
                ) from exc
            raise MyCoolPayError('MyCoolPay status check was rejected') from exc
        except (requests.RequestException, ValueError) as exc:
            raise MyCoolPayError('Unable to check the payment status') from exc
        if response.status_code != 200 or not isinstance(data, dict):
            raise MyCoolPayError('Unexpected MyCoolPay status response')
        if data.get('status') != 'success':
            raise MyCoolPayError('MyCoolPay status check failed')
        return data


def initiate_payment(
    *,
    user,
    plan,
    phone_number,
    language='fr',
    idempotency_key=None,
    client=None,
    amount=None,
    currency=None,
):
    """Persist the merchant reference before calling MyCoolPay.

    ``amount``/``currency`` let a caller charge something other than the
    plan's full price (e.g. a prorated plan-change charge) while reusing the
    same Paylink creation and webhook fulfillment pipeline as a normal
    purchase. When omitted, the full plan price is quoted as before.
    """
    if amount is None or currency is None:
        quote = quote_plan(plan, user)
        amount = quote['amount']
        currency = quote['currency']
    payment = PaymentTransaction.objects.create(
        user=user,
        plan=plan,
        amount=amount,
        currency=currency,
        idempotency_key=idempotency_key,
    )
    try:
        provider_data = (client or MyCoolPayPaylinkClient()).create_paylink(
            payment,
            phone_number,
            language,
        )
    except MyCoolPayAmbiguousError:
        # Do not create another provider transaction blindly. A valid callback
        # can still bind the provider reference to this merchant reference.
        payment.provider_message = 'provider_response_unknown'
        payment.save(update_fields=['provider_message', 'updated_at'])
        return payment
    except MyCoolPayError:
        payment.status = PaymentTransaction.STATUS_FAILED
        payment.provider_message = 'paylink_creation_failed'
        payment.save(update_fields=['status', 'provider_message', 'updated_at'])
        raise

    payment.provider_transaction_ref = provider_data['transaction_ref']
    payment.payment_url = provider_data['payment_url']
    payment.status = PaymentTransaction.STATUS_PENDING
    payment.save(update_fields=[
        'provider_transaction_ref',
        'payment_url',
        'status',
        'updated_at',
    ])
    return payment


def _bind_and_validate_provider_payload(payment, payload):
    if str(payload.get('app_transaction_ref')) != payment.app_transaction_ref:
        raise MyCoolPayError('Merchant reference mismatch')
    provider_reference = str(payload.get('transaction_ref') or '')
    if not provider_reference:
        raise MyCoolPayError('Provider reference is missing')
    if (
        payment.provider_transaction_ref
        and provider_reference != payment.provider_transaction_ref
    ):
        raise MyCoolPayError('Provider reference mismatch')
    if not payment.provider_transaction_ref:
        if PaymentTransaction.objects.exclude(id=payment.id).filter(
            provider_transaction_ref=provider_reference,
        ).exists():
            raise MyCoolPayError('Provider reference is already bound')
        payment.provider_transaction_ref = provider_reference
    if str(payload.get('transaction_type')) != 'PAYIN':
        raise MyCoolPayError('Unexpected transaction type')
    if canonical_amount(payload.get('transaction_amount')) != canonical_amount(payment.amount):
        raise MyCoolPayError('Transaction amount mismatch')
    if str(payload.get('transaction_currency', '')).upper() != payment.currency:
        raise MyCoolPayError('Transaction currency mismatch')
    allowed_operators = getattr(
        settings,
        'MYCOOLPAY_ALLOWED_OPERATORS',
        ('MCP', 'CM_MOMO', 'CM_OM', 'CARD'),
    )
    if isinstance(allowed_operators, str):
        allowed_operators = allowed_operators.split(',')
    allowed_operators = {
        str(operator).strip() for operator in allowed_operators
    }
    provider_operator = str(
        payload.get('transaction_operator') or ''
    ).strip()
    provider_status = str(
        payload.get('transaction_status') or ''
    ).upper()
    # A newly-created Paylink has no operator until the customer selects a
    # payment method. My-CoolPay reports that legitimate pre-payment state as
    # CREATED (and may also report PENDING). Terminal states must always carry
    # a recognised operator before they can alter entitlements.
    operator_may_be_unset = provider_status in {'CREATED', 'PENDING'}
    if (
        (not provider_operator and not operator_may_be_unset)
        or (provider_operator and provider_operator not in allowed_operators)
    ):
        raise MyCoolPayError('Unexpected transaction operator')


@transaction.atomic
def apply_provider_status(payment_id, payload):
    """Validate provider data and fulfill a successful payment exactly once."""
    # Lock only the merchant transaction. Joining the nullable, anonymisable
    # user relation here produces an outer join that PostgreSQL cannot lock.
    payment = PaymentTransaction.objects.select_for_update().get(id=payment_id)
    _bind_and_validate_provider_payload(payment, payload)

    provider_status = str(payload.get('transaction_status', '')).upper()
    # A freshly-created real Paylink is reported as CREATED before it moves to
    # PENDING.  Both are non-terminal provider states and map to the single
    # local PENDING state.  Keeping the mapping here also covers reconciliation
    # and mobile polling through the same validation/finalization path.
    if provider_status == 'CREATED':
        provider_status = PaymentTransaction.STATUS_PENDING
    valid_statuses = {
        PaymentTransaction.STATUS_PENDING,
        PaymentTransaction.STATUS_SUCCESS,
        PaymentTransaction.STATUS_CANCELED,
        PaymentTransaction.STATUS_FAILED,
    }
    if provider_status not in valid_statuses:
        raise MyCoolPayError('Unexpected transaction status')

    terminal_statuses = {
        PaymentTransaction.STATUS_SUCCESS,
        PaymentTransaction.STATUS_CANCELED,
        PaymentTransaction.STATUS_FAILED,
    }
    if payment.status in terminal_statuses and payment.status != provider_status:
        raise MyCoolPayError('Terminal transaction status mismatch')

    payment.last_checked_at = timezone.now()
    payment.provider_message = str(payload.get('transaction_message') or '')[:255]

    if provider_status == PaymentTransaction.STATUS_SUCCESS:
        if not payment.is_fulfilled:
            if payment.user is None:
                raise MyCoolPayError('The customer account no longer exists')
            # A provider callback can arrive after an otherwise authorised
            # checkout has lost KYC validity. Keep the payment record for
            # support/reconciliation, but never grant effective Premium until
            # the independent KYC predicate is true at fulfillment time.
            from profiles.kyc import has_active_kyc

            if not has_active_kyc(payment.user):
                payment.status = PaymentTransaction.STATUS_SUCCESS
                payment.paid_at = timezone.now()
                payment.provider_message = 'kyc_required_for_activation'
                payment.save(update_fields=[
                    'provider_transaction_ref',
                    'status',
                    'provider_message',
                    'paid_at',
                    'fulfilled_at',
                    'last_checked_at',
                    'updated_at',
                ])
                return payment
            from .services import SubscriptionService

            SubscriptionService().create_subscription(
                user=payment.user,
                plan=payment.plan,
                payment_data={
                    'subscription_id': payment.provider_transaction_ref,
                    'payment_intent_id': payment.provider_transaction_ref,
                    'amount': payment.amount,
                    'currency': payment.currency,
                    'payment_method': str(
                        payload.get('transaction_operator') or 'mycoolpay'
                    ),
                },
            )
            payment.paid_at = timezone.now()
            payment.fulfilled_at = timezone.now()
        payment.status = PaymentTransaction.STATUS_SUCCESS
    elif payment.status != PaymentTransaction.STATUS_SUCCESS:
        payment.status = provider_status

    payment.save(update_fields=[
        'provider_transaction_ref',
        'status',
        'provider_message',
        'paid_at',
        'fulfilled_at',
        'last_checked_at',
        'updated_at',
    ])
    return payment


def reconcile_payment(payment, client=None):
    if not payment.provider_transaction_ref or payment.is_fulfilled:
        return payment
    payload = (client or MyCoolPayPaylinkClient()).check_status(
        payment.provider_transaction_ref
    )
    return apply_provider_status(payment.id, payload)


def reconcile_payment_if_due(
    payment_id,
    *,
    client=None,
    min_interval_seconds=5,
    force=False,
):
    """Claim one pending payment before contacting MyCoolPay.

    The atomic update prevents the mobile polling endpoint and Celery workers
    from issuing concurrent status checks for the same payment.
    """
    now = timezone.now()
    queryset = PaymentTransaction.objects.filter(
        id=payment_id,
        status=PaymentTransaction.STATUS_PENDING,
        provider_transaction_ref__isnull=False,
    )
    if not force:
        cutoff = now - timedelta(seconds=max(1, min_interval_seconds))
        queryset = queryset.filter(
            Q(last_checked_at__isnull=True) | Q(last_checked_at__lte=cutoff)
        )
    claimed = queryset.update(last_checked_at=now)
    payment = PaymentTransaction.objects.get(id=payment_id)
    if not claimed:
        return payment, False
    return reconcile_payment(payment, client=client), True
