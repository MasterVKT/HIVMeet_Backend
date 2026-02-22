# Architecture & Patterns - HIVMeet Backend

**Import with**: `@.claude/rules/architecture.md`

---

## Django Apps Structure

HIVMeet Backend est organisé en apps Django modulaires suivant le principe de séparation des responsabilités :

### Apps Principales

```
hivmeet_backend/
├── authentication/          # Gestion utilisateurs et auth
│   ├── models.py           # User, FCMToken
│   ├── views.py            # Register, Login, Firebase exchange
│   ├── backends.py         # FirebaseBackend
│   ├── middleware.py       # FirebaseAuthenticationMiddleware
│   └── serializers.py      # UserSerializer, RegisterSerializer
│
├── profiles/               # Profils utilisateurs
│   ├── models.py           # UserProfile, Photo, Preference
│   ├── views.py            # ProfileViewSet, PhotoUpload
│   ├── views_premium.py    # Likes received, super-likes
│   ├── views_settings.py   # User settings
│   └── serializers.py      # UserProfileSerializer
│
├── matching/               # Système de matching
│   ├── models.py           # Like, SuperLike, Match
│   ├── views.py            # Discovery, Like/Unlike, Matches
│   ├── services.py         # MatchingService, DiscoveryService
│   └── serializers.py      # LikeSerializer, MatchSerializer
│
├── messaging/              # Messagerie
│   ├── models.py           # Conversation, Message
│   ├── views.py            # ConversationViewSet, MessageViewSet
│   └── serializers.py      # ConversationSerializer, MessageSerializer
│
├── subscriptions/          # Abonnements premium
│   ├── models.py           # Subscription, Payment
│   ├── views.py            # SubscriptionViewSet, Webhooks
│   └── services.py         # SubscriptionService, PaymentProcessor
│
└── resources/              # Ressources éducatives
    ├── models.py           # Article, Resource
    ├── views.py            # ResourceViewSet
    └── serializers.py      # ResourceSerializer
```

### Principes d'Organisation

1. **Une app = un domaine métier** : Chaque app gère une fonctionnalité spécifique
2. **Models isolés** : Pas de dépendances circulaires entre apps
3. **Services layer** : Logique métier complexe dans `services.py`
4. **URLs namespace** : Chaque app a son propre `urls.py`

---

## Service Layer Pattern

Pour éviter les "fat models" et "fat views", utiliser une couche de services :

### Structure

```python
# matching/services.py

class MatchingService:
    """
    Service centralisant la logique métier du matching.
    """
    
    @staticmethod
    def create_like(from_user, to_user, is_super_like=False):
        """
        Crée un like et vérifie si un match est créé.
        
        Returns:
            tuple: (like, match or None)
        """
        from django.db import transaction
        from .models import Like, SuperLike, Match
        
        with transaction.atomic():
            # Créer le like
            if is_super_like:
                like = SuperLike.objects.create(
                    from_user=from_user,
                    to_user=to_user
                )
            else:
                like = Like.objects.create(
                    from_user=from_user,
                    to_user=to_user
                )
            
            # Vérifier si match réciproque
            reverse_like = Like.objects.filter(
                from_user=to_user,
                to_user=from_user
            ).exists()
            
            match = None
            if reverse_like:
                # Créer le match
                match, created = Match.objects.get_or_create(
                    user1=min(from_user.id, to_user.id),
                    user2=max(from_user.id, to_user.id)
                )
                
                if created:
                    # Envoyer notification
                    NotificationService.send_match_notification(
                        from_user, to_user
                    )
            
            return like, match
    
    @staticmethod
    def get_discovery_profiles(user, filters=None):
        """
        Récupère les profils recommandés pour l'utilisateur.
        
        Args:
            user: User instance
            filters: Dict avec age_range, distance, genders_sought
        
        Returns:
            QuerySet: Profils filtrés et ordonnés
        """
        from .models import UserProfile, Like
        from django.db.models import Q
        
        # Profils déjà likés/rejetés
        liked_ids = Like.objects.filter(
            from_user=user
        ).values_list('to_user_id', flat=True)
        
        # Query de base
        profiles = UserProfile.objects.exclude(
            Q(user=user) |
            Q(user_id__in=liked_ids) |
            Q(user__is_active=False)
        )
        
        # Filtres utilisateur
        prefs = user.profile.preferences or {}
        
        if filters:
            # Âge
            if 'age_range' in filters:
                min_age, max_age = filters['age_range']
                profiles = profiles.filter(
                    age__gte=min_age,
                    age__lte=max_age
                )
            
            # Distance
            if 'max_distance' in filters and user.profile.location:
                # Implémenter calcul de distance géographique
                pass
            
            # Genres recherchés
            if 'genders_sought' in filters:
                profiles = profiles.filter(
                    gender__in=filters['genders_sought']
                )
        
        # Ordre : score de compatibilité (algorithme à définir)
        profiles = profiles.order_by('?')  # Ordre aléatoire pour l'instant
        
        return profiles
```

