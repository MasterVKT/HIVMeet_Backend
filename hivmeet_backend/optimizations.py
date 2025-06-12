"""
Performance optimizations for HIVMeet backend.
File: hivmeet_backend/optimizations.py
"""
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch, Q, F, Count
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from functools import wraps
import hashlib
import json


# Cache configuration
CACHE_TTL = {
    'user_profile': 300,      # 5 minutes
    'discovery': 180,         # 3 minutes
    'premium_status': 300,    # 5 minutes
    'match_count': 600,       # 10 minutes
    'resource_list': 3600,    # 1 hour
    'subscription_plans': 86400,  # 24 hours
}


def cache_key_wrapper(prefix, *args, **kwargs):
    """Generate consistent cache keys."""
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    key_hash = hashlib.md5(
        json.dumps(key_data, sort_keys=True).encode()
    ).hexdigest()
    return f"{prefix}:{key_hash}"


def cached_result(cache_prefix, ttl=None):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = cache_key_wrapper(cache_prefix, *args, **kwargs)
            result = cache.get(cache_key)
            
            if result is None:
                result = func(*args, **kwargs)
                cache_ttl = ttl or CACHE_TTL.get(cache_prefix, 300)
                cache.set(cache_key, result, cache_ttl)
            
            return result
        return wrapper
    return decorator


class QueryOptimizations:
    """Database query optimizations."""
    
    @staticmethod
    def optimize_profile_query(queryset):
        """Optimize profile queries with proper prefetching."""
        return queryset.select_related(
            'user',
            'user__subscription'
        ).prefetch_related(
            Prefetch('photos', 
                     queryset=ProfilePhoto.objects.filter(is_approved=True).order_by('-is_main', '-uploaded_at')),
            'user__sent_likes',
            'user__received_likes'
        )
    
    @staticmethod
    def optimize_discovery_query(user, queryset):
        """Optimize discovery queries."""
        # Get user preferences
        profile = user.profile
        
        # Apply filters efficiently
        queryset = queryset.filter(
            user__is_active=True,
            is_hidden=False,
            allow_profile_in_discovery=True
        ).exclude(
            user=user
        ).exclude(
            user__in=user.blocked_users.all()
        )
        
        # Apply preference filters
        if profile.genders_sought:
            queryset = queryset.filter(gender__in=profile.genders_sought)
        
        # Add distance annotation if location is available
        if profile.latitude and profile.longitude:
            queryset = queryset.extra(
                select={
                    'distance': '''
                        earth_distance(
                            ll_to_earth(%s, %s),
                            ll_to_earth(latitude, longitude)
                        ) / 1000
                    '''
                },
                select_params=(profile.latitude, profile.longitude)
            ).filter(
                # Use bounding box for initial filtering
                latitude__range=(
                    profile.latitude - (profile.distance_max_km / 111.0),
                    profile.latitude + (profile.distance_max_km / 111.0)
                ),
                longitude__range=(
                    profile.longitude - (profile.distance_max_km / (111.0 * abs(profile.latitude))),
                    profile.longitude + (profile.distance_max_km / (111.0 * abs(profile.latitude)))
                )
            )
        
        return QueryOptimizations.optimize_profile_query(queryset)
    
    @staticmethod
    def optimize_match_query(queryset):
        """Optimize match queries."""
        return queryset.select_related(
            'conversation'
        ).prefetch_related(
            Prefetch('users',
                     queryset=User.objects.select_related('profile').prefetch_related('profile__photos')),
            'conversation__messages'
        ).annotate(
            last_message_time=F('conversation__last_message_at')
        ).order_by('-last_message_time', '-created_at')


class CacheManager:
    """Centralized cache management."""
    
    @staticmethod
    def invalidate_user_cache(user_id):
        """Invalidate all user-related caches."""
        patterns = [
            f'user_profile:{user_id}:*',
            f'discovery:*:{user_id}:*',
            f'premium_status:{user_id}',
            f'match_count:{user_id}'
        ]
        
        # Delete matching keys
        for pattern in patterns:
            cache.delete_pattern(pattern)
    
    @staticmethod
    def warm_cache(user):
        """Pre-warm cache for user."""
        from profiles.models import Profile
        from subscriptions.utils import is_premium_user
        
        # Cache user profile
        profile_key = f'user_profile:{user.id}'
        profile = Profile.objects.select_related('user').prefetch_related('photos').get(user=user)
        cache.set(profile_key, profile, CACHE_TTL['user_profile'])
        
        # Cache premium status
        premium_key = f'premium_status:{user.id}'
        cache.set(premium_key, is_premium_user(user), CACHE_TTL['premium_status'])


class DatabaseOptimizations:
    """Database-level optimizations."""
    
    # Indexes to create
    INDEXES = [
        # Profiles
        'CREATE INDEX idx_profiles_location ON profiles_profile USING gist(ll_to_earth(latitude, longitude));',
        'CREATE INDEX idx_profiles_discovery ON profiles_profile(is_hidden, allow_profile_in_discovery) WHERE is_hidden = FALSE;',
        'CREATE INDEX idx_profiles_gender ON profiles_profile(gender);',
        
        # Matches
        'CREATE INDEX idx_matches_users ON matching_match_users(match_id, user_id);',
        'CREATE INDEX idx_matches_active ON matching_match(is_active, created_at DESC) WHERE is_active = TRUE;',
        
        # Messages
        'CREATE INDEX idx_messages_conversation ON messaging_message(conversation_id, created_at DESC);',
        'CREATE INDEX idx_messages_unread ON messaging_message(conversation_id, is_read) WHERE is_read = FALSE;',
        
        # Subscriptions
        'CREATE INDEX idx_subscriptions_active ON subscriptions_subscription(user_id, status) WHERE status IN (\'active\', \'trialing\');',
    ]
    
    @staticmethod
    def create_indexes():
        """Create optimized indexes."""
        from django.db import connection
        
        with connection.cursor() as cursor:
            for index in DatabaseOptimizations.INDEXES:
                try:
                    cursor.execute(index)
                except Exception as e:
                    print(f"Index creation failed: {e}")


# View mixins for common optimizations
class CachedViewMixin:
    """Mixin for cached views."""
    
    cache_timeout = 300  # 5 minutes default
    
    @method_decorator(cache_page(cache_timeout))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class OptimizedQueryMixin:
    """Mixin for optimized queries."""
    
    def get_queryset(self):
        """Apply optimizations to queryset."""
        queryset = super().get_queryset()
        
        # Apply model-specific optimizations
        model_name = queryset.model.__name__.lower()
        
        if model_name == 'profile':
            return QueryOptimizations.optimize_profile_query(queryset)
        elif model_name == 'match':
            return QueryOptimizations.optimize_match_query(queryset)
        
        return queryset


# Settings optimizations
OPTIMIZATION_SETTINGS = {
    # Database connection pooling
    'CONN_MAX_AGE': 600,
    
    # Query optimization
    'DEBUG_TOOLBAR_CONFIG': {
        'SHOW_TOOLBAR_CALLBACK': lambda request: settings.DEBUG and request.user.is_superuser,
        'SHOW_TEMPLATE_CONTEXT': False,
        'ENABLE_STACKTRACES': False,
    },
    
    # Cache backend optimization
    'REDIS_CONNECTION_POOL_KWARGS': {
        'max_connections': 50,
        'connection_class': 'redis.connection.Connection',
    },
    
    # Session optimization
    'SESSION_ENGINE': 'django.contrib.sessions.backends.cache',
    'SESSION_CACHE_ALIAS': 'default',
    
    # Static files optimization
    'STATICFILES_STORAGE': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage',
}