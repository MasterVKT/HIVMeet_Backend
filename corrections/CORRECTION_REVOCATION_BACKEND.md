# 🔧 Correction Backend - Profils Révoqués dans la Découverte

## 📋 Problème Identifié

Lorsqu'un utilisateur annule un like ou un pass (révocation), le profil **ne retourne PAS dans la page de découverte** comme prévu.

### Analyse des Logs Backend

```
INFO services 🚫 Excluding 28 profiles:
INFO services    - Active interactions (is_revoked=False): 14
INFO services    - Legacy likes: 14  ← ⚠️ PROBLÈME ICI
INFO services    - Legacy dislikes: 13  ← ⚠️ PROBLÈME ICI
```

**Le problème** : Le backend exclut **TOUS** les profils qui ont déjà eu une interaction (même révoquée) dans les "Legacy likes" et "Legacy dislikes".

**Comportement attendu** : Le backend devrait **UNIQUEMENT** exclure les interactions **actives** (`is_revoked=False`), et **PAS** les interactions révoquées (`is_revoked=True`).

---

## 🎯 Solution Requise

### Fichier Backend à Modifier

Le fichier exact n'est pas accessible depuis ce workspace, mais d'après les logs, il s'agit de **`services.py`** dans le backend Django, probablement dans :
- `hivmeet_backend/discovery/services.py` ou
- `hivmeet_backend/matching/services.py`

### Code à Corriger

Recherchez la fonction `get_recommendations()` qui contient cette logique d'exclusion :

```python
# ❌ CODE ACTUEL (INCORRECT)
# Exclut TOUS les likes, même révoqués
legacy_likes = UserInteraction.objects.filter(
    user=user,
    interaction_type='like'
).values_list('target_user_id', flat=True)

legacy_dislikes = UserInteraction.objects.filter(
    user=user,
    interaction_type='dislike'
).values_list('target_user_id', flat=True)

# Exclut tous ces profils
excluded_ids = list(active_interactions) + list(legacy_likes) + list(legacy_dislikes)
```

```python
# ✅ CODE CORRIGÉ (CORRECT)
# N'exclut que les interactions ACTIVES (non révoquées)
# Les interactions révoquées sont déjà dans active_interactions avec is_revoked=False
# On ne devrait PAS avoir de "Legacy likes/dislikes" car toutes les interactions
# sont gérées via le nouveau système Interaction avec is_revoked

# Récupérer uniquement les interactions actives
active_interactions = Interaction.objects.filter(
    user=user,
    is_revoked=False
).values_list('target_user__id', flat=True)

# ⚠️ SUPPRIMER COMPLÈTEMENT les requêtes "legacy_likes" et "legacy_dislikes"
# OU les filtrer pour exclure is_revoked=True

# Si vous utilisez encore l'ancien système UserInteraction:
legacy_likes = UserInteraction.objects.filter(
    user=user,
    interaction_type='like',
    is_revoked=False  # ← AJOUTER CETTE CONDITION
).values_list('target_user_id', flat=True)

legacy_dislikes = UserInteraction.objects.filter(
    user=user,
    interaction_type='dislike',
    is_revoked=False  # ← AJOUTER CETTE CONDITION
).values_list('target_user_id', flat=True)

excluded_ids = list(active_interactions) + list(legacy_likes) + list(legacy_dislikes)
```

---

## ✅ Vérification

Après la modification, les logs devraient afficher :

```
INFO services 🚫 Excluding X profiles:
INFO services    - Active interactions (is_revoked=False): 14
INFO services    - Legacy likes: 0  ← Devrait être 0 ou diminuer après révocation
INFO services    - Legacy dislikes: 0  ← Devrait être 0 ou diminuer après révocation
```

Et lorsqu'un utilisateur révoque une interaction :

```
INFO views_history ✅ Interaction xxx revoked successfully
```

Le profil devrait :
1. ✅ Être marqué `is_revoked=True` dans la base de données
2. ✅ Ne plus apparaître dans "Active interactions"
3. ✅ **Réapparaître dans la découverte** lors du prochain appel à `/api/v1/discovery/profiles`

---

## 🔍 Code de Test

Pour vérifier que la correction fonctionne, testez ce scénario :

```python
# 1. L'utilisateur A like l'utilisateur B
POST /api/v1/discovery/interactions/like
{
  "target_user_id": "user_b_id"
}

# 2. Vérifier que B n'apparaît plus dans la découverte de A
GET /api/v1/discovery/profiles
# ✅ user_b ne doit PAS être dans les résultats

# 3. A révoque le like
POST /api/v1/discovery/interactions/{interaction_id}/revoke

# 4. Vérifier que B réapparaît dans la découverte de A
GET /api/v1/discovery/profiles
# ✅ user_b DOIT être dans les résultats
```

---

## 📝 Notes Importantes

### Migration de Données

Si vous avez des anciennes interactions dans la table `UserInteraction` qui n'ont pas le champ `is_revoked`, vous devrez peut-être :

1. **Ajouter le champ `is_revoked`** à `UserInteraction` si absent :
```python
# models.py
class UserInteraction(models.Model):
    # ... autres champs
    is_revoked = models.BooleanField(default=False)
```

2. **Créer une migration** :
```bash
python manage.py makemigrations
python manage.py migrate
```

### Alternative : Utiliser Uniquement le Nouveau Système

Si vous avez complètement migré vers le modèle `Interaction` avec `is_revoked`, vous pouvez **supprimer complètement** les requêtes "legacy_likes" et "legacy_dislikes" :

```python
# ✅ VERSION SIMPLIFIÉE (Si migration complète)
active_interactions = Interaction.objects.filter(
    user=user,
    is_revoked=False
).values_list('target_user__id', flat=True)

excluded_ids = list(active_interactions)
# Plus besoin de legacy_likes/legacy_dislikes
```

---

## 🐛 Débogage

Ajoutez ces logs pour comprendre ce qui se passe :

```python
# Dans get_recommendations()
logger.info(f"🔍 Récupération des interactions pour user {user.email}")

active = Interaction.objects.filter(user=user, is_revoked=False)
revoked = Interaction.objects.filter(user=user, is_revoked=True)

logger.info(f"   📊 Interactions actives: {active.count()}")
logger.info(f"   📊 Interactions révoquées: {revoked.count()}")

for interaction in revoked:
    logger.info(f"      ↪ Révoquée: {interaction.target_user.email} (type: {interaction.interaction_type})")
```

Cela vous permettra de vérifier que :
1. Les révocations sont bien enregistrées (`is_revoked=True`)
2. Les profils révoqués ne sont pas dans les exclusions
3. La découverte retourne bien ces profils

---

## ⚡ Impact

Cette correction permettra :
- ✅ Les profils likés/passés puis révoqués **réapparaissent dans la découverte**
- ✅ Les utilisateurs peuvent "réessayer" avec un profil qu'ils avaient rejeté
- ✅ Amélioration de l'UX - pas besoin de créer un nouveau compte pour revoir un profil
