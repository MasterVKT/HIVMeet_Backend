"""Server-owned subscription pricing and currency resolution."""

from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist


EUR = 'EUR'
XAF = 'XAF'
SUPPORTED_CURRENCIES = (XAF, EUR)
EUR_TO_XAF = Decimal('655.957')
PREMIUM_DAILY_REWINDS = 5

_CEMAC_COUNTRIES = {
    'cameroon',
    'cameroun',
    'cm',
    'central african republic',
    'republique centrafricaine',
    'cf',
    'chad',
    'tchad',
    'td',
    'republic of the congo',
    'republique du congo',
    'congo brazzaville',
    'cg',
    'equatorial guinea',
    'guinee equatoriale',
    'gq',
    'gabon',
    'ga',
}


def _normalize_country(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', ' ', text.casefold()).strip()


def get_enabled_currencies():
    """Return configured MyCoolPay currencies in stable, supported order."""
    configured = getattr(
        settings,
        'MYCOOLPAY_ENABLED_CURRENCIES',
        SUPPORTED_CURRENCIES,
    )
    if isinstance(configured, str):
        configured = configured.split(',')
    enabled = []
    for value in configured:
        currency = str(value).strip().upper()
        if currency in SUPPORTED_CURRENCIES and currency not in enabled:
            enabled.append(currency)
    return tuple(enabled) or (XAF,)


def get_default_currency():
    configured = str(
        getattr(settings, 'MYCOOLPAY_DEFAULT_CURRENCY', XAF)
    ).strip().upper()
    enabled = get_enabled_currencies()
    return configured if configured in enabled else enabled[0]


def resolve_effective_currency(user):
    """Resolve AUTO from the profile country without using precise location."""
    try:
        profile = user.profile
    except (AttributeError, ObjectDoesNotExist):
        profile = None
    preferred = str(
        getattr(profile, 'preferred_currency', 'AUTO') or 'AUTO'
    ).upper()
    if preferred == 'AUTO':
        country = _normalize_country(getattr(profile, 'country', ''))
        preferred = XAF if country in _CEMAC_COUNTRIES else EUR

    enabled = get_enabled_currencies()
    if preferred in enabled:
        return preferred
    return get_default_currency()


def quantum_for_currency(currency):
    """Smallest billable unit for a currency (XAF has no minor unit)."""
    return Decimal('1') if str(currency).upper() == XAF else Decimal('0.01')


def convert_amount(amount, source_currency, target_currency):
    """Convert EUR/XAF using the fixed BEAC parity and payment precision."""
    value = Decimal(str(amount))
    source = str(source_currency).upper()
    target = str(target_currency).upper()
    if source == target:
        converted = value
    elif source == EUR and target == XAF:
        converted = value * EUR_TO_XAF
    elif source == XAF and target == EUR:
        converted = value / EUR_TO_XAF
    else:
        raise ValueError('Unsupported subscription currency conversion')

    return converted.quantize(quantum_for_currency(target), rounding=ROUND_HALF_UP)


def quote_plan(plan, user):
    # Currency choice applies to the canonical EUR catalogue. Preserve any
    # historical/provider-native plan currency so existing subscriptions and
    # test fixtures are not silently repriced.
    currency = (
        resolve_effective_currency(user)
        if str(plan.currency).upper() == EUR
        else str(plan.currency).upper()
    )
    return {
        'amount': convert_amount(plan.price, plan.currency, currency),
        'currency': currency,
    }


def monthly_equivalent(plan, target_currency):
    divisor = Decimal('12') if plan.billing_interval == plan.INTERVAL_YEAR else Decimal('1')
    base_monthly = Decimal(plan.price) / divisor
    return convert_amount(base_monthly, plan.currency, target_currency)


def savings_percentage(plan, monthly_reference_price):
    if plan.billing_interval != plan.INTERVAL_YEAR or not monthly_reference_price:
        return 0
    full_year = Decimal(monthly_reference_price) * Decimal('12')
    if full_year <= 0 or Decimal(plan.price) >= full_year:
        return 0
    savings = (full_year - Decimal(plan.price)) * Decimal('100') / full_year
    return int(savings.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
