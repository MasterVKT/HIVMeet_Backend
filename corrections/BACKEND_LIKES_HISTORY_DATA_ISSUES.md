# BACKEND — Historique des interactions : données incohérentes & filtre `matched_only` défaillant

**Priorité** : 🔴 CRITIQUE  
**Modules concernés** : `discovery/interactions` — endpoints `my-likes`, `my-passes`  
**Date de détection** : 2026-03-26  
**Compte test impacté** : `0e5ac2cb-07d8-4160-9f36-90393356f8c0`

---

## 1. Problèmes identifiés

### 1.1. Filtre `matched_only=true` retourne des résultats incohérents avec la liste des matches

**Logs backend observés** :
```
INFO 2026-03-26 01:11:47,001 views_history "User 0e5ac2cb-07d8-4160-9f36-90393356f8c0 requesting likes history"
INFO 2026-03-26 01:11:47,153 views_history "✅ Returning 8 likes for user 0e5ac2cb-07d8-4160-9f36-90393356f8c0"
INFO "GET /api/v1/discovery/interactions/my-likes?page=1&page_size=20&matched_only=true HTTP/1.1" 200 5440

INFO "GET /api/v1/matches/?page=1&page_size=20 HTTP/1.1" 200 52
```

**Analyse** :
- `GET /api/v1/matches/` retourne **0 matches** (52 bytes = objet JSON vide ou liste vide).
- `GET /api/v1/discovery/interactions/my-likes?matched_only=true` retourne **8 likes** prétendument "matchés".

**Incohérence** : Si l'utilisateur n'a aucun match, le filtre `matched_only=true` devrait retourner **0 résultats**. Retourner 8 résultats est une erreur de logique dans le filtre.

**Cause probable** : Le filtrage par `matched_only=true` utilise probablement une condition incorrecte, par exemple :
- Filtre sur un champ booléen `is_matched` sur le modèle `InteractionHistory` qui aurait une valeur par défaut incorrecte (`True`).
- Filtre par existence d'un match dans la table `matches` qui pointe vers la mauvaise relation (ex. : `to_user` vs `from_user` inversés).
- Absence de jointure avec la table des matches actuels : le filtre vérifie si un match a DÉJÀ existé (même supprimé) plutôt que si un match est ACTIF.

---

### 1.2. Données d'interactions non supprimées pour le compte de test

**Attendu** : Le compte test `0e5ac2cb-07d8-4160-9f36-90393356f8c0` ne doit avoir **aucune** interaction (likes, passes) enregistrée, suite à une demande de nettoyage précédente.

**Observé** : 8 interactions de type "like" sont toujours présentes dans la base de données pour ce compte.

---

### 1.3. (Rappel) Paginator levait déjà un avertissement sur les profils

```
UnorderedObjectListWarning: Pagination may yield inconsistent results with an
unordered object_list: <class 'profiles.models.Profile'> QuerySet.
```

Ce warning est aussi visible sur les appels history si le modèle `InteractionHistory` n'est pas non plus ordonné. Voir [BACKEND_DISCOVERY_CYCLING_AND_PAGINATION.md](BACKEND_DISCOVERY_CYCLING_AND_PAGINATION.md) pour le détail.

---

## 2. Corrections requises

### 2.1. Corriger la logique du filtre `matched_only`

**Endpoint concerné** :
```
GET /api/v1/discovery/interactions/my-likes?matched_only=true&page=1&page_size=20
```

**Comportement attendu** :
- `matched_only=false` (défaut) : Retourner TOUS les likes envoyés par l'utilisateur, qu'ils aient matché ou non.
- `matched_only=true` : Retourner UNIQUEMENT les likes ayant abouti à un match **actif** (non supprimé).

**Implémentation correcte suggérée** :

