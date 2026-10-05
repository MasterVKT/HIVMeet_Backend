# Documentation de l’API HIVMeet

## Table des Matières
1. Authentification
2. Profils Utilisateurs
3. Découverte et Matching
4. Messagerie
5. Appels
6. Ressources et Contenu
7. Abonnements Premium
8. Paramètres Utilisateur
9. Webhooks
10. Monitoring
11. Conventions (Auth, Pagination, i18n, Erreurs)

---

## Authentification

### POST `/api/v1/auth/register/`
- **Description**: creates the Django and Firebase accounts with compensation.
- **Request**:
  ```json
  {"email":"string","password":"string","password_confirm":"string","display_name":"string","birth_date":"YYYY-MM-DD","gender":"male|female","phone_number":"string?"}
  ```
- **Response** (201): `{ "user_id": "uuid", "email": "string", "display_name": "string" }`.
- **Errors**: 400 validation; 500 `registration_failed` without internal detail.

---

### GET `/api/v1/auth/verify-email/{verification_token}`
- **Description** : Vérifie l'email d'un utilisateur
- **Réponse** (200) :
  ```json
  { "verified": true, "message": "Email vérifié avec succès" }
  ```

---

### POST `/api/v1/auth/login`
- **Description** : Authentifie un utilisateur (email + mot de passe)
- **Requête** :
  ```json
  { "email": "string", "password": "string", "remember_me": false }
  ```
- **Réponse** (200) :
  ```json
  {
    "token": "jwt_token",
    "refresh_token": "refresh_token",
    "user": { "id": "uuid", "email": "string", "username": "string" }
  }
  ```

---

### POST `/api/v1/auth/firebase-exchange/`
- **Description**: exchanges a Firebase token for an already registered account.
- **Request**: `{ "firebase_token": "string" }`.
- **Response** (200): JWT tokens and user snapshot.
- **Errors**: `409 registration_required` when no local account exists; `409 firebase_uid_mismatch` when the identity differs. With the secure default `HIVMEET_REQUIRE_EXPLICIT_REGISTRATION=True`, this route never creates a local account. The documented, temporary legacy bridge is available only while that setting is explicitly false.

---

### POST `/api/v1/auth/forgot-password`
- **Description** : Demande de réinitialisation de mot de passe
- **Requête** : `{ "email": "string" }`
- **Réponse** (200) : `{ "message": "Email de réinitialisation envoyé" }`

---

### POST `/api/v1/auth/reset-password`
- **Description** : Réinitialise le mot de passe
- **Requête** :
  ```json
  { "token": "string", "new_password": "string" }
  ```
- **Réponse** (200) : `{ "message": "Mot de passe réinitialisé avec succès" }`

---

### POST `/api/v1/auth/refresh-token`
- **Description** : Rafraîchit un token d'accès expiré
- **Requête** : `{ "refresh_token": "string" }`
- **Réponse** (200) : `{ "token": "new_jwt_token" }`

---

### POST `/api/v1/auth/logout`
- **Description** : Déconnecte l'utilisateur (invalide les tokens)
- **Réponse** (200) : `{ "message": "Déconnexion réussie" }`

---

### POST `/api/v1/auth/fcm-token`
- **Description** : Enregistre ou renouvelle le token FCM de l?installation courante pour les notifications push.
- **Requ?te** : `{ "fcm_token": "string", "platform": "android|ios|web", "device_id": "string" }` (`device_id` est facultatif).
- **R?ponse** (200) : `{ "message": "Token FCM enregistr?" }`
- Le m?me token est d?tach? des autres comptes avant son association. `DELETE` sur cette route accepte `{ "fcm_token": "string" }` dans le corps et retourne `204`.
- Un ?chec temporaire FCM est journalis? avec son code et un identifiant de corr?lation non r?versible ; aucune valeur de token n?est journalis?e. Seuls les codes FCM prouvant qu?un token est invalide d?clenchent sa suppression.

---

## Historiques et badges de matches

### GET `/api/v1/discovery/interactions/my-likes` et `my-passes`
- **Description** : historique paginé, recherché côté serveur.
- **Paramètres** : `page`, `page_size` (maximum 100), `q`,
  `match_state=all|matched|unmatched` et `include_revoked`.
