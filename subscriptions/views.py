"""
Views for subscriptions app.
"""
import logging
import re
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (
    SubscriptionPlan,
    Subscription,
    Transaction,
    PaymentTransaction,
)
from .utils import invalidate_premium_status_cache
from .pricing import (
    get_default_currency,
    get_enabled_currencies,
    resolve_effective_currency,
)
from hivmeet_backend.utils import api_error_response
from .serializers import (
    SubscriptionPlanSerializer,
    CurrentSubscriptionSerializer,
    EmptySubscriptionSerializer,
    PurchaseSubscriptionSerializer,
    SubscriptionResponseSerializer,
    CancelSubscriptionSerializer,
    CancelSubscriptionResponseSerializer,
    ModifySubscriptionSerializer,
)
from .services import SubscriptionService, PlanChangeRequiresPaymentError
from .payment_gateway import (
    MyCoolPayError,
    MyCoolPayConfigurationError,
    apply_provider_status,
    initiate_payment,
    is_mycoolpay_callback_flow_configured,
    is_mycoolpay_payment_flow_configured,
    reconcile_payment_if_due,
    resolve_callback_source_ip,
    verify_callback_signature,
)

logger = logging.getLogger('hivmeet.subscriptions')

IDEMPOTENCY_KEY_PATTERN = re.compile(r'^[A-Za-z0-9._:-]{8,64}$')


def _payment_session_payload(payment, *, idempotent_replay=False):
    status_mapping = {
        PaymentTransaction.STATUS_SUCCESS: 'succeeded',
        PaymentTransaction.STATUS_CANCELED: 'cancelled',
        PaymentTransaction.STATUS_FAILED: 'failed',
    }
    return {
        'payment_id': str(payment.id),
        'payment_url': payment.payment_url or None,
        'payment_status': status_mapping.get(payment.status, 'pending'),
        'amount': format(payment.amount, 'f'),
        'currency': payment.currency,
        'idempotent_replay': idempotent_replay,
    }


def _validated_idempotency_key(request):
    value = request.headers.get('Idempotency-Key')
    if value is None:
        return None
    value = value.strip()
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise ValidationError({
            'idempotency_key': _(
                'Idempotency-Key must contain 8 to 64 safe characters.'
            ),
        })
    return value


class SubscriptionPlanListView(generics.ListAPIView):
    """
    Get available subscription plans.
    
    GET /api/v1/subscriptions/plans
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SubscriptionPlanSerializer
    
    def get_queryset(self):
        """Get active subscription plans."""
        return SubscriptionPlan.objects.filter(is_active=True).order_by('order', 'price')
    
    def get_serializer_context(self):
        """Add language to context."""
        context = super().get_serializer_context()
        context['language'] = self.request.headers.get('Accept-Language', 'fr')[:2]
        context['monthly_reference_price'] = (
            SubscriptionPlan.objects.filter(
                plan_id='hivmeet_monthly',
                is_active=True,
            ).values_list('price', flat=True).first()
        )
        return context


class PaymentCapabilitiesView(APIView):
    """Expose non-secret checkout readiness and currency capabilities."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        callback_verification_available = (
            is_mycoolpay_callback_flow_configured()
        )
        payment_flow_available = is_mycoolpay_payment_flow_configured()
        return Response({
            'provider': 'mycoolpay',
            'available': payment_flow_available,
            'callback_verification_available': (
                callback_verification_available
            ),
            'automatic_return_available': callback_verification_available,
            'confirmation_mode': (
                'webhook_and_polling'
                if callback_verification_available
                else 'polling_only'
            ),
            'enabled_currencies': list(get_enabled_currencies()),
            'default_currency': get_default_currency(),
            'effective_currency': resolve_effective_currency(request.user),
        })