### Utilisation dans les Views

```python
# matching/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import MatchingService

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_user(request, user_id):
    """
    Like un utilisateur (logique déléguée au service).
    """
    from authentication.models import User
    
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Utilisateur introuvable'}, status=404)
    
    # Appeler le service
    is_super_like = request.data.get('is_super_like', False)
    like, match = MatchingService.create_like(
        from_user=request.user,
        to_user=target_user,
        is_super_like=is_super_like
    )
    
    response_data = {
        'like_id': like.id,
        'is_match': match is not None
    }
    
    if match:
        response_data['match_id'] = match.id
    
    return Response(response_data, status=201)
```

**Avantages** :
- Views légères (thin controllers)
- Logique métier réutilisable
- Tests unitaires plus simples
- Transaction management centralisé

---

## ViewSets vs APIView

### Quand utiliser ViewSet

Pour les ressources CRUD standards :

```python
# profiles/views.py

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les profils utilisateurs.
    Endpoints automatiques: list, retrieve, create, update, partial_update, destroy
    """
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filtrer selon l'utilisateur connecté
        return UserProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Endpoint custom: GET /api/v1/user-profiles/me/
        """
        profile = request.user.profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def set_main_photo(self, request, pk=None):
        """
        Endpoint custom: POST /api/v1/user-profiles/{id}/set_main_photo/
        """
        profile = self.get_object()
        photo_id = request.data.get('photo_id')
        
        # Logique...
        
        return Response({'success': True})
```

### Quand utiliser APIView/Function-based Views

Pour des endpoints spécifiques sans CRUD standard :

```python
# matching/views.py

from rest_framework.decorators import api_view

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def discovery(request):
    """
    Endpoint de découverte de profils.
    Pas de CRUD standard → APIView simple.
    """
    filters = {
        'age_range': request.query_params.get('age_range'),
        'max_distance': request.query_params.get('max_distance'),
    }
    
    profiles = MatchingService.get_discovery_profiles(
        user=request.user,
        filters=filters
    )
    
    # Pagination
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(profiles, request)
    
    serializer = UserProfileSerializer(page, many=True)
    
    return paginator.get_paginated_response(serializer.data)
```

---

## Dependency Injection Pattern

Pour les services dépendant de services externes (Firebase, email, paiement) :

```python
# subscriptions/services.py

class PaymentProcessor:
    """
    Interface pour les processeurs de paiement.
    Permet de changer facilement de provider (Stripe → PayPal).
    """
    
    def charge(self, user, amount, currency='USD'):
        raise NotImplementedError
    
    def refund(self, payment_id):
        raise NotImplementedError


class StripePaymentProcessor(PaymentProcessor):
    def __init__(self, api_key):
        self.api_key = api_key
        # Initialiser Stripe SDK
    
    def charge(self, user, amount, currency='USD'):
        # Logique Stripe
        pass
    
    def refund(self, payment_id):
        # Logique Stripe
        pass


class SubscriptionService:
    def __init__(self, payment_processor: PaymentProcessor):
        self.payment_processor = payment_processor
    
    def activate_premium(self, user, subscription_type):
        # Charger l'utilisateur
        amount = self._get_subscription_price(subscription_type)
        
        # Utiliser le processeur injecté
        payment = self.payment_processor.charge(user, amount)
        
        # Activer l'abonnement
        # ...


# Dans settings.py ou factory
from decouple import config

stripe_processor = StripePaymentProcessor(
    api_key=config('STRIPE_SECRET_KEY')
)

subscription_service = SubscriptionService(
    payment_processor=stripe_processor
)
```

**Avantages** :
- Facile à tester (mock le payment processor)
- Changement de provider sans modifier SubscriptionService
- Configuration centralisée

---

## Signals for Cross-App Communication

Pour déclencher des actions dans d'autres apps sans couplage direct :

```python
# profiles/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserProfile

@receiver(post_save, sender=UserProfile)
def on_profile_updated(sender, instance, created, **kwargs):
    """
    Signal déclenché après sauvegarde d'un profil.
    """
    if created:
        # Nouveau profil créé
        from messaging.services import NotificationService
        
        NotificationService.send_welcome_email(instance.user)
    
    else:
        # Profil mis à jour
        # Invalider le cache si nécessaire
        from django.core.cache import cache
        cache.delete(f'profile_{instance.user.id}')
```

**Enregistrement dans apps.py** :

```python
# profiles/apps.py

from django.apps import AppConfig

class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profiles'
    
    def ready(self):
        import profiles.signals  # Charger les signals
```

**Attention** : Ne pas abuser des signals (peut rendre le code difficile à suivre).

---

## Caching Strategy

### Cache de requêtes fréquentes