- **Réponse** (200) : pagination standard complétée par `selectable_count`.
  Chaque entrée contient `can_revoke`; un like associé à un match actif est
  non révocable et doit passer par la suppression du match.

### POST `/api/v1/discovery/interactions/revoke-bulk`
- **Description** : annule plusieurs interactions de manière atomique.
- **Requête** : `history_type` (`likes` ou `passes`) et soit
  `interaction_ids`, soit `select_all=true` avec les filtres `q`,
  `match_state`, `include_revoked`.
- **Réponse** (200) : `revoked_count`, `revoked_interaction_ids`.
- **Erreur** (409) : `bulk_revoke_not_possible`, avec `reasons`; aucune
  interaction n'est alors modifiée.

### GET `/api/v1/matches/unseen-count/`
- **Réponse** (200) : `{ "unseen_count": 0 }`, calculée pour le participant
  connecté uniquement.

### PUT `/api/v1/matches/seen/`
- **Requête** : `{ "match_ids": ["uuid"] }`; l'absence de `match_ids`
  marque tous les matches actifs du participant.
- **Réponse** (200) : `seen_count` et `unseen_count`.

Voir [PHASE_5_HISTORIES_AND_BADGES.md](PHASE_5_HISTORIES_AND_BADGES.md) pour
les règles de transition, migration et retour arrière.

---

## Profils Utilisateurs

### GET `/api/v1/user-profiles/me/`
- **Description** : Récupère le profil de l'utilisateur connecté
- **Réponse** (200) : Profil complet utilisateur, avec
  `preferred_currency` (`AUTO`, `XAF` ou `EUR`) et `effective_currency`
  (`XAF` ou `EUR`). En mode `AUTO`, le pays du profil est utilisé sans lire
  les coordonnées précises.

---

### PUT `/api/v1/user-profiles/me/`
- **Description** : Met à jour le profil utilisateur
- **Requête** : bio, birthdate, gender, location, preferences et
  `preferred_currency`. `PATCH` est également accepté.
- **Réponse** (200) : Profil mis à jour

---

### PUT or PATCH `/api/v1/user-profiles/me/complete/`
- **Description**: updates profile fields and location in one transaction.
- **Request**:
  ```json
  {
    "profile": {"bio": "string", "genders_sought": ["male"]},
    "location": {"location_enabled": false, "city_id": 2220957}
  }
  ```
- **Rules**: `genders_sought` is `[]`, `["male"]`, or `["female"]`.
  A location error rolls back the profile object. Coordinates belong only in
  `location` and are never returned to another participant.
- **Errors**: 400 `profile_required`, `invalid_location`, or serializer errors;
  401 when unauthenticated.

### GET `/api/v1/user-profiles/geo/countries/`
### GET `/api/v1/user-profiles/geo/cities/?country=XX&q=query`
- **Description**: authenticated, paginated GeoNames catalogue for manual
  location. A city query requires the selected two-letter country code.
- **Response**: `results` contains countries (`code`, `label`) or cities
  (`geonames_id`, `name`, `country_code`, `country_name`). Free text is never
  accepted as a location update.

---

### GET `/api/v1/user-profiles/{user_id}/`
- **Description** : Récupère le profil d'un autre utilisateur

---

### POST `/api/v1/user-profiles/me/photos/`
- **Description** : Upload d'une photo de profil (multipart/form-data)
- **Stockage** : depuis la phase 2, l'original et sa miniature sont créés sous
  des clés opaques dans le bucket privé de médias, chiffré par CMEK. Aucune URL
  publique ni clé de stockage n'est persistée ou retournée. Le champ `url` est
  une route API authentifiée, produite seulement pour le propriétaire ou un
  demandeur ayant un KYC actif au moment de la réponse. Le droit est
  réévalué à chaque lecture ; aucune URL GET signée de bucket n'est émise.
  Cette route ne doit jamais être écrite dans les logs, analytics,
  notifications ni exports.
- **Réponse** (201) : détails sûrs de la photo et route de lecture seulement
  quand elle est autorisée.