```python
# Dans views_history.py (ou équivalent)

def get_my_likes(request):
    user = request.user
    matched_only = request.query_params.get('matched_only', 'false').lower() == 'true'

    # Récupérer les IDs des profils avec lesquels l'utilisateur a un match ACTIF
    # (la table Match contient les deux directions, adapter selon votre modèle)
    active_match_user_ids = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        is_active=True,  # ou status='active', adapter selon votre champ
    ).values_list(
        # Récupérer l'ID de l'autre utilisateur (pas l'utilisateur courant)
        Case(
            When(user1=user, then='user2_id'),
            default='user1_id'
        ),
        flat=True,
    )

    # QuerySet de base : tous les likes envoyés par l'utilisateur
    queryset = InteractionHistory.objects.filter(
        from_user=user,
        interaction_type='LIKE',  # adapter selon votre valeur d'enum
    ).select_related('to_user__profile').order_by('-created_at')

    if matched_only:
        # Filtrer uniquement les likes vers des utilisateurs avec lesquels il y a un MATCH ACTIF
        queryset = queryset.filter(to_user_id__in=active_match_user_ids)

    # Paginer et retourner
    # ...
```

**Vérifications importantes** :
1. Le champ `is_active` (ou `status`) sur le modèle `Match` doit être `True` UNIQUEMENT pour les matches non supprimés/non expirés.
2. La relation `user1`/`user2` dans `Match` doit correspondre à la réalité : vérifier que les deux sens de la relation sont bien couverts (un match peut avoir l'utilisateur en `user1` OU en `user2`).
3. Si le modèle Match n'a pas de champ `is_active`, utiliser `status` ou l'absence dans une table de suppression.

---

### 2.2. Nettoyage COMPLET des données du compte de test (MISE À JOUR 2026-03-27)

**Objectif** : Repartir d'un état vierge pour le compte de test — **0 likes, 0 passes, 0 matches** — afin de valider que toute nouvelle interaction (like ou pass depuis la page découverte) apparaît bien dans les pages d'historique.

> ⚠️ Le nettoyage doit couvrir **TOUS les modèles** stockant des interactions, y compris ceux utilisés par les nouveaux endpoints `/like` et `/dislike` (actuellement soupçonnés de stocker dans un modèle différent de `InteractionHistory` selon [BACKEND_DISCOVERY_EXCLUSION_BUG.md]).

**Compte à nettoyer** :
- User ID : `0e5ac2cb-07d8-4160-9f36-90393356f8c0`
- Firebase UID : `ayFjmQHalCYhmh8g6fOAPuf88ER2`

**État actuel connu** :
- 8 likes anciens visibles via `my-likes` (avant correction `matched_only`)
- 20 passes visibles via `my-passes`
- 31 "Active interactions (is_revoked=False)" selon les logs backend du service d'exclusion
- Nouveaux swipes créés via les endpoints `/like` et `/dislike` apparemment **non inclus** dans les 20 passes / 8 likes affichés → potentiellement dans un modèle séparé

**Script de nettoyage Django shell (recommandé)** :
```python
# python manage.py shell

from django.contrib.auth import get_user_model

User = get_user_model()
test_user = User.objects.get(id='0e5ac2cb-07d8-4160-9f36-90393356f8c0')

# Lister tous les modèles d'interaction disponibles dans votre projet
# et supprimer TOUTES les interactions impliquant cet utilisateur.
# Adapter les imports selon la structure réelle du projet :

# --- Modèle principal d'historique (utilisé par my-likes / my-passes) ---
try:
    from discovery.models import InteractionHistory  # adapter le chemin
    sent = InteractionHistory.objects.filter(from_user=test_user).delete()
    received = InteractionHistory.objects.filter(to_user=test_user).delete()
    print(f"InteractionHistory supprimé: {sent[0]} envoyées, {received[0]} reçues")
except Exception as e:
    print(f"InteractionHistory: ERREUR - {e}")

# --- Modèle Interaction (utilisé par les endpoints /like et /dislike si différent) ---
try:
    from interactions.models import Interaction  # adapter le chemin
    sent2 = Interaction.objects.filter(from_user=test_user).delete()
    received2 = Interaction.objects.filter(to_user=test_user).delete()
    print(f"Interaction supprimé: {sent2[0]} envoyées, {received2[0]} reçues")
except Exception as e:
    print(f"Interaction: {e}")  # Normal si c'est le même modèle que ci-dessus

# --- Modèle Swipe / SwipeInteraction si applicable ---
try:
    from matching.models import SwipeInteraction  # adapter le chemin
    sw = SwipeInteraction.objects.filter(swiper=test_user).delete()
    print(f"SwipeInteraction supprimé: {sw[0]}")
except Exception as e:
    print(f"SwipeInteraction: {e}")

# --- Matches ---
try:
    from matches.models import Match  # adapter le chemin
    m1 = Match.objects.filter(user1=test_user).delete()
    m2 = Match.objects.filter(user2=test_user).delete()
    print(f"Match supprimé: {m1[0] + m2[0]}")
except Exception as e:
    print(f"Match: ERREUR - {e}")

# --- Vérification finale ---
print("\n=== VÉRIFICATION ===")
# Relancer la commande qui retournait "Active interactions: 31" pour confirmer → doit être 0
# Vérifier que my-likes et my-passes retournent 0 résultats
```

> **Note importante** : Si certains modèles utilisent des noms de champs différents (`initiator` au lieu de `from_user`, ou `target` au lieu de `to_user`), adapter le script. En cas de doute, inspecter avec `Interaction._meta.get_fields()` avant de supprimer.

**Vérification post-nettoyage** : Les logs backend suivants doivent tous afficher 0 :
```
🚫 Excluding 0 profiles:
   - Active interactions (is_revoked=False): 0
   - Legacy likes: 0
   - Legacy dislikes: 0

✅ Returning 0 likes for user 0e5ac2cb...
✅ Returning 0 passes for user 0e5ac2cb...
```

---

### 2.3. Ajouter `order_by` aux QuerySets de l'historique

Pour éviter le même `UnorderedObjectListWarning` sur les endpoints d'historique :

```python
# Dans toutes les vues d'historique (my-likes, my-passes)
queryset = InteractionHistory.objects.filter(
    from_user=user,
    # ...
).order_by('-created_at')  # ← Toujours ajouter un ORDER BY
```

---

## 3. Réponse API attendue après correction

**Cas 1 : Compte test après nettoyage, sans match actif**

```
GET /api/v1/discovery/interactions/my-likes?matched_only=true&page=1&page_size=20
```

Réponse attendue :
```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

**Cas 2 : Compte test après nettoyage, tous les likes**

```
GET /api/v1/discovery/interactions/my-likes?matched_only=false&page=1&page_size=20
```

Réponse attendue :
```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

---

## 4. Tests de validation à effectuer après correction

1. **Test filtre `matched_only`** :
   - Appeler `GET /api/v1/matches/` → vérifier le count de matches actifs.
   - Appeler `GET /api/v1/discovery/interactions/my-likes?matched_only=true` → vérifier que le count retourné est **identique** au nombre de matches actifs (pas plus, pas moins).

2. **Test nettoyage compte test** :
   - Appeler `GET /api/v1/discovery/interactions/my-likes` pour le compte `0e5ac2cb-07d8-4160-9f36-90393356f8c0` → doit retourner `count: 0`.
   - Appeler `GET /api/v1/discovery/interactions/my-passes` pour le même compte → doit retourner `count: 0`.
   - Appeler `GET /api/v1/matches/` pour le même compte → doit retourner `count: 0`.

3. **Test de non-régression** :
   - Pour un autre compte utilisateur ayant des likes et des matches réels : vérifier que les données sont toujours correctement retournées.
   - Créer un nouveau like test → vérifier qu'il apparaît dans `my-likes?matched_only=false` mais **pas** dans `my-likes?matched_only=true` (si pas encore de match).
   - Simuler un match → vérifier que le like correspondant apparaît dans `my-likes?matched_only=true`.

---

## 5. Résumé des actions requises

| # | Action | Priorité | Type |
|---|--------|----------|------|
| 1 | Corriger la logique du filtre `matched_only` dans `my-likes` | 🔴 CRITIQUE | Code backend |
| 2 | Supprimer toutes les interactions du compte test `0e5ac2cb...` | 🔴 CRITIQUE | Script DB |
| 3 | Ajouter `order_by('-created_at')` aux QuerySets `my-likes` et `my-passes` | 🟡 IMPORTANT | Code backend |
| 4 | Vérifier que le modèle `Match` a un champ `is_active` ou `status` fiable | 🟡 IMPORTANT | Audit DB |
