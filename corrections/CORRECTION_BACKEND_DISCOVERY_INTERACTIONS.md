# Corrections Backend - Discovery Interactions

## Date: 2025-12-31

## Problèmes identifiés

### 1. ❌ Erreur "duplicate key" lors du rewind puis dislike

**Erreur observée:**
```
django.db.utils.IntegrityError: duplicate key value violates unique constraint "unique_active_interaction"
DETAIL: Key (user_id, target_user_id, interaction_type)=(0e5ac2cb-07d8-4160-9f36-90393356f8c0, ab0b4b94-0be8-4a0b-9d6b-59b580b373fa, dislike) already exists.
```

**Scénario qui provoque l'erreur:**
1. L'utilisateur dislike un profil (Steph - `ab0b4b94-0be8-4a0b-9d6b-59b580b373fa`)
2. L'utilisateur fait un rewind (retour en arrière)
3. L'utilisateur essaie de re-disliker le même profil
4. Le backend essaie de créer une nouvelle entrée au lieu de mettre à jour l'existante

**Location de l'erreur:**
- Fichier: `matching/services.py`
- Méthode: `MatchingService.dislike_profile()`
- Ligne: appel à `InteractionHistory.create_or_reactivate()`

**Correction requise:**

Dans `matching/models.py`, la méthode `InteractionHistory.create_or_reactivate()` doit:

```python
@classmethod
def create_or_reactivate(cls, user, target_user, interaction_type, **kwargs):
    """
    Crée une nouvelle interaction ou réactive une interaction existante.
    
    IMPORTANT: Doit gérer le cas où une interaction active existe déjà
    pour éviter la violation de contrainte unique.
    """
    try:
        # Vérifier si une interaction ACTIVE existe déjà
        existing = cls.objects.filter(
            user=user,
            target_user=target_user,
            interaction_type=interaction_type,
            is_active=True
        ).first()
        
        if existing:
            # Mettre à jour l'interaction existante au lieu de créer une nouvelle
            existing.created_at = timezone.now()
            for key, value in kwargs.items():
                setattr(existing, key, value)
            existing.save()
            return existing
        
        # Vérifier si une interaction INACTIVE existe (après rewind)
        inactive = cls.objects.filter(
            user=user,
            target_user=target_user,
            interaction_type=interaction_type,
            is_active=False
        ).first()
        
        if inactive:
            # Réactiver l'interaction existante
            inactive.is_active = True
            inactive.created_at = timezone.now()
            for key, value in kwargs.items():
                setattr(inactive, key, value)
            inactive.save()
            return inactive
        
        # Créer une nouvelle interaction
        return cls.objects.create(
            user=user,
            target_user=target_user,
            interaction_type=interaction_type,
            **kwargs
        )
        
    except IntegrityError:
        # En cas d'erreur de contrainte unique, récupérer l'interaction existante
        existing = cls.objects.get(
            user=user,
            target_user=target_user,
            interaction_type=interaction_type,
            is_active=True
        )
        # Mettre à jour la date
        existing.created_at = timezone.now()
        existing.save()
        return existing
```

**Alternative simple:**
Si la logique ci-dessus est trop complexe, une solution simple serait de:
1. Désactiver l'interaction existante avant d'en créer une nouvelle
2. Ou utiliser `get_or_create()` avec `update_or_create()`

```python
# Dans matching/services.py, méthode dislike_profile()
interaction, created = InteractionHistory.objects.update_or_create(
    user=user,
    target_user=target_user,
    interaction_type='dislike',
    defaults={
        'is_active': True,
        'created_at': timezone.now(),
    }
)
```

### 2. ⚠️ Compteur de likes non renvoyé dans la réponse du dislike

**Problème:**
Le endpoint `/api/v1/discovery/interactions/dislike` ne renvoie pas les compteurs de likes restants comme le fait l'endpoint `like` et `superlike`.

**Logs backend actuels:**
```
INFO 2025-12-31 17:36:42,161 basehttp 6876 15612 "POST /api/v1/discovery/interactions/dislike HTTP/1.1" 201 21
```