- **Erreurs** : `400` (validation ou plafond Free/Premium), `503`
  `photo_storage_unavailable` si le stockage configuré ne peut pas accepter
  la photo. Le backend de mémoire est réservé aux tests/développement ; la
  production exige le bucket privé configuré et vérifié.

---

### GET `/api/v1/user-profiles/media/photos/{photo_id}/{variant}/`
- **Description** : lit une photo privée via le backend, sans accès direct au
  bucket. `variant` vaut `main` ou `thumbnail`. Le propriétaire y accède pour
  gérer son profil ; toute autre personne doit avoir un KYC actif au moment de
  chaque `GET`.
- **Réponse** (200) : JPEG avec `Cache-Control: private, no-store, max-age=0`
  et `X-Content-Type-Options: nosniff`.
- **Erreurs** : `403` `kyc_required` sans KYC actif pour la photo d'autrui,
  `404` si la photo n'est pas encore migrée ou n'existe pas, `503`
  `photo_storage_unavailable` si le stockage privé est indisponible.

---

### PUT `/api/v1/user-profiles/me/photos/{photo_id}/`
- **Description** : Remplace le fichier d'une photo existante
  (multipart/form-data) sans changer son identifiant, son ordre ou son statut
  de photo principale.
- **Réponse** (200) : même DTO que l'ajout de photo.
- **Erreurs** : `400`, `404` si la photo ne relève pas de l'utilisateur,
  `503` `photo_storage_unavailable`.

---

### PUT `/api/v1/user-profiles/me/photos/{photo_id}/set-main/`
- **Description** : Définit une photo comme principale

---

### DELETE `/api/v1/user-profiles/me/photos/{photo_id}/`
- **Description** : Supprime une photo
- **Réponse** (204)

---

### GET `/api/v1/user-profiles/likes-received/`
- **Description** : Liste des likes reçus (Premium)

---

### GET `/api/v1/user-profiles/super-likes-received/`
- **Description** : Liste des super-likes reçus (Premium)

---

### GET `/api/v1/user-profiles/premium-status/`
- **Description** : Statut des fonctionnalités premium

---

### GET `/api/v1/user-profiles/me/verification/`
> **KYC v1 — brouillon canonique de travail (phases 0 à 2) :** les contrats, statuts et erreurs
> prévus sont définis dans
> [docs/kyc/KYC_V1_CONTRACT.openapi.yaml](kyc/KYC_V1_CONTRACT.openapi.yaml) et
> les décisions/gates dans [docs/kyc/KYC_PHASE_0_GOVERNANCE.md](kyc/KYC_PHASE_0_GOVERNANCE.md).
> La phase 1 rend la lecture sans effet de bord et bloque les deux routes
> historiques ci-dessous. L'activation production demeure interdite sans les
> gates documentés.
- **Description** : état KYC sûr du demandeur : statut, tentative, états sûrs
  des documents et dates. Elle ne renvoie jamais code, URL, chemin, hash ou
  document.

---

### POST `/api/v1/user-profiles/me/verification/start/`
- **Description** : démarre ou rejoue de manière idempotente une tentative
  avec version de consentement et confirmations obligatoires.
- **Réponse** : tentative et défi selfie à usage unique de 30 minutes,
  uniquement dans la réponse directe authentifiée.
- **Erreurs** : 400 validation, 409 état, 429 quota, 503 dépendance.

---

### POST `/api/v1/user-profiles/me/verification/upload-intents/`
- **Description** : crée ou rejoue une intention d'upload à usage unique vers
  un objet KYC à clé opaque. La réponse `201` (ou `200` en rejeu idempotent)
  contient `upload_id`, `expires_at`, l'en-tête obligatoire `Content-Type` et
  une URL PUT V4 courte. L'URL n'est ni persistée ni journalisée.
- **Contraintes** : identité officielle ou document médical/sérologique : JPEG,
  PNG ou PDF, jusqu'à 10 MiB ; selfie avec défi : JPEG/PNG, jusqu'à 5 MiB. Le
  type, la taille et le SHA-256 déclarés sont revalidés côté serveur après PUT.
- **Erreurs** : `400` validation, `409` état/idempotence, `410 intent_expired`,
  `503 dependency_unavailable`. Aucun chemin ou objet n'est exposé.

---

