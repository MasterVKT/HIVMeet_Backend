# BACKEND - Correction du Compteur de Swipes/Likes

**Version**: 1.0  
**Date**: 24 Mars 2026  
**Priorité**: HAUTE  
**Module**: Discovery - Compteur de likes  
**Statut**: À implémenter côté backend

---

## 📋 Table des Matières

1. [Analyse des Problèmes](#analyse-des-problèmes)
2. [Problème 1: Compteur non affiché au démarrage](#problème-1-compteur-non-affiché-au-démarrage)
3. [Problème 2: Erreur off-by-one (12 au lieu de 10)](#problème-2-erreur-off-by-one-12-au-lieu-de-10)
4. [Problème 3: Limite non vérifiée avant le swipe](#problème-3-limite-non-vérifiée-avant-le-swipe)
5. [Solution Complète](#solution-complète)
6. [Fichiers à Modifier](#fichiers-à-modifier)
7. [Tests de Validation](#tests-de-validation)

---

## 🔍 Analyse des Problèmes

### Symptômes Observés

1. **Le compteur ne s'affiche pas au démarrage** - L'utilisateur ne voit pas le nombre de swipes restants avant de faire son premier swipe
2. **Le compteur affiche 10 après le premier swipe** - Le nombre correct devrait être affiché dès le chargement
3. **Off-by-one error** - L'utilisateur peut effectuer 12 swipes au lieu de 10 avant que la limite soit atteinte
4. **La limite n'est pas bloquante** - Un swipe supplémentaire est toujours possible après avoir affiché 0

### Causes Identifiées

D'après les logs backend :

```
INFO 2026-03-24 04:18:26,068 views_discovery 10316 13696 👎 Dislike sent - User: ..., daily_likes_remaining: -1
INFO 2026-03-24 04:18:28,044 views_discovery 10316 13696 👎 Dislike sent - User: ..., daily_likes_remaining: -1
INFO 2026-03-24 04:18:29,732 daily_likes_service 10316 13696 [DAILY_LIKES] BEFORE_LIKE - User: ..., is_premium=True, daily_likes_remaining=-1, likes_used_today=0, super_likes_remaining=5, daily_likes_limit=None
```

**Problèmes identifiés :**

1. `daily_likes_limit=None` pour l'utilisateur premium (comportement attendu)
2. `daily_likes_remaining=-1` - Indique une valeur par défaut incorrecte
3. Pour les utilisateurs **gratuits**, le backend ne retourne pas le `daily_likes_remaining` dans la réponse de `/discovery/profiles/`

---

## 🛠️ Problème 1: Compteur non affiché au démarrage

### Cause

Le endpoint `GET /api/v1/discovery/profiles/` ne retourne pas les informations de limite quotidienne (`daily_likes_remaining`, `daily_likes_limit`).

### Solution

Modifier le endpoint `GET /discovery/profiles/` pour inclure les informations de limite dans la réponse.

### Fichier: `discovery/views_discovery.py`

```python
@api_view(['GET'])
@authentication_classes([FirebaseTokenAuthentication])
@permission_classes([IsAuthenticated])
def get_discovery_profiles(request):
    # ... code existant ...
    
    # Obtenir les informations de limite quotidienne
    daily_likes_info = get_daily_likes_info(request.user)
    
    # Construire la réponse
    response_data = {
        'profiles': profiles_data,
        'count': len(profiles_data),
        'page': page,
        'page_size': page_size,
        # AJOUTER CES CHAMPS
        'daily_likes_remaining': daily_likes_info.get('remaining', 10),  # 10 pour gratuits, -1 pour premium
        'daily_likes_limit': daily_likes_info.get('limit', 10),  # None pour premium
        'likes_used_today': daily_likes_info.get('used_today', 0),
    }
    
    return Response(response_data, status=status.HTTP_200_OK)
```

### Nouvelle fonction à ajouter dans `services/daily_likes_service.py`

```python
def get_daily_likes_info(user):
    """
    Retourne les informations de likes quotidiens pour l'utilisateur.
    
    Returns:
        dict: {
            'remaining': int,  # Nombre de likes restants (-1 si premium/sans limite)
            'limit': int|None,  # Limite quotidienne (None si premium)
            'used_today': int,  # Likes utilisés aujourd'hui
            'reset_at': datetime,  # Heure de réinitialisation
        }
    """
    # Vérifier si premium
    if user.profile.is_premium:
        return {
            'remaining': -1,  # Pas de limite
            'limit': None,
            'used_today': 0,
            'reset_at': None,
        }
    
    # Configuration pour utilisateurs gratuits
    DAILY_LIKES_LIMIT = 10  # Depuis settings
    
    # Récupérer les likes utilisés aujourd'hui
    today = timezone.now().date()
    likes_used_today = Interaction.objects.filter(
        liker=user.profile,
        interaction_type='like',
        created_at__date=today
    ).count()
    
    # Calculer les likes restants
    remaining = max(0, DAILY_LIKES_LIMIT - likes_used_today)
    
    # Calculer l'heure de réinitialisation (minuit)
    tomorrow = today + timedelta(days=1)
    reset_at = timezone.make_aware(datetime.combine(tomorrow, datetime.min.time()))
    
    return {
        'remaining': remaining,
        'limit': DAILY_LIKES_LIMIT,
        'used_today': likes_used_today,
        'reset_at': reset_at,
    }
```

---

## 🛠️ Problème 2: Erreur off-by-one (12 au lieu de 10)

### Cause

La vérification de la limite se fait **après** le decrement, ce qui permet un swipe supplémentaire.

### Solution

Vérifier la limite **avant** d'autoriser le swipe, pas après.

### Fichier: `discovery/views_discovery.py`

```python
@api_view(['POST'])
@authentication_classes([FirebaseTokenAuthentication])
@permission_classes([IsAuthenticated])
def like_profile(request):
    target_id = request.data.get('target_id')
    
    if not target_id:
        return Response(
            {'error': 'target_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # VÉRIFICATION AVANT LE SWIPE - pas après
    daily_info = get_daily_likes_info(request.user)
    
    # Pour les utilisateurs gratuits, vérifier la limite
    if daily_info['limit'] is not None:
        if daily_info['remaining'] <= 0:
            return Response(
                {
                    'error': 'Daily like limit reached',
                    'daily_likes_remaining': 0,
                    'daily_likes_limit': daily_info['limit'],
                    'reset_at': daily_info['reset_at'].isoformat() if daily_info['reset_at'] else None,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
    
    # ... suite du code existant pour créer l'interaction ...
```

---

## 🛠️ Problème 3: Limite non vérifiée avant le swipe

### Cause

Le frontend envoie la requête de like, et le backend l'accepte même si la limite est atteinte. La limite est seulement retournée dans la réponse.

### Solution

Bloquer la requête côté backend et retourner un code 429 si la limite est atteinte.

### Code à ajouter dans `services/daily_likes_service.py`

```python
def check_daily_likes_limit(user):
    """
    Vérifie si l'utilisateur a atteint sa limite de likes quotidiens.
    
    Args:
        user: L'utilisateur à vérifier
        
    Returns:
        tuple: (is_allowed: bool, remaining: int, limit: int|None)
    """
    daily_info = get_daily_likes_info(user)
    
    # Premium n'a pas de limite
    if daily_info['limit'] is None:
        return (True, -1, None)
    
    # Vérifier si des likes sont encore disponibles
    if daily_info['remaining'] <= 0:
        return (False, 0, daily_info['limit'])
    
    return (True, daily_info['remaining'], daily_info['limit'])
```

---

## 📝 Solution Complète

### Fichier: `discovery/services.py` (ou créer nouveau fichier)

```python
# discovery/services/daily_likes_service.py

from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from discovery.models import Interaction

# Configuration par défaut (peut être surchargée via settings)
DAILY_LIKES_LIMIT_FREE = getattr(settings, 'DAILY_LIKES_LIMIT_FREE', 10)


def get_daily_likes_info(user):
    """
    Retourne les informations complètes de likes quotidiens.
    
    Args:
        user: L'utilisateur Django
        
    Returns:
        dict: {
            'remaining': int,
            'limit': int|None,
            'used_today': int,
            'reset_at': datetime|None,
            'is_premium': bool,
        }
    """
    # Vérifier si premium
    is_premium = getattr(user, 'is_premium', False)
    
    if is_premium:
        return {
            'remaining': -1,  # Pas de limite
            'limit': None,
            'used_today': 0,
            'reset_at': None,
            'is_premium': True,
        }
    
    # Compter les likes d'aujourd'hui
    today = timezone.now().date()
    likes_used_today = Interaction.objects.filter(
        liker=getattr(user, 'profile', None),
        interaction_type='like',
        created_at__date=today,
        is_revoked=False
    ).count()
    
    # Calculer les restants
    remaining = max(0, DAILY_LIKES_LIMIT_FREE - likes_used_today)
    
    # Calculer l'heure de réinitialisation (minuit)
    tomorrow = today + timedelta(days=1)
    reset_at = timezone.make_aware(
        datetime.combine(tomorrow, datetime.min.time())
    )
    
    return {
        'remaining': remaining,
        'limit': DAILY_LIKES_LIMIT_FREE,
        'used_today': likes_used_today,
        'reset_at': reset_at,
        'is_premium': False,
    }


def check_and_use_daily_like(user):
    """
    Vérifie et décrémente la limite de likes quotidiens.
    
    Args:
        user: L'utilisateur Django
        
    Returns:
        tuple: (success: bool, remaining: int, limit: int|None, error: str|None)
    """
    daily_info = get_daily_likes_info(user)
    
    # Premium n'a pas de limite
    if daily_info['limit'] is None:
        return (True, -1, None, None)
    
    # Vérifier si la limite est atteinte
    if daily_info['remaining'] <= 0:
        return (
            False,
            0,
            daily_info['limit'],
            f"Daily like limit reached. Limit: {daily_info['limit']}, Reset at: {daily_info['reset_at']}"
        )
    
    # Retourner le nombre restant APRÈS ce like (pour mise à jour du frontend)
    return (
        True,
        daily_info['remaining'] - 1,  # -1 car le like va être créé
        daily_info['limit'],
        None
    )
```

### Fichier: `discovery/views_discovery.py` - Modifications

```python
# Endpoint GET profiles - ajouter daily_likes_info à la réponse
@api_view(['GET'])
@authentication_classes([FirebaseTokenAuthentication])
@permission_classes([IsAuthenticated])
def get_discovery_profiles(request):
    # ... code existant jusqu'à la réponse ...
    
    daily_info = get_daily_likes_info(request.user)
    
    return Response({
        'profiles': profiles_data,
        'count': len(profiles_data),
        'page': page,
        'page_size': page_size,
        # NOUVEAU: Informations de limite
        'daily_likes_remaining': daily_info['remaining'],
        'daily_likes_limit': daily_info['limit'],
        'daily_likes_used_today': daily_info['used_today'],
        'daily_likes_reset_at': daily_info['reset_at'].isoformat() if daily_info['reset_at'] else None,
        'is_premium': daily_info['is_premium'],
    })


# Endpoint POST like - vérifier la limite AVANT de créer l'interaction
@api_view(['POST'])
@authentication_classes([FirebaseTokenAuthentication])
@permission_classes([IsAuthenticated])
def like_profile(request):
    target_id = request.data.get('target_id')
    
    if not target_id:
        return Response(
            {'error': 'target_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # VÉRIFICATION DE LA LIMITE ICI
    success, remaining, limit, error = check_and_use_daily_like(request.user)
    
    if not success:
        return Response(
            {
                'error': error,
                'daily_likes_remaining': remaining,
                'daily_likes_limit': limit,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    # ... reste du code existant ...
```

---

## 📁 Fichiers à Modifier

| Fichier | Action | Description |
|---------|--------|-------------|
| `discovery/services/daily_likes_service.py` | Créer | Nouveau service pour la gestion des likes quotidiens |
| `discovery/views_discovery.py` | Modifier | Ajouter daily_likes_info aux réponses GET et vérifier la limite dans POST like |
| `discovery/urls.py` | Aucun | Pas de changement nécessaire |

---

## ✅ Tests de Validation

### Test 1: Compteur affiché au démarrage

```bash
# 1. Se connecter avec un compte gratuit
# 2. Aller sur la page de découverte
# 3. Vérifier que le compteur "10 swipes restants" s'affiche immédiatement
# 4. Ne faire AUCUN swipe
# 5. Vérifier que le compteur affiche toujours 10
```

### Test 2: Compteur décrémente correctement

```bash
# 1. Compteur à 10
# 2. Faire un like
# 3. Vérifier que le compteur affiche 9
# 4. Répéter jusqu'à 0
```

### Test 3: Blocage à 0

```bash
# 1. Compteur à 0
# 2. Tenter de faire un like
# 3. Vérifier que le swipe est BLOQUÉ (pas juste un message d'erreur)
# 4. Vérifier que le message "Limite atteinte" s'affiche
```

### Test 4: Réinitialisation à minuit

```bash
# 1. Utiliser tous les 10 likes
# 2. Attendre minuit (ou modifier l'heure système)
# 3. Vérifier que le compteur est réinitialisé à 10
```

### Script de test automatisé

```python
# test_daily_likes.py

import os
import django
import sys

# Setup Django
sys.path.insert(0, 'D:/Projets/HIVMeet/env/hivmeet_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from discovery.services.daily_likes_service import (
    get_daily_likes_info,
    check_and_use_daily_like,
    DAILY_LIKES_LIMIT_FREE
)
from users.models import User

def test_free_user_likes():
    """Test le compteur de likes pour un utilisateur gratuit"""
    # Récupérer un utilisateur gratuit de test
    user = User.objects.filter(profile__is_premium=False).first()
    
    if not user:
        print("❌ Aucun utilisateur gratuit trouvé")
        return
    
    print(f"✅ Utilisateur: {user.email}")
    
    # Test 1: Vérifier les infos initiales
    info = get_daily_likes_info(user)
    print(f"📊 Likes restants: {info['remaining']}/{info['limit']}")
    assert info['remaining'] <= info['limit'], "Erreur: remaining > limit"
    
    # Test 2: Utiliser un like
    success, remaining, limit, error = check_and_use_daily_like(user)
    print(f"🔄 Après un like: remaining={remaining}, limit={limit}")
    assert success, f"Erreur: {error}"
    assert remaining == info['remaining'] - 1, "Erreur: décrémentation incorrecte"
    
    print("✅ Tous les tests passent!")

if __name__ == '__main__':
    test_free_user_likes()
```

---

## 📝 Checklist de Mise en Œuvre

- [ ] Créer `discovery/services/daily_likes_service.py`
- [ ] Implémenter `get_daily_likes_info()`
- [ ] Implémenter `check_and_use_daily_like()`
- [ ] Modifier `GET /discovery/profiles/` pour inclure `daily_likes_info`
- [ ] Modifier `POST /discovery/interactions/like` pour vérifier la limite
- [ ] Tester avec un compte gratuit
- [ ] Vérifier que le compteur s'affiche dès le chargement
- [ ] Vérifier que le blocage fonctionne à 0

---

**Dernière mise à jour**: 24 Mars 2026  
**Créé par**: AI Agent (GitHub Copilot)  
**Pour**: Équipe de Développement HIVMeet Backend
