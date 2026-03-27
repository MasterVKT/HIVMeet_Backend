# Rapport de Correction - BACKEND_DISCOVERY_EXCLUSION_BUG

**Date** : 2026-03-27  
**Fichiers modifiés** : `matching/services.py`, `matching/views_history.py`  
**Status** : ✅ Corrigé

---

## Problèmes Identifiés

### 1. QuerySets paresseux dans `services.py`

**Symptôme** : Le compteur "Active interactions" restait figé à 31 même après plusieurs swipes.

**Cause** : Les QuerySets Django sont évalués paresseusement (lazy evaluation). Lorsqu'on les combine avec `set()` dans la même requête HTTP, ils peuvent retourner des données obsolètes car la base de données n'a pas encore Commité les nouvelles insertions.

**Solution** : Évaluer explicitement tous les QuerySets en listes AVANT de les utiliser :

```python
# ❌ AVANT (problème)
interacted_user_ids = InteractionHistory.objects.filter(...).values_list(...)
excluded_ids = set(interacted_user_ids) | set(...)

# ✅ APRÈS (corrigé)
interacted_user_ids_list = list(
    InteractionHistory.objects.filter(...).values_list(...)
)
excluded_ids = set(interacted_user_ids_list) | set(...)
```

**Fichiers modifiés** :
- `matching/services.py` - Conversion de tous les QuerySets en listes

---

### 2. Logique `matched_only` incorrecte dans `views_history.py`

**Symptôme** : `GET /api/v1/discovery/interactions/my-likes?matched_only=true` retournait 8 résultats au lieu de 0.

**Cause** : La logique de filtrage était trop permissive. Le paramètre `include_matched` forçait le retour de tous les likes même quand `matched_only=true`.

**Solution** : Simplifier la logique pour respecter strictement le paramètre `matched_only` :

```python
# ✅ Logique corrigée
if matched_only:
    if matched_ids:
        interactions = interactions.filter(target_user_id__in=matched_ids)
    else:
        interactions = interactions.none()  # Aucun match = résultat vide
# else: matched_only=false = retourner tous les likes
```

**Fichiers modifiés** :
- `matching/views_history.py` - Simplification de la logique `matched_only`

---

## Résumé des Modifications

| Fichier | Modification |
|---------|-------------|
| `matching/services.py` | Conversion des QuerySets en listes pour éviter les données obsolètes |
| `matching/views_history.py` | Simplification du filtre `matched_only` |

---

## Vérification

```bash
python manage.py check
# System check identified no issues (0 silenced). ✅
```

---

## Comportement Attendu Après Correction

### Discovery (exclusion des profils swipés)
- Après chaque swipe (like/dislike), le compteur "Active interactions" doit augmenter de 1
- Les profils swipés ne doivent plus réapparaître dans la découverte

### my-likes (paramètre matched_only)
- `matched_only=false` (défaut) : retourne TOUS les likes
- `matched_only=true` : retourne UNIQUEMENT les likes avec un match actif
  - Si aucun match → retourne 0 résultats

---

## Notes

1. **Cache de base de données** : LesQuerySets évalués en listes sont maintenant immune aux problèmes de transaction isolation level.

2. **Logs ajoutés** : Des logs de debug supplémentaires ont été ajoutés pour faciliter le diagnostic futur :
   - Nombre de matches actifs trouvés
   - Résultat du filtrage matched_only
   - Nombre de résultats retournés

3. **Tests recommandés** :
   - Tester plusieurs swipes consécutifs et vérifier que le compteur increase
   - Tester `my-likes?matched_only=true` avec et sans matches actifs