### POST `/api/v1/user-profiles/me/verification/upload-intents/complete/`
- **Description** : confirme seulement l'`upload_id` après PUT direct et
  programme le scan Celery idempotent. La réponse `202` retourne
  `{upload_id, state: "processing", idempotent_replay}` ; elle ne signifie pas
  que le document est accepté ni que le KYC est validé.
- **Traitement** : contrôle de l'objet, taille, MIME déclaré/réel, SHA-256,
  parseur complet borné et antivirus. Une anomalie, un malware, une absence ou
  une expiration place l'objet en quarantaine puis planifie sa purge ; seul un
  résultat techniquement accepté peut être soumis à la revue humaine future.

---

### POST `/api/v1/user-profiles/me/verification/submit/`
- **Description** : accepte uniquement trois intents serveur consommés et
  techniquement acceptés, avec défi selfie non expiré et clé d'idempotence.
- **Réponse** : 202 pending_review; 409 pour transition/intents invalides,
  410 pour défi expiré.

---

### POST `/api/v1/user-profiles/me/verification/generate-upload-url/`
- **Statut** : route historique dépréciée, réponse 410
  kyc_legacy_endpoint_deprecated. Aucun chemin ou URL n'est renvoyé.

---

### POST `/api/v1/user-profiles/me/verification/submit-documents/`
- **Statut** : route historique dépréciée, réponse 410
  kyc_legacy_endpoint_deprecated. Les chemins client ne sont plus acceptés.

---

## Découverte et Matching

### GET `/api/v1/discovery/`
- **Description** : Profils recommandés pour découverte
- **Query** : `page`, `page_size`

---

### GET `/api/v1/discovery/profiles`
- **Description** : Alias de `/api/v1/discovery/`

---

### GET `/api/v1/discovery/filters/get`
### PUT `/api/v1/discovery/filters`
- **Description**: returns or persists the authenticated account's Discovery
  preferences.
- **Payload**: `age_min`, `age_max`, `distance_max_km`, `genders`,
  `relationship_types`, `verified_only`, and `online_only`.
- **Selection values**: `genders` is `[]`, `["male"]`, or `["female"]`;
  `relationship_types` is `[]` or one of `friendship`, `long_term`,
  `short_term`, `casual`. `[]` means all.
- **Response**: the canonical values are returned below `filters`.

---

### POST `/api/v1/discovery/interactions/like`
- **Description** : Like un profil
- **Requête** : `{ "target_user_id": "uuid" }`
- **Quota gratuit** : consomme un des 10 swipes quotidiens

---

### POST `/api/v1/discovery/interactions/dislike`
- **Description** : Dislike un profil
- **Quota gratuit** : consomme un des 10 swipes quotidiens

---

### POST `/api/v1/discovery/interactions/superlike`
- **Description** : Super-like réservé aux comptes Premium (5/jour)
- **Compte gratuit** : réponse `403 premium_required`, sans consommation de swipe

---

### GET `/api/v1/discovery/interactions/status`
- **Description** : quota courant (`daily_likes_remaining`, limite, reset UTC et super Likes)

---

### POST `/api/v1/discovery/interactions/{interaction_id}/rewind/`
- **Description** : annule exactement l’interaction indiquée (Premium).
- **Sécurité** : l’opération verrouille le compte, l’interaction et la projection associée.
- **Limites** : fenêtre de cinq minutes, cinq rewinds par jour, sans remboursement du swipe.
- **Réponse 200** : `status`, `interaction_id`, `previous_profile`, `already_rewound`.
- **Erreurs métier** : `403 premium_required`, `404 interaction_not_found`,
  `409 match_exists_use_unmatch` ou `interaction_not_active`,
  `410 rewind_expired`, `429 rewind_daily_limit`.
- Une répétition après succès retourne `200` avec `already_rewound: true` et
  ne consomme pas de quota. Un match existant reste intact.
- `POST /api/v1/discovery/interactions/rewind` demeure un alias temporaire
  pour les anciens clients. Les clients actuels utilisent l’identifiant exact.
### GET `/api/v1/discovery/interactions/liked-me`
- **Description** : Voir qui m'a liké (Premium)

---

### POST `/api/v1/discovery/boost/activate`
- **Description** : Active un boost de profil (Premium)

