# 📜 Spécification Backend - Historique des Interactions

## 📋 Vue d'ensemble

Cette spécification décrit l'implémentation complète d'un système d'historique des interactions utilisateur permettant de consulter et gérer les profils précédemment likés ou passés.

### Objectifs

1. Permettre aux utilisateurs de revoir leurs interactions passées (likes et dislikes)
2. Offrir la possibilité de "revenir" sur un profil précédemment passé
3. Faciliter la gestion des erreurs de swipe
4. Améliorer l'expérience utilisateur avec une traçabilité complète

---

## 🗄️ Modèle de Données

### Table: `interaction_history`

Stocke l'historique complet de toutes les interactions utilisateur.

```sql
CREATE TABLE interaction_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    target_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    interaction_type VARCHAR(20) NOT NULL, -- 'like', 'dislike', 'super_like'
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE,
    
    -- Index pour performances
    CONSTRAINT unique_active_interaction UNIQUE (user_id, target_user_id, interaction_type) 
        WHERE is_revoked = FALSE
);

-- Index pour optimiser les requêtes fréquentes
CREATE INDEX idx_interaction_history_user_id ON interaction_history(user_id);
CREATE INDEX idx_interaction_history_target_user_id ON interaction_history(target_user_id);
CREATE INDEX idx_interaction_history_type ON interaction_history(interaction_type);
CREATE INDEX idx_interaction_history_created_at ON interaction_history(created_at DESC);
CREATE INDEX idx_interaction_history_active ON interaction_history(user_id, is_revoked) 
    WHERE is_revoked = FALSE;
```

### Modificatons aux tables existantes

#### Table: `matches`

Ajouter une référence à l'interaction d'origine :

```sql
ALTER TABLE matches 
ADD COLUMN like_interaction_id UUID REFERENCES interaction_history(id),
ADD COLUMN matched_like_interaction_id UUID REFERENCES interaction_history(id);
```

---

## 🔌 Endpoints API

### 1. Récupérer l'historique des likes

**Endpoint:** `GET /api/v1/discovery/interactions/my-likes`

**Description:** Retourne la liste paginée de tous les profils que l'utilisateur a likés (incluant super likes)

**Authentification:** Requise

**Query Parameters:**
```
page: integer (default: 1)
page_size: integer (default: 20, max: 100)
include_matched: boolean (default: false) - Inclure les likes qui ont abouti à un match
include_revoked: boolean (default: false) - Inclure les likes annulés
order_by: string (default: 'recent') - Options: 'recent', 'oldest'
```

**Réponse Success (200):**
```json
{
  "count": 127,
  "next": "http://api.example.com/api/v1/discovery/interactions/my-likes?page=2",
  "previous": null,
  "results": [
    {
      "id": "interaction-uuid-1",
      "profile": {
        "id": "profile-uuid-1",
        "display_name": "Sophie",
        "age": 26,
        "photos": [
          {
            "photo_url": "https://storage.example.com/photo.jpg",
            "thumbnail_url": "https://storage.example.com/thumb.jpg",
            "is_main": true
          }
        ],
        "city": "Paris",
        "distance_km": 5.2,
        "is_verified": true
      },
      "interaction_type": "like",
      "liked_at": "2025-12-28T14:30:00Z",
      "is_matched": false,
      "can_rematch": true
    },
    {
      "id": "interaction-uuid-2",
      "profile": {
        "id": "profile-uuid-2",
        "display_name": "Julie",
        "age": 24,
        "photos": [...],
        "city": "Lyon",
        "distance_km": 12.8,
        "is_verified": false
      },
      "interaction_type": "super_like",
      "liked_at": "2025-12-27T10:15:00Z",
      "is_matched": true,
      "match_id": "match-uuid-1",
      "can_rematch": false
    }
  ]
}
```

**Logique Backend:**

