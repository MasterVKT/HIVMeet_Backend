# ⚠️ PROBLÈME BACKEND - Endpoint 404 Not Found

**Date**: 29 Décembre 2025  
**Type**: Backend - Endpoint manquant  
**Criticité**: 🔴 BLOQUANT - Empêche l'affichage des profils passés

---

## 🔴 Symptômes observés

### Backend (Logs)
```log
WARNING 2025-12-29 12:57:06,353 log 24068 22760 Not Found: /api/v1/discovery/interactions/my-passes
WARNING 2025-12-29 12:57:06,354 basehttp 24068 22760 "GET /api/v1/discovery/interactions/my-passes?page=1&page_size=20 HTTP/1.1" 404 7118
```

### Frontend (Comportement)
- Navigation vers "Profils passés" → Écran blanc ou message d'erreur
- Utilisateur ne peut pas voir ses passes précédents
- Impossible d'annuler un pass

### Requête effectuée
```http
GET /api/v1/discovery/interactions/my-passes?page=1&page_size=20 HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 🔍 Analyse du problème

### Endpoint manquant
L'URL `/api/v1/discovery/interactions/my-passes` **n'est pas enregistrée** dans les URLs Django.

### Comparaison avec endpoints fonctionnels

| Endpoint | Status | Backend |
|----------|--------|---------|
| `/api/v1/discovery/profiles` | ✅ 200 | Implémenté |
| `/api/v1/matches/` | ✅ 200 | Implémenté |
| `/api/v1/user-profiles/likes-received/` | ⚠️ 403 | Implémenté (problème permissions) |
| `/api/v1/discovery/interactions/my-passes` | ❌ 404 | **NON IMPLÉMENTÉ** |
| `/api/v1/discovery/interactions/my-likes` | ❓ Non testé | Probablement manquant aussi |

### Structure attendue
D'après la documentation frontend, l'endpoint devrait retourner:

```json
{
  "count": 10,
  "next": "http://localhost:8000/api/v1/discovery/interactions/my-passes?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid-interaction-123",
      "interaction_type": "dislike",
      "profile": {
        "user_id": "uuid-user-456",
        "username": "john_doe",
        "profile_photo": "https://storage.googleapis.com/photo.jpg",
        "age": 28,
        "city": "Paris",
        "country": "France"
      },
      "created_at": "2025-12-28T14:30:00Z"
    }
  ]
}
```

---

## ✅ Solutions proposées

### Solution 1 : Créer le ViewSet Django (RECOMMANDÉE)

#### Fichier : `backend/apps/discovery/views.py` (ou créer `views_interactions.py`)

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from .models import Interaction
from .serializers import InteractionHistorySerializer

class InteractionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API pour gérer l'historique des interactions (likes, passes)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = InteractionHistorySerializer
    
    def get_queryset(self):
        """Filtrer les interactions de l'utilisateur connecté uniquement"""
        return Interaction.objects.filter(
            user=self.request.user
        ).select_related('target_user__profile').order_by('-created_at')
    
    @action(detail=False, methods=['get'], url_path='my-likes')
    def my_likes(self, request):
        """
        GET /api/v1/discovery/interactions/my-likes
        Retourne les profils que l'utilisateur a likés
        """
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        matched_only = request.query_params.get('matched_only', 'false').lower() == 'true'
        
        # Filtrer les likes (type 'like' ou 'super_like')
        queryset = self.get_queryset().filter(
            interaction_type__in=['like', 'super_like']
        )
        
        # Si matched_only=true, filtrer seulement ceux qui ont matché
        if matched_only:
            queryset = queryset.filter(is_match=True)
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size
        total_count = queryset.count()
        interactions = queryset[start:end]
        
        # Sérialiser
        serializer = self.get_serializer(interactions, many=True)
        
        return Response({
            'count': total_count,
            'next': f'/api/v1/discovery/interactions/my-likes?page={page + 1}&page_size={page_size}' if end < total_count else None,
            'previous': f'/api/v1/discovery/interactions/my-likes?page={page - 1}&page_size={page_size}' if page > 1 else None,
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'], url_path='my-passes')
    def my_passes(self, request):
        """
        GET /api/v1/discovery/interactions/my-passes
        Retourne les profils que l'utilisateur a passés (dislike)
        """
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        # Filtrer les passes (type 'dislike')
        queryset = self.get_queryset().filter(
            interaction_type='dislike'
        )
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size
        total_count = queryset.count()
        interactions = queryset[start:end]
        
        # Sérialiser
        serializer = self.get_serializer(interactions, many=True)
        
        return Response({
            'count': total_count,
            'next': f'/api/v1/discovery/interactions/my-passes?page={page + 1}&page_size={page_size}' if end < total_count else None,
            'previous': f'/api/v1/discovery/interactions/my-passes?page={page - 1}&page_size={page_size}' if page > 1 else None,
            'results': serializer.data
        })
    
    @action(detail=True, methods=['post'], url_path='revoke')
    def revoke_interaction(self, request, pk=None):
        """
        POST /api/v1/discovery/interactions/{id}/revoke
        Annule une interaction (like ou pass)
        """
        try:
            interaction = self.get_queryset().get(id=pk)
            
            # Vérifier que l'interaction appartient bien à l'utilisateur
            if interaction.user != request.user:
                return Response(
                    {'error': 'Non autorisé'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Supprimer l'interaction (le profil réapparaîtra dans discovery)
            interaction.delete()
            
            return Response(
                {'message': 'Interaction révoquée avec succès'},
                status=status.HTTP_200_OK
            )
            
        except Interaction.DoesNotExist:
            return Response(
                {'error': 'Interaction non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'], url_path='stats')
    def get_stats(self, request):
        """
        GET /api/v1/discovery/interactions/stats
        Retourne les statistiques d'interactions de l'utilisateur
        """
        queryset = self.get_queryset()
        
        total_likes = queryset.filter(interaction_type='like').count()
        total_super_likes = queryset.filter(interaction_type='super_like').count()
        total_dislikes = queryset.filter(interaction_type='dislike').count()
        total_matches = queryset.filter(is_match=True).count()
        
        # Ratio like → match
        all_likes = total_likes + total_super_likes
        like_to_match_ratio = (total_matches / all_likes) if all_likes > 0 else 0.0
        
        # Interactions aujourd'hui
        from django.utils import timezone
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        total_interactions_today = queryset.filter(created_at__gte=today_start).count()
        
        # Limites quotidiennes (à adapter selon votre logique)
        daily_limit = 100  # Par exemple
        remaining_today = max(0, daily_limit - total_interactions_today)
        
        return Response({
            'total_likes': total_likes,
            'total_super_likes': total_super_likes,
            'total_dislikes': total_dislikes,
            'total_matches': total_matches,
            'like_to_match_ratio': like_to_match_ratio,
            'total_interactions_today': total_interactions_today,
            'daily_limit': daily_limit,
            'remaining_today': remaining_today
        })
```