---

### GET `/api/v1/matches/`
- **Description** : Liste des matches

---

### DELETE `/api/v1/matches/{match_id}`
- **Description** : Supprime un match pour les deux participants.
- **RÃ©ponse** : `204 No Content`, y compris lors d'une rÃ©pÃ©tition par un
  participant du match dÃ©jÃ  supprimÃ©. Un match supprimÃ© ne peut pas Ãªtre
  rÃ©activÃ© automatiquement par un nouveau like.

---

### POST `/api/v1/matches/likes-received/reveal/`
- **Authentification** : JWT requise.
- **Description** : action explicite qui révèle au compte Free son unique like reçu du mois civil UTC. Une répétition retourne le même profil et ne consomme jamais un second jeton.
- **Réponse** : `200` avec `profile`, `already_revealed` et `monthly_token_consumed`.
- **Erreurs** : `404 no_received_like`, `409 monthly_token_used` ou `feature_disabled`.

### POST `/api/v1/matches/{match_id}/unlock-free/`
- **Authentification** : JWT requise, participant du match uniquement.
- **Description** : retente le déblocage d'un match Free-Free. Les deux jetons du mois sont consommés atomiquement seulement s'ils sont tous les deux disponibles. Le DTO Match retourné expose `access_level`, `can_view_profile`, `can_send_messages`, `free_messages_remaining` et `access_locked_reason`.
- **Réponse** : `200`, y compris pour une nouvelle tentative sans changement.
- **Erreurs** : `404 match_not_found`, `409` pour un état non réessayable.

---

## Messagerie

### GET `/api/v1/conversations/`
- **Authentification** : JWT requise.
- **Query** : `status` vaut exclusivement `all` (défaut), `unread` ou
  `archived`; `page >= 1`; `page_size` est compris entre `1` et `50`.
- **Résultat** : les conversations masquées pour l'utilisateur sont exclues,
  puis le filtre `unread` est appliqué. L'ordre est stable :
  `-last_message_at`, puis `-id`. Le statut `archived` répond `200` avec une
  liste vide : il ne constitue pas un alias du masquage individuel.
- **Erreurs** : toute valeur de filtre ou pagination invalide répond `400`
  avec l'enveloppe `{ "error": "…", "details": { … } }`.

---

### GET `/api/v1/conversations/unread-count/`
- **Authentification** : JWT requise.
- **Query** : aucun paramètre.
- **Résultat** : `200` avec `{ "unread_count": <entier >= 0> }`. Somme
  serveur des compteurs `unread_count_for_me` sur toutes les conversations
  actives et non masquées pour l'appelant — même périmètre que
  `GET /api/v1/conversations/`, mais sans plafond de pagination. Destiné au
  badge global; sommer la première page de la liste sous-estime le total
  au-delà de `page_size` conversations non lues.
- **Erreurs** : `401` sans authentification.

---

### GET `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : messages visibles d'une conversation, sans effet de bord
  sur les non-lus.
- **Query** : `limit` et `page_size` sont des entiers de `1` à `50`;
  `before_message_id` est un UUID de message appartenant à la conversation.
  Les paramètres malformés ou un curseur non valide répondent `400` avec
  `{error, details}`. Le curseur s'appuie sur `(created_at, id)` et `next` vaut
  `null` sur la dernière page réelle.

---

### DELETE `/api/v1/conversations/{conversation_id}/`
- **Description** : Masque la conversation de la liste de l'utilisateur authentifié, sans supprimer le match ni les messages de l'autre participant. Un nouveau message reçu la réaffiche.
- **Réponse** : `204 No Content` (idempotent)
- **Erreurs** : `401` authentification manquante/invalide ; `404` conversation active absente ou non accessible

---

### PUT `/api/v1/conversations/{conversation_id}/restore/`
- **Description** : annule le masquage pour le seul participant authentifie.
- **Reponse** : `204 No Content`, y compris si la conversation n etait pas masquee.
- **Erreurs** : `401` sans session ; `404` si le match actif est inaccessible.

---