class CurrentSubscriptionView(generics.RetrieveAPIView):
    """
    Get current user's subscription.
    
    GET /api/v1/subscriptions/current
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on subscription status."""
        try:
            subscription = self.request.user.subscription
            if subscription and subscription.is_active:
                return CurrentSubscriptionSerializer
        except Subscription.DoesNotExist:
            pass
        return EmptySubscriptionSerializer
    
    def get_object(self):
        """Get user's subscription, or the user as a non-null placeholder.

        Returning ``None`` made DRF serialize nothing at all: with an instance
        of ``None`` and no input data, ``Serializer.data`` falls back to
        ``get_initial()``, which skips read-only fields — and every field of
        ``EmptySubscriptionSerializer`` is a read-only ``SerializerMethodField``.
        The endpoint therefore answered ``{}`` instead of the documented
        ``status: "none"`` payload. The placeholder is never read: the empty
        serializer's methods ignore their argument.
        """
        try:
            return self.request.user.subscription
        except Subscription.DoesNotExist:
            return self.request.user
    
    def get_serializer_context(self):
        """Add language to context."""
        context = super().get_serializer_context()
        context['language'] = self.request.headers.get('Accept-Language', 'fr')[:2]
        return context


class PurchaseSubscriptionView(generics.CreateAPIView):
    """
    Purchase a subscription.
    
    POST /api/v1/subscriptions/purchase
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseSubscriptionSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a Paylink; only the backend can later activate Premium."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_id = serializer.validated_data['plan_id']
        phone_number = serializer.validated_data['phone_number']
        language = serializer.validated_data['language']
        plan = get_object_or_404(SubscriptionPlan, plan_id=plan_id, is_active=True)
        idempotency_key = _validated_idempotency_key(request)

        if not is_mycoolpay_payment_flow_configured():
            logger.error("MyCoolPay payment flow is not configured")
            return api_error_response(
                'payment_not_configured',
                _("Payment is temporarily unavailable"),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if idempotency_key:
            existing_payment = PaymentTransaction.objects.filter(
                user=request.user,
                idempotency_key=idempotency_key,
            ).first()
            if existing_payment:
                if existing_payment.plan_id != plan.id:
                    return api_error_response(
                        'idempotency_conflict',
                        _(
                            'This idempotency key was already used for another plan.'
                        ),
                        status.HTTP_409_CONFLICT,
                    )
                return Response(
                    _payment_session_payload(
                        existing_payment,
                        idempotent_replay=True,
                    ),
                    status=status.HTTP_200_OK,
                )

        try:
            existing_sub = request.user.subscription
            if existing_sub.is_active:
                return api_error_response(
                    'active_subscription_exists',
                    _("You already have an active subscription"),
                    status.HTTP_409_CONFLICT,
                )
        except Subscription.DoesNotExist:
            pass

        try:
            payment = initiate_payment(
                user=request.user,
                plan=plan,
                phone_number=phone_number,
                language=language,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            if not idempotency_key:
                raise
            payment = PaymentTransaction.objects.filter(
                user=request.user,
                idempotency_key=idempotency_key,
            ).first()
            if payment is None:
                raise
            if payment.plan_id != plan.id:
                return api_error_response(
                    'idempotency_conflict',
                    _(
                        'This idempotency key was already used for another plan.'
                    ),
                    status.HTTP_409_CONFLICT,
                )
            return Response(
                _payment_session_payload(payment, idempotent_replay=True),
                status=status.HTTP_200_OK,
            )
        except MyCoolPayConfigurationError:
            logger.error("MyCoolPay is not configured")
            return api_error_response(
                'payment_not_configured',
                _("Payment is temporarily unavailable"),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except MyCoolPayError:
            logger.warning("MyCoolPay Paylink creation failed")
            return api_error_response(
                'payment_provider_unavailable',
                _("Unable to create the payment link"),
                status.HTTP_502_BAD_GATEWAY,
            )

        response_status = (
            status.HTTP_201_CREATED
            if payment.payment_url
            else status.HTTP_202_ACCEPTED
        )
        return Response(_payment_session_payload(payment), status=response_status)


class PaymentStatusView(generics.GenericAPIView):
    """Return backend-owned status and reconcile pending payments."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id, *args, **kwargs):
        payment = get_object_or_404(
            PaymentTransaction.objects.select_related('plan'),
            id=payment_id,
            user=request.user,
        )

        if (
            payment.status == PaymentTransaction.STATUS_PENDING
            and payment.provider_transaction_ref
        ):
            try:
                payment, _ = reconcile_payment_if_due(
                    payment.id,
                    min_interval_seconds=getattr(
                        settings,
                        'MYCOOLPAY_STATUS_MIN_INTERVAL_SECONDS',
                        5,
                    ),
                )
            except MyCoolPayError:
                logger.warning("MyCoolPay reconciliation failed")

        subscription_id = None
        activated_at = None
        subscription_payload = None
        if payment.is_fulfilled:
            try:
                subscription = request.user.subscription
                subscription_id = subscription.subscription_id
                activated_at = subscription.current_period_start
                subscription_payload = {
                    'subscription_id': subscription.subscription_id,
                    'plan_id': subscription.plan.plan_id,
                    'status': subscription.status,
                    'current_period_start': subscription.current_period_start,
                    'current_period_end': subscription.current_period_end,
                }
            except Subscription.DoesNotExist:
                pass

        status_mapping = {
            PaymentTransaction.STATUS_SUCCESS: 'succeeded',
            PaymentTransaction.STATUS_CANCELED: 'cancelled',
            PaymentTransaction.STATUS_FAILED: 'failed',
        }
        return Response({
            'payment_id': str(payment.id),
            'payment_status': status_mapping.get(payment.status, 'pending'),
            'fulfilled': payment.is_fulfilled,
            'subscription_id': subscription_id,
            'activated_at': activated_at,
            'subscription': subscription_payload,
        })


