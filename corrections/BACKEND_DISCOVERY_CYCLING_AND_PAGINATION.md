# BACKEND — Cyclage des profils en découverte & pagination non-déterministe

**Priorité** : 🔴 CRITIQUE  
**Module concerné** : `discovery` — endpoint `GET /api/v1/discovery/profiles`  
**Date de détection** : 2026-03-26  
**Symptôme observé** : Les mêmes profils réapparaissent à chaque session de découverte ou après quelques swipes, de façon cyclique.

---

## ⚠️ HOTFIX URGENT — Erreur 500 active en production (ajouté le 2026-03-26)

**Problème immédiat** : Suite à l'implémentation de la recommandation `order_by('created_at')` de ce document, le backend génère une erreur **HTTP 500** bloquante sur `GET /api/v1/discovery/profiles`.

**Traceback** :
```
django.core.exceptions.FieldError: Cannot resolve keyword 'created_at' into field.
Choices are: birth_date, date_joined, updated_at, ...
```

**Cause** : Le modèle `User` (utilisé dans le QuerySet de découverte dans `matching/services.py`) **n'a pas de champ `created_at`**. Le champ équivalent sur ce modèle est **`date_joined`**.

**Correction immédiate** : Dans `matching/services.py` (ligne ~252 et toute autre occurrence), remplacer :
```python
# ❌ INCORRECT — champ inexistant
queryset = queryset.order_by('created_at')
```
par :
```python
# ✅ CORRECT — champ réel du modèle User
queryset = queryset.order_by('date_joined')
```

**Vérification** : Après correction, l'appel `GET /api/v1/discovery/profiles?page=1&page_size=5` doit retourner HTTP 200.

---

---

## 1. Problèmes identifiés

### 1.1. QuerySet non ordonné → Pagination non-déterministe

**Log d'avertissement Django observé** :
```
D:\Projets\HIVMeet\env\Lib\site-packages\rest_framework\pagination.py:200:
UnorderedObjectListWarning: Pagination may yield inconsistent results with an
unordered object_list: <class 'profiles.models.Profile'> QuerySet.
  paginator = self.django_paginator_class(queryset, page_size)
```

**Explication** : Le QuerySet `Profile` utilisé dans la vue de découverte ne possède pas de clause `ORDER BY`. Django REST Framework lève cet avertissement car, sans ordre stable, la pagination par offset (`page=1`, `page=2`, etc.) peut :
- Retourner les mêmes profils sur deux pages différentes si un enregistrement est inséré entretemps.
- Sauter des profils si la base de données réorganise l'ordre de stockage.
- Retourner les mêmes profils d'une session à l'autre car l'ordre est arbitraire et potentiellement constant (ex. : ordre de création dans le heap PostgreSQL).

**Impact utilisateur** : L'utilisateur voit toujours les mêmes profils lors de chaque session.

---

### 1.2. Profils déjà swipés non exclus du résultat

**Symptôme** : Après avoir liké ou passé un profil, il peut réapparaître dans la pile de découverte lors d'un rechargement.

**Cause probable** : Le filtre d'exclusion des interactions existantes (likes, passes) de l'utilisateur connecté n'est pas appliqué, ou est partiellement appliqué (ex. : exclut les likes mais pas les passes, ou vice-versa).

---

### 1.3. (Point d'attention frontend) : Le frontend envoie toujours `page=1`

Le frontend envoie actuellement toujours `page=1&page_size=20` pour récupérer des profils supplémentaires (`_loadMoreProfiles`). Cela signifie qu'après que les 20 premiers profils sont swipés, le frontend redemande la même page 1, ce qui retourne les mêmes profils (ceux-ci ne sont pas encore exclus si le problème 1.2 n'est pas corrigé).

**Note** : La résolution du problème 1.2 (exclusion des profils déjà swipés) suffit à corriger ce symptôme côté frontend à court terme, car même si `page=1` est redemandé, les profils swipés seront exclus du résultat.

---

## 2. Corrections requises côté backend

### 2.1. Ajouter un ORDER BY stable au QuerySet de découverte

**Objectif** : Rendre la pagination déterministe et éviter les doublons inter-pages.

**Action** : Dans la vue ou le manager qui construit le QuerySet pour la découverte, ajouter un `.order_by()` explicite.

**Option A — Ordre par date d'inscription (recommandé)** :
```python
# Dans la vue ou le queryset de découverte
# ⚠️ Le modèle User utilise 'date_joined', PAS 'created_at'
queryset = Profile.objects.filter(...).order_by('date_joined')
```

**Option B — Ordre aléatoire par session (pour diversité)** :
```python
import random
from django.db.models.functions import Random

# Chaque appel retourne un ordre différent, mais la pagination d'une même session
# reste cohérente si on utilise un seed de session (moins recommandé, complexe)
queryset = Profile.objects.filter(...).order_by('?')
# ⚠️ ATTENTION : order_by('?') est très lent sur de grandes tables PostgreSQL
# Préférer l'option A ou C
```

**Option C — Ordre par un hash de UUID stable (pagination par curseur)** :
Si vous migrez vers une pagination par curseur (recommandé à long terme), utiliser l'ID UUID comme curseur naturel :
```python
queryset = Profile.objects.filter(...).order_by('id')
```