```python
from django.db.models import Q, Prefetch
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_likes(request):
    user = request.user
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    include_matched = request.GET.get('include_matched', 'false').lower() == 'true'
    include_revoked = request.GET.get('include_revoked', 'false').lower() == 'true'
    order_by = request.GET.get('order_by', 'recent')
    
    # Base query
    interactions = InteractionHistory.objects.filter(
        user_id=user.id,
        interaction_type__in=['like', 'super_like']
    )
    
    # Filtres
    if not include_revoked:
        interactions = interactions.filter(is_revoked=False)
    
    # Prefetch des profils et photos
    interactions = interactions.select_related('target_user__profile').prefetch_related(
        'target_user__profile__photos'
    )
    
    # Ordering
    if order_by == 'recent':
        interactions = interactions.order_by('-created_at')
    else:
        interactions = interactions.order_by('created_at')
    
    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = page_size
    paginated_interactions = paginator.paginate_queryset(interactions, request)
    
    # Serialization
    results = []
    for interaction in paginated_interactions:
        target_profile = interaction.target_user.profile
        
        # Vérifier si match
        match = Match.objects.filter(
            Q(user1=user, user2=interaction.target_user) |
            Q(user1=interaction.target_user, user2=user)
        ).first()
        
        # Vérifier si rematch possible
        can_rematch = not match and not interaction.is_revoked
        
        # Skip si matched et include_matched=false
        if match and not include_matched:
            continue
            
        results.append({
            'id': str(interaction.id),
            'profile': serialize_profile(target_profile, user),
            'interaction_type': interaction.interaction_type,
            'liked_at': interaction.created_at.isoformat(),
            'is_matched': bool(match),
            'match_id': str(match.id) if match else None,
            'can_rematch': can_rematch
        })
    
    return paginator.get_paginated_response(results)
```

---

### 2. Récupérer l'historique des dislikes/passes

**Endpoint:** `GET /api/v1/discovery/interactions/my-passes`

**Description:** Retourne la liste paginée de tous les profils que l'utilisateur a passés/unlikés

**Authentification:** Requise

**Query Parameters:**
```
page: integer (default: 1)
page_size: integer (default: 20, max: 100)
include_revoked: boolean (default: false)
order_by: string (default: 'recent')
```

**Réponse Success (200):**
```json
{
  "count": 523,
  "next": "http://api.example.com/api/v1/discovery/interactions/my-passes?page=2",
  "previous": null,
  "results": [
    {
      "id": "interaction-uuid-3",
      "profile": {
        "id": "profile-uuid-3",
        "display_name": "Marc",
        "age": 30,
        "photos": [...],
        "city": "Marseille",
        "distance_km": 25.5,
        "is_verified": false
      },
      "passed_at": "2025-12-28T16:45:00Z",
      "can_reconsider": true
    }
  ]
}
```

**Logique Backend:**

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_passes(request):
    user = request.user
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    include_revoked = request.GET.get('include_revoked', 'false').lower() == 'true'
    order_by = request.GET.get('order_by', 'recent')
    
    # Base query
    interactions = InteractionHistory.objects.filter(
        user_id=user.id,
        interaction_type='dislike'
    )
    
    if not include_revoked:
        interactions = interactions.filter(is_revoked=False)
    
    # Prefetch
    interactions = interactions.select_related('target_user__profile').prefetch_related(
        'target_user__profile__photos'
    )
    
    # Ordering
    if order_by == 'recent':
        interactions = interactions.order_by('-created_at')
    else:
        interactions = interactions.order_by('created_at')
    
    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = page_size
    paginated_interactions = paginator.paginate_queryset(interactions, request)
    
    # Serialization
    results = []
    for interaction in paginated_interactions:
        target_profile = interaction.target_user.profile
        
        results.append({
            'id': str(interaction.id),
            'profile': serialize_profile(target_profile, user),
            'passed_at': interaction.created_at.isoformat(),
            'can_reconsider': not interaction.is_revoked
        })
    
    return paginator.get_paginated_response(results)
```

---

### 3. Révoquer une interaction (Reconsider)

**Endpoint:** `POST /api/v1/discovery/interactions/{interaction_id}/revoke`

**Description:** Annule une interaction précédente (like ou dislike) pour revoir le profil ultérieurement

**Authentification:** Requise

**Path Parameters:**
- `interaction_id`: UUID de l'interaction à révoquer

**Request Body:** Aucun

**Réponse Success (200):**
```json
{
  "status": "revoked",
  "interaction_id": "interaction-uuid",
  "message": "L'interaction a été annulée. Ce profil pourra réapparaître dans votre découverte."
}
```

**Réponses d'erreur:**
```json
// 404 - Interaction non trouvée
{
  "error": "interaction_not_found",
  "message": "Cette interaction n'existe pas ou ne vous appartient pas"
}

// 400 - Interaction déjà révoquée
{
  "error": "already_revoked",
  "message": "Cette interaction a déjà été annulée"
}

// 400 - Match existant
{
  "error": "cannot_revoke_match",
  "message": "Impossible d'annuler un like qui a abouti à un match actif"
}
```

**Logique Backend:**

```python
from django.utils import timezone

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_interaction(request, interaction_id):
    user = request.user
    
    try:
        interaction = InteractionHistory.objects.get(
            id=interaction_id,
            user_id=user.id
        )
    except InteractionHistory.DoesNotExist:
        return Response(
            {
                'error': 'interaction_not_found',
                'message': "Cette interaction n'existe pas ou ne vous appartient pas"
            },
            status=404
        )
    
    # Vérifier si déjà révoquée
    if interaction.is_revoked:
        return Response(
            {
                'error': 'already_revoked',
                'message': "Cette interaction a déjà été annulée"
            },
            status=400
        )
    
    # Vérifier si match actif (seulement pour les likes)
    if interaction.interaction_type in ['like', 'super_like']:
        active_match = Match.objects.filter(
            Q(user1=user, user2=interaction.target_user) |
            Q(user1=interaction.target_user, user2=user)
        ).exists()
        
        if active_match:
            return Response(
                {
                    'error': 'cannot_revoke_match',
                    'message': "Impossible d'annuler un like qui a abouti à un match actif"
                },
                status=400
            )
    
    # Révoquer l'interaction
    interaction.is_revoked = True
    interaction.revoked_at = timezone.now()
    interaction.save()
    
    # Logger l'événement
    log_user_action(
        user=user,
        action='interaction_revoked',
        details={
            'interaction_id': str(interaction.id),
            'interaction_type': interaction.interaction_type,
            'target_user_id': str(interaction.target_user_id)
        }
    )
    
    return Response({
        'status': 'revoked',
        'interaction_id': str(interaction.id),
        'message': "L'interaction a été annulée. Ce profil pourra réapparaître dans votre découverte."
    })
```

---

### 4. Statistiques des interactions

**Endpoint:** `GET /api/v1/discovery/interactions/stats`

**Description:** Retourne des statistiques sur les interactions de l'utilisateur

**Authentification:** Requise

**Réponse Success (200):**
```json
{
  "total_likes": 127,
  "total_super_likes": 12,
  "total_dislikes": 523,
  "total_matches": 18,
  "like_to_match_ratio": 0.14,
  "most_active_day": "2025-12-25",
  "total_interactions_today": 45,
  "daily_limit": 100,
  "remaining_today": 55
}
```

**Logique Backend:**

```python
from django.db.models import Count, Q
from datetime import datetime, timedelta

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_interaction_stats(request):
    user = request.user
    today = timezone.now().date()
    
    # Compteurs
    likes_count = InteractionHistory.objects.filter(
        user_id=user.id,
        interaction_type='like',
        is_revoked=False
    ).count()
    
    super_likes_count = InteractionHistory.objects.filter(
        user_id=user.id,
        interaction_type='super_like',
        is_revoked=False
    ).count()
    
    dislikes_count = InteractionHistory.objects.filter(
        user_id=user.id,
        interaction_type='dislike',
        is_revoked=False
    ).count()
    
    matches_count = Match.objects.filter(
        Q(user1=user) | Q(user2=user)
    ).count()
    
    # Ratio like -> match
    total_likes = likes_count + super_likes_count
    like_to_match_ratio = matches_count / total_likes if total_likes > 0 else 0
    
    # Interactions aujourd'hui
    interactions_today = InteractionHistory.objects.filter(
        user_id=user.id,
        created_at__date=today
    ).count()
    
    # Limites
    daily_limit = get_daily_like_limit(user)
    remaining_today = max(0, daily_limit - interactions_today)
    
    return Response({
        'total_likes': likes_count,
        'total_super_likes': super_likes_count,
        'total_dislikes': dislikes_count,
        'total_matches': matches_count,
        'like_to_match_ratio': round(like_to_match_ratio, 2),
        'total_interactions_today': interactions_today,
        'daily_limit': daily_limit,
        'remaining_today': remaining_today
    })