#### Fichier : `backend/apps/discovery/serializers.py`

```python
from rest_framework import serializers
from .models import Interaction

class InteractionProfileSerializer(serializers.Serializer):
    """Sérialiseur pour le profil dans l'historique d'interactions"""
    user_id = serializers.UUIDField(source='id')
    username = serializers.CharField()
    profile_photo = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    city = serializers.CharField(source='profile.city', allow_null=True)
    country = serializers.CharField(source='profile.country', allow_null=True)
    
    def get_profile_photo(self, obj):
        """Récupérer la photo principale du profil"""
        if hasattr(obj, 'profile') and obj.profile:
            photos = obj.profile.photos.filter(is_main=True).first()
            if photos:
                return photos.photo_url
        return None
    
    def get_age(self, obj):
        """Calculer l'âge à partir de la date de naissance"""
        if hasattr(obj, 'profile') and obj.profile and obj.profile.date_of_birth:
            from datetime import date
            today = date.today()
            born = obj.profile.date_of_birth
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return None

class InteractionHistorySerializer(serializers.ModelSerializer):
    """Sérialiseur pour l'historique d'interactions"""
    profile = InteractionProfileSerializer(source='target_user', read_only=True)
    
    class Meta:
        model = Interaction
        fields = ['id', 'interaction_type', 'profile', 'created_at', 'is_match']
        read_only_fields = ['id', 'created_at']
```

