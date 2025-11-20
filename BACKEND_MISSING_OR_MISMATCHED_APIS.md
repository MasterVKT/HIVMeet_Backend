## Gaps et divergences API Backend vs Frontend (HIVMeet)

Date: 2025-09-15

Référentiel: `API_DOCUMENTATION.md` (Version API v1, 2025-09-14)

### Résumé
- Alignements effectués côté frontend: découverte/matching, messagerie, ressources, abonnements, profils, paramètres.
- Headers normalisés: `Authorization: Bearer <jwt>`, `Accept-Language: fr|en` via intercepteur.
- Refresh token: payload `{ "refresh_token": "..." }`, réponse tolère `{ token, refresh_token }` ou `{ access, refresh }`.

### Endpoints précédemment erronés (corrigés côté frontend)
- Découverte (legacy): `/api/v1/like/`, `/api/v1/dislike/`, `/api/v1/super-like/`, `/api/v1/rewind/` → remplacés par:
  - `POST /api/v1/discovery/interactions/like`
  - `POST /api/v1/discovery/interactions/dislike`
  - `POST /api/v1/discovery/interactions/superlike`
  - `POST /api/v1/discovery/interactions/rewind`
- Ressources (legacy): `/api/v1/resources/`, `/api/v1/favorites/` → remplacés par:
  - `GET /api/v1/content/resources`
  - `GET /api/v1/content/favorites`
  - `POST /api/v1/content/resources/{resource_id}/favorite`
- Messagerie (non documenté): `POST /api/v1/conversations/{id}/update` → supprimé côté frontend.

### Vérifications d’authentification
- Requête non authentifiée détectée côté backend: `GET /api/v1/discovery/` (401). C’est attendu: endpoint protégé.
- Frontend met désormais le token automatiquement via `ApiClient` sauf pour `/api/v1/auth/*` et `/health/*`.

### Points à confirmer côté backend
- Discovery list: la doc indique `GET /api/v1/discovery/` et alias `/api/v1/discovery/` vs `/api/v1/discovery/profiles`. Le frontend utilise `GET /api/v1/discovery/profiles` (documenté). Merci de confirmer que les deux existent ou conserver uniquement `/api/v1/discovery/profiles`.
- Structures de réponses: le frontend tolère `{"results": [...]}` et `{"data": [...]}` pour pagination. La doc montre `{"count", "next", "previous", "results"}`. Idéalement standardiser sur ce format.
- Refresh token: doc `POST /api/v1/auth/refresh-token` répond `{ "token": "new_jwt_token" }`. Le frontend accepte aussi `{ access }`. Confirmer le format final et ajouter `refresh_token` si renouvelé.
- Health endpoints: doc expose `/health/`, `/health/simple/`, `/health/ready/`. Confirmé.

### Actions backend proposées (si nécessaire)
- Standardiser la pagination au format doc (count/next/previous/results) sur tous les endpoints listants.
- Harmoniser la réponse de refresh: `{ token, refresh_token? }` et documenter clairement.
- Clarifier l’URL officielle de discovery list (garder `/api/v1/discovery/profiles`).

### Internationalisation
- Le frontend envoie `Accept-Language: fr|en`. Merci de vérifier la prise en charge côté Django (locale middleware).

### Sécurité
- 401 attendu pour endpoints protégés sans token.
- CSRF non applicable pour clients JWT.

---
Contact: Frontend HIVMeet

