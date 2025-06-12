"""
Middleware for subscriptions app.
"""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework import status
from .services import PremiumFeatureService


class PremiumRequiredMiddleware(MiddlewareMixin):
    """
    Middleware to check premium status for protected endpoints.
    """
    
    # Endpoints that require premium access
    PREMIUM_ENDPOINTS = [
        '/api/v1/profiles/likes-received/',
        '/api/v1/matches/rewind/',
        '/api/v1/conversations/media/',
        '/api/v1/calls/',
        '/api/v1/profiles/boost/',
        '/api/v1/matches/super-like/',
    ]
    
    def process_request(self, request):
        """Check if the request requires premium access."""
        # Skip if user is not authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        # Check if the endpoint requires premium
        path = request.path
        requires_premium = any(path.startswith(endpoint) for endpoint in self.PREMIUM_ENDPOINTS)
        
        if requires_premium:
            # Check premium status
            if not PremiumFeatureService.check_premium_status(request.user):
                return JsonResponse(
                    {
                        "error": "premium_required",
                        "message": "Cette fonctionnalité nécessite un abonnement premium"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
        
        return None


def premium_required(view_func):
    """
    Decorator to require premium access for a view.
    
    Usage:
    @premium_required
    def my_view(request):
        # View logic here
    """
    def wrapped_view(request, *args, **kwargs):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not PremiumFeatureService.check_premium_status(request.user):
            return JsonResponse(
                {
                    "error": "premium_required",
                    "message": "Cette fonctionnalité nécessite un abonnement premium"
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view


def check_feature_limit(feature_name, use_feature=False):
    """
    Decorator to check and optionally use feature limits.
    
    Usage:
    @check_feature_limit('super_like', use_feature=True)
    def send_super_like(request, user_id):
        # View logic here
    """
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return JsonResponse(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            try:
                subscription = request.user.subscription
                if not subscription.is_premium:
                    return JsonResponse(
                        {
                            "error": "premium_required",
                            "message": "Cette fonctionnalité nécessite un abonnement premium"
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Check and reset counters if needed
                from .services import PremiumFeatureService
                PremiumFeatureService.check_and_reset_counters(subscription)
                
                # Check feature-specific limits
                if feature_name == 'boost':
                    if subscription.boosts_remaining <= 0:
                        return JsonResponse(
                            {
                                "error": "limit_reached",
                                "message": "Vous avez utilisé tous vos boosts ce mois-ci"
                            },
                            status=status.HTTP_429_TOO_MANY_REQUESTS
                        )
                    if use_feature:
                        subscription.use_boost()
                
                elif feature_name == 'super_like':
                    if subscription.super_likes_remaining <= 0:
                        return JsonResponse(
                            {
                                "error": "limit_reached",
                                "message": "Vous avez utilisé tous vos super likes aujourd'hui"
                            },
                            status=status.HTTP_429_TOO_MANY_REQUESTS
                        )
                    if use_feature:
                        subscription.use_super_like()
                
            except:
                return JsonResponse(
                    {
                        "error": "premium_required",
                        "message": "Cette fonctionnalité nécessite un abonnement premium"
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator