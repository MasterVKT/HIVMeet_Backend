"""
Utility functions for subscriptions app.
File: subscriptions/utils.py
"""
from django.core.cache import cache
from django.utils import timezone
from functools import wraps
from rest_framework.response import Response
from rest_framework import status


def is_premium_user(user):
    """
    Check if a user has an active premium subscription.
    
    Args:
        user: User instance
    
    Returns:
        bool: True if user has active premium subscription
    """
    if not user or not user.is_authenticated:
        return False
    
    # Check cache first
    cache_key = f"user_premium_status_{user.id}"
    cached_status = cache.get(cache_key)
    if cached_status is not None:
        return cached_status
    
    # Check database
    is_premium = False
    if user.is_premium and user.premium_until:
        is_premium = user.premium_until > timezone.now()
    
    # Cache result for 5 minutes
    cache.set(cache_key, is_premium, 300)
    
    return is_premium


def get_user_subscription(user):
    """
    Get user's active subscription if exists.
    
    Args:
        user: User instance
    
    Returns:
        Subscription instance or None
    """
    if not user or not user.is_authenticated:
        return None
    
    try:
        from .models import Subscription
        subscription = user.subscription
        if subscription.is_active:
            return subscription
    except Subscription.DoesNotExist:
        pass
    
    return None


def check_feature_availability(user, feature_name):
    """
    Check if a user can access a specific premium feature.
    
    Args:
        user: User instance
        feature_name: Name of the feature to check
    
    Returns:
        dict: {'available': bool, 'reason': str}
    """
    if not is_premium_user(user):
        return {
            'available': False,
            'reason': 'premium_required'
        }
    
    subscription = get_user_subscription(user)
    if not subscription:
        return {
            'available': False,
            'reason': 'no_active_subscription'
        }
    
    # Check specific features
    feature_checks = {
        'unlimited_likes': lambda s: s.plan.unlimited_likes,
        'see_likers': lambda s: s.plan.can_see_likers,
        'rewind': lambda s: s.plan.can_rewind,
        'boost': lambda s: s.boosts_remaining > 0,
        'super_like': lambda s: s.super_likes_remaining > 0,
        'media_messaging': lambda s: s.plan.media_messaging_enabled,
        'calls': lambda s: s.plan.audio_video_calls_enabled,
    }
    
    check_func = feature_checks.get(feature_name)
    if not check_func:
        return {
            'available': False,
            'reason': 'unknown_feature'
        }
    
    if check_func(subscription):
        return {
            'available': True,
            'reason': 'ok'
        }
    else:
        return {
            'available': False,
            'reason': 'limit_reached' if feature_name in ['boost', 'super_like'] else 'feature_not_included'
        }


def consume_premium_feature(user, feature_name):
    """
    Consume a limited premium feature (boost, super_like).
    
    Args:
        user: User instance
        feature_name: 'boost' or 'super_like'
    
    Returns:
        dict: {'success': bool, 'remaining': int, 'error': str}
    """
    subscription = get_user_subscription(user)
    if not subscription:
        return {
            'success': False,
            'remaining': 0,
            'error': 'no_active_subscription'
        }
    
    # Check and reset counters if needed
    from .services import PremiumFeatureService
    PremiumFeatureService.check_and_reset_counters(subscription)
    
    if feature_name == 'boost':
        if subscription.use_boost():
            return {
                'success': True,
                'remaining': subscription.boosts_remaining,
                'error': None
            }
        else:
            return {
                'success': False,
                'remaining': 0,
                'error': 'no_boosts_remaining'
            }
    
    elif feature_name == 'super_like':
        if subscription.use_super_like():
            return {
                'success': True,
                'remaining': subscription.super_likes_remaining,
                'error': None
            }
        else:
            return {
                'success': False,
                'remaining': 0,
                'error': 'no_super_likes_remaining'
            }
    
    return {
        'success': False,
        'remaining': 0,
        'error': 'unknown_feature'
    }


def premium_required_response():
    """
    Standard response for premium-required endpoints.
    """
    return Response(
        {
            "error": "premium_required",
            "message": "Cette fonctionnalité nécessite un abonnement premium",
            "upgrade_url": "/subscriptions/plans"
        },
        status=status.HTTP_403_FORBIDDEN
    )


def get_premium_limits(user):
    """
    Get current premium feature limits and usage for a user.
    
    Args:
        user: User instance
    
    Returns:
        dict: Feature limits and current usage
    """
    if not is_premium_user(user):
        return {
            'is_premium': False,
            'limits': {}
        }
    
    subscription = get_user_subscription(user)
    if not subscription:
        return {
            'is_premium': True,
            'limits': {}
        }
    
    # Check and reset counters
    from .services import PremiumFeatureService
    PremiumFeatureService.check_and_reset_counters(subscription)
    
    return {
        'is_premium': True,
        'limits': {
            'boosts': {
                'total': subscription.plan.monthly_boosts_count,
                'remaining': subscription.boosts_remaining,
                'reset_date': subscription.last_boosts_reset + timezone.timedelta(days=30)
            },
            'super_likes': {
                'total': subscription.plan.daily_super_likes_count,
                'remaining': subscription.super_likes_remaining,
                'reset_date': subscription.last_super_likes_reset + timezone.timedelta(days=1)
            },
            'features': {
                'unlimited_likes': subscription.plan.unlimited_likes,
                'can_see_likers': subscription.plan.can_see_likers,
                'can_rewind': subscription.plan.can_rewind,
                'media_messaging': subscription.plan.media_messaging_enabled,
                'calls': subscription.plan.audio_video_calls_enabled
            }
        }
    }