# Exemples d'intégration du système premium dans les autres applications

## 1. Dans l'application Matching

### Fichier: `matching/views.py`

```python
from rest_framework.decorators import api_view
from subscriptions.middleware import premium_required, check_feature_limit
from subscriptions.utils import is_premium_user, check_feature_availability

class RewindLastSwipeView(APIView):
    """
    Rewind last swipe (Premium feature).
    POST /api/v1/matches/rewind/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @premium_required
    def post(self, request):
        # Logic to rewind last swipe
        pass

class SendSuperLikeView(APIView):
    """
    Send a super like (Premium feature with daily limit).
    POST /api/v1/matches/{user_id}/super-like/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @check_feature_limit('super_like', use_feature=True)
    def post(self, request, user_id):
        # Logic to send super like
        # The decorator already consumed one super like
        pass

class ProfileBoostView(APIView):
    """
    Boost profile visibility (Premium feature with monthly limit).
    POST /api/v1/profiles/boost/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @check_feature_limit('boost', use_feature=True)
    def post(self, request):
        # Logic to boost profile
        # The decorator already consumed one boost
        pass
```

### Fichier: `matching/serializers.py`

```python
from subscriptions.utils import is_premium_user, get_premium_limits

class RecommendedProfileSerializer(serializers.ModelSerializer):
    """Enhanced with premium features."""
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        if request and request.user:
            # Add premium-specific fields
            if is_premium_user(request.user):
                # Premium users can see who liked them
                data['has_liked_you'] = self.check_if_liked(instance, request.user)
            else:
                # Non-premium users see blurred info
                data['has_liked_you'] = None
        
        return data
```

## 2. Dans l'application Messaging

### Fichier: `messaging/views.py`

```python
from subscriptions.utils import check_feature_availability, premium_required_response

class SendMediaMessageView(APIView):
    """
    Send media message (Premium only).
    POST /api/v1/conversations/{conversation_id}/messages/media/
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]
    
    def post(self, request, conversation_id):
        # Check premium status
        feature_check = check_feature_availability(request.user, 'media_messaging')
        if not feature_check['available']:
            return premium_required_response()
        
        # Logic to handle media upload
        pass

class InitiateCallView(APIView):
    """
    Initiate audio/video call (Premium only).
    POST /api/v1/calls/initiate/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Check premium status
        feature_check = check_feature_availability(request.user, 'calls')
        if not feature_check['available']:
            return premium_required_response()
        
        # Logic to initiate call
        pass
```

## 3. Dans l'application Profiles

### Fichier: `profiles/views.py`

```python
from subscriptions.utils import is_premium_user, get_user_subscription

class LikesReceivedView(generics.ListAPIView):
    """
    Get list of users who liked the current user (Premium only).
    GET /api/v1/profiles/likes-received/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    def get_queryset(self):
        if not is_premium_user(self.request.user):
            # Return empty queryset for non-premium users
            return Profile.objects.none()
        
        # Get users who liked the current user
        return Profile.objects.filter(
            user__in=Like.objects.filter(
                target_user=self.request.user,
                is_super_like=False
            ).values_list('user', flat=True)
        )
    
    def list(self, request, *args, **kwargs):
        if not is_premium_user(request.user):
            return premium_required_response()
        
        return super().list(request, *args, **kwargs)
```

### Fichier: `profiles/serializers.py`

```python
from subscriptions.utils import get_premium_limits

class ProfileSerializer(serializers.ModelSerializer):
    """Enhanced with premium limits."""
    
    premium_limits = serializers.SerializerMethodField()
    
    def get_premium_limits(self, obj):
        request = self.context.get('request')
        if request and request.user == obj.user:
            return get_premium_limits(request.user)
        return None
```

## 4. Mise à jour du modèle User

### Fichier: `authentication/models.py`

```python
class User(AbstractBaseUser, PermissionsMixin):
    # ... champs existants ...
    
    # Premium status fields
    is_premium = models.BooleanField(
        default=False,
        verbose_name=_('Premium status')
    )
    
    premium_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Premium until')
    )
    
    @property
    def premium_features(self):
        """Get available premium features."""
        from subscriptions.utils import get_premium_limits
        return get_premium_limits(self)
    
    @property
    def can_send_super_like(self):
        """Check if user can send super likes."""
        from subscriptions.utils import check_feature_availability
        return check_feature_availability(self, 'super_like')['available']
```

## 5. Middleware global pour les stats

### Fichier: `hivmeet_backend/middleware.py`

```python
from subscriptions.utils import is_premium_user

class PremiumStatusMiddleware:
    """
    Add premium status to request.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.is_premium = is_premium_user(request.user)
        else:
            request.is_premium = False
        
        response = self.get_response(request)
        return response
```

## 6. Signaux pour synchronisation

### Fichier: `matching/signals.py`

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from subscriptions.utils import consume_premium_feature

@receiver(post_save, sender=Like)
def handle_super_like_sent(sender, instance, created, **kwargs):
    """Handle super like consumption."""
    if created and instance.is_super_like:
        # Consume super like from user's quota
        result = consume_premium_feature(instance.user, 'super_like')
        if not result['success']:
            # This should not happen as it's checked before
            # Log error
            logger.error(f"Failed to consume super like: {result['error']}")
```

## 7. Templates d'admin personnalisés

### Fichier: `templates/admin/premium_badge.html`

```html
{% if original.is_premium %}
<span style="background: gold; color: black; padding: 2px 6px; border-radius: 3px;">
    PREMIUM
</span>
{% endif %}
```

## 8. Commandes de gestion

### Fichier: `subscriptions/management/commands/check_premium_stats.py`

```python
from django.core.management.base import BaseCommand
from django.db.models import Count
from authentication.models import User
from subscriptions.models import Subscription

class Command(BaseCommand):
    help = 'Display premium subscription statistics'
    
    def handle(self, *args, **options):
        total_users = User.objects.count()
        premium_users = User.objects.filter(is_premium=True).count()
        active_subscriptions = Subscription.objects.filter(
            status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING]
        ).count()
        
        self.stdout.write(f"Total users: {total_users}")
        self.stdout.write(f"Premium users: {premium_users}")
        self.stdout.write(f"Active subscriptions: {active_subscriptions}")
        self.stdout.write(f"Conversion rate: {(premium_users/total_users*100):.2f}%")
```