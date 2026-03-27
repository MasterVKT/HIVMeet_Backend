# BACKEND — Bug critique : nouvelles interactions non exclues de la découverte

**Priorité** : 🔴 CRITIQUE — Bloquant  
**Module** : `discovery` — services de recommandation  
**Date de détection** : 2026-03-27  
**Symptôme** : Les 3 mêmes profils réapparaissent en boucle après chaque swipe, même après plusieurs likes/dislikes.

---

## Preuve dans les logs backend

Les logs montrent que **le compteur "Active interactions" reste figé à 31** même après plusieurs swipes réussis (HTTP 201) dans la même session :

```
01:04:05 → POST /api/v1/discovery/interactions/dislike  → 201 ✅
01:04:07 → Discovery: "Active interactions (is_revoked=False): 31"  ← aurait dû être 32

01:04:10 → POST /api/v1/discovery/interactions/dislike  → 201 ✅
01:04:11 → Discovery: "Active interactions (is_revoked=False): 31"  ← aurait dû être 33

01:04:13 → POST /api/v1/discovery/interactions/like    → 201 ✅
01:04:13 → Discovery: "Active interactions (is_revoked=False): 31"  ← aurait dû être 34

01:04:16 → POST /api/v1/discovery/interactions/dislike  → 201 ✅
01:04:16 → Discovery: "Active interactions (is_revoked=False): 31"  ← aurait dû être 35
```

**Conclusion** : Les interactions créées via les endpoints `/like` et `/dislike` ne sont **pas** récupérées par la requête d'exclusion dans `get_recommendations` / `services.py`.

---

## Piste 1 (la plus probable) : `interaction_type` ne correspond pas au filtre d'exclusion

La requête d'exclusion dans `services.py` filtre probablement sur des valeurs spécifiques d'`interaction_type`, par exemple :

```python
# ❌ Filtre trop restrictif — n'inclut peut-être pas le type utilisé par les nouveaux endpoints
already_interacted_ids = Interaction.objects.filter(
    from_user=user,
    is_revoked=False,
    interaction_type__in=['LIKE', 'SUPER_LIKE'],  # ← PASS / DISLIKE manquants ?
).values_list('to_user_id', flat=True)
```

Or les nouveaux endpoints stockent peut-être les dislikes avec `interaction_type='DISLIKE'` (ou `'PASS'`), et la requête d'exclusion ne couvre pas ce type.

**Vérification** : Exécuter en Django shell :
```python
from interactions.models import Interaction  # adapter le nom du module
from django.contrib.auth import get_user_model
User = get_user_model()

user = User.objects.get(id='0e5ac2cb-07d8-4160-9f36-90393356f8c0')

# Lister tous les interaction_type distincts pour cet utilisateur
interactions = Interaction.objects.filter(from_user=user, is_revoked=False)
print(interactions.values('interaction_type').distinct())
print(f"Total: {interactions.count()}")
```

Si le résultat montre des types non couverts par le filtre d'exclusion (ex. `'DISLIKE'`, `'PASS'`), c'est la cause.

**Correction** :
```python
# ✅ Inclure TOUS les types d'interaction dans l'exclusion
already_interacted_ids = Interaction.objects.filter(
    from_user=user,
    is_revoked=False,
    interaction_type__in=['LIKE', 'SUPER_LIKE', 'PASS', 'DISLIKE'],
).values_list('to_user_id', flat=True)
```

---

## Piste 2 : Deux modèles différents (nouveau endpoint vs requête d'exclusion)

Il est possible que les endpoints `/like` et `/dislike` créent des enregistrements dans un modèle différent de celui interrogé pour l'exclusion.

**Vérification** : Vérifier dans `views_discovery.py` (ou le fichier du endpoint) quel modèle est utilisé pour créer l'interaction :
```python
# Dans le endpoint POST /api/v1/discovery/interactions/dislike
# Quel modèle crée-t-il ?
# Interaction ? SwipeInteraction ? UserInteraction ?
```

Et dans `services.py`, quel modèle est interrogé pour l'exclusion ?

Si ce sont deux modèles différents → **il faut unifier la requête d'exclusion pour couvrir les deux**.

---

## Piste 3 : Champ `from_user` vs `user` ou autre nom de champ

La requête d'exclusion utilise peut-être `from_user=user` mais le modèle stocke l'interaction avec un champ nommé différemment (`initiator`, `sender`, `user_id`, etc.).

**Vérification** :
```python
# Inspecter la structure du modèle
from interactions.models import Interaction
print(Interaction._meta.get_fields())
```

---

## Piste 4 : `is_revoked=True` par défaut sur les nouvelles interactions

Si le champ `is_revoked` a une valeur par défaut `True` dans le modèle, les nouvelles interactions seraient ignorées par le filtre `is_revoked=False` de l'exclusion.

**Vérification** :
```python
# Vérifier les interactions récentes de l'utilisateur
from interactions.models import Interaction
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(id='0e5ac2cb-07d8-4160-9f36-90393356f8c0')

# Afficher les 5 dernières interactions triées par date
recent = Interaction.objects.filter(from_user=user).order_by('-created_at')[:5]
for i in recent:
    print(f"id={i.id}, type={i.interaction_type}, is_revoked={i.is_revoked}, created={i.created_at}")
```

Si `is_revoked=True` sur les nouvelles interactions → corriger la valeur par défaut du modèle.

---

## Correction attendue

Après correction, les logs doivent montrer que le compteur "Active interactions" augmente de 1 après chaque swipe :

```
# Attendu après correction :
01:04:07 → Discovery: "Active interactions (is_revoked=False): 32"  ✅
01:04:11 → Discovery: "Active interactions (is_revoked=False): 33"  ✅
01:04:13 → Discovery: "Active interactions (is_revoked=False): 34"  ✅
```

Et `Total profiles after all filters` doit décroître au fil des swipes (pas rester constant à 3).

---

## Note sur le UnorderedObjectListWarning encore présent

Le warning suivant apparaît toujours dans les logs à 01:04:31, **mais cette fois pour un autre endpoint** (pas discovery) :

```
UnorderedObjectListWarning: Pagination may yield inconsistent results with an unordered object_list: <class 'profiles.models.Profile'> QuerySet.
```

Ce warning est déclenché par `GET /api/v1/user-profiles/likes-received/?page=1&page_size=1`.  
→ Ajouter un `.order_by('date_joined')` sur le QuerySet de cet endpoint également.

---

## Note sur l'historique (my-likes renvoie 8 au lieu de 0)

```
GET /api/v1/discovery/interactions/my-likes?page=1&page_size=20&matched_only=true → 200 (8 résultats)
```

Le paramètre `matched_only=true` devrait filtrer uniquement les likes qui ont abouti à un match. Pour le compte de test `0e5ac2cb-07d8-4160-9f36-90393356f8c0`, il n'y a aucun match réel, donc ce filtre devrait retourner 0 résultats.

Voir `BACKEND_LIKES_HISTORY_DATA_ISSUES.md` pour les détails et le script de nettoyage.