### PATCH `/api/v1/conversations/{conversation_id}/messages/{message_id}/`
- **Requete** : `{ "content": "texte" }`.
- **Description** : modifie un message texte intact de son propre auteur Premium pendant quinze minutes. La reponse `200` est le message canonique, avec `edited_at`.
- **Erreurs** : `400 validation_error`, `403 premium_required`, `403 edit_not_author`, `403 edit_window_expired`, `404` conversation ou message absent, `409 message_not_editable`.
- **WebSocket** : une modification valide diffuse `message.updated` apres commit avec `conversation_id`, `message_id`, `content` et `edited_at`.

---
---

### POST `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : envoi d'un message texte (JSON uniquement). Un retry avec
  le même `client_message_id` retourne le message canonique : la déduplication
  est contrainte par `(match, sender, client_message_id)`.
- **Accès Free-Free** : un match débloqué autorise dix messages texte sortants
  par participant. Les messages entrants et l'historique restent lisibles
  ensuite. `403 free_match_locked` ou `403 free_message_limit_reached` est
  retourné sans créer de message.

---

### POST `/api/v1/conversations/{conversation_id}/messages/media/`
- **Description** : unique chemin d'envoi de média (multipart, Premium,
  image/vidéo/audio, 10 Mo maximum). Aucun endpoint d'URL d'upload signée
  n'est exposé. Les réponses `media_url` et `media_download_url` pointent vers
  la route API authentifiée de téléchargement, jamais vers le stockage. Un
  compte sans KYC actif reçoit `403 kyc_required`; aucun `/media/messages/`,
  chemin, bucket ou URL signée ne doit être consommé par le client.

---

### GET `/api/v1/conversations/{conversation_id}/messages/{message_id}/media/`
- **Description** : tÃ©lÃ©charge explicitement un mÃ©dia pour un participant
  autorisÃ© de la conversation active. Supporte un unique header `Range` afin de
  reprendre un tÃ©lÃ©chargement annulÃ©. La ressource renvoie `404` lorsqu'elle
  est inaccessible ou supprimÃ©e globalement sans en rÃ©vÃ©ler la raison.
- **RÃ©ponses** : `200` flux complet, `206` flux partiel, `401` non
  authentifiÃ©, `403` match Free verrouillÃ©, `404` non accessible, `416` plage
  invalide.

---

### PUT `/api/v1/conversations/{conversation_id}/messages/mark-as-read/`
- **Description** : marque les seuls messages entrants `sent` ou `delivered`
  jusqu'à `last_read_message_id` inclus. Sans curseur, tous les entrants non
  lus sont traités. Un curseur d'une autre conversation, de l'expéditeur ou
  incohérent répond `400`, sans révéler son origine.
- **Réponse 200** : contient au minimum `messages_marked` et
  `unread_count_for_me`; `read_at` est présent lorsqu'un statut a changé.

---

### PUT `/api/v1/conversations/{conversation_id}/messages/{message_id}/read/`
- **Description** : chemin compatible pour marquer uniquement cet ID ; il
  applique le même recalcul transactionnel de `unread_count_for_me`.
- **Réponse 200** : `messages_marked`, `unread_count_for_me` et `read_at`
  lorsqu'une lecture a été persistée.

---

### DELETE `/api/v1/conversations/{conversation_id}/messages/{message_id}/`
- **Description** : Supprime un message (soft-delete)

---

## Appels

### POST `/api/v1/calls/initiate`
- **Description** : Initie un appel

---

### POST `/api/v1/calls/{call_id}/answer`
- **Description** : Répond à un appel

---

### POST `/api/v1/calls/{call_id}/ice-candidate`
- **Description** : Ajoute un candidat ICE

---

### POST `/api/v1/calls/{call_id}/terminate`
- **Description** : Termine un appel

---

### POST `/api/v1/conversations/calls/initiate-premium/`
- **Description** : Initie un appel premium (Premium)

Note: L'URL premium d'appel est exposée sous le préfixe `conversations/` dans ce backend.

---

## Ressources et Contenu

### GET `/api/v1/content/resource-categories`
- **Description** : Liste des catégories

---

### GET `/api/v1/content/resources`
- **Description** : Liste des ressources

---

### GET `/api/v1/content/resources/{resource_id}`
- **Description** : Détails d'une ressource

---

### POST `/api/v1/content/resources/{resource_id}/favorite`
- **Description** : Ajoute/retire des favoris