def _payment_return_response(result):
    response = HttpResponse(status=302)
    response['Location'] = f'hivmeet://payment/result?status={result}'
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def payment_return_success(request):
    """UX-only redirect; it never confirms or fulfills a payment."""
    return _payment_return_response('success')


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def payment_return_cancel(request):
    """UX-only cancellation signal; backend status remains authoritative."""
    return _payment_return_response('cancelled')


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def payment_return_failure(request):
    """UX-only failure signal; backend status remains authoritative."""
    return _payment_return_response('failed')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_subscription(request):
    """
    Cancel current subscription.
    
    POST /api/v1/subscriptions/current/cancel
    """
    serializer = CancelSubscriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        subscription = request.user.subscription
        if not subscription.is_active:
            return Response(
                {"error": _("No active subscription to cancel")},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Mark subscription for cancellation at period end
        subscription.cancel_at_period_end = True
        subscription.canceled_at = timezone.now()
        subscription.cancellation_reason = serializer.validated_data.get('reason', '')
        subscription.save()
        
        logger.info("Subscription canceled")
        
        response_serializer = CancelSubscriptionResponseSerializer(subscription)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
        
    except Subscription.DoesNotExist:
        return Response(
            {"error": _("No subscription found")},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reactivate_subscription(request):
    """
    Reactivate a canceled subscription.
    
    POST /api/v1/subscriptions/current/reactivate
    """
    try:
        subscription = request.user.subscription
        
        # Check if subscription can be reactivated
        if not subscription.cancel_at_period_end:
            return Response(
                {"error": _("Subscription is not scheduled for cancellation")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if subscription.current_period_end < timezone.now():
            return Response(
                {"error": _("Subscription has already expired")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reactivate subscription
        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        subscription.cancellation_reason = ''
        subscription.save()
        
        logger.info("Subscription reactivated")
        
        response_serializer = CurrentSubscriptionSerializer(
            subscription,
            context={'language': request.headers.get('Accept-Language', 'fr')[:2]}
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
        
    except Subscription.DoesNotExist:
        return Response(
            {"error": _("No subscription found")},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def modify_subscription(request):
    """
    Change the current subscription to a new plan (upgrade/downgrade).

    POST /api/v1/subscriptions/current/modify/

    Body:
        new_plan_id (str): the plan_id of the target plan.
        proration (bool, default True): if True, apply the change immediately
            — without payment if the outgoing plan's unused credit covers
            the new plan in full, otherwise by creating a new Paylink for
            the prorated net amount (MyCoolPay has no subscription-
            modification API, only Paylink-based purchases). If False,
            schedule the change for the next billing cycle instead.
        phone_number, language: only required when a Paylink turns out to
            be necessary (positive net amount with proration=True) — same
            shape as ``POST /subscriptions/purchase/``.

    A response carrying ``payment_id``/``payment_url`` means a Paylink was
    created: the plan itself is only switched once the webhook confirms
    that payment (identical pipeline to a fresh purchase). Otherwise the
    response is the updated subscription, applied immediately.
    """
    serializer = ModifySubscriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new_plan_id = serializer.validated_data['new_plan_id']
    proration_requested = serializer.validated_data.get('proration', True)
    phone_number = serializer.validated_data.get('phone_number') or None
    payment_language = serializer.validated_data.get('language', 'fr')
    idempotency_key = _validated_idempotency_key(request)

    user = request.user

    # 1. Verify an active subscription exists
    try:
        subscription = user.subscription
    except Subscription.DoesNotExist:
        return Response(
            {
                "error": "no_active_subscription",
                "message": _("Aucun abonnement actif à modifier."),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not subscription.is_active:
        return Response(
            {
                "error": "no_active_subscription",
                "message": _("Aucun abonnement actif à modifier."),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Load the target plan (already validated by serializer, but load instance)
    new_plan = SubscriptionPlan.objects.get(plan_id=new_plan_id, is_active=True)

    # 3. Reject same-plan modification
    if subscription.plan_id == new_plan.id:
        return Response(
            {
                "error": "same_plan",
                "message": _("Le nouveau plan est identique au plan actuel."),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 4. Delegate to the service
    subscription_service = SubscriptionService()
    try:
        result = subscription_service.modify_subscription(
            subscription=subscription,
            new_plan=new_plan,
            proration=proration_requested,
        )
    except PlanChangeRequiresPaymentError as e:
        # A real charge is required: create a new Paylink for the prorated
        # net amount, mirroring PurchaseSubscriptionView. The plan change
        # itself is only applied once the webhook confirms this payment.
        if not phone_number:
            return Response(
                {
                    "error": "phone_number_required",
                    "message": _(
                        "Un numéro de téléphone est requis pour ce changement de plan."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not is_mycoolpay_payment_flow_configured():
            logger.error("MyCoolPay payment flow is not configured")
            return api_error_response(
                'payment_not_configured',
                _("Payment is temporarily unavailable"),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        proration_info = e.proration_info
        net_amount = (
            proration_info['charge_amount'] - proration_info['credit_amount']
        )

        if idempotency_key:
            existing_payment = PaymentTransaction.objects.filter(
                user=user,
                idempotency_key=idempotency_key,
            ).first()
            if existing_payment:
                if existing_payment.plan_id != new_plan.id:
                    return api_error_response(
                        'idempotency_conflict',
                        _(
                            'This idempotency key was already used for another plan.'
                        ),
                        status.HTTP_409_CONFLICT,
                    )
                return Response(
                    _payment_session_payload(
                        existing_payment,
                        idempotent_replay=True,
                    ),
                    status=status.HTTP_200_OK,
                )

        try:
            payment = initiate_payment(
                user=user,
                plan=new_plan,
                phone_number=phone_number,
                language=payment_language,
                idempotency_key=idempotency_key,
                amount=net_amount,
                currency=proration_info['currency'],
            )
        except IntegrityError:
            if not idempotency_key:
                raise
            payment = PaymentTransaction.objects.filter(
                user=user,
                idempotency_key=idempotency_key,
            ).first()
            if payment is None:
                raise
            if payment.plan_id != new_plan.id:
                return api_error_response(
                    'idempotency_conflict',
                    _(
                        'This idempotency key was already used for another plan.'
                    ),
                    status.HTTP_409_CONFLICT,
                )
            return Response(
                _payment_session_payload(payment, idempotent_replay=True),
                status=status.HTTP_200_OK,
            )
        except MyCoolPayConfigurationError:
            logger.error("MyCoolPay is not configured")
            return api_error_response(
                'payment_not_configured',
                _("Payment is temporarily unavailable"),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except MyCoolPayError:
            logger.warning("MyCoolPay Paylink creation failed for plan modification")
            return api_error_response(
                'payment_provider_unavailable',
                _("Unable to create the payment link"),
                status.HTTP_502_BAD_GATEWAY,
            )

        response_status = (
            status.HTTP_201_CREATED
            if payment.payment_url
            else status.HTTP_202_ACCEPTED
        )
        logger.info(
            "Plan-change Paylink created; plan=%s net_amount=%s",
            new_plan.plan_id,
            net_amount,
        )
        return Response(_payment_session_payload(payment), status=response_status)
    except Exception:
        logger.exception("Subscription modification failed")
        return Response(
            {
                "error": "modification_failed",
                "message": _("Erreur lors de la modification."),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 5. Invalidate premium cache (also done in the service, but double-check)
    invalidate_premium_status_cache(user)

    # 6. Serialize the updated subscription and append proration info
    response_language = request.headers.get('Accept-Language', 'fr')[:2]
    response_serializer = CurrentSubscriptionSerializer(
        subscription,
        context={'request': request, 'language': response_language},
    )
    data = response_serializer.data
    data['proration'] = result.get('proration_info')

    logger.info(
        "Subscription modified; plan=%s proration=%s",
        new_plan.plan_id,
        proration_requested,
    )

    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Webhook doesn't have user auth
def mycoolpay_webhook(request):
    """Verify and apply the single MyCoolPay callback."""
    payload = request.data
    if not isinstance(payload, dict):
        return HttpResponse('KO', status=400, content_type='text/plain')
    source_ip = resolve_callback_source_ip(request)
    allowed_ips = getattr(
        settings,
        'MYCOOLPAY_CALLBACK_ALLOWED_IPS',
        (),
    )
    if isinstance(allowed_ips, str):
        allowed_ips = tuple(
            value.strip() for value in allowed_ips.split(',') if value.strip()
        )
    if source_ip not in allowed_ips:
        logger.warning("Rejected MyCoolPay callback from an unauthorized IP")
        return HttpResponse('KO', status=403, content_type='text/plain')

    required_fields = {
        'application',
        'app_transaction_ref',
        'transaction_ref',
        'transaction_type',
        'transaction_amount',
        'transaction_currency',
        'transaction_operator',
        'transaction_status',
        'signature',
    }
    if not required_fields.issubset(payload.keys()):
        return HttpResponse('KO', status=400, content_type='text/plain')

    public_key = getattr(settings, 'MYCOOLPAY_PUBLIC_KEY', '')
    if not public_key or payload.get('application') != public_key:
        logger.warning("Rejected MyCoolPay callback for another application")
        return HttpResponse('KO', status=403, content_type='text/plain')

    try:
        if not verify_callback_signature(payload):
            logger.warning("Rejected MyCoolPay callback with invalid signature")
            return HttpResponse('KO', status=403, content_type='text/plain')
        payment = PaymentTransaction.objects.get(
            app_transaction_ref=payload['app_transaction_ref']
        )
        apply_provider_status(payment.id, payload)
    except PaymentTransaction.DoesNotExist:
        logger.warning("MyCoolPay callback references an unknown payment")
        return HttpResponse('KO', status=404, content_type='text/plain')
    except (MyCoolPayError, MyCoolPayConfigurationError):
        logger.warning("Rejected inconsistent MyCoolPay callback")
        return HttpResponse('KO', status=400, content_type='text/plain')

    return HttpResponse('OK', content_type='text/plain')