```

---

## 🔄 Modifications aux Endpoints Existants

### Modification: Like Profile

**Endpoint:** `POST /api/v1/discovery/interactions/like`

**Changements:**
- Enregistrer l'interaction dans `interaction_history`
- Vérifier si une interaction précédente révoquée existe
- Si match, lier les deux interactions

**Logique mise à jour:**

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_profile(request):
    user = request.user
    target_user_id = request.data.get('target_user_id')
    
    # Validation...
    
    # Vérifier interaction révoquée existante
    existing_interaction = InteractionHistory.objects.filter(
        user_id=user.id,
        target_user_id=target_user_id,
        interaction_type='like',
        is_revoked=True
    ).first()
    
    if existing_interaction:
        # Réactiver l'interaction
        existing_interaction.is_revoked = False
        existing_interaction.created_at = timezone.now()
        existing_interaction.revoked_at = None
        existing_interaction.save()
        interaction = existing_interaction
    else:
        # Créer nouvelle interaction
        interaction = InteractionHistory.objects.create(
            user_id=user.id,
            target_user_id=target_user_id,
            interaction_type='like'
        )
    
    # Vérifier match mutuel
    mutual_like = InteractionHistory.objects.filter(
        user_id=target_user_id,
        target_user_id=user.id,
        interaction_type__in=['like', 'super_like'],
        is_revoked=False
    ).first()
    
    if mutual_like:
        # Créer match avec références aux interactions
        match = Match.objects.create(
            user1=user,
            user2_id=target_user_id,
            like_interaction_id=interaction.id,
            matched_like_interaction_id=mutual_like.id
        )
        
        # Notifications...
        
        return Response({
            'result': 'match',
            'match_id': str(match.id),
            'interaction_id': str(interaction.id)
        })
    
    return Response({
        'result': 'like_sent',
        'interaction_id': str(interaction.id)
    })
```

### Modification: Dislike Profile

**Endpoint:** `POST /api/v1/discovery/interactions/dislike`

**Changements:**
- Enregistrer l'interaction dans `interaction_history`

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dislike_profile(request):
    user = request.user
    target_user_id = request.data.get('target_user_id')
    
    # Validation...
    
    # Vérifier interaction révoquée existante
    existing_interaction = InteractionHistory.objects.filter(
        user_id=user.id,
        target_user_id=target_user_id,
        interaction_type='dislike',
        is_revoked=True
    ).first()
    
    if existing_interaction:
        existing_interaction.is_revoked = False
        existing_interaction.created_at = timezone.now()
        existing_interaction.revoked_at = None
        existing_interaction.save()
    else:
        InteractionHistory.objects.create(
            user_id=user.id,
            target_user_id=target_user_id,
            interaction_type='dislike'
        )
    
    return Response({'result': 'dislike_sent'})
```

### Modification: Get Discovery Profiles

**Endpoint:** `GET /api/v1/discovery/profiles`

**Changements:**
- Exclure les profils avec interactions actives (non révoquées)

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_discovery_profiles(request):
    user = request.user
    
    # Profils déjà interagis (non révoqués)
    interacted_profile_ids = InteractionHistory.objects.filter(
        user_id=user.id,
        is_revoked=False
    ).values_list('target_user_id', flat=True)
    
    # Query principale
    profiles = UserProfile.objects.exclude(
        user_id__in=interacted_profile_ids
    ).exclude(
        user_id=user.id
    )
    
    # Appliquer filtres de recherche utilisateur...
    # Ordering par score de compatibilité...
    
    return paginate_and_respond(profiles, request)
```