```python
from django.core.cache import cache
from django.conf import settings

def get_user_profile(user_id):
    """
    Récupère un profil avec cache de 5 minutes.
    """
    cache_key = f'profile_{user_id}'
    
    # Vérifier le cache
    profile = cache.get(cache_key)
    
    if profile is None:
        # Cache miss → récupérer de la DB
        profile = UserProfile.objects.select_related('user').get(user_id=user_id)
        
        # Mettre en cache
        cache.set(cache_key, profile, timeout=300)  # 5 minutes
    
    return profile
```

### Cache de compteurs

```python
def get_unread_message_count(user):
    """
    Compte des messages non lus (souvent affiché).
    """
    cache_key = f'unread_count_{user.id}'
    
    count = cache.get(cache_key)
    
    if count is None:
        from messaging.models import Message
        count = Message.objects.filter(
            conversation__participants=user,
            is_read=False
        ).exclude(sender=user).count()
        
        cache.set(cache_key, count, timeout=60)  # 1 minute
    
    return count


# Invalider le cache quand un message est lu
@receiver(post_save, sender=Message)
def on_message_read(sender, instance, **kwargs):
    if instance.is_read:
        for participant in instance.conversation.participants.all():
            cache_key = f'unread_count_{participant.id}'
            cache.delete(cache_key)
```

---

## Error Handling Strategy

### Custom Exceptions

```python
# core/exceptions.py

from rest_framework.exceptions import APIException

class InsufficientCreditsException(APIException):
    status_code = 402
    default_detail = "Crédits insuffisants pour cette action"
    default_code = 'insufficient_credits'


class PremiumRequiredException(APIException):
    status_code = 403
    default_detail = "Cette fonctionnalité nécessite un abonnement premium"
    default_code = 'premium_required'


class InvalidMatchException(APIException):
    status_code = 400
    default_detail = "Impossible de créer un match avec cet utilisateur"
    default_code = 'invalid_match'
```

### Global Exception Handler

```python
# hivmeet_backend/settings.py

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

# core/exceptions.py

from rest_framework.views import exception_handler
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Handler global pour toutes les exceptions DRF.
    """
    # Appeler le handler par défaut
    response = exception_handler(exc, context)
    
    if response is not None:
        # Enrichir la réponse avec des métadonnées
        response.data['status_code'] = response.status_code
        
        # Logger l'erreur avec contexte
        request = context.get('request')
        logger.error(
            f"API Error - {exc.__class__.__name__}: {str(exc)} - "
            f"Path: {request.path if request else 'N/A'} - "
            f"User: {request.user.id if request and request.user.is_authenticated else 'Anonymous'}",
            exc_info=True
        )
    
    return response
```

---

## Async Task Processing with Celery

Pour les tâches longues (envoi d'emails, traitement d'images, calculs complexes) :

```python
# profiles/tasks.py

from celery import shared_task
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_verification_email(user_id, verification_url):
    """
    Tâche asynchrone : envoi d'email de vérification.
    """
    from authentication.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        send_mail(
            subject="Vérifiez votre compte HIVMeet",
            message=f"Cliquez sur ce lien: {verification_url}",
            from_email="noreply@hivmeet.com",
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"Email de vérification envoyé à {user.email}")
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for verification email")
    
    except Exception as e:
        logger.error(f"Erreur envoi email vérification: {str(e)}", exc_info=True)


@shared_task
def process_profile_photo(photo_id):
    """
    Tâche asynchrone : redimensionner et optimiser une photo.
    """
    from profiles.models import Photo
    from PIL import Image
    from io import BytesIO
    
    try:
        photo = Photo.objects.get(id=photo_id)
        
        # Redimensionner l'image
        img = Image.open(photo.file.path)
        img.thumbnail((800, 800))
        
        # Sauvegarder
        img.save(photo.file.path, optimize=True, quality=85)
        
        logger.info(f"Photo {photo_id} optimisée avec succès")
        
    except Exception as e:
        logger.error(f"Erreur traitement photo {photo_id}: {str(e)}", exc_info=True)
```

**Appel dans la vue** :

```python
# profiles/views.py

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_photo(request):
    serializer = PhotoSerializer(data=request.data)
    
    if serializer.is_valid():
        photo = serializer.save(user_profile=request.user.profile)
        
        # Traiter l'image en arrière-plan
        from .tasks import process_profile_photo
        process_profile_photo.delay(photo.id)
        
        return Response(serializer.data, status=201)
    
    return Response(serializer.errors, status=400)
```

---

## Best Practices Summary

1. **Modularity** : Une app = un domaine métier
2. **Service Layer** : Logique métier hors des views
3. **ViewSets for CRUD** : APIView pour endpoints spécifiques
4. **Dependency Injection** : Services externes configurables
5. **Signals for Decoupling** : Communication inter-apps
6. **Caching** : Requêtes fréquentes et compteurs
7. **Custom Exceptions** : Erreurs métier claires
8. **Celery for Async** : Tâches longues en arrière-plan

---

**Import in CLAUDE.md**: `@.claude/rules/architecture.md`
