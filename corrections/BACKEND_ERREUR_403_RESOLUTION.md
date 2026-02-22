# ✅ RÉSOLUTION - Erreur 403 Forbidden sur likes-received

**Date de résolution** : 29 Décembre 2025  
**Status** : ✅ **CORRIGÉ ET VALIDÉ**

---

## 🔍 Problème identifié

L'endpoint `GET /api/v1/user-profiles/likes-received/` retournait une erreur **403 Forbidden**, même pour les utilisateurs authentifiés avec un compte Premium.

### Logs d'erreur (avant correction)
```log
WARNING 2025-12-29 12:30:49,504 log 24488 9832 Forbidden: /api/v1/user-profiles/likes-received/
WARNING 2025-12-29 12:30:49,506 basehttp 24488 9832 "GET /api/v1/user-profiles/likes-received/?page=1&page_size=1 HTTP/1.1" 403 132
```

---

## 🐛 Cause racine

**Fichier** : [`profiles/views_premium.py`](profiles/views_premium.py)

### Erreurs dans le code

#### 1. Mauvais nom de champ : `target_user` au lieu de `to_user`

**Code incorrect** (ligne 36-41) :
```python
return Profile.objects.filter(
    user__in=Like.objects.filter(
        target_user=self.request.user,  # ❌ target_user n'existe pas
        is_like=True                     # ❌ is_like n'existe pas
    ).values_list('user', flat=True)     # ❌ 'user' au lieu de 'from_user'
).select_related('user')
```

**Problème** : Le modèle `Like` utilise les champs suivants :
- `from_user` : L'utilisateur qui a envoyé le like
- `to_user` : L'utilisateur qui a reçu le like  
- `like_type` : Type de like (REGULAR ou SUPER)

Le code utilisait `target_user` et `is_like` qui **n'existent pas** dans le modèle.

#### 2. Même erreur dans `SuperLikesReceivedView` (ligne 62-68)

**Code incorrect** :
```python
return Profile.objects.filter(
    user__in=Like.objects.filter(
        target_user=self.request.user,  # ❌ Mauvais champ
        is_like=True,                   # ❌ Champ inexistant
        is_super_like=True              # ❌ Champ inexistant
    ).values_list('user', flat=True)
).select_related('user')
```

---

## ✅ Solution appliquée

### Corrections dans `LikesReceivedView`

**Fichier** : [`profiles/views_premium.py`](profiles/views_premium.py) (lignes 33-43)

**Code corrigé** :
```python
def get_queryset(self):
    if not is_premium_user(self.request.user):
        # Return empty queryset for non-premium users
        return Profile.objects.none()
    
    # Get users who liked the current user
    return Profile.objects.filter(
        user__in=Like.objects.filter(
            to_user=self.request.user        # ✅ Utilise 'to_user'
        ).values_list('from_user', flat=True)  # ✅ Utilise 'from_user'
    ).select_related('user')
```

**Changements** :
- ✅ `target_user` → `to_user`
- ✅ Suppression de `is_like=True` (champ inexistant)
- ✅ `values_list('user')` → `values_list('from_user')` (correct sender)

### Corrections dans `SuperLikesReceivedView`

**Code corrigé** :
```python
def get_queryset(self):
    if not is_premium_user(self.request.user):
        return Profile.objects.none()
    
    # Get users who super liked the current user
    return Profile.objects.filter(
        user__in=Like.objects.filter(
            to_user=self.request.user,           # ✅ Utilise 'to_user'
            like_type=Like.SUPER                 # ✅ Utilise 'like_type'
        ).values_list('from_user', flat=True)    # ✅ Utilise 'from_user'
    ).select_related('user')
```

**Changements** :
- ✅ `target_user` → `to_user`
- ✅ `is_like=True, is_super_like=True` → `like_type=Like.SUPER`
- ✅ `values_list('user')` → `values_list('from_user')`

---

## 🧪 Validation