La réponse semble être minimale (21 bytes seulement).

**Réponse actuelle (supposée):**
```json
{
  "status": "disliked"
}
```

**Réponse attendue:**
```json
{
  "status": "disliked",
  "daily_likes_remaining": 9,
  "super_likes_remaining": 5
}
```

**Correction requise:**

Dans `matching/views_discovery.py`, méthode `dislike_profile()`:

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dislike_profile(request):
    """Dislike un profil"""
    target_user_id = request.data.get('target_user_id')
    
    if not target_user_id:
        return Response(
            {'error': 'target_user_id requis'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        target_user = User.objects.get(id=target_user_id)
    except User.DoesNotExist:
        return Response(
            {'error': 'Utilisateur cible introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Effectuer le dislike
    success, error_msg = MatchingService.dislike_profile(
        user=request.user,
        target_user=target_user
    )
    
    if not success:
        return Response(
            {'error': error_msg},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Récupérer les compteurs mis à jour
    daily_limit = MatchingService.get_daily_like_limit(request.user)
    super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
    
    return Response({
        'status': 'disliked',
        'daily_likes_remaining': daily_limit.get('remaining_likes', 0),
        'super_likes_remaining': super_likes_remaining
    }, status=status.HTTP_201_CREATED)
```

**Note importante:**
Le dislike ne devrait PAS décrémenter le compteur de likes quotidiens. Seuls les likes (et super-likes) devraient décrémenter ce compteur. Le dislike est gratuit et illimité.

Cependant, il est utile de renvoyer le compteur actuel pour que le frontend puisse afficher la bonne valeur à l'utilisateur.

### 4. ❌ Le backend renvoie `daily_likes_remaining: 999` au lieu de la vraie valeur

**Problème observé dans les logs:**
```
INFO 2025-12-31 18:13:41,678 basehttp "POST /api/v1/discovery/interactions/like HTTP/1.1" 201 72
```

Après un like, le frontend reçoit:
```
DailyLikeLimit(999, 50, 2026-01-01 17:13:34.606557)
```

**Cause:**
Le backend renvoie une valeur incorrecte (999) pour `daily_likes_remaining`. Cela peut être dû à :
1. Une valeur de test/mock codée en dur dans le backend
2. Un calcul incorrect du nombre de likes restants
3. Un problème avec la récupération des limites depuis la base de données

**Correction requise dans `matching/views_discovery.py`:**

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_profile(request):
    """Like un profil"""
    target_user_id = request.data.get('target_user_id')
    
    if not target_user_id:
        return Response(
            {'error': 'target_user_id requis'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        target_user = User.objects.get(id=target_user_id)
    except User.DoesNotExist:
        return Response(
            {'error': 'Utilisateur cible introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Effectuer le like
    result, error_msg = MatchingService.like_profile(
        user=request.user,
        target_user=target_user
    )
    
    if not result:
        return Response(
            {'error': error_msg},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # IMPORTANT: Récupérer les compteurs RÉELS depuis la base de données
    # Ne PAS utiliser de valeurs codées en dur comme 999
    daily_limit = MatchingService.get_daily_like_limit(request.user)
    super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
    
    # S'assurer que les valeurs sont correctes
    remaining_likes = daily_limit.get('remaining_likes', 0)
    
    # Debug: logger les valeurs
    logger.info(f"✅ Like successful - Remaining likes: {remaining_likes}")
    
    return Response({
        'result': 'match' if result.get('is_match') else 'like_sent',
        'match_id': result.get('match_id'),
        'daily_likes_remaining': remaining_likes,  # Valeur RÉELLE
        'super_likes_remaining': super_likes_remaining
    }, status=status.HTTP_201_CREATED)
```

**Vérification à effectuer:**
1. Vérifier que `MatchingService.get_daily_like_limit()` retourne les vraies valeurs
2. S'assurer qu'il n'y a pas de valeur mock/test (999) dans le code
3. Vérifier que les likes sont bien enregistrés dans la base de données
4. Confirmer que le compteur se décrémente après chaque like

### 3. 📋 Résumé des modifications nécessaires

**Fichiers backend à modifier:**

1. **`matching/models.py`**
   - Méthode: `InteractionHistory.create_or_reactivate()`
   - Action: Ajouter la gestion du cas où une interaction active existe déjà

2. **`matching/views_discovery.py`**
   - Méthode: `dislike_profile()` 
   - Action: Ajouter les compteurs `daily_likes_remaining` et `super_likes_remaining` dans la réponse
   - Méthode: `like_profile()`
   - Action: S'assurer de retourner la VRAIE valeur de `daily_likes_remaining`, pas 999

3. **`matching/serializers.py`** ⚠️ **NOUVEAU PROBLÈME**
   - Problème: `ImportError: cannot import name 'DiscoveryProfileSerializer' from 'profiles.serializers'`
   - Contexte: Erreur lors de l'accès à la page des profils likés (`/api/v1/discovery/interactions/my-likes`)
   - Action requise: Créer le serializer `DiscoveryProfileSerializer` dans `profiles/serializers.py` OU modifier `matching/serializers.py` pour utiliser un serializer existant

**Erreur complète:**
```python
File "matching/serializers.py", line 414, in get_profile
    from profiles.serializers import DiscoveryProfileSerializer
ImportError: cannot import name 'DiscoveryProfileSerializer' from 'profiles.serializers'
```

**Solution option 1: Créer le serializer manquant**

Dans `profiles/serializers.py`:
```python
class DiscoveryProfileSerializer(serializers.ModelSerializer):
    """
    Serializer pour les profils dans la découverte.
    Version simplifiée pour l'affichage dans les listes.
    """
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    display_name = serializers.CharField(source='user.display_name', read_only=True)
    photos = serializers.SerializerMethodField()
    interests = serializers.ListField(child=serializers.CharField(), required=False)
    relationship_types_sought = serializers.ListField(
        child=serializers.CharField(), 
        required=False
    )
    
    class Meta:
        model = Profile
        fields = [
            'user_id', 
            'display_name', 
            'age', 
            'bio', 
            'city', 
            'country',
            'photos',
            'interests',
            'relationship_types_sought',
            'is_verified',
            'is_online',
            'distance_km'
        ]
        read_only_fields = fields
    
    def get_photos(self, obj):
        """Retourne la liste des URLs des photos"""
        photos = []
        if obj.main_photo:
            photos.append({
                'photo_url': obj.main_photo.url if hasattr(obj.main_photo, 'url') else str(obj.main_photo),
                'is_main': True
            })
        # Ajouter les autres photos si disponibles
        return photos
```

**Solution option 2: Utiliser un serializer existant**

Dans `matching/serializers.py`, ligne 414, modifier:
```python
# Au lieu de:
from profiles.serializers import DiscoveryProfileSerializer

# Utiliser:
from profiles.serializers import ProfileSerializer  # ou un autre serializer existant

# Puis dans get_profile():
def get_profile(self, obj):
    return ProfileSerializer(obj.target_user.profile).data
```

2. **`matching/views_discovery.py`**
   - Méthode: `dislike_profile()`
   - Action: Ajouter les compteurs `daily_likes_remaining` et `super_likes_remaining` dans la réponse

**Tests à effectuer après correction:**

1. ✅ Dislike un profil → vérifier que le compteur est renvoyé
2. ✅ Like un profil → vérifier que le compteur se décrémente CORRECTEMENT (pas 999)
3. ✅ Dislike un profil → Rewind → Re-dislike le même profil → vérifier qu'il n'y a pas d'erreur
4. ✅ Like un profil → Rewind → Re-like le même profil → vérifier qu'il n'y a pas d'erreur
5. ✅ Vérifier que le dislike ne décrémente pas le compteur de likes
6. ✅ Aller dans la page des matches → Profils likés → vérifier qu'il n'y a pas d'erreur ImportError
7. ✅ Vérifier que le compteur initial est correct (10 likes, pas 999)

## Comportement attendu du compteur après rewind

**Question de l'utilisateur:** Quand je like puis rewind puis dislike, le compteur reste figé. Est-ce normal ?

**Réponse:** **OUI, c'est le comportement attendu** selon deux logiques possibles :

### Option 1: Le like est consommé définitivement
- Quand un utilisateur like un profil, il consomme 1 de ses likes quotidiens
- Même si l'utilisateur fait rewind (annule son action), le like a déjà été comptabilisé
- Le rewind permet de changer d'avis, mais ne "rembourse" pas le like consommé
- C'est une limitation voulue pour éviter les abus (liker/rewind en boucle)

### Option 2: Le rewind devrait restaurer le compteur (alternative)
Si vous souhaitez que le rewind restaure le compteur, il faudrait :
1. Incrémenter `daily_likes_remaining` lors du rewind d'un like
2. Ne décrémenter le compteur qu'après confirmation définitive de l'action

**Recommandation:** Garder l'option 1 (le like reste consommé) car :
- C'est plus simple à implémenter
- C'est cohérent avec la plupart des apps de dating (Tinder, Bumble, etc.)
- Cela évite les abus du système de rewind
- Le rewind est une fonctionnalité premium donc limitée

**Si vous voulez l'option 2**, il faut modifier le backend pour:
```python
# Dans matching/services.py, méthode rewind_last_swipe()
def rewind_last_swipe(user):
    # ... code existant ...
    
    # Si l'interaction annulée était un like, restaurer le compteur
    if last_interaction.interaction_type == 'like':
        # Incrémenter le compteur de likes quotidiens
        daily_usage = DailyLikeUsage.objects.get_or_create(
            user=user,
            date=timezone.now().date()
        )[0]
        daily_usage.likes_sent = max(0, daily_usage.likes_sent - 1)
        daily_usage.save()
    
    # ... reste du code ...
```

## Modifications Frontend effectuées

✅ **1. Mise à jour du type de retour de `dislikeProfile`**
- Fichier: `lib/domain/repositories/match_repository.dart`
- Changement: `Future<Either<Failure, void>>` → `Future<Either<Failure, SwipeResult>>`

✅ **2. Mise à jour du use case `DislikeProfile`**
- Fichier: `lib/domain/usecases/match/dislike_profile.dart`
- Changement: `UseCase<void, ...>` → `UseCase<SwipeResult, ...>`

✅ **3. Mise à jour de l'implémentation du repository**
- Fichier: `lib/data/repositories/match_repository_impl.dart`
- Action: Parser la réponse du backend pour extraire `daily_likes_remaining` et `super_likes_remaining`

✅ **4. Mise à jour du bloc Discovery**
- Fichier: `lib/presentation/blocs/discovery/discovery_bloc.dart`
- Action: Utiliser le `SwipeResult` retourné par le dislike au lieu de créer un objet vide

✅ **5. Mise à jour du mock repository**
- Fichier: `lib/data/repositories/match_repository_mock.dart`
- Action: Retourner un `SwipeResult` au lieu de `void`

## Impact

**Avant corrections:**
- ❌ Le compteur de likes ne se met pas à jour après un dislike
- ❌ Erreur 500 quand on fait rewind puis dislike sur le même profil
- ❌ Le frontend ne reçoit pas les compteurs après un dislike

**Après corrections:**
- ✅ Le compteur de likes s'affiche correctement (même s'il ne change pas pour un dislike)
- ✅ Pas d'erreur lors du rewind puis dislike
- ✅ Le frontend reçoit toujours les compteurs à jour
- ✅ Cohérence entre like, dislike et superlike dans les réponses

## Validation

Pour valider que les corrections fonctionnent:

1. Exécuter l'application
2. Liker plusieurs profils et observer le compteur se décrémenter
3. Disliker un profil et observer que le compteur reste affiché
4. Faire rewind puis disliker à nouveau le même profil
5. Vérifier qu'il n'y a pas d'erreur 500 dans les logs backend

## Références

- **Frontend corrections:** Ce document
- **Backend error logs:** Voir les logs du userRequest initial
- **Contrainte unique:** `unique_active_interaction` sur `(user_id, target_user_id, interaction_type)`
