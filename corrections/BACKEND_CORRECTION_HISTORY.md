# BACKEND - Correction de l'Historique des Interactions

**Version**: 1.0  
**Date**: 24 Mars 2026  
**Priorité**: HAUTE  
**Module**: Interaction History  
**Statut**: Action requise côté backend

---

## 📋 Table des Matières

1. [Description du Problème](#description-du-problème)
2. [Analyse des Causes](#analyse-des-causes)
3. [Spécifications Attendues](#spécifications-attendues)
4. [Solutions Proposées](#solutions-proposées)
5. [Code Backend à Implémenter](#code-backend-à-implémenter)
6. [Script de Réinitialisation](#script-de-réinitialisation)
7. [Tests de Validation](#tests-de-validation)
8. [Checklist de Correction](#checklist-de-correction)

---

## 🔴 Description du Problème

### Symptômes Observés
- L'historique des likes ne reflète pas correctement les profils réellement likés par l'utilisateur
- L'historique des passes (dislikes) ne correspond pas aux действий effectuées
- Les données affichées sont incomplètes ou incorrectes
- Après correction, l'utilisateur suggère de réinitialiser les données de test

### Impact sur l'Expérience Utilisateur
- ❌ L'utilisateur ne peut pas voir qui il a liké
- ❌ Confusion sur les actions effectuées
- ❌ Impossible de révoquer une interaction si l'historique est incorrect

---

## 🔍 Analyse des Causes

### Cause N°1 : Requêtes API incorrectes

Les endpoints `GET /interactions/likes/` et `GET /interactions/passes/` utilisent peut-être des requêtes mal structurées.

### Cause N°2 : Données mal structurées

Les réponses API ne retournent peut-être pas les bonnes données (profils au lieu d'utilisateurs, etc.).

### Cause N°3 : Inclusion des interactions révoquées

L'historique inclut peut-être les interactions qui ont été révoquées (après un rewind ou une révocation).

### Cause N°4 : Problème de Jointure

La jointure entre les tables `Interaction`, `Profile` et `User` n'est peut-être pas correcte.

---

## 📋 Spécifications Attendues

### Structure de Réponse Attendue

```json
// GET /api/v1/interactions/likes/
{
  "likes": [
    {
      "id": "uuid",
      "profile": {
        "id": "uuid",
        "display_name": "Sarah",
        "age": 28,
        "photos": [...],
        "distance_km": 5.2
      },
      "liked_at": "2024-01-20T10:30:00Z",
      "is_revoked": false
    }
  ],
  "total_count": 15,
  "has_next": true
}

// GET /api/v1/interactions/passes/
{
  "passes": [
    {
      "id": "uuid",
      "profile": {
        "id": "uuid",
        "display_name": "John",
        "age": 25,
        "photos": [...],
        "distance_km": 8.5
      },
      "passed_at": "2024-01-20T10:35:00Z",
      "is_revoked": false
    }
  ],
  "total_count": 23,
  "has_next": true
}
```

### Règles de Filtrage

1. **Exclure les interactions révoquées** (`is_revoked=False`)
2. **Inclure uniquement les likes** pour l'historique des likes
3. **Inclure uniquement les dislikes** pour l'historique des passes
4. **Trier par date décroissante** (plus récent en premier)

---

## 🛠️ Solutions Proposées

### Solution 1 : Corriger les endpoints API

```python
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_my_likes(request):
    """
    Retourne la liste des profils likés par l'utilisateur.
    
    GET /api/v1/interactions/likes/
    """
    user = request.user
    
    # IMPORTANT: Exclure les interactions révoquées
    interactions = Interaction.objects.filter(
        from_user=user,
        interaction_type='like',
        is_revoked=False  # Ne pas inclure les likes révoqués
    ).select_related(
        'to_user__profile'  # Optimiser la requête
    ).order_by('-created_at')
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    per_page = int(request.query_params.get('per_page', 20))
    
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated_interactions = interactions[start:end]
    
    # Construire la réponse
    likes = []
    for interaction in paginated_interactions:
        profile = interaction.to_user.profile
        likes.append({
            'id': str(interaction.id),
            'profile': {
                'id': str(profile.id),
                'display_name': profile.display_name,
                'age': profile.age,
                'photos': [...],  # À implémenter selon le modèle
                'distance_km': calculate_distance(user, profile)  # À implémenter
            },
            'liked_at': interaction.created_at.isoformat(),
            'is_revoked': interaction.is_revoked
        })
    
    return Response({
        'likes': likes,
        'total_count': interactions.count(),
        'has_next': interactions.count() > end
    })
```

### Solution 2 : Ajouter une méthode de nettoyage

Supprimer les interactions révoquées de la vue historique :

```python
def get_visible_interactions(user, interaction_type):
    """
    Retourne les interactions visibles (non révoquées).
    """
    return Interaction.objects.filter(
        from_user=user,
        interaction_type=interaction_type,
        is_revoked=False  # Important!
    )
```

### Solution 3 : Créer un script de réinitialisation

Script pour réinitialiser les données de test.

---

## 💻 Code Backend à Implémenter

### Fichier: `apps/discovery/views.py`

```python
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_my_likes(request):
    """
    Retourne la liste des profils likés par l'utilisateur.
    
    GET /api/v1/interactions/likes/
    
    Paramètres:
        - page: Numéro de page
        - per_page: Nombre d'éléments par page
        - include_revoked: Inclure les likes révoqués (optionnel, défaut: false)
    
    Response:
        {
            "likes": [...],
            "total_count": 15,
            "has_next": true
        }
    """
    user = request.user
    
    # Paramètres
    include_revoked = request.query_params.get('include_revoked', 'false').lower() == 'true'
    
    # Construire la requête de base
    queryset = Interaction.objects.filter(
        from_user=user,
        interaction_type='like'
    )
    
    # Filtrer selon include_revoked
    if not include_revoked:
        queryset = queryset.filter(is_revoked=False)
    
    # Ordonner par date décroissante
    queryset = queryset.order_by('-created_at')
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    per_page = int(request.query_params.get('per_page', 20))
    
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated_interactions = list(queryset[start:end])
    total_count = queryset.count()
    
    # Construire la réponse avec les données du profil
    likes = []
    for interaction in paginated_interactions:
        try:
            profile = interaction.to_user.profile
            likes.append({
                'id': str(interaction.id),
                'profile': {
                    'id': str(profile.id),
                    'display_name': profile.display_name,
                    'age': profile.age,
                    'bio': profile.bio,
                    'photos': [
                        {
                            'id': str(photo.id),
                            'url': photo.photo_url,
                            'is_main': photo.is_main
                        }
                        for photo in profile.photos.all()[:3]  # Limiter à 3 photos
                    ],
                    'is_verified': profile.is_verified,
                    'is_online': profile.is_online
                },
                'liked_at': interaction.created_at.isoformat(),
                'is_revoked': interaction.is_revoked
            })
        except Exception as e:
            # Logger l'erreur mais continuer
            print(f"Erreur lors de la récupération du profil: {e}")
            continue
    
    return Response({
        'likes': likes,
        'total_count': total_count,
        'has_next': total_count > end
    })


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_my_passes(request):
    """
    Retourne la liste des profils passés (dislikés) par l'utilisateur.
    
    GET /api/v1/interactions/passes/
    
    Paramètres:
        - page: Numéro de page
        - per_page: Nombre d'éléments par page
        - include_revoked: Inclure les passes révoqués (optionnel, défaut: false)
    
    Response:
        {
            "passes": [...],
            "total_count": 23,
            "has_next": true
        }
    """
    user = request.user
    
    # Paramètres
    include_revoked = request.query_params.get('include_revoked', 'false').lower() == 'true'
    
    # Construire la requête de base
    queryset = Interaction.objects.filter(
        from_user=user,
        interaction_type='dislike'
    )
    
    # Filtrer selon include_revoked
    if not include_revoked:
        queryset = queryset.filter(is_revoked=False)
    
    # Ordonner par date décroissante
    queryset = queryset.order_by('-created_at')
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    per_page = int(request.query_params.get('per_page', 20))
    
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated_interactions = list(queryset[start:end])
    total_count = queryset.count()
    
    # Construire la réponse avec les données du profil
    passes = []
    for interaction in paginated_interactions:
        try:
            profile = interaction.to_user.profile
            passes.append({
                'id': str(interaction.id),
                'profile': {
                    'id': str(profile.id),
                    'display_name': profile.display_name,
                    'age': profile.age,
                    'bio': profile.bio,
                    'photos': [
                        {
                            'id': str(photo.id),
                            'url': photo.photo_url,
                            'is_main': photo.is_main
                        }
                        for photo in profile.photos.all()[:3]
                    ],
                    'is_verified': profile.is_verified,
                    'is_online': profile.is_online
                },
                'passed_at': interaction.created_at.isoformat(),
                'is_revoked': interaction.is_revoked
            })
        except Exception as e:
            print(f"Erreur lors de la récupération du profil: {e}")
            continue
    
    return Response({
        'passes': passes,
        'total_count': total_count,
        'has_next': total_count > end
    })
```

---

## 🧹 Script de Réinitialisation

### Fichier: `reset_test_interactions.py`

```python
#!/usr/bin/env python
"""
Script pour réinitialiser les interactions des utilisateurs de test.
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet.settings')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'env', 'hivmeet_backend'))
django.setup()

from django.contrib.auth import get_user_model
from apps.discovery.models import Interaction, Profile

User = get_user_model()


def reset_test_users_interactions():
    """Réinitialise les interactions des utilisateurs de test."""
    
    print("=== Réinitialisation des interactions de test ===\n")
    
    # Identifier les utilisateurs de test (à adapter selon votre convention)
    test_users = User.objects.filter(
        email__contains='test'
    ).values_list('id', flat=True)
    
    if not test_users:
        print("Aucun utilisateur de test trouvé!")
        return
    
    print(f"Nombre d'utilisateurs de test: {len(test_users)}")
    
    total_deleted = 0
    
    for user_id in test_users:
        # Compter les interactions avant suppression
        likes_count = Interaction.objects.filter(
            from_user_id=user_id,
            interaction_type='like'
        ).count()
        
        passes_count = Interaction.objects.filter(
            from_user_id=user_id,
            interaction_type='dislike'
        ).count()
        
        # Supprimer toutes les interactions
        deleted = Interaction.objects.filter(
            from_user_id=user_id
        ).delete()[0]
        
        total_deleted += deleted
        
        print(f"Utilisateur {user_id}: {likes_count} likes, {passes_count} passes supprimés")
    
    print(f"\n=== Total: {total_deleted} interactions supprimées ===")


def reset_all_interactions():
    """Réinitialise TOUTES les interactions (dangereux!)."""
    
    print("⚠️  ATTENTION: Cette action va supprimer TOUTES les interactions!")
    confirmation = input("Êtes-vous sûr? Tapez 'OUI' pour confirmer: ")
    
    if confirmation != 'OUI':
        print("Opération annulée.")
        return
    
    # Compter avant suppression
    total_likes = Interaction.objects.filter(interaction_type='like').count()
    total_passes = Interaction.objects.filter(interaction_type='dislike').count()
    
    print(f"\nLikes à supprimer: {total_likes}")
    print(f"Passes à supprimer: {total_passes}")
    
    # Supprimer
    deleted = Interaction.objects.all().delete()[0]
    
    print(f"\n=== Total: {deleted} interactions supprimées ===")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Réinitialiser les interactions')
    parser.add_argument('--all', action='store_true', 
                       help='Réinitialiser TOUTES les interactions (dangereux)')
    
    args = parser.parse_args()
    
    if args.all:
        reset_all_interactions()
    else:
        reset_test_users_interactions()
```

---

## 🧪 Tests de Validation

### Test 1 : Historique des likes
```
Préconditions: Utilisateur avec des likes
Actions:
  1. Appeler GET /api/v1/interactions/likes/
  
Résultats attendus:
  ✅ Retourne la liste des profils likés
  ✅ Les likes révoqués ne sont pas inclus (par défaut)
  ✅ Les données du profil sont complètes
  ✅ Trié par date décroissante
```

### Test 2 : Historique des passes
```
Préconditions: Utilisateur avec des passes
Actions:
  1. Appeler GET /api/v1/interactions/passes/
  
Résultats attendus:
  ✅ Retourne la liste des profils passés
  ✅ Les passes révoqués ne sont pas inclus (par défaut)
  ✅ Les données du profil sont complètes
  ✅ Trié par date décroissante
```

### Test 3 : Inclusion des révoqués
```
Préconditions: Utilisateur avec des likes révoqués
Actions:
  1. Appeler GET /api/v1/interactions/likes/?include_revoked=true
  
Résultats attendus:
  ✅ Les likes révoqués sont inclus
```

---

## ✅ Checklist de Correction

### Backend (À faire par le développeur backend)

- [ ] **Corriger `get_my_likes()`** pour exclure les interactions révoquées
- [ ] **Corriger `get_my_passes()`** pour exclure les interactions révoquées
- [ ] **Vérifier les jointures** avec les tables Profile et User
- [ ] **Ajouter la pagination** si absente
- [ ] **Tester les endpoints** avec des données réelles

### Réinitialisation des Données

- [ ] **Exécuter le script de réinitialisation** `reset_test_interactions.py`
- [ ] **Vérifier que les données de test** sont correctement réinitialisées

### Tests à Effectuer

- [ ] **Tester GET /interactions/likes/** avec un utilisateur réel
- [ ] **Tester GET /interactions/passes/** avec un utilisateur réel
- [ ] **Vérifier la pagination**
- [ ] **Vérifier les données de profil** retournées

---

## 📝 Notes Additionnelles

### URLs à configurer

```python
# urls.py
from django.urls import path
from apps.discovery import views

urlpatterns = [
    # ... existing URLs ...
    path('interactions/likes/', views.get_my_likes, name='get_my_likes'),
    path('interactions/passes/', views.get_my_passes, name='get_my_passes'),
]
```

### Commandes utiles

```bash
# Réinitialiser les interactions de test
python manage.py shell < reset_test_interactions.py

# Réinitialiser TOUTES les interactions (dangereux!)
python manage.py shell < reset_test_interactions.py --all
```

---

## 🔗 Références

- Documentation API: `guides/INTERACTION_HISTORY_API_DOCUMENTATION.md`
- Spécifications: `docs/BACKEND_INTERACTION_HISTORY_SPECIFICATION.md`

---

**Dernière mise à jour**: 24 Mars 2026  
**Créé par**: AI Agent (GitHub Copilot)  
**Pour**: Équipe de Développement HIVMeet Backend