---

## 🔐 Sécurité et Permissions

### Rate Limiting

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'interaction_history': '100/hour'
    }
}
```

### Permissions Custom

```python
from rest_framework import permissions

class CanAccessInteractionHistory(permissions.BasePermission):
    """
    Permission pour accéder à l'historique des interactions
    """
    def has_permission(self, request, view):
        # Tous les utilisateurs authentifiés
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Seul le propriétaire peut voir ses interactions
        return obj.user_id == request.user.id
```

---

## 📊 Analytics et Monitoring

### Métriques à Tracker

```python
# Événements à logger dans analytics
INTERACTION_HISTORY_EVENTS = [
    'interaction_history_viewed',  # Utilisateur consulte son historique
    'interaction_revoked',          # Utilisateur annule une interaction
    'profile_reconsidered',         # Profil passé est reliké
    'history_filter_used',          # Filtres appliqués sur historique
]

def log_interaction_history_event(user, event_type, metadata=None):
    """
    Log un événement lié à l'historique des interactions
    """
    analytics.track(
        user_id=str(user.id),
        event=event_type,
        properties={
            'timestamp': timezone.now().isoformat(),
            'platform': 'mobile',
            **(metadata or {})
        }
    )
```

---

## 🧪 Tests Unitaires

### Test: Création d'interaction

```python
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class InteractionHistoryTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', email='user1@test.com')
        self.user2 = User.objects.create_user(username='user2', email='user2@test.com')
    
    def test_create_like_interaction(self):
        """Test création d'une interaction like"""
        interaction = InteractionHistory.objects.create(
            user_id=self.user1.id,
            target_user_id=self.user2.id,
            interaction_type='like'
        )
        
        self.assertEqual(interaction.user_id, self.user1.id)
        self.assertEqual(interaction.interaction_type, 'like')
        self.assertFalse(interaction.is_revoked)
    
    def test_revoke_interaction(self):
        """Test révocation d'une interaction"""
        interaction = InteractionHistory.objects.create(
            user_id=self.user1.id,
            target_user_id=self.user2.id,
            interaction_type='like'
        )
        
        interaction.is_revoked = True
        interaction.save()
        
        self.assertTrue(interaction.is_revoked)
        self.assertIsNotNone(interaction.revoked_at)
    
    def test_get_user_likes(self):
        """Test récupération des likes d'un utilisateur"""
        # Créer plusieurs interactions
        for i in range(5):
            user = User.objects.create_user(username=f'target{i}')
            InteractionHistory.objects.create(
                user_id=self.user1.id,
                target_user_id=user.id,
                interaction_type='like'
            )
        
        likes = InteractionHistory.objects.filter(
            user_id=self.user1.id,
            interaction_type='like'
        )
        
        self.assertEqual(likes.count(), 5)
