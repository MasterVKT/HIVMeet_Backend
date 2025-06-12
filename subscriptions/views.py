"""
Views for subscriptions app.
"""
import logging
import hmac
import hashlib
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import SubscriptionPlan, Subscription, Transaction, WebhookEvent
from .serializers import (
    SubscriptionPlanSerializer,
    CurrentSubscriptionSerializer,
    EmptySubscriptionSerializer,
    PurchaseSubscriptionSerializer,
    SubscriptionResponseSerializer,
    CancelSubscriptionSerializer,
    CancelSubscriptionResponseSerializer,
    WebhookSerializer
)
from .services import MyCoolPayService, SubscriptionService

logger = logging.getLogger('hivmeet.subscriptions')


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
        return context


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
        """Get user's subscription or None."""
        try:
            return self.request.user.subscription
        except Subscription.DoesNotExist:
            return None
    
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
        """Create a new subscription."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan_id = serializer.validated_data['plan_id']
        payment_token = serializer.validated_data['payment_method_token']
        coupon_code = serializer.validated_data.get('coupon_code')
        
        # Get the plan
        plan = get_object_or_404(SubscriptionPlan, plan_id=plan_id, is_active=True)
        
        # Check if user already has an active subscription
        try:
            existing_sub = request.user.subscription
            if existing_sub.is_active:
                return Response(
                    {"error": _("You already have an active subscription")},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Subscription.DoesNotExist:
            pass
        
        # Initialize payment service
        payment_service = MyCoolPayService()
        subscription_service = SubscriptionService()
        
        try:
            # Create payment session with MyCoolPay
            payment_result = payment_service.create_payment_session(
                user=request.user,
                plan=plan,
                payment_token=payment_token,
                coupon_code=coupon_code
            )
            
            if payment_result['status'] == 'succeeded':
                # Create or update subscription
                subscription = subscription_service.create_subscription(
                    user=request.user,
                    plan=plan,
                    payment_data=payment_result
                )
                
                logger.info(f"Subscription created for user {request.user.email}")
                
                response_serializer = SubscriptionResponseSerializer(subscription)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
            elif payment_result['status'] == 'requires_action':
                # Payment requires additional action (3D Secure, etc.)
                return Response(
                    {
                        "status": "requires_action",
                        "payment_intent_client_secret": payment_result.get('client_secret'),
                        "message": _("Additional payment verification required")
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )
            
            else:
                # Payment failed
                return Response(
                    {
                        "error": _("Payment failed"),
                        "message": payment_result.get('error_message', _("Unknown error"))
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Subscription purchase error: {str(e)}")
            return Response(
                {"error": _("Unable to process subscription")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
        
        # Notify payment provider
        payment_service = MyCoolPayService()
        payment_service.cancel_subscription(subscription.subscription_id)
        
        logger.info(f"Subscription canceled for user {request.user.email}")
        
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
        
        # Notify payment provider
        payment_service = MyCoolPayService()
        payment_service.reactivate_subscription(subscription.subscription_id)
        
        logger.info(f"Subscription reactivated for user {request.user.email}")
        
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
@permission_classes([permissions.AllowAny])  # Webhook doesn't have user auth
def mycoolpay_webhook(request):
    """
    Handle MyCoolPay webhook events.
    
    POST /api/v1/webhooks/payments/mycoolpay
    """
    # Verify webhook signature
    signature = request.headers.get('X-MyCoolPay-Signature', '')
    webhook_secret = getattr(settings, 'MYCOOLPAY_WEBHOOK_SECRET', '')
    
    # Calculate expected signature
    payload = request.body.decode('utf-8')
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning("Invalid webhook signature")
        return Response(
            {"error": "Invalid signature"},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    serializer = WebhookSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    event_id = serializer.validated_data['event_id']
    event_type = serializer.validated_data['event_type']
    event_data = serializer.validated_data['data']
    
    # Check if event was already processed
    if WebhookEvent.objects.filter(event_id=event_id).exists():
        logger.info(f"Webhook event {event_id} already processed")
        return Response({"status": "already_processed"}, status=status.HTTP_200_OK)
    
    # Store webhook event
    webhook_event = WebhookEvent.objects.create(
        event_id=event_id,
        event_type=event_type,
        payload=request.data
    )
    
    try:
        # Process event based on type
        subscription_service = SubscriptionService()
        
        if event_type == 'payment.succeeded':
            subscription_service.handle_payment_success(event_data)
        
        elif event_type == 'payment.failed':
            subscription_service.handle_payment_failure(event_data)
        
        elif event_type == 'subscription.renewed':
            subscription_service.handle_subscription_renewal(event_data)
        
        elif event_type == 'subscription.canceled':
            subscription_service.handle_subscription_cancellation(event_data)
        
        elif event_type == 'refund.issued':
            subscription_service.handle_refund(event_data)
        
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
        
        # Mark event as processed
        webhook_event.processed = True
        webhook_event.processed_at = timezone.now()
        webhook_event.save()
        
        return Response({"status": "success"}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        webhook_event.error_message = str(e)
        webhook_event.save()
        
        # Return success to avoid retries for processing errors
        return Response({"status": "error"}, status=status.HTTP_200_OK)