---

### GET `/api/v1/content/favorites`
- **Description** : Liste des favoris

---

### POST `/api/v1/feed/posts`
- **Description** : Crée un post de feed

---

### GET `/api/v1/feed/posts`
- **Description** : Liste les posts du feed

---

### POST `/api/v1/feed/posts/{post_id}/like`
- **Description** : Like/unlike un post

---

### POST `/api/v1/feed/posts/{post_id}/comments`
- **Description** : Ajoute un commentaire

---

### GET `/api/v1/feed/posts/{post_id}/comments`
- **Description** : Liste des commentaires

---

## Abonnements Premium

### GET `/api/v1/subscriptions/plans/`
- **Description** : Liste paginée des seuls plans actifs.
- **Authentification** : Bearer JWT requis.
- **Prix** : `price` et `currency` utilisent la devise effective du profil;
  `base_price` et `base_currency` conservent le tarif EUR de référence.
- **Métadonnées** : `monthly_equivalent`, `savings_percentage`,
  `most_popular`, `recommended` et `features`. Le plan annuel expose 40 %
  d'économie et les plans Premium exposent cinq rewinds immédiats par jour.
- **Catalogue canonique** : `hivmeet_monthly` et `hivmeet_annual`.

---

### GET `/api/v1/subscriptions/payment-capabilities/`
- **Description** : état non secret de la configuration MyCoolPay.
- **Authentification** : Bearer JWT requis.
- **Réponse 200** : `provider`, `available`,
  `callback_verification_available`, `enabled_currencies`,
  `default_currency` et `effective_currency`.
- Aucune clé publique ou privée n'est renvoyée.

---

### GET `/api/v1/subscriptions/current/`
- **Description** : Abonnement actuel

---

### POST `/api/v1/subscriptions/purchase/`
- **Description** : crée une transaction locale puis un Paylink MyCoolPay
- **Authentification** : Bearer JWT requis
- **Body** : `{ "plan_id": "hivmeet_monthly", "phone_number": "699009900", "language": "fr" }`
- **Header optionnel** : `Idempotency-Key`, 8 à 64 caractères sûrs. Flutter
  doit le fournir et le réutiliser lors d'un retry de la même tentative.
- **Réponse 201** : `payment_id`, `payment_url` HTTPS MyCoolPay,
  `payment_status: "pending"`, `amount`, `currency` et
  `idempotent_replay: false`.
- **Réponse 202** : transaction locale conservée après une réponse fournisseur
  ambiguë; `payment_url` vaut `null` et le client vérifie le statut sans créer
  une seconde transaction.
- **Replay 200** : même transaction, avec `idempotent_replay: true`.
- **Erreurs** : `400 validation_error`, `409 idempotency_conflict` ou
  `active_subscription_exists`, `502 payment_provider_unavailable`,
  `503 payment_not_configured`, dans l'enveloppe
  `{error, message, details, status_code}`.
- Le succès HTTP ne signifie jamais que Premium est actif.

---

### GET `/api/v1/subscriptions/payments/{payment_id}/`
- **Description** : statut backend du paiement ; réconcilie les transactions en attente
- **Réponse** : `payment_status`, `fulfilled`, `subscription_id`,
  `activated_at` et `subscription` (`plan_id`, statut et période courante).
- La transaction doit appartenir à l'utilisateur authentifié. Les vérifications
  concurrentes mobile/Celery sont limitées par une prise atomique.

---

### GET `/api/v1/subscriptions/payment-return/{success|cancel|failure}/`
- **Description** : redirection UX HTTPS vers
  `hivmeet://payment/result?status=...`.
- Aucun de ces retours ne confirme un paiement ni n'active Premium.
- Réponse `302` non mise en cache; la confirmation reste l'endpoint de statut
  authentifié ci-dessus.

---

### POST `/api/v1/subscriptions/current/cancel/`
- **Description** : Annule l'abonnement courant

---

### POST `/api/v1/subscriptions/current/reactivate/`
- **Description** : Réactive l'abonnement

---