#### Fichier : `backend/apps/discovery/urls.py`

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InteractionHistoryViewSet

router = DefaultRouter()
router.register(r'interactions', InteractionHistoryViewSet, basename='interactions')

urlpatterns = [
    path('', include(router.urls)),
]
```

#### Fichier : `backend/config/urls.py` (URLs principales)

```python
from django.urls import path, include

urlpatterns = [
    # ... autres URLs
    path('api/v1/discovery/', include('apps.discovery.urls')),
]
```

---

### Solution 2 : Vérifier les modèles existants

Si le modèle `Interaction` n'existe pas encore, créer :

#### Fichier : `backend/apps/discovery/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class Interaction(models.Model):
    """Modèle pour stocker les interactions entre utilisateurs"""
    
    INTERACTION_TYPES = [
        ('like', 'Like'),
        ('super_like', 'Super Like'),
        ('dislike', 'Dislike'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_made'
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_received'
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES
    )
    is_match = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'discovery_interactions'
        unique_together = ['user', 'target_user']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['target_user', '-created_at']),
            models.Index(fields=['interaction_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} → {self.interaction_type} → {self.target_user.username}"
```

#### Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 🧪 Tests de validation

### Test 1 : Vérifier l'enregistrement des URLs

```python
# backend/manage.py shell
from django.urls import resolve

# Tester que l'URL est bien enregistrée
try:
    match = resolve('/api/v1/discovery/interactions/my-passes')
    print(f"✅ URL trouvée: {match.func}")
except:
    print("❌ URL non trouvée")
```

### Test 2 : cURL direct

```bash
# Récupérer le token JWT
TOKEN="<votre_token_jwt>"

# Tester l'endpoint my-passes
curl -X GET "http://localhost:8000/api/v1/discovery/interactions/my-passes?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -v
```

**Résultat attendu** :
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid-123",
      "interaction_type": "dislike",
      "profile": {
        "user_id": "uuid-456",
        "username": "john_doe",
        "profile_photo": "https://...",
        "age": 28,
        "city": "Paris",
        "country": "France"
      },
      "created_at": "2025-12-29T10:30:00Z",
      "is_match": false
    }
  ]
}
```

### Test 3 : Créer des données de test

```python
# backend/manage.py shell
from apps.accounts.models import User
from apps.discovery.models import Interaction

# Récupérer les utilisateurs
marie = User.objects.get(email='marie.claire@test.com')
john = User.objects.create_user(username='john_doe', email='john@test.com')

# Créer une interaction (pass)
interaction = Interaction.objects.create(
    user=marie,
    target_user=john,
    interaction_type='dislike'
)

print(f"✅ Interaction créée: {interaction.id}")

# Tester la requête
from apps.discovery.views import InteractionHistoryViewSet
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

factory = APIRequestFactory()
request = factory.get('/api/v1/discovery/interactions/my-passes')
force_authenticate(request, user=marie)

view = InteractionHistoryViewSet.as_view({'get': 'my_passes'})
response = view(request)
print(f"Status: {response.status_code}")
print(f"Data: {response.data}")
```

---

## 📋 Checklist de correction

- [ ] **Backend** : Créer le modèle `Interaction` si absent
- [ ] **Backend** : Créer le serializer `InteractionHistorySerializer`
- [ ] **Backend** : Créer le ViewSet `InteractionHistoryViewSet`
- [ ] **Backend** : Enregistrer les URLs dans `discovery/urls.py`
- [ ] **Backend** : Ajouter l'app dans `INSTALLED_APPS` si nécessaire
- [ ] **Backend** : Exécuter `makemigrations` et `migrate`
- [ ] **Backend** : Créer des données de test (interactions)
- [ ] **Backend** : Tester avec cURL + token JWT
- [ ] **Backend** : Vérifier les permissions (IsAuthenticated)
- [ ] **Backend** : Tester la pagination
- [ ] **Frontend** : Relancer l'application
- [ ] **Frontend** : Naviguer vers "Profils passés"
- [ ] **Frontend** : Vérifier l'affichage des données
- [ ] **Frontend** : Tester l'annulation d'un pass

---

## 🔧 Alternative : Utiliser un endpoint existant

Si vous avez déjà un modèle différent pour stocker les interactions (par exemple `Swipe`, `Like`, etc.), adapter le code ci-dessus en utilisant votre modèle existant.

**Exemple avec un modèle `Swipe`** :

```python
class InteractionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Swipe.objects.filter(
            user=self.request.user
        ).select_related('target_profile').order_by('-created_at')
    
    @action(detail=False, methods=['get'], url_path='my-passes')
    def my_passes(self, request):
        queryset = self.get_queryset().filter(
            action='dislike'  # ou swipe_direction='left'
        )
        # ... reste du code pagination
```

---

## 📊 Impact utilisateur

### Avant correction
- ❌ Erreur 404 lors de l'accès aux "Profils passés"
- ❌ Écran blanc ou message d'erreur
- ❌ Fonctionnalité complètement inutilisable

### Après correction backend
- ✅ Liste des profils passés affichée
- ✅ Pagination fonctionnelle
- ✅ Bouton "Annuler ce pass" opérationnel
- ✅ Profils révoqués réapparaissent dans Discovery

---

## 📞 Prochaines étapes

### Immédiat
1. **Backend** : Appliquer la Solution 1 (créer le ViewSet)
2. **Backend** : Tester avec cURL
3. **Backend** : Créer quelques interactions de test
4. **Backend** : Redémarrer le serveur Django
5. **Frontend** : Relancer l'application et tester

### Court terme
- Ajouter des tests unitaires pour les endpoints
- Documenter les endpoints dans un fichier OpenAPI/Swagger
- Ajouter un système de cache pour les listes

### Long terme
- Implémenter un système de recommandations basé sur l'historique
- Analytics sur les taux de match
- Système de notification quand un pass est révoqué

---

## 📝 Notes techniques

### Structure de la base de données suggérée

```
Table: discovery_interactions
├── id (UUID, PK)
├── user_id (UUID, FK → users)
├── target_user_id (UUID, FK → users)
├── interaction_type (VARCHAR: 'like', 'super_like', 'dislike')
├── is_match (BOOLEAN)
├── created_at (TIMESTAMP)
└── UNIQUE(user_id, target_user_id)
```

### Index recommandés
- `(user_id, created_at DESC)` : Pour les requêtes my-likes/my-passes
- `(target_user_id, created_at DESC)` : Pour likes-received
- `(interaction_type)` : Pour filtrer par type

### Logique de match
Quand un utilisateur A like un utilisateur B :
1. Créer une interaction `(A → B, type='like')`
2. Vérifier si B a déjà liké A
3. Si oui, mettre `is_match=True` sur les 2 interactions
4. Créer un `Match` dans la table des matches

---

## ⚠️ Autres problèmes détectés

### 1. Endpoint `likes-received` - 403 Forbidden
Voir : [`BACKEND_ERREUR_403_LIKES_RECEIVED.md`](d:\Projets\HIVMeet\hivmeet\BACKEND_ERREUR_403_LIKES_RECEIVED.md)

### 2. Endpoint `my-likes` - Probablement 404 aussi
À vérifier et corriger en même temps que `my-passes`

---

## ✅ Statut final

| Endpoint | Méthode | Status | Action requise |
|----------|---------|--------|----------------|
| `/discovery/interactions/my-passes` | GET | ❌ 404 | **Créer le ViewSet** |
| `/discovery/interactions/my-likes` | GET | ❓ À tester | Probablement à créer aussi |
| `/discovery/interactions/{id}/revoke` | POST | ❓ À tester | À créer |
| `/discovery/interactions/stats` | GET | ❓ À tester | À créer |

---

**Créé par** : GitHub Copilot  
**Date** : 29 Décembre 2025  
**Référence** : Erreur 404 sur my-passes  
**Priorité** : 🔴 CRITIQUE - Bloque complètement la fonctionnalité