**Recommandation** : Utiliser `order_by('date_joined')` en priorité (c'est le champ `date_joined` du modèle `User`, équivalent à `created_at`). Si la diversité est souhaitée, une combinaison d'un seed aléatoire côté applicatif stocké en session est préférable à `order_by('?')`.

---

### 2.2. Exclure systématiquement les profils déjà interagis

**Objectif** : Un profil liké ou passé par l'utilisateur connecté ne doit JAMAIS réapparaître dans la découverte.

**Action** : Filtrer les profils qui ont une interaction existante (`LIKE`, `PASS`, `SUPER_LIKE`) de la part de l'utilisateur connecté.

**Implémentation suggérée** :
```python
from interactions.models import Interaction  # Adapter selon votre nom de modèle

def get_discovery_queryset(user):
    # Récupérer les IDs des profils déjà interagis
    already_interacted_profile_ids = Interaction.objects.filter(
        from_user=user,
        interaction_type__in=['LIKE', 'PASS', 'SUPER_LIKE'],
    ).values_list('to_user_id', flat=True)

    # Exclure ces profils ET le profil de l'utilisateur lui-même
    queryset = Profile.objects.filter(
        is_active=True,
        # ... autres filtres de découverte (âge, distance, genre, etc.)
    ).exclude(
        user_id__in=already_interacted_profile_ids,
    ).exclude(
        user_id=user.id,
    ).order_by('date_joined')  # ← Ordonné et déterministe (champ réel du modèle User)

    return queryset
```

**À vérifier** :
- Que le modèle `Interaction` (ou son équivalent) contient bien les actions `PASS` et non seulement `LIKE`.
- Que les passes (`PASS`) sont bien enregistrées dans la base (certaines implémentations n'enregistrent que les likes).

---

### 2.3. (Amélioration optionnelle) : Pagination par curseur avec `last_profile_id`

**Contexte** : Le frontend passe un paramètre `lastProfileId` dans ses appels "load more" mais la couche repository ne l'utilise pas encore dans l'URL (toujours `page=1`). Une migration vers la pagination par curseur permettrait une meilleure performance et éviterait les doublons sur de grandes collections.

**Paramètre frontend attendu** :
```
GET /api/v1/discovery/profiles?last_profile_id=<uuid>&page_size=20
```

**Implémentation backend suggérée** :
```python
def get(self, request):
    last_profile_id = request.query_params.get('last_profile_id')
    page_size = int(request.query_params.get('page_size', 20))

    queryset = get_discovery_queryset(request.user).order_by('date_joined')

    if last_profile_id:
        try:
            last_user = User.objects.get(id=last_profile_id)
            # Récupérer uniquement les profils APRÈS le dernier vu
            # ⚠️ Utiliser 'date_joined' (champ réel) et non 'created_at'
            queryset = queryset.filter(date_joined__gt=last_user.date_joined)
        except User.DoesNotExist:
            pass  # Ignorer si l'utilisateur n'existe plus

    profiles = queryset[:page_size]
    # ... serialisation et réponse
```

**Réponse attendue** :
```json
{
  "results": [...],
  "count": 20,
  "has_more": true,
  "next_cursor": "<last_profile_id_from_results>"
}
```

**Note** : Cette amélioration est optionnelle à court terme si le problème 2.2 (exclusion des profils swipés) est correctement implémenté. Elle devient importante lorsque le nombre de profils disponibles est élevé.

---

## 3. Tests de validation à effectuer après correction

1. **Test d'ordre stable** :
   - Appeler `GET /api/v1/discovery/profiles?page=1&page_size=5` deux fois consécutives.
   - Les profils retournés doivent être identiques (ordre stable).

2. **Test d'exclusion** :
   - Swiper (like ou pass) 5 profils.
   - Appeler `GET /api/v1/discovery/profiles?page=1&page_size=20`.
   - Aucun des 5 profils swipés ne doit apparaître dans les résultats.

3. **Test de non-régression** :
   - S'assurer que les filtres de découverte (âge, distance, genre) fonctionnent toujours correctement.
   - S'assurer que le warning `UnorderedObjectListWarning` n'apparaît plus dans les logs.

4. **Test de pagination** :
   - Naviguer à travers plus de 20 profils.
   - Vérifier qu'aucun doublon n'apparaît entre les pages.

---

## 4. Résumé des actions requises

| # | Action | Priorité | Fichiers concernés |
|---|--------|----------|-------------------|
| 1 | Ajouter `order_by('created_at')` au QuerySet de découverte | 🔴 CRITIQUE | `discovery/views.py` ou équivalent |
| 2 | Exclure les profils ayant une interaction existante | 🔴 CRITIQUE | `discovery/views.py`, `interactions/models.py` |
| 3 | Exclure le profil de l'utilisateur lui-même | 🟡 IMPORTANT | `discovery/views.py` |
| 4 | Implémenter pagination par curseur avec `last_profile_id` | 🟢 OPTIONNEL | `discovery/views.py`, `discovery/serializers.py` |
