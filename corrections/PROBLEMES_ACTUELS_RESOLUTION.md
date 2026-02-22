# Problèmes actuels et résolutions - HIVMeet Discovery

**Date:** 2025-12-31
**Statut:** Corrections backend requises

---

## 🔴 Problème 1: Compteur de likes affiche 999 au lieu de la vraie valeur

### Symptôme
Après avoir liké un profil, le compteur passe de 10 à 999 au lieu de se décrémenter à 9.

**Logs observés:**
```
DailyLikeLimit(10, 50, 2026-01-01 17:13:34.606557)  // Avant le like
DailyLikeLimit(999, 50, 2026-01-01 17:13:34.606557) // Après le like ❌
```

### Cause
Le backend renvoie une valeur incorrecte (probablement une valeur de test/mock codée en dur).

### Solution backend requise

**Fichier:** `matching/views_discovery.py`
**Méthode:** `like_profile()`

```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_profile(request):
    target_user_id = request.data.get('target_user_id')
    
    # ... validation ...
    
    # Effectuer le like
    result, error_msg = MatchingService.like_profile(
        user=request.user,
        target_user=target_user
    )
    
    # IMPORTANT: Récupérer les compteurs RÉELS depuis la base de données
    daily_limit = MatchingService.get_daily_like_limit(request.user)
    super_likes_remaining = MatchingService.get_super_likes_remaining(request.user)
    
    remaining_likes = daily_limit.get('remaining_likes', 0)
    
    # ⚠️ NE PAS mettre de valeur en dur comme 999
    # ⚠️ S'assurer que get_daily_like_limit() retourne la vraie valeur
    
    return Response({
        'result': 'match' if result.get('is_match') else 'like_sent',
        'match_id': result.get('match_id'),
        'daily_likes_remaining': remaining_likes,  # ← Valeur RÉELLE
        'super_likes_remaining': super_likes_remaining
    }, status=status.HTTP_201_CREATED)
```

**Vérifications à faire:**
1. Vérifier qu'il n'y a pas de `daily_likes_remaining: 999` codé en dur
2. Vérifier que `MatchingService.get_daily_like_limit()` interroge vraiment la BDD
3. Vérifier que les likes sont bien enregistrés et comptabilisés
4. Tester: Like → Vérifier que le compteur se décrémente de 1

---

## 🟡 Problème 2: Compteur figé après like → rewind → dislike

### Symptôme
1. Je like un profil (compteur passe de 10 à 999)
2. Je fais rewind (retour en arrière)
3. Je dislike le même profil
4. Le compteur reste à 999 (ne change pas)

### Est-ce un bug ?

**NON, c'est le comportement attendu** pour les raisons suivantes:

1. **Le like a été consommé**: Quand vous likez un profil, vous consommez 1 de vos likes quotidiens
2. **Le rewind ne "rembourse" pas**: Le rewind permet de changer d'avis, mais ne restaure pas le like consommé
3. **Cohérence avec les apps de dating**: C'est le comportement standard (Tinder, Bumble, etc.)
4. **Évite les abus**: Empêche de liker/rewind en boucle pour "espionner" les profils

### Si vous voulez changer ce comportement

Il faudrait modifier le backend pour incrémenter le compteur lors du rewind d'un like :

```python
# Dans matching/services.py, méthode rewind_last_swipe()
def rewind_last_swipe(user):
    last_interaction = get_last_interaction(user)
    
    # Si l'interaction annulée était un like, restaurer le compteur
    if last_interaction.interaction_type == 'like':
        daily_usage = DailyLikeUsage.objects.get_or_create(
            user=user,
            date=timezone.now().date()
        )[0]
        daily_usage.likes_sent = max(0, daily_usage.likes_sent - 1)
        daily_usage.save()
    
    # Désactiver l'interaction
    last_interaction.is_active = False
    last_interaction.save()
```

**Recommandation:** Garder le comportement actuel (like reste consommé).

---

## 🔴 Problème 3: Erreur lors de l'accès à la page "Profils likés"

### Symptôme
Quand on clique sur "Mes likes" dans la page des matches, on obtient une erreur 500.

**Logs backend:**
```python
ImportError: cannot import name 'DiscoveryProfileSerializer' from 'profiles.serializers'
File "matching/serializers.py", line 414, in get_profile
    from profiles.serializers import DiscoveryProfileSerializer
```

### Cause
Le serializer `DiscoveryProfileSerializer` n'existe pas dans `profiles/serializers.py`.

### Solution backend requise

**Option 1: Créer le serializer manquant** (recommandé)

**Fichier:** `profiles/serializers.py`

```python
class DiscoveryProfileSerializer(serializers.ModelSerializer):
    """
    Serializer pour les profils dans la découverte et historique.
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
    distance_km = serializers.SerializerMethodField()
    
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
                'photo_url': self.get_photo_url(obj.main_photo),
                'is_main': True
            })
        return photos
    
    def get_photo_url(self, photo):
        """Retourne l'URL complète de la photo"""
        if hasattr(photo, 'url'):
            return photo.url
        return str(photo)
    
    def get_distance_km(self, obj):
        """Calcule la distance si les coordonnées sont disponibles"""
        # Implémenter le calcul de distance si nécessaire
        return None
```

**Option 2: Utiliser un serializer existant**

**Fichier:** `matching/serializers.py` (ligne ~414)

```python
# Modifier l'import
from profiles.serializers import ProfileSerializer  # Au lieu de DiscoveryProfileSerializer

# Puis dans la méthode get_profile()
def get_profile(self, obj):
    if not obj.target_user or not hasattr(obj.target_user, 'profile'):
        return None
    return ProfileSerializer(obj.target_user.profile).data
```

---

## ✅ Corrections frontend déjà effectuées

1. ✅ Modification de `dislikeProfile()` pour retourner un `SwipeResult`
2. ✅ Mise à jour du BLoC pour utiliser le `SwipeResult` du dislike
3. ✅ Le frontend parse correctement `daily_likes_remaining` du backend
4. ✅ Le frontend met à jour le compteur après chaque swipe (like/dislike)

---

## 📋 Checklist de validation

Après avoir appliqué les corrections backend, tester:

- [ ] **Like un profil** → Le compteur passe de 10 à 9 (pas 999)
- [ ] **Like 3 profils** → Le compteur passe de 10 à 7
- [ ] **Dislike un profil** → Le compteur ne change pas
- [ ] **Like → Rewind → Dislike** → Pas d'erreur backend (duplicate key)
- [ ] **Aller dans Matches → Profils likés** → Pas d'erreur ImportError
- [ ] **Vérifier les logs backend** → Pas de valeur 999 dans les réponses

---

## 🔗 Fichiers de référence

- [CORRECTION_BACKEND_DISCOVERY_INTERACTIONS.md](./CORRECTION_BACKEND_DISCOVERY_INTERACTIONS.md) - Documentation complète des corrections backend
- Frontend: Corrections déjà appliquées (voir commits précédents)

---

## 📞 Questions ouvertes

1. **Comportement du rewind:** Voulez-vous que le rewind restaure le compteur de likes ?
   - ✅ **Recommandé:** Non, le like reste consommé (comportement standard)
   - ❌ Oui, restaurer le compteur (nécessite modifications backend)

2. **Valeur 999:** D'où vient cette valeur dans le backend ?
   - Vérifier `MatchingService.get_daily_like_limit()`
   - Vérifier s'il y a des valeurs mock/test
   - Vérifier les migrations de la base de données