```

---

## 🚀 Migration

### Script de Migration

```python
# migrations/0042_create_interaction_history.py
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('discovery', '0041_previous_migration'),
    ]
    
    operations = [
        migrations.CreateModel(
            name='InteractionHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('user_id', models.UUIDField()),
                ('target_user_id', models.UUIDField()),
                ('interaction_type', models.CharField(max_length=20, choices=[
                    ('like', 'Like'),
                    ('super_like', 'Super Like'),
                    ('dislike', 'Dislike')
                ])),
                ('is_revoked', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('revoked_at', models.DateTimeField(null=True, blank=True)),
            ],
            options={
                'db_table': 'interaction_history',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='interactionhistory',
            index=models.Index(fields=['user_id'], name='idx_ih_user'),
        ),
        migrations.AddIndex(
            model_name='interactionhistory',
            index=models.Index(fields=['target_user_id'], name='idx_ih_target'),
        ),
        migrations.AddIndex(
            model_name='interactionhistory',
            index=models.Index(fields=['-created_at'], name='idx_ih_created'),
        ),
    ]
```

### Script de Backfill (Migration des données existantes)

```python
# management/commands/backfill_interaction_history.py
from django.core.management.base import BaseCommand
from django.db import transaction
from discovery.models import Like, Dislike, Match, InteractionHistory

class Command(BaseCommand):
    help = 'Backfill interaction history from existing like/dislike records'
    
    def handle(self, *args, **options):
        self.stdout.write('Starting backfill...')
        
        with transaction.atomic():
            # Migrer les likes existants
            likes = Like.objects.all()
            for like in likes:
                InteractionHistory.objects.get_or_create(
                    user_id=like.user_id,
                    target_user_id=like.target_user_id,
                    defaults={
                        'interaction_type': 'like' if not like.is_super else 'super_like',
                        'created_at': like.created_at
                    }
                )
            
            self.stdout.write(f'Migrated {likes.count()} likes')
            
            # Migrer les dislikes existants
            dislikes = Dislike.objects.all()
            for dislike in dislikes:
                InteractionHistory.objects.get_or_create(
                    user_id=dislike.user_id,
                    target_user_id=dislike.target_user_id,
                    defaults={
                        'interaction_type': 'dislike',
                        'created_at': dislike.created_at
                    }
                )
            
            self.stdout.write(f'Migrated {dislikes.count()} dislikes')
        
        self.stdout.write(self.style.SUCCESS('Backfill completed successfully!'))
```

---

## 📱 Intégration Frontend

### Types TypeScript/Dart

```dart
// lib/domain/entities/interaction_history.dart
class InteractionHistory {
  final String id;
  final DiscoveryProfile profile;
  final InteractionType type;
  final DateTime timestamp;
  final bool isMatched;
  final String? matchId;
  final bool canRevoke;
  
  const InteractionHistory({
    required this.id,
    required this.profile,
    required this.type,
    required this.timestamp,
    this.isMatched = false,
    this.matchId,
    this.canRevoke = true,
  });
}

enum InteractionType {
  like,
  superLike,
  dislike,
}
```

### Repository

```dart
// lib/domain/repositories/interaction_history_repository.dart
abstract class InteractionHistoryRepository {
  Future<Either<Failure, List<InteractionHistory>>> getMyLikes({
    int page = 1,
    int pageSize = 20,
    bool includeMatched = false,
  });
  
  Future<Either<Failure, List<InteractionHistory>>> getMyPasses({
    int page = 1,
    int pageSize = 20,
  });
  
  Future<Either<Failure, void>> revokeInteraction(String interactionId);
  
  Future<Either<Failure, InteractionStats>> getStats();
}
```

---

## 🎨 UI/UX Recommandations

### Navigation

```
Paramètres > Historique des interactions
  ├── Profils likés (127)
  ├── Profils passés (523)
  └── Statistiques
```

### Fonctionnalités UI

1. **Liste paginée avec pull-to-refresh**
2. **Filtres:** Tout / Matchés / Non matchés
3. **Action rapide:** Bouton "Annuler" sur chaque carte
4. **Confirmation:** Dialog avant révocation
5. **Feedback:** Toast "Profil retiré de votre historique"

---

## 💡 Fonctionnalités Premium (Optionnel)

### Historique Avancé (Premium)

- **Recherche:** Par nom, ville, âge
- **Filtres avancés:** Par date, type d'interaction, distance
- **Export:** CSV de tout l'historique
- **Notes privées:** Ajouter des notes sur les interactions

### Implementation

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPremiumUser])
def search_interaction_history(request):
    user = request.user
    query = request.GET.get('q', '')
    
    interactions = InteractionHistory.objects.filter(
        user_id=user.id
    ).select_related('target_user__profile')
    
    if query:
        interactions = interactions.filter(
            Q(target_user__profile__display_name__icontains=query) |
            Q(target_user__profile__city__icontains=query)
        )
    
    # ... pagination et serialization
```

---

## 📈 Métriques de Succès

### KPIs à Mesurer

1. **Taux d'utilisation:** % d'utilisateurs qui consultent leur historique
2. **Taux de révocation:** % d'interactions révoquées
3. **Taux de reconversion:** % de profils passés qui sont finalement likés
4. **Temps passé:** Durée moyenne sur la page historique
5. **Engagement:** Nombre moyen de consultations par semaine

### Requêtes Analytics

```sql
-- Taux d'utilisation hebdomadaire
SELECT 
    COUNT(DISTINCT user_id) as active_users,
    COUNT(*) as total_views
FROM analytics_events
WHERE event_type = 'interaction_history_viewed'
    AND created_at >= NOW() - INTERVAL '7 days';

-- Profils les plus révoqués
SELECT 
    target_user_id,
    COUNT(*) as revoke_count
FROM interaction_history
WHERE is_revoked = TRUE
GROUP BY target_user_id
ORDER BY revoke_count DESC
LIMIT 10;
```

---

## 🔧 Maintenance et Performance

### Optimisations

1. **Cache:** Mettre en cache les compteurs de statistiques
2. **Pagination:** Utiliser cursor-based pagination pour grandes listes
3. **Index:** Créer index composites pour requêtes fréquentes
4. **Archivage:** Archiver interactions > 6 mois

### Monitoring

```python
# Alertes à configurer
ALERTS = {
    'high_revocation_rate': {
        'threshold': 0.3,  # 30% de révocations
        'action': 'notify_product_team'
    },
    'slow_query': {
        'threshold': 2.0,  # 2 secondes
        'action': 'optimize_query'
    }
}
```

---

## 📚 Documentation Additionnelle

### Endpoints Summary

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| GET | `/api/v1/discovery/interactions/my-likes` | Liste des likes | ✅ |
| GET | `/api/v1/discovery/interactions/my-passes` | Liste des passes | ✅ |
| POST | `/api/v1/discovery/interactions/{id}/revoke` | Révoquer interaction | ✅ |
| GET | `/api/v1/discovery/interactions/stats` | Statistiques | ✅ |

### Codes d'Erreur

| Code | Message | Description |
|------|---------|-------------|
| 400 | `already_revoked` | Interaction déjà révoquée |
| 400 | `cannot_revoke_match` | Impossible de révoquer un match actif |
| 404 | `interaction_not_found` | Interaction inexistante |
| 429 | `rate_limit_exceeded` | Trop de requêtes |

---

## ✅ Checklist d'Implémentation

### Backend

- [ ] Créer modèle `InteractionHistory`
- [ ] Créer migrations base de données
- [ ] Implémenter endpoint `GET /my-likes`
- [ ] Implémenter endpoint `GET /my-passes`
- [ ] Implémenter endpoint `POST /{id}/revoke`
- [ ] Implémenter endpoint `GET /stats`
- [ ] Modifier endpoint `POST /like`
- [ ] Modifier endpoint `POST /dislike`
- [ ] Modifier endpoint `GET /discovery/profiles`
- [ ] Ajouter tests unitaires (>80% coverage)
- [ ] Ajouter tests d'intégration
- [ ] Configurer rate limiting
- [ ] Ajouter monitoring et alertes
- [ ] Documenter API (Swagger/OpenAPI)
- [ ] Script de backfill données existantes

### Frontend

- [ ] Créer modèles d'entités
- [ ] Créer repository
- [ ] Créer use cases
- [ ] Créer BLoC/State management
- [ ] Créer page "Profils likés"
- [ ] Créer page "Profils passés"
- [ ] Créer page "Statistiques"
- [ ] Ajouter navigation
- [ ] Implémenter révocation d'interaction
- [ ] Ajouter confirmation dialogs
- [ ] Tests unitaires
- [ ] Tests d'intégration UI
- [ ] Localisation (FR/EN)

### DevOps

- [ ] Déployer migration en staging
- [ ] Exécuter backfill en staging
- [ ] Tests de charge
- [ ] Déployer en production
- [ ] Monitorer métriques
- [ ] A/B testing si nécessaire

---

## 📞 Support

Pour toute question sur cette implémentation :
- **Backend Lead:** [Nom]
- **Frontend Lead:** [Nom]
- **Product Manager:** [Nom]

---

*Document créé le: 29 Décembre 2025*
*Version: 1.0*
*Statut: ✅ Prêt pour implémentation*
