# Phase 5 — Historiques et badges

## Déploiement

1. Déployer ce backend et exécuter `python manage.py migrate`.
2. Vérifier `python manage.py check` puis les tests de `matching.tests_history_badges`.
3. Déployer l'application Flutter compatible. Les anciens clients continuent à
   lire les champs préexistants des historiques et de la liste des matches.

La migration `matching.0004_match_participant_seen_state` initialise les
matches déjà existants comme vus pour leurs deux participants. Les matches
créés après la migration restent non vus jusqu'à la première consultation.
Elle est additive et le rétroremplissage non atomique procède par lots de
1 000 lignes afin de limiter les verrous. Son rollback structurel retire les
colonnes et index ; il ne peut pas reconstituer les instants de consultation
supprimés.

## Historiques d'interactions

`GET /api/v1/discovery/interactions/my-likes` et
`GET /api/v1/discovery/interactions/my-passes` acceptent :

- `page` et `page_size` (maximum 100) ;
- `q`, recherche insensible à la casse et aux accents sur le nom affiché ;
- `match_state=all|matched|unmatched` ;
- l'ancien `matched_only=true`, conservé comme alias de `matched` ;
- `include_revoked=true|false`.

La réponse paginée contient les champs existants et `selectable_count`.
`can_revoke` est faux pour un like qui a créé un match actif. Ces likes restent
consultables mais doivent être traités par `DELETE /api/v1/matches/{id}`.

`POST /api/v1/discovery/interactions/revoke-bulk` attend :

```json
{
  "history_type": "likes",
  "interaction_ids": ["uuid"],
  "select_all": false
}
```

Pour tous les résultats sélectionnables des filtres actifs :

```json
{
  "history_type": "passes",
  "select_all": true,
  "q": "nom",
  "match_state": "unmatched",
  "include_revoked": false
}
```

Une réponse `200` renvoie `revoked_count` et `revoked_interaction_ids`. Une
réponse `409 bulk_revoke_not_possible` renvoie `reasons` avec
`interaction_id`, `profile_user_id` et le code applicable, et ne modifie
aucune ligne. Les likes avec match actif sont exclus d'une
sélection globale ; s'ils arrivent dans une sélection explicite devenue
obsolète, la transaction est refusée entièrement.

## Badge Matches par participant

`GET /api/v1/matches/unseen-count/` renvoie :

```json
{ "unseen_count": 2 }
```

`PUT /api/v1/matches/seen/` accepte `{"match_ids": ["uuid"]}` et renvoie
`seen_count` ainsi que le nouveau `unseen_count`. Sans `match_ids`, il marque
tous les matches actifs de l'appelant. L'état est stocké séparément pour les
deux participants et ne dépend pas de notifications supprimables.

La liste des matches contient désormais `is_new`. Les compteurs des
conversations et des notifications restent fournis par leurs endpoints
`unread-count` respectifs ; le client les réconcilie après toute lecture ou
suppression.
