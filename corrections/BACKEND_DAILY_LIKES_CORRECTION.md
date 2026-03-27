# BACKEND - Correction du Compteur de Likes Quotidiens

**Version**: 1.0  
**Date**: 23 Mars 2026  
**Priorité**: HAUTE  
**Module**: Discovery / Matching  
**Statut**: Action requise côté backend

---

## 📋 Table des Matières

1. [Description du Problème](#description-du-problème)
2. [Analyse des Causes](#analyse-des-causes)
3. [Spécifications Attendues](#spécifications-attendues)
4. [Solutions Proposées](#solutions-proposées)
5. [Code Backend à Implémenter](#code-backend-à-implémenter)
6. [Impact sur l'Utilisateur](#impact-sur-lutilisateur)
7. [Tests de Validation](#tests-de-validation)
8. [Checklist de Correction](#checklist-de-correction)

---

## 🔴 Description du Problème

### Symptômes Observés
- Le compteur de likes restants affiche une valeur incorrecte (999, 1000, ou reste bloqué)
- Le compteur ne décrémente pas correctement après chaque like
- Le compteur passe de 10 à 999 au lieu de passer à 9

### Comportement Attendu vs Réel

| Action | Comportement Attendu | Comportement Réel |
|--------|---------------------|-------------------|
| Premier like | Compteur = 9/10 | Compteur affiche une valeur incohérente |
| Deuxième like | Compteur = 8/10 | Compteur passe à 999 ou reste identique |
| Like suivant | Compteur = 7/10 | Le compteur ne décrémente pas correctement |

### Endpoints Concernés
- `POST /api/v1/discovery/interactions/like/` - Envoi d'un like
- `POST /api/v1/discovery/interactions/dislike/` - Envoi d'un dislike
- `POST /api/v1/discovery/interactions/super-like/` - Envoi d'un super like
- `GET /api/v1/discovery/interactions/like/status/` - Statut du like (optionnel)

---

## 🔍 Analyse des Causes

### Cause Probable N°1 : Valeur `daily_likes_remaining` absente ou incorrecte dans la réponse API

Le frontend attend la clé `daily_likes_remaining` dans la réponse du endpoint de like :

```json
// Réponse attendue par le frontend
{
  "result": "like_sent",
  "match_id": null,
  "daily_likes_remaining": 49,  // ← Cette valeur doit être présente
  "super_likes_remaining": 1
}
```

**Si le backend ne retourne pas cette valeur**, le frontend ne peut pas mettre à jour le compteur.

### Cause Probable N°2 : Logique de calcul du compteur côté backend incorrecte

Le backend doit :
1. Compter les likes envoyés par l'utilisateur aujourd'hui
2. Soustraire ce nombre de la limite quotidienne (50 pour les utilisateurs gratuits)
3. Retourner le résultat dans `daily_likes_remaining`

### Cause Probable N°3 : Compteur non persisté entre les requêtes

Si le backend recalcule le compteur dynamiquement mais avec une erreur de logique (par exemple, une condition inversée), cela peut produire des valeurs incorrectes comme 999.

### Cause Probable N°4 : Problème de timezone ou de reset du compteur

Si le reset du compteur quotidien ne fonctionne pas correctement (par exemple, utilisation d'une timezone incorrecte), le compteur peut afficher des valeurs erronées.

---

## 📋 Spécifications Attendues

### Limites par Tier d'Utilisateur

| Fonctionnalité | Utilisateur Gratuit | Utilisateur Premium |
|---------------|-------------------|-------------------|
| Likes quotidiens | **10** | Illimités |
| Super likes par jour | 1 | 5 |
| Rewinds par jour | 0 | 5 |
| Voir qui a liké | Non | Oui |

> **Note** : La limite de 10 likes gratuits par jour est volontairement basse pour encourager les utilisateurs à souscrire à l'abonnement premium.

### Structure de Réponse Attendue

```json
{
  "result": "like_sent",  // ou "match", "dislike_sent", etc.
  "match_id": "uuid-string-or-null",
  "daily_likes_remaining": 49,  // Nombre de likes restants (0-50)
  "super_likes_remaining": 1,   // Nombre de super likes restants
  "message": "Like envoyé avec succès"
}
```

### Champs Requis dans la Réponse

| Champ | Type | Description | Obligatoire |
|-------|------|-------------|-------------|
| `result` | string | Type de résultat (match, like_sent, dislike_sent, etc.) | Oui |
| `match_id` | string/null | ID du match si c'est un match | Conditionnel |
| `daily_likes_remaining` | integer | Likes restants pour aujourd'hui (0 à 50) | **Oui** |
| `super_likes_remaining` | integer | Super likes restants | Oui |
| `message` | string | Message optionnel | Non |

---

## 🛠️ Solutions Proposées

### Solution 1 : Corriger la Réponse API du Endpoint de Like

Le backend doit retourner `daily_likes_remaining` dans toutes les réponses de swipe.

### Solution 2 : Implémenter une Fonction de Calcul Robuste

Créer une fonction utilitaire qui calcule correctement le nombre de likes restants :

```python
def calculate_daily_likes_remaining(user):
    """
    Calcule les likes restants pour aujourd'hui.
    
    Args:
        user: L'utilisateur connecté
        
    Returns:
        int: Nombre de likes restants (entre 0 et 50 pour les gratuits)
    """
    # Obtenir la limite quotidienne selon le tier
    daily_limit = get_user_daily_limit(user)
    
    # Compter les likes d'aujourd'hui
    today_likes = count_user_likes_today(user)
    
    # Calculer les likes restants
    remaining = max(0, daily_limit - today_likes)
    
    return remaining
```

### Solution 3 : Ajouter des Logs de Diagnostic

Pour faciliter le debug futur, ajouter des logs dans les endpoints de swipe :

```python
# logs/daily_likes_debug.log
logger.info(f"[DAILY_LIKES] User {user.id} - daily_likes_remaining={remaining}, "
            f"today_likes={today_likes}, daily_limit={daily_limit}")
```

### Solution 4 : Créer un Endpoint de Statut (Optionnel mais Recommandé)

```python
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_like_status(request):
    """
    Retourne le nombre de likes restants pour l'utilisateur.
    Utile pour afficher le compteur avant tout swipe.
    """
    user = request.user
    remaining = calculate_daily_likes_remaining(user)
    daily_limit = get_user_daily_limit(user)
    
    return Response({
        'daily_likes_remaining': remaining,
        'daily_likes_limit': daily_limit,
        'super_likes_remaining': get_super_likes_remaining(user),
        'reset_at': get_next_reset_time()  # Timestamp du prochain reset
    })
```

---

## 💻 Code Backend à Implémenter

### Fichier: `apps/discovery/services/likes_service.py`

```python
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q
from apps.subscriptions.models import Subscription, SubscriptionTier
from apps.users.models import User


class DailyLikesService:
    """Service pour gérer les limites de likes quotidiens."""
    
    # Limites par défaut (10 likes gratuits pour encourager le premium)
    FREE_DAILY_LIKES_LIMIT = 10
    FREE_DAILY_SUPER_LIKES_LIMIT = 1
    PREMIUM_DAILY_SUPER_LIKES_LIMIT = 5
    
    @staticmethod
    def get_user_daily_limit(user: User) -> int:
        """
        Retourne la limite quotidienne de likes pour un utilisateur.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Limite quotidienne (50 pour gratuits, illimité pour premium)
        """
        if DailyLikesService.is_premium_user(user):
            return -1  # Indique illimité
        
        return DailyLikesService.FREE_DAILY_LIKES_LIMIT
    
    @staticmethod
    def is_premium_user(user: User) -> bool:
        """Vérifie si l'utilisateur a un abonnement premium actif."""
        return Subscription.objects.filter(
            user=user,
            is_active=True,
            tier__in=[SubscriptionTier.PREMIUM, SubscriptionTier.GOLD]
        ).exists()
    
    @staticmethod
    def get_start_of_day() -> datetime:
        """Retourne le début de la journée en UTC."""
        now = timezone.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def get_end_of_day() -> datetime:
        """Retourne la fin de la journée en UTC."""
        now = timezone.now()
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def count_likes_today(user: User) -> int:
        """
        Compte les likes envoyés par l'utilisateur aujourd'hui.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de likes envoyés aujourd'hui
        """
        from apps.discovery.models import Interaction
        
        return Interaction.objects.filter(
            from_user=user,
            interaction_type='like',
            created_at__gte=DailyLikesService.get_start_of_day(),
            created_at__lt=DailyLikesService.get_end_of_day(),
            is_revoked=False
        ).count()
    
    @staticmethod
    def count_super_likes_today(user: User) -> int:
        """
        Compte les super likes envoyés par l'utilisateur aujourd'hui.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de super likes envoyés aujourd'hui
        """
        from apps.discovery.models import Interaction
        
        return Interaction.objects.filter(
            from_user=user,
            interaction_type='super_like',
            created_at__gte=DailyLikesService.get_start_of_day(),
            created_at__lt=DailyLikesService.get_end_of_day(),
            is_revoked=False
        ).count()
    
    @staticmethod
    def get_likes_remaining(user: User) -> int:
        """
        Calcule les likes restants pour aujourd'hui.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de likes restants (0 à 50 pour les gratuits)
        """
        daily_limit = DailyLikesService.get_user_daily_limit(user)
        
        # Les utilisateurs premium ont des likes illimités
        if daily_limit == -1:
            return -1  # Indique illimité
        
        likes_sent = DailyLikesService.count_likes_today(user)
        remaining = daily_limit - likes_sent
        
        # S'assurer que la valeur est dans les limites valides
        return max(0, min(remaining, daily_limit))
    
    @staticmethod
    def get_super_likes_remaining(user: User) -> int:
        """
        Calcule les super likes restants pour aujourd'hui.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de super likes restants
        """
        if DailyLikesService.is_premium_user(user):
            limit = DailyLikesService.PREMIUM_DAILY_SUPER_LIKES_LIMIT
        else:
            limit = DailyLikesService.FREE_DAILY_SUPER_LIKES_LIMIT
        
        sent = DailyLikesService.count_super_likes_today(user)
        remaining = limit - sent
        
        return max(0, min(remaining, limit))
    
    @staticmethod
    def can_user_like(user: User) -> tuple[bool, str]:
        """
        Vérifie si l'utilisateur peut encore liker aujourd'hui.
        
        Returns:
            tuple: (peut_liker, message_erreur)
        """
        if DailyLikesService.is_premium_user(user):
            return True, ""
        
        remaining = DailyLikesService.get_likes_remaining(user)
        
        if remaining <= 0:
            return False, "Limite de likes quotidiens atteinte. Réessayez demain!"
        
        return True, ""
    
    @staticmethod
    def get_next_reset_time() -> datetime:
        """
        Retourne l'heure du prochain reset du compteur.
        
        Returns:
            datetime: Timestamp du prochain reset (minuit UTC)
        """
        now = timezone.now()
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
```

### Modification du Endpoint de Like: `apps/discovery/views.py`

```python
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from apps.discovery.models import Interaction, Profile
from apps.discovery.services.likes_service import DailyLikesService


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic
def send_like(request):
    """
    Endpoint pour envoyer un like à un profil.
    
    POST /api/v1/discovery/interactions/like/
    
    Body:
        {
            "target_profile_id": "uuid"
        }
    
    Response:
        {
            "result": "like_sent" | "match",
            "match_id": "uuid" | null,
            "daily_likes_remaining": 49,
            "super_likes_remaining": 1,
            "message": "Like envoyé avec succès" | "C'est un match!"
        }
    """
    user = request.user
    target_profile_id = request.data.get('target_profile_id')
    
    # Validation de base
    if not target_profile_id:
        return Response(
            {'error': 'target_profile_id est requis'},
            status=400
        )
    
    # Vérifier si l'utilisateur peut encore liker
    can_like, error_message = DailyLikesService.can_user_like(user)
    if not can_like:
        return Response(
            {'error': error_message},
            status=429  # Too Many Requests
        )
    
    # Récupérer le profil cible
    try:
        target_profile = Profile.objects.get(id=target_profile_id)
    except Profile.DoesNotExist:
        return Response(
            {'error': 'Profil non trouvé'},
            status=404
        )
    
    # Créer l'interaction
    interaction = Interaction.objects.create(
        from_user=user,
        to_user=target_profile.user,
        interaction_type='like'
    )
    
    # Vérifier si c'est un match (like réciproque)
    mutual_like = Interaction.objects.filter(
        from_user=target_profile.user,
        to_user=user,
        interaction_type='like',
        is_revoked=False
    ).exists()
    
    # Calculer les likes restants APRÈS ce like
    daily_likes_remaining = DailyLikesService.get_likes_remaining(user)
    super_likes_remaining = DailyLikesService.get_super_likes_remaining(user)
    
    # Préparer la réponse
    response_data = {
        'result': 'match' if mutual_like else 'like_sent',
        'match_id': None,
        'daily_likes_remaining': daily_likes_remaining,
        'super_likes_remaining': super_likes_remaining,
        'message': "C'est un match!" if mutual_like else "Like envoyé avec succès"
    }
    
    # Si c'est un match, créer l'instance de match et retourner l'ID
    if mutual_like:
        from apps.matches.models import Match
        match = Match.objects.create(
            user1=user,
            user2=target_profile.user
        )
        response_data['match_id'] = str(match.id)
        
        # Envoyer notification push ici
        # send_match_notification(user, target_profile.user)
    
    return Response(response_data, status=200)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def send_dislike(request):
    """
    Endpoint pour envoyer un dislike à un profil.
    
    POST /api/v1/discovery/interactions/dislike/
    
    Body:
        {
            "target_profile_id": "uuid"
        }
    
    Response:
        {
            "result": "dislike_sent",
            "daily_likes_remaining": 49,  // inchangé pour dislike
            "super_likes_remaining": 1
        }
    """
    user = request.user
    target_profile_id = request.data.get('target_profile_id')
    
    if not target_profile_id:
        return Response(
            {'error': 'target_profile_id est requis'},
            status=400
        )
    
    # Créer l'interaction dislike (ne consomme pas de likes)
    try:
        target_profile = Profile.objects.get(id=target_profile_id)
        Interaction.objects.create(
            from_user=user,
            to_user=target_profile.user,
            interaction_type='dislike'
        )
    except Profile.DoesNotExist:
        return Response(
            {'error': 'Profil non trouvé'},
            status=404
        )
    
    # Retourner les compteurs actuels (inchangés par un dislike)
    return Response({
        'result': 'dislike_sent',
        'daily_likes_remaining': DailyLikesService.get_likes_remaining(user),
        'super_likes_remaining': DailyLikesService.get_super_likes_remaining(user)
    }, status=200)
```

### Endpoint de Statut (Optionnel): `apps/discovery/views.py`

```python
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_interaction_status(request):
    """
    Endpoint pour obtenir le statut des interactions quotidiennes.
    
    GET /api/v1/discovery/interactions/status/
    
    Response:
        {
            "daily_likes_remaining": 49,
            "daily_likes_limit": 50,
            "super_likes_remaining": 1,
            "super_likes_limit": 1,
            "is_premium": false,
            "reset_at": "2026-03-24T00:00:00Z"
        }
    """
    user = request.user
    
    return Response({
        'daily_likes_remaining': DailyLikesService.get_likes_remaining(user),
        'daily_likes_limit': DailyLikesService.get_user_daily_limit(user),
        'super_likes_remaining': DailyLikesService.get_super_likes_remaining(user),
        'super_likes_limit': (
            DailyLikesService.PREMIUM_DAILY_SUPER_LIKES_LIMIT 
            if DailyLikesService.is_premium_user(user) 
            else DailyLikesService.FREE_DAILY_SUPER_LIKES_LIMIT
        ),
        'is_premium': DailyLikesService.is_premium_user(user),
        'reset_at': DailyLikesService.get_next_reset_time().isoformat()
    }, status=200)
```

---

## 📊 Impact sur l'Utilisateur

### Impact Positif (Après Correction)
- ✅ Le compteur de likes affiche la valeur correcte (9, 8, 7...)
- ✅ L'utilisateur a une visibilité claire sur ses likes restants
- ✅ L'utilisateur sait quand il a atteint sa limite quotidienne
- ✅ L'expérience utilisateur est fluide et prévisible

### Impact Négatif (Si Non Corrigé)
- ❌ L'utilisateur ne sait pas combien de likes il lui reste
- ❌ L'utilisateur peut penser que l'application ne fonctionne pas
- ❌ Frustration et abandon potentiel de l'application
- ❌ Mauvaise réputation de l'application

### Message Utilisateur

Quand la limite est atteinte, afficher :

```
⚠️ Limite de likes atteinte

Vous avez utilisé vos 50 likes gratuits d'aujourd'hui. 

Vos likes seront réinitialisés à minuit.
 
💎 Vous voulez plus de likes ?
→ Débloquez HIVMeet Premium pour des likes illimités !
[Voir les plans Premium]
```

---

## 🧪 Tests de Validation

### Test 1 : Compteur Initial
```
Préconditions: Nouvel utilisateur ou compteur réinitialisé
Actions: 
  1. Se connecter
  2. Aller sur la page de découverte
  
Résultats attendus:
  ✅ Le compteur affiche "50 likes restants"
  ✅ Aucun profil liké n'a été comptabilisé
```

### Test 2 : Décrémentation du Compteur
```
Préconditions: Compteur à 50
Actions:
  1. Liker un profil
  2. Vérifier le compteur
  
Résultats attendus:
  ✅ Le compteur affiche "49 likes restants"
  ✅ L'indicateur de like a bien été envoyé
```

### Test 3 : Limite Atteinte
```
Préconditions: Compteur à 1
Actions:
  1. Liker un profil
  
Résultats attendus:
  ✅ Le compteur affiche "0 likes restants"
  ✅ Le message "Limite atteinte" s'affiche
  ✅ L'utilisateur ne peut plus liker (bouton désactivé)
```

### Test 4 : Reset Quotidien
```
Préconditions: Compteur à 0 (fin de journée)
Actions:
  1. Attendre minuit (ou simuler via Timezone)
  2. Rafraîchir l'application
  
Résultats attendus:
  ✅ Le compteur affiche "50 likes restants"
  ✅ Les likes sont bien réinitialisés
```

### Test 5 : Vérification API Response
```
Préconditions: Utilisateur connecté
Actions:
  1. Envoyer un like via l'API
  2. Vérifier la réponse JSON
  
Résultats attendus:
  ✅ La réponse contient "daily_likes_remaining": 49
  ✅ La valeur est entre 0 et 50
  ✅ Pas de valeur null ou incohérente
```

### Script de Test Automatisé

```bash
#!/bin/bash
# test_daily_likes_counter.sh

BASE_URL="http://localhost:8000/api/v1"
TOKEN="your_test_token"

echo "=== Test du Compteur de Likes ==="

# Test 1: Vérifier le statut initial
echo "Test 1: Statut initial"
RESPONSE=$(curl -s -H "Authorization: Token $TOKEN" \
  "$BASE_URL/discovery/interactions/status/")
echo "Réponse: $RESPONSE"

# Vérifier que daily_likes_remaining est présent et valide
LIKE_COUNT=$(echo $RESPONSE | jq -r '.daily_likes_remaining')
if [ "$LIKE_COUNT" == "null" ] || [ "$LIKE_COUNT" -gt 50 ]; then
  echo "❌ ERREUR: daily_likes_remaining invalide: $LIKE_COUNT"
  exit 1
fi
echo "✅ daily_likes_remaining = $LIKE_COUNT (valide)"

# Test 2: Envoyer un like et vérifier la décrémentation
echo ""
echo "Test 2: Décrémentation après like"
BEFORE=$LIKE_COUNT

# Envoyer un like (remplacer TARGET_ID par un vrai ID)
LIKE_RESPONSE=$(curl -s -X POST -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_profile_id": "TARGET_PROFILE_ID"}' \
  "$BASE_URL/discovery/interactions/like/")
echo "Réponse like: $LIKE_RESPONSE"

AFTER=$(echo $LIKE_RESPONSE | jq -r '.daily_likes_remaining')
echo "Avant: $BEFORE, Après: $AFTER"

if [ "$AFTER" -eq $((BEFORE - 1)) ]; then
  echo "✅ Compteur décrémenté correctement"
else
  echo "❌ ERREUR: Compteur non décrémenté correctement"
  exit 1
fi

echo ""
echo "=== Tous les tests passent ! ==="
```

---

## ✅ Checklist de Correction

### Backend (À faire par le développeur backend)

- [ ] **Créer le service `DailyLikesService`** dans `apps/discovery/services/`
- [ ] **Implémenter `calculate_daily_likes_remaining()`** avec logique correcte
- [ ] **Modifier `send_like()`** pour retourner `daily_likes_remaining` dans la réponse
- [ ] **Modifier `send_dislike()`** pour retourner `daily_likes_remaining` dans la réponse
- [ ] **Modifier `send_super_like()`** pour retourner `daily_likes_remaining` dans la réponse
- [ ] **Ajouter l'endpoint `GET /discovery/interactions/status/`** (optionnel)
- [ ] **Ajouter des logs de debug** pour faciliter le diagnostic futur
- [ ] **Vérifier la timezone** (doit être UTC)
- [ ] **Tester la logique de reset** à minuit
- [ ] **Déployer les modifications** sur l'environnement de staging

### Frontend (Déjà corrigé)

- [x] **Modifier `discovery_bloc.dart`** pour valider les valeurs du backend
- [x] **Implémenter la décrémentation locale** si le backend retourne une valeur invalide
- [x] **Corriger la valeur initiale** à 50 likes (au lieu de 20)
- [x] **Afficher le compteur** pour tous les utilisateurs gratuits

### Tests à Effectuer

- [ ] **Test manuel**: Vérifier que le compteur affiche 50 au démarrage
- [ ] **Test manuel**: Liker et vérifier que le compteur passe à 49
- [ ] **Test manuel**: Liker plusieurs fois et vérifier la décrémentation
- [ ] **Test manuel**: Vérifier que la limite est bloquante à 0
- [ ] **Test automatisé**: Exécuter le script de test ci-dessus
- [ ] **Test de regression**: Vérifier que les matches fonctionnent toujours

### Surveillance Post-Déploiement

- [ ] **Monitorer les logs** pour détecter d'éventuelles valeurs incohérentes
- [ ] **Vérifier les rapports d'erreur** dans Sentry/Datadog
- [ ] **Recueillir les feedbacks utilisateurs** sur la fonctionnalité

---

## 📝 Notes Additionnelles

### Valeurs de Limites à Respecter

| Tier | Likes/Jour | Super Likes/Jour | Rewinds/Jour |
|------|------------|------------------|--------------|
| Gratuit | **50** | 1 | 0 |
| Premium | Illimité | 5 | 5 |
| Gold | Illimité | 5 | 5 |

### Chemins des Fichiers Backend à Modifier

```
hivmeet_backend/
├── apps/
│   └── discovery/
│       ├── __init__.py
│       ├── models.py              # Ajouter le modèle Interaction si pas existant
│       ├── views.py               # Modifier send_like, send_dislike, send_super_like
│       ├── urls.py                # Ajouter les routes
│       └── services/
│           ├── __init__.py
│           └── likes_service.py    # CRÉER CE FICHIER
└── manage.py
```

### Rotation des Logs

Configurer la rotation des logs pour le debug :

```python
# settings.py
LOGGING = {
    'handlers': {
        'daily_likes_file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': 'logs/daily_likes_debug.log',
            'when': 'midnight',
            'interval': 1,
        },
    },
    'loggers': {
        'discovery.likes': {
            'handlers': ['daily_likes_file'],
            'level': 'INFO',
        },
    },
}
```

---

## 🔗 Références

- Documentation API Frontend: `docs/FRONTEND_MATCHING_API.md`
- Spécifications fonctionnelles: `docs/Spécifications Fonctionnelles Frontend - HIVMeet.txt`
- Modèle de données: `docs/Modèle de Données Frontend - HIVMeet.txt`

---

**Dernière mise à jour**: 23 Mars 2026  
**Créé par**: AI Agent (GitHub Copilot)  
**Pour**: Équipe de Développement HIVMeet Backend
