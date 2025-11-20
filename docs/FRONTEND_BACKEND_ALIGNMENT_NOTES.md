# Notes d’Alignement Frontend ↔ Backend (HIVMeet)

Date: 2025-09-15
Version API: v1

## 1) Discovery / Matching
- URL officielle de la liste: `GET /api/v1/discovery/profiles` (alias supporté: `GET /api/v1/discovery/`)
- Interactions (inchangé):
  - `POST /api/v1/discovery/interactions/like`
  - `POST /api/v1/discovery/interactions/dislike`
  - `POST /api/v1/discovery/interactions/superlike`
  - `POST /api/v1/discovery/interactions/rewind` (premium)
  - `GET /api/v1/discovery/interactions/liked-me` (premium)
- Boost: `POST /api/v1/discovery/boost/activate` (premium)
- Pagination standardisée partout: `page`, `page_size` → réponses au format `{ count, next, previous, results }`.
- Action requise côté frontend: Utiliser `page` et `page_size` pour toutes les listes; ne pas dépendre de `{ data: [...] }`.

## 2) Messagerie
- Conversations: `GET /api/v1/conversations/`
- Messages: 
  - `GET /api/v1/conversations/{conversation_id}/messages/` (supporte `page`/`page_size`; conserve `has_more`/`show_premium_prompt`)
  - `POST /api/v1/conversations/{conversation_id}/messages/`
  - `POST /api/v1/conversations/{conversation_id}/messages/media/` (premium)
  - `PUT /api/v1/conversations/{conversation_id}/messages/mark-as-read/`
  - `DELETE /api/v1/conversations/{conversation_id}/messages/{message_id}/`
- Appels (standards): `POST /api/v1/calls/initiate`, `POST /api/v1/calls/{id}/answer`, `POST /api/v1/calls/{id}/ice-candidate`, `POST /api/v1/calls/{id}/terminate`.
- Appel premium: `POST /api/v1/conversations/calls/initiate-premium/` (note: exposé sous `conversations/`).
- Action frontend: Mettre à jour le client pagination messages pour lire `{ count, next, previous, results }`.

## 3) Authentification / Tokens
- Login: `POST /api/v1/auth/login` → réponse standardisée `{ access_token, refresh_token, user }`.
- Firebase exchange: `POST /api/v1/auth/firebase-exchange/`
  - Requête: accepte `id_token` (préféré) ou `firebase_token` (compat).
  - Réponse: expose à la fois `{ access_token, refresh_token }` et alias `{ token, access, refresh }`.
- Refresh: `POST /api/v1/auth/refresh-token` → réponse standardisée `{ access_token, refresh_token }` + alias `{ token, access, refresh }`.
- Logout: `POST /api/v1/auth/logout` (optionnellement passer `refresh_token` pour blacklist).
- Action frontend: Normaliser l’utilisation des clés `access_token`/`refresh_token`; conserver compat avec alias si déjà implémenté.

## 4) Ressources / Feed
- Catégories: `GET /api/v1/content/resource-categories`
- Ressources: `GET /api/v1/content/resources`
- Détail: `GET /api/v1/content/resources/{id}`
- Favoris: `POST|DELETE /api/v1/content/resources/{id}/favorite`, `GET /api/v1/content/favorites`
- Feed: `POST /api/v1/feed/posts`, `GET /api/v1/feed/posts`, `POST /api/v1/feed/posts/{id}/like`, `POST /api/v1/feed/posts/{id}/comments`, `GET /api/v1/feed/posts/{id}/comments`
- Pagination standardisée `{ count, next, previous, results }`.
- Action frontend: S’appuyer sur `page`/`page_size` partout.

## 5) Abonnements
- `GET /api/v1/subscriptions/plans/`, `GET /api/v1/subscriptions/current/`, `POST /api/v1/subscriptions/purchase/`, `POST /api/v1/subscriptions/current/cancel/`, `POST /api/v1/subscriptions/current/reactivate/`
- Webhook MyCoolPay: `POST /api/v1/webhooks/payments/mycoolpay/`

## 6) Internationalisation
- Le backend respecte `Accept-Language: fr|en` via `LocaleMiddleware`.
- Action frontend: Envoyer systématiquement `Accept-Language`.

## 7) Monitoring
- Santé: `/health/`, `/health/simple/`, `/health/ready/` ; Métriques: `/metrics/`.

## 8) Checklist Frontend
- Mettre à jour l’ApiClient pour pagination standard `{ count, next, previous, results }`.
- Uniformiser la lecture de tokens: utiliser `access_token` et `refresh_token`.
- Lors de l’échange Firebase, envoyer `id_token` (ou `firebase_token` en secours).
- Envoyer `Accept-Language` systématiquement.
- Utiliser `GET /api/v1/discovery/profiles` (alias `/api/v1/discovery/` reste fonctionnel).
- Vérifier l’endpoint d’appel premium: `POST /api/v1/conversations/calls/initiate-premium/`.

---

Pour toute divergence constatée, remonter les cas avec payloads/réponses exacts pour ajustement backend si nécessaire.