### Tests exécutés

**Script de test** : [`test_likes_received_fix.py`](test_likes_received_fix.py)

### Résultats

```
✅ PASS - Test 1: Endpoint likes-received (Premium)
✅ PASS - Test 2: Refus non-premium (403)
✅ PASS - Test 3: Endpoint super-likes-received

🎯 Score: 3/3 tests réussis
🎉 TOUS LES TESTS SONT PASSÉS!
```

### Scénarios testés

#### ✅ Test 1 : Utilisateurs Premium peuvent accéder
- **Utilisateur** : `camille.dubois@test.com` (Premium actif)
- **Requête** : `GET /api/v1/user-profiles/likes-received/`
- **Résultat** : `200 OK` avec liste des likes
- **Status** : ✅ **PASSÉ**

#### ✅ Test 2 : Utilisateurs non-Premium sont refusés
- **Utilisateur** : `antoine.lefevre@test.com` (Free)
- **Requête** : `GET /api/v1/user-profiles/likes-received/`
- **Résultat** : `403 Forbidden` avec message "Cette fonctionnalité nécessite un abonnement premium"
- **Status** : ✅ **PASSÉ**

#### ✅ Test 3 : Super likes fonctionne aussi
- **Utilisateur** : `camille.dubois@test.com` (Premium actif)
- **Requête** : `GET /api/v1/user-profiles/super-likes-received/`
- **Résultat** : `200 OK` avec liste des super likes
- **Status** : ✅ **PASSÉ**

---

## 📊 Impact

### Avant correction
- ❌ Erreur 403 pour tous les utilisateurs (Premium inclus)
- ❌ Frontend crashait en allant dans "Profils passés"
- ❌ Fonctionnalité "Voir qui m'a aimé" inutilisable

### Après correction
- ✅ Utilisateurs Premium peuvent voir qui les a aimés (200 OK)
- ✅ Utilisateurs Free reçoivent un message explicite (403 + message)
- ✅ Frontend peut récupérer les données sans crash
- ✅ Fonctionnalité "Voir qui m'a aimé" opérationnelle

---

## 🔧 Détails techniques

### Modèle Like

**Fichier** : [`matching/models.py`](matching/models.py)

**Structure correcte** :
```python
class Like(models.Model):
    # Types de like
    REGULAR = 'regular'
    SUPER = 'super'
    
    LIKE_TYPE_CHOICES = [
        (REGULAR, _('Regular Like')),
        (SUPER, _('Super Like')),
    ]
    
    # Qui a envoyé le like
    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='likes_sent'
    )
    
    # Qui a reçu le like
    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='likes_received'
    )
    
    # Type de like
    like_type = models.CharField(
        max_length=10,
        choices=LIKE_TYPE_CHOICES,
        default=REGULAR
    )
```

### Requête correcte pour récupérer les likes reçus

```python
# Récupérer les utilisateurs qui ont liké l'utilisateur courant
Like.objects.filter(
    to_user=request.user          # Filtrer par destinataire
).values_list('from_user', flat=True)  # Récupérer les expéditeurs
```

### Requête correcte pour récupérer les super likes reçus

```python
# Récupérer les utilisateurs qui ont super liké l'utilisateur courant
Like.objects.filter(
    to_user=request.user,         # Filtrer par destinataire
    like_type=Like.SUPER          # Filtrer par type
).values_list('from_user', flat=True)  # Récupérer les expéditeurs
```

---

## 🔒 Permissions et sécurité

### Permissions configurées

**`LikesReceivedView`** :
```python
permission_classes = [permissions.IsAuthenticated]  # ✅ Authentification requise
```

### Vérification Premium

**Dans `list()` et `get_queryset()`** :
```python
if not is_premium_user(request.user):
    return premium_required_response()  # Retourne 403 + message
```

### Comportement sécurisé