### POST `/api/v1/subscriptions/current/modify/`
- **Description** : Modifie l'abonnement actuel (changement de plan / upgrade / downgrade)
- **Authentification** : Bearer JWT requis
- **Headers** : `Accept-Language: fr|en` (pour la localisation du `plan_name`)
- **Body** :
  ```json
  {
    "new_plan_id": "hivmeet_annual",
    "proration": true
  }
  ```
  | Champ | Type | Requis | Description |
  |-------|------|--------|-------------|
  | `new_plan_id` | string | ✅ | `plan_id` du nouveau plan |
  | `proration` | boolean | ❌ (default: `true`) | Si `true`, calcule un avoir au prorata et applique le changement immédiatement. Si `false`, programme le changement au prochain cycle. |

- **Réponse 200 OK** :
  ```json
  {
    "subscription_id": "sub_external_id",
    "plan_id": "hivmeet_annual",
    "plan_name": "HIVMeet Premium Annuel",
    "status": "active",
    "current_period_start": "2026-07-31T16:00:00Z",
    "current_period_end": "2027-07-31T16:00:00Z",
    "auto_renew": true,
    "cancel_at_period_end": false,
    "scheduled_change": null,
    "features_summary": { ... },
    "proration": {
      "credit_amount": 3.50,
      "charge_amount": 0.00,
      "currency": "EUR",
      "prorated_period_start": "2026-07-31T16:00:00Z",
      "prorated_period_end": "2027-07-31T16:00:00Z"
    }
  }
  ```
- Quand `proration` vaut `false`, `scheduled_change` contient le forfait cible
  et `effective_at`. Ce choix correspond à un changement de forfait confirmé,
  pas au réglage de renouvellement automatique.
  Le block `proration` est `null` si `proration: false` a été demandé.

- **Erreurs** :
  | Status | `error` | Cas |
  |--------|---------|-----|
  | 400 | `invalid_plan` | `new_plan_id` manquant, introuvable ou inactif |
  | 400 | `no_active_subscription` | L'utilisateur n'a pas d'abonnement actif |
  | 400 | `same_plan` | Le nouveau plan est identique au plan courant |
  | 402 | `payment_required` | Un paiement est requis et le moyen de paiement est invalide |
  | 401 | — | Non authentifié |

---

## Paramètres Utilisateur

### GET `/api/v1/user-settings/notification-preferences`
### PUT `/api/v1/user-settings/notification-preferences`

- **Preference de lecture** : `message_read_notifications` est un booleen de `notification-preferences`. Pour un compte Premium, son absence vaut `true`; seul `false` est une desactivation explicite. Un compte Free le voit toujours a `false` sans ecraser un ancien choix Premium.
- **Alerte de lecture Premium** : quand un lot de messages passe reellement a `read`, le serveur cree une notification persistante `message_read` pour l'auteur Premium eligible. Son `data` contient `notification_id`, `conversation_id`, `reader_id`, `representative_message_id`, `message_count` et `read_at`, sans contenu de message. FCM et WebSocket reutilisent le meme `notification_id`.
### GET `/api/v1/user-settings/privacy-preferences`
### PUT `/api/v1/user-settings/privacy-preferences`

### GET `/api/v1/user-settings/blocks`
### POST `/api/v1/user-settings/blocks/{user_id}`

### POST `/api/v1/user-settings/delete-account`

### GET `/api/v1/user-settings/export-data`

---

## Webhooks

### POST `/api/v1/webhooks/payments/mycoolpay/`
- **Description** : callback MyCoolPay à signature MD5 vérifiée et source IP filtrée
- **Réponse** : texte `OK` uniquement après validation et traitement idempotent

---

## Monitoring

### GET `/health/`
### GET `/health/simple/`
### GET `/health/ready/`
### GET `/metrics/`

---

## Conventions

### Authentification
- Header requis (sauf `/api/v1/auth/*`) :
```
Authorization: Bearer <jwt_token>
```

### Pagination
- Paramètres: `page`, `page_size`
- Réponse paginée:
```json
{ "count": 100, "next": "?page=2", "previous": null, "results": [ ... ] }
```

### Internationalisation
- Header supporté: `Accept-Language: fr` ou `en`

### Erreurs (format commun)
```json
{ "error": true, "message": "Description", "details": { } }
```

---

Dernière mise à jour: 2025-09-14 — Version API: v1