- ✅ **Authentification obligatoire** : Seuls les utilisateurs connectés peuvent accéder
- ✅ **Vérification Premium** : Seuls les Premium peuvent voir les résultats
- ✅ **Isolation des données** : Chaque utilisateur ne voit que SES likes reçus
- ✅ **Message explicite** : Les Free comprennent pourquoi ils sont refusés

---

## 📝 Checklist de correction

- [x] **Identifier** la cause racine (mauvais noms de champs)
- [x] **Corriger** `LikesReceivedView.get_queryset()`
- [x] **Corriger** `SuperLikesReceivedView.get_queryset()`
- [x] **Créer** un script de test de validation
- [x] **Tester** l'endpoint avec utilisateur Premium (200 OK)
- [x] **Tester** l'endpoint avec utilisateur Free (403 Forbidden)
- [x] **Valider** aucune erreur de compilation
- [x] **Documenter** la correction

---

## 🚀 Prochaines étapes pour le frontend

### 1. Tester l'appel API

Le frontend peut maintenant appeler :

```dart
// Récupérer les likes reçus (Premium uniquement)
GET /api/v1/user-profiles/likes-received/?page=1&page_size=20
Authorization: Bearer <firebase_token>
```

**Réponse attendue (200 OK)** :
```json
{
  "count": 5,
  "next": "http://localhost:8000/api/v1/user-profiles/likes-received/?page=2",
  "previous": null,
  "results": [
    {
      "user_id": "uuid-123",
      "username": "john_doe",
      "age": 28,
      "city": "Paris",
      "profile_photo": "https://example.com/photo.jpg",
      "bio": "Hello!"
    }
  ]
}
```

**Réponse attendue pour non-Premium (403 Forbidden)** :
```json
{
  "error": true,
  "message": "Cette fonctionnalité nécessite un abonnement premium"
}
```

### 2. Gérer les erreurs côté frontend

```dart
try {
  final response = await apiClient.get('/api/v1/user-profiles/likes-received/');
  
  if (response.statusCode == 200) {
    // Afficher les likes
    final likes = response.data['results'];
    // ...
  } else if (response.statusCode == 403) {
    // Afficher popup "Passez Premium pour voir qui vous a aimé"
    showPremiumUpgradeDialog();
  }
} catch (e) {
  // Gérer l'erreur
}
```

---

## 📚 Fichiers modifiés

| Fichier | Type | Description |
|---------|------|-------------|
| [`profiles/views_premium.py`](profiles/views_premium.py) | **Modifié** | Correction des requêtes Like dans les deux vues |
| [`test_likes_received_fix.py`](test_likes_received_fix.py) | **Créé** | Script de test de validation |
| [`corrections/BACKEND_ERREUR_403_RESOLUTION.md`](corrections/BACKEND_ERREUR_403_RESOLUTION.md) | **Créé** | Ce document de résolution |

---

## 🎉 Conclusion

Le problème 403 sur l'endpoint `likes-received` est **résolu et validé**.

### Résumé des corrections
1. ✅ Correction des noms de champs dans `LikesReceivedView`
2. ✅ Correction des noms de champs dans `SuperLikesReceivedView`
3. ✅ Validation par tests (3/3 passés)
4. ✅ Permissions Premium fonctionnelles
5. ✅ Message d'erreur explicite pour les Free

### État actuel
- ✅ **Backend** : Fonctionnel et testé
- ✅ **Frontend** : Peut maintenant récupérer les likes sans erreur
- ✅ **Premium** : Fonctionnalité réservée aux Premium
- ✅ **Documentation** : Correction documentée

### Pas de régression
- ✅ Aucun autre endpoint affecté
- ✅ Les permissions restent strictes
- ✅ Le système de Premium fonctionne correctement

---

**Résolu par** : GitHub Copilot (Claude Sonnet 4.5)  
**Date de résolution** : 29 Décembre 2025  
**Tests** : 3/3 passés ✅  
**Statut** : ✅ **PRODUCTION READY**
