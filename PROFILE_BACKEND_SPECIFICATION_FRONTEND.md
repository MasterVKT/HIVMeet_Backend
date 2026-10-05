# Specification backend pour implementation frontend de la page Profil

> **Archivage KYC v0 :** l'intégralité des références KYC historiques de cette
> spécification est non contractuelle. Utiliser exclusivement
> `docs/kyc/KYC_V1_CONTRACT.openapi.yaml` et
> `docs/kyc/KYC_PHASE_0_GOVERNANCE.md`. Les routes historiques
> `generate-upload-url/` et `submit-documents/` retournent `410`
> `kyc_legacy_endpoint_deprecated`; il est interdit d'envoyer un chemin de
> stockage ou de persister/afficher une URL ou un code KYC issus de ce document.

Document destine a un agent frontend autonome. Il decrit le contrat backend reel du projet `hivmeet_backend` pour toutes les fonctionnalites liees au profil utilisateur exposees par l'app Django `profiles/`.

Date d'audit: 2026-05-16  
Base API: `/api/v1`  
Authentification: `Authorization: Bearer <access_token>` sur tous les endpoints de ce document.

## Sources backend auditees

- Routes principales: `hivmeet_backend/api_urls.py`
- Routes profil: `profiles/urls.py`
- Routes parametres utilisateur: `profiles/urls_settings.py`
- Vues profil/photos/verification: `profiles/views.py`
- Vues premium: `profiles/views_premium.py`
- Vues parametres: `profiles/views_settings.py`
- Modeles: `profiles/models.py`, `authentication/models.py`, `matching/models.py`
- Serializers: `profiles/serializers.py`, `authentication/serializers.py`
- Premium helpers: `subscriptions/utils.py`
- Storage Firebase: `hivmeet_backend/storage/manager.py`
- Creation automatique profil/verification: `profiles/signals.py`
- Documentation croisee: `docs/API_DOCUMENTATION.md`

## Regles globales d'integration

- Tous les endpoints profil officiels sont sous `/api/v1/user-profiles/`, pas `/api/v1/profiles/`.
- Les endpoints de preferences et blocage sont sous `/api/v1/user-settings/`.
- Les routes `user-profiles` utilisent un slash final. Exemple: `/api/v1/user-profiles/me/`.
- Les routes `user-settings` sont definies sans slash final. Exemple exact: `/api/v1/user-settings/privacy-preferences`.
- Le backend utilise JWT SimpleJWT. Envoyer `Authorization: Bearer <access_token>`.
- Reponse d'erreur DRF globale typique: `{ "error": true, "message": "...", "details": ..., "status_code": 400, "error_code": "..." }`.
- Plusieurs vues fonctionnelles retournent aussi des erreurs manuelles plus simples: `{ "error": true, "message": "...", "details": {...} }` ou `{ "error": "premium_required", ... }`.
- Les dates sont en ISO 8601. Le backend est configure en timezone UTC.
- `Accept-Language: fr` ou `en` est supporte. La langue par defaut est `fr`.
- Les champs Decimal Django comme `latitude` et `longitude` peuvent revenir en JSON sous forme de string. Le frontend doit accepter string ou number et normaliser localement.

## Inventaire complet des fonctionnalites frontend profil

| Fonctionnalite | Methode | Endpoint exact | Backend | Auth | Notes |
|---|---:|---|---|---|---|
| Charger mon profil complet | GET | `/api/v1/user-profiles/me/` | `MyProfileView` + `ProfileSerializer` | Oui | Cree le profil si absent. |
| Mettre a jour mon profil | PUT/PATCH | `/api/v1/user-profiles/me/` | `MyProfileView` + `ProfileCreateUpdateSerializer` | Oui | PATCH recommande pour edition partielle. |
| Consulter un profil public | GET | `/api/v1/user-profiles/{user_id}/` | `UserProfileView` + `PublicProfileSerializer` | Oui | `user_id` est l'UUID du User, pas du Profile. |
| Uploader une photo | POST multipart | `/api/v1/user-profiles/me/photos/` | `upload_photo_view` | Oui | Champ fichier obligatoire: `file`. |
| Definir photo principale | PUT | `/api/v1/user-profiles/me/photos/{photo_id}/set-main/` | `set_main_photo_view` | Oui | Une seule photo principale par profil. |
| Supprimer une photo | DELETE | `/api/v1/user-profiles/me/photos/{photo_id}/` | `delete_photo_view` | Oui | Interdit de supprimer la seule photo si elle est principale. |
| Voir les likes recus | GET | `/api/v1/user-profiles/likes-received/` | `LikesReceivedView` | Oui + Premium | Pagine par DRF. 403 non premium. |
| Voir les super-likes recus | GET | `/api/v1/user-profiles/super-likes-received/` | `SuperLikesReceivedView` | Oui + Premium | Pagine par DRF. 403 non premium. |
| Statut premium profil | GET | `/api/v1/user-profiles/premium-status/` | `PremiumFeaturesStatusView` | Oui | Sert aux badges/limites/CTA premium. |
| Statut verification | GET | `/api/v1/user-profiles/me/verification/` | `VerificationStatusView` | Oui | Cree le record et genere un code si besoin. |
| Generer URL upload document | POST | `/api/v1/user-profiles/me/verification/generate-upload-url/` | `generate_upload_url_view` | Oui | Retourne une URL signee Firebase PUT. |
| Soumettre documents verification | POST | `/api/v1/user-profiles/me/verification/submit-documents/` | `submit_verification_documents_view` | Oui | Utilise les chemins storage retournes precedemment. |
| Preferences notifications | GET/PUT | `/api/v1/user-settings/notification-preferences` | `NotificationPreferencesView` | Oui | JSON libre, merge defaults seulement au GET. |
| Preferences confidentialite | GET/PUT | `/api/v1/user-settings/privacy-preferences` | `PrivacyPreferencesView` | Oui | Mappe vers plusieurs champs `Profile`. |
| Liste utilisateurs bloques | GET | `/api/v1/user-settings/blocks` | `BlockedUsersListView` | Oui | Retourne `{count, results}`. |
| Bloquer utilisateur | POST | `/api/v1/user-settings/blocks/{user_id}` | `block_unblock_user_view` | Oui | Limite: 100 utilisateurs bloques. |
| Debloquer utilisateur | DELETE | `/api/v1/user-settings/blocks/{user_id}` | `block_unblock_user_view` | Oui | 204 si succes. |
| Demande suppression compte | POST | `/api/v1/user-settings/delete-account` | `delete_account_view` | Oui | Stub actuel: accuse reception seulement. |
| Demande export donnees | GET | `/api/v1/user-settings/export-data` | `export_data_view` | Oui | Stub actuel: accuse reception seulement. |

## Donnees metier et enums

### Genres autorises

Utiliser exactement ces valeurs:

```json
["male", "female", "non_binary", "trans_male", "trans_female", "other", "prefer_not_to_say"]
```

Libelles suggeres frontend:

| Valeur | Libelle FR |
|---|---|
| `male` | Homme |
| `female` | Femme |
| `non_binary` | Non-binaire |
| `trans_male` | Homme trans |
| `trans_female` | Femme trans |
| `other` | Autre |
| `prefer_not_to_say` | Prefere ne pas dire |

### Types de relation autorises

```json
["friendship", "long_term", "short_term", "casual"]
```

Libelles suggeres:

| Valeur | Libelle FR |
|---|---|
| `friendship` | Amitie |
| `long_term` | Relation serieuse |
| `short_term` | Relation courte |
| `casual` | Rencontre casual |

### Statuts de verification backend

```json
["not_started", "pending_id", "pending_medical", "pending_selfie", "pending_review", "verified", "rejected", "expired"]
```

Important: le modele `User.verification_status` utilise des valeurs plus courtes: `not_started`, `pending`, `verified`, `rejected`, `expired`. La page Profil doit afficher prioritairement le statut detaille de `/me/verification/` pour le workflow documents.

### Types de document de verification

```json
["identity_document", "medical_document", "selfie_with_code"]
```

### MIME types acceptes

Photos de profil:

```json
["image/jpeg", "image/jpg", "image/png"]
```

Documents de verification:

```json
["image/jpeg", "image/jpg", "image/png", "application/pdf"]
```

## Schemas de donnees

### User imbrique dans mon profil

`GET /api/v1/user-profiles/me/` inclut `user` via `UserSerializer`:

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "Marie",
  "birth_date": "1990-01-01",
  "age": 36,
  "is_verified": false,
  "is_premium": false,
  "verification_status": "not_started",
  "profile_complete": true,
  "last_active": "2026-05-16T10:00:00Z",
  "date_joined": "2026-01-01T10:00:00Z"
}
```

Champs `User` non modifiables via les endpoints profil actuels: `email`, `display_name`, `birth_date`, `phone_number`. Il n'existe pas dans `profiles/` d'endpoint pour changer le nom d'affichage ou la date de naissance.

### Photo de profil

```json
{
  "id": "uuid",
  "photo_url": "https://storage.googleapis.com/...",
  "thumbnail_url": "https://storage.googleapis.com/...",
  "is_main": true,
  "caption": "Texte optionnel",
  "order": 0,
  "uploaded_at": "2026-05-16T10:00:00Z"
}
```

Le backend stocke aussi `is_approved` et `moderation_notes`, mais ces champs ne sont pas exposes aux serializers frontend.

### Mon profil complet

Reponse de `GET /api/v1/user-profiles/me/`:

```json
{
  "id": "uuid_profile",
  "user": { "...": "voir UserSerializer" },
  "bio": "Bio jusqu'a 500 caracteres",
  "gender": "female",
  "latitude": "4.0511000",
  "longitude": "9.7679000",
  "city": "Douala",
  "country": "Cameroun",
  "hide_exact_location": false,
  "interests": ["musique", "voyage", "lecture"],
  "relationship_types_sought": ["friendship", "long_term"],
  "age_min_preference": 25,
  "age_max_preference": 45,
  "distance_max_km": 25,
  "genders_sought": ["male"],
  "is_hidden": false,
  "show_online_status": true,
  "allow_profile_in_discovery": true,
  "photos": [{ "...": "voir Photo" }],
  "age": 36,
  "distance_from_me_km": null,
  "premium_limits": {
    "is_premium": false,
    "limits": {
      "super_likes": {"total": 0, "remaining": 0, "reset_date": null},
      "boosts": {"total": 0, "remaining": 0, "reset_date": null},
      "features": {
        "unlimited_likes": false,
        "can_see_likers": false,
        "can_rewind": false,
        "media_messaging": false,
        "calls": false
      }
    }
  },
  "created_at": "2026-01-01T10:00:00Z",
  "updated_at": "2026-05-16T10:00:00Z"
}
```

Champs existants en base mais non exposes par `ProfileSerializer`: `verified_only`, `online_only`, `profile_views`, `likes_received`.

### Profil public d'un autre utilisateur

Reponse de `GET /api/v1/user-profiles/{user_id}/`, de `likes-received` et de `super-likes-received`:

```json
{
  "id": "uuid_profile",
  "display_name": "Jean",
  "bio": "Bio publique",
  "age": 34,
  "city": "Yaounde",
  "country": "Cameroun",
  "interests": ["sport", "cinema"],
  "relationship_types_sought": ["friendship"],
  "is_verified": true,
  "is_premium": false,
  "last_active_display": "Online",
  "photos": [{ "...": "voir Photo" }],
  "distance_from_me_km": null
}
```

Confidentialite: si `hide_exact_location=true` sur le profil cible, le serializer retire `city` de la reponse publique. `country` reste expose.

## Workflow 1: charger et afficher la page Profil

1. Appeler `GET /api/v1/user-profiles/me/`.
2. Afficher les donnees `user`, `bio`, `gender`, localisation, preferences, photos, visibilite, limites premium.
3. En parallele ou apres, appeler selon les sections visibles:
   - `GET /api/v1/user-profiles/premium-status/` pour une carte premium detaillee.
   - `GET /api/v1/user-profiles/me/verification/` pour la carte verification.
   - `GET /api/v1/user-settings/privacy-preferences` pour les toggles confidentialite simplifiees.
   - `GET /api/v1/user-settings/notification-preferences` si la page Profil contient une section notifications.
   - `GET /api/v1/user-settings/blocks` si la page Profil contient une section blocages.

Le backend cree automatiquement `Profile` et `Verification` a la creation du `User` via signals. `GET /me/` et `GET /me/verification/` ont aussi des garde-fous `get_or_create`.

## Workflow 2: modifier mon profil

Endpoint recommande: `PATCH /api/v1/user-profiles/me/`.

Payload plat attendu, sans objets imbriques:

```json
{
  "bio": "Nouvelle bio",
  "gender": "female",
  "latitude": 4.0511,
  "longitude": 9.7679,
  "city": "Douala",
  "country": "Cameroun",
  "hide_exact_location": true,
  "interests": ["musique", "voyage"],
  "relationship_types_sought": ["friendship", "long_term"],
  "age_min_preference": 25,
  "age_max_preference": 45,
  "distance_max_km": 50,
  "genders_sought": ["male", "non_binary"],
  "is_hidden": false,
  "show_online_status": true,
  "allow_profile_in_discovery": true
}
```

Contraintes backend:

- `bio`: max 500 caracteres.
- `gender`: choix enum genre.
- `interests`: maximum 3 elements, chaque element max 50 caracteres.
- `relationship_types_sought`: liste de valeurs enum relation.
- `age_min_preference`: entier 18-99.
- `age_max_preference`: entier 18-99.
- `age_min_preference <= age_max_preference`.
- `distance_max_km`: entier 5-100.
- `genders_sought`: liste de genres. Liste vide `[]` signifie ouvert a tous les genres.
- `latitude`: decimal max 10 chiffres, 7 decimales.
- `longitude`: decimal max 10 chiffres, 7 decimales.
- `city` et `country`: max 100 caracteres.

Reponse succes: status 200 avec les champs du serializer de mise a jour uniquement, pas forcement le profil complet avec `user` et `photos`. Apres sauvegarde, le frontend doit soit merger localement, soit refaire `GET /api/v1/user-profiles/me/`.

Erreurs principales:

```json
{
  "error": true,
  "message": "Validation error",
  "details": {
    "age_max_preference": ["Maximum age must be greater than minimum age."]
  },
  "status_code": 400
}
```

## Workflow 3: gestion des photos

### Charger les photos

Les photos sont dans `GET /api/v1/user-profiles/me/` sous `photos`, triees par `order`, puis `-uploaded_at`.

### Upload photo

Endpoint: `POST /api/v1/user-profiles/me/photos/`  
Content-Type: `multipart/form-data`

Champs:

| Champ | Type | Requis | Contraintes |
|---|---|---:|---|
| `file` | image file | Oui | JPEG/JPG/PNG, max 5 MB |
| `is_main` | boolean | Non | `false` par defaut |
| `caption` | string | Non | max 200 caracteres, blanc autorise |

Important: le champ s'appelle `file`, pas `photo`.

Limite nombre de photos:

- Non-premium: 1 photo.
- Premium: 6 photos.
- Le code actuel teste `request.user.is_premium`, sans verifier directement `premium_until` dans cette vue. Utiliser quand meme `/premium-status/` cote frontend pour l'UX.

Reponse 201:

```json
{
  "photo_id": "uuid",
  "url": "https://storage.googleapis.com/...",
  "thumbnail_url": "https://storage.googleapis.com/...",
  "is_main": true,
  "caption": "",
  "uploaded_at": "2026-05-16T10:00:00Z"
}
```

Le backend redimensionne et convertit l'image en JPEG via Firebase Storage:

- image principale: max 1920x1920, qualite 85.
- miniature: max 200x200.
- chemin storage: `profiles/{user.id}/main/...` et `profiles/{user.id}/thumbnails/...`.

Erreurs:

- 400 si fichier invalide, >5 MB, type MIME interdit.
- 400 si limite photo atteinte: `Photo limit reached. {max} photos allowed.`
- 500 si erreur Firebase/traitement image.

### Definir la photo principale

Endpoint: `PUT /api/v1/user-profiles/me/photos/{photo_id}/set-main/`

Reponse 200:

```json
{ "message": "Main photo updated successfully." }
```

Le modele force l'unicite: toute autre photo principale du meme profil est mise a `is_main=false`.

Erreurs:

- 404 si `photo_id` n'appartient pas a l'utilisateur connecte.

### Supprimer une photo

Endpoint: `DELETE /api/v1/user-profiles/me/photos/{photo_id}/`

Reponse:

- 204 sans body si succes.
- 400 si tentative de supprimer la seule photo et qu'elle est principale.
- 404 si la photo n'existe pas ou n'appartient pas a l'utilisateur.

Si la photo supprimee etait principale et qu'il reste d'autres photos, le backend promeut automatiquement la premiere photo restante.

Non implemente cote backend actuellement:

- Modifier uniquement la legende d'une photo.
- Reordonner les photos.
- Remplacer un fichier photo existant.
- Supprimer immediatement le fichier Firebase Storage lors du DELETE. Le code supprime seulement l'enregistrement DB.

## Workflow 4: verification d'identite et statut medical

### Lire le statut

Endpoint: `GET /api/v1/user-profiles/me/verification/`

Reponse 200:

```json
{
  "id": "uuid",
  "status": "not_started",
  "rejection_reason": "",
  "submitted_at": null,
  "reviewed_at": null,
  "expires_at": null,
  "verification_code": "ABC123",
  "required_documents": [
    {"type": "identity_document", "status": "pending", "name": "Identity Document"},
    {"type": "medical_document", "status": "pending", "name": "Medical Document"},
    {"type": "selfie_with_code", "status": "pending", "name": "Selfie with Code"}
  ]
}
```

Effet de bord: si aucun code n'existe et que le statut n'est pas `verified`, le backend genere un code alphanumerique de 6 caracteres et le sauvegarde.

### Generer une URL signee d'upload

Endpoint: `POST /api/v1/user-profiles/me/verification/generate-upload-url/`

Payload:

```json
{
  "document_type": "identity_document",
  "file_type": "image/jpeg",
  "file_size": 1048576
}
```

Contraintes:

- `document_type`: `identity_document`, `medical_document`, `selfie_with_code`.
- `file_type`: JPEG/JPG/PNG/PDF.
- `file_size`: max 10 MB.

Reponse 200:

```json
{
  "upload_url": "https://signed-firebase-url...",
  "file_path_on_storage": "verification/{user_id}/identity_document.jpeg"
}
```

Le frontend doit ensuite envoyer le fichier directement vers `upload_url` avec une requete HTTP `PUT`, body binaire du fichier, et `Content-Type` egal a `file_type`.

### Soumettre les documents pour revue

Endpoint: `POST /api/v1/user-profiles/me/verification/submit-documents/`

Payload:

```json
{
  "documents": [
    {
      "document_type": "identity_document",
      "file_path_on_storage": "verification/{user_id}/identity_document.jpeg"
    },
    {
      "document_type": "medical_document",
      "file_path_on_storage": "verification/{user_id}/medical_document.pdf"
    },
    {
      "document_type": "selfie_with_code",
      "file_path_on_storage": "verification/{user_id}/selfie_with_code.jpeg"
    }
  ],
  "selfie_code_used": "ABC123"
}
```

Reponse 200:

```json
{
  "verification_status": "pending_review",
  "message": "Documents submitted for verification."
}
```

Regles backend:

- Chaque document doit contenir `document_type` et `file_path_on_storage`.
- Si `selfie_with_code` est soumis avec `selfie_code_used`, le code doit correspondre a `verification_code`.
- Si les trois chemins sont presents, statut `pending_review` et `submitted_at=now`.
- Sinon statut partiel: `pending_id`, `pending_medical` ou `pending_selfie`.
- `User.verification_status` est mis a `pending` apres une soumission reussie.
- Quand un admin/moderateur mettra `Verification.status=verified`, le signal mettra `User.is_verified=true`, `User.verification_status=verified`, et `expires_at=now+180 jours`.

Point de vigilance frontend: le backend actuel accepte une soumission de selfie sans `selfie_code_used` si le champ est omis. Pour une UX sure, l'app doit toujours demander et envoyer le code affiche.

## Workflow 5: statut premium et fonctionnalites premium de la page Profil

### Statut premium

Endpoint: `GET /api/v1/user-profiles/premium-status/`

Reponse non-premium 200:

```json
{
  "is_premium": false,
  "subscription_type": null,
  "premium_until": null,
  "features": {
    "unlimited_likes": false,
    "can_see_likers": false,
    "can_rewind": false,
    "media_messaging": false,
    "calls": false
  },
  "usage": {
    "super_likes": {"total": 0, "remaining": 0, "used": 0, "reset_at": null},
    "boosts": {"total": 0, "remaining": 0, "used": 0, "reset_at": null}
  }
}
```

Reponse premium 200:

```json
{
  "is_premium": true,
  "subscription_type": "Premium Monthly",
  "premium_until": "2026-06-16T10:00:00+00:00",
  "features": {
    "unlimited_likes": true,
    "can_see_likers": true,
    "can_rewind": true,
    "media_messaging": true,
    "calls": true
  },
  "usage": {
    "super_likes": {"total": 5, "remaining": 3, "used": 2, "reset_at": "2026-05-17T10:00:00Z"},
    "boosts": {"total": 1, "remaining": 1, "used": 0, "reset_at": "2026-06-16T10:00:00Z"}
  }
}
```

### Likes recus

Endpoint: `GET /api/v1/user-profiles/likes-received/?page=1`

- Premium uniquement.
- Non-premium: 403.
- Reponse premium: pagination DRF avec `results` contenant des `PublicProfileSerializer`.

Erreur non-premium:

```json
{
  "error": "premium_required",
  "message": "Cette fonctionnalite necessite un abonnement premium",
  "upgrade_url": "/subscriptions/plans"
}
```

### Super-likes recus

Endpoint: `GET /api/v1/user-profiles/super-likes-received/?page=1`

Identique a `likes-received`, mais filtre `Like.like_type = "super"`.

Note technique: ces listes utilisent le modele `matching.Like` avec `from_user` et `to_user`. Le tri backend actuel est `-user__date_joined`, pas par date de like. Ne pas promettre a l'utilisateur un tri "likes les plus recents" sauf correction backend.

## Workflow 6: preferences de confidentialite

Endpoint: `GET /api/v1/user-settings/privacy-preferences`

Reponse:

```json
{
  "profile_visibility": "visible_to_all",
  "show_online_status": true,
  "show_distance": true,
  "profile_discoverable": true
}
```

Mapping backend:

- `profile_visibility = "visible_to_all"` si `Profile.allow_profile_in_discovery=true`, sinon `"hidden"`.
- `show_online_status` mappe `Profile.show_online_status`.
- `show_distance = !Profile.hide_exact_location`.
- `profile_discoverable` mappe `Profile.allow_profile_in_discovery`.

Endpoint: `PUT /api/v1/user-settings/privacy-preferences`

Payload:

```json
{
  "profile_visibility": "visible_to_all",
  "show_online_status": true,
  "show_distance": false,
  "profile_discoverable": true
}
```

Reponse:

```json
{ "message": "Privacy preferences updated successfully." }
```

Important: `profile_visibility` et `profile_discoverable` ecrivent tous les deux `allow_profile_in_discovery`. Si les deux sont envoyes avec des valeurs contradictoires, `profile_discoverable` gagne car il est applique apres dans le code. Le frontend doit garder ces deux controles synchronises ou n'envoyer qu'un seul des deux.

## Workflow 7: preferences de notifications

Endpoint: `GET /api/v1/user-settings/notification-preferences`

Reponse avec defaults:

```json
{
  "new_match_notifications": true,
  "new_message_notifications": true,
  "profile_like_notifications": false,
  "app_update_notifications": true,
  "promotional_notifications": false,
  "do_not_disturb_settings": {
    "enabled": false,
    "start_time_utc": "22:00",
    "end_time_utc": "07:00"
  }
}
```

`profile_like_notifications` vaut par defaut `user.is_premium`.

Endpoint: `PUT /api/v1/user-settings/notification-preferences`

Payload: JSON complet de preferences. Le backend sauvegarde `request.data` tel quel dans `User.notification_settings`; il ne valide pas le schema au PUT.

Reponse: le JSON sauvegarde.

Implementation frontend recommandee:

- Toujours partir de la reponse GET, modifier localement, puis renvoyer l'objet complet.
- Conserver `do_not_disturb_settings` comme objet imbrique avec `enabled`, `start_time_utc`, `end_time_utc`.
- Ne pas envoyer de cles sensibles ou experimentales non gerees par l'app, car elles seront persistees.

## Workflow 8: utilisateurs bloques

### Lister les blocages

Endpoint: `GET /api/v1/user-settings/blocks`

Reponse:

```json
{
  "count": 2,
  "results": [
    {
      "user_id": "uuid",
      "display_name": "Jean",
      "profile_photo_url": "https://storage.googleapis.com/..."
    }
  ]
}
```

`profile_photo_url` correspond a la miniature de la photo principale si elle existe, sinon `null`.

### Bloquer

Endpoint: `POST /api/v1/user-settings/blocks/{user_id}`

Reponse 201:

```json
{
  "status": "user_blocked",
  "blocked_user_id": "uuid"
}
```

Erreurs:

- 400: impossible de se bloquer soi-meme.
- 404: utilisateur cible introuvable.
- 409: utilisateur deja bloque.
- 429: limite de 100 utilisateurs bloques atteinte.

Effet de securite: `GET /api/v1/user-profiles/{user_id}/` refuse ensuite la consultation dans les deux sens si l'un des deux utilisateurs a bloque l'autre.

### Debloquer

Endpoint: `DELETE /api/v1/user-settings/blocks/{user_id}`

Reponse:

- 204 sans body si succes.
- 404 si l'utilisateur n'est pas dans la liste de blocage ou n'existe pas.

## Workflow 9: suppression compte et export donnees

Ces endpoints existent mais sont actuellement des stubs fonctionnels, pas une suppression/export reel.

### Demande suppression compte

Endpoint: `POST /api/v1/user-settings/delete-account`

Payload: aucun requis actuellement.

Reponse 202:

```json
{
  "message": "Account deletion request received. You will receive a confirmation email."
}
```

Le backend ne verifie pas encore le mot de passe, ne desactive pas le compte, et ne programme pas de suppression. Le frontend doit presenter cela comme une demande recue, pas comme une suppression effective immediate.

### Demande export donnees

Endpoint: `GET /api/v1/user-settings/export-data`

Reponse 202:

```json
{
  "message": "Your data export request is being processed. You will receive an email with download link."
}
```

Le backend ne genere pas encore de fichier dans cette vue.

## Workflow 10: consulter un profil public depuis la page Profil ou un lien utilisateur

Endpoint: `GET /api/v1/user-profiles/{user_id}/`

Parametre path:

- `user_id`: UUID du `User`, pas `Profile.id`.

Regles backend:

- Authentification requise.
- Le profil cible doit appartenir a un user actif.
- `Profile.is_hidden=false`.
- `Profile.allow_profile_in_discovery=true`.
- Refus si le viewer a bloque le cible.
- Refus si le cible a bloque le viewer.
- Incremente `profile.profile_views` a chaque consultation valide.

Reponse: `PublicProfileSerializer`.

Status possibles:

- 200 si visible.
- 403 si blocage.
- 404 si profil masque, non decouvrable, user inactif ou inexistant.

## Endpoints inexistants ou obsoletes a ne pas utiliser

Des anciennes docs du repo mentionnent des routes qui ne sont pas montees dans le backend actuel. Ne pas les appeler depuis la page Profil:

- `POST /api/v1/user-profiles/`
- `POST /api/v1/user-profiles/photos`
- `PUT /api/v1/user-profiles/photos/{photo_id}`
- `POST /api/v1/user-profiles/verification/request`
- `POST /api/v1/user-profiles/verification/upload`
- `PUT /api/v1/user-profiles/search-preferences`
- `PUT /api/v1/user-profiles/visibility-settings`
- `GET /api/v1/user-profiles/suggestions`
- `GET /api/v1/user-profiles/search`
- `GET /api/v1/user-profiles/statistics`
- `/api/v1/profiles/likes-received/`
- `/api/v1/profiles/super-likes-received/`
- `/api/v1/profiles/premium-status/`

Equivalents reels quand ils existent:

- Preferences recherche: `PATCH /api/v1/user-profiles/me/` avec `age_min_preference`, `age_max_preference`, `distance_max_km`, `genders_sought`, `relationship_types_sought`.
- Visibilite: `PATCH /api/v1/user-profiles/me/` ou `PUT /api/v1/user-settings/privacy-preferences`.
- Photos: routes sous `/api/v1/user-profiles/me/photos/...`.
- Verification: workflow URL signee + soumission sous `/api/v1/user-profiles/me/verification/...`.
- Likes/premium: routes sous `/api/v1/user-profiles/...`.

## Matrice d'acces et confidentialite

| Ressource | Anonyme | Utilisateur authentifie | Proprietaire | Premium | Admin |
|---|---:|---:|---:|---:|---:|
| Mon profil | Non | Oui pour soi | Oui | N/A | Via admin Django seulement |
| Modifier mon profil | Non | Non pour autrui | Oui | N/A | Via admin Django seulement |
| Profil public visible | Non | Oui si non bloque | N/A | N/A | Via admin Django seulement |
| Photos du proprietaire | Non | Non pour autrui | CRUD partiel | Limite 6 uploads | Via admin Django |
| Likes recus | Non | 403 si non premium | Oui si premium | Oui | N/A |
| Verification documents | Non | Non pour autrui | Oui | N/A | Review via admin/model, pas endpoint public |
| Preferences user-settings | Non | Non pour autrui | Oui | N/A | N/A |
| Blocages | Non | Non pour autrui | Oui | N/A | N/A |

Donnees sensibles:

- Ne jamais stocker localement les documents de verification plus longtemps que necessaire.
- Les documents sont uploades via URL signee Firebase; les URLs signees expirent apres 30 minutes.
- Les chemins de documents (`file_path_on_storage`) ne doivent pas etre affiches a l'utilisateur.
- Les logs frontend ne doivent pas contenir `upload_url`, `file_path_on_storage`, JWT, documents, email ou donnees medicales.

## Recommandations d'architecture frontend

### Client API minimal

Prevoir des fonctions dediees:

- `getMyProfile()`
- `updateMyProfile(payload)`
- `uploadProfilePhoto(file, {isMain, caption})`
- `setMainProfilePhoto(photoId)`
- `deleteProfilePhoto(photoId)`
- `getVerificationStatus()`
- `generateVerificationUploadUrl(documentType, file)`
- `uploadFileToSignedUrl(uploadUrl, file, fileType)`
- `submitVerificationDocuments(documents, selfieCode)`
- `getPremiumProfileStatus()`
- `getLikesReceived(page)`
- `getSuperLikesReceived(page)`
- `getPrivacyPreferences()`
- `updatePrivacyPreferences(payload)`
- `getNotificationPreferences()`
- `updateNotificationPreferences(payload)`
- `getBlockedUsers()`
- `blockUser(userId)`
- `unblockUser(userId)`
- `requestAccountDeletion()`
- `requestDataExport()`

### Etat UI conseille

Conserver separement:

- `profile`: reponse complete `/me/`.
- `profileDraft`: payload plat editable.
- `photos`: derive de `profile.photos`, rafraichi apres mutations.
- `verification`: reponse `/me/verification/`.
- `premiumStatus`: reponse `/premium-status/`.
- `privacyPreferences`: reponse `/user-settings/privacy-preferences`.
- `notificationPreferences`: reponse `/user-settings/notification-preferences`.
- `blockedUsers`: reponse `/user-settings/blocks`.

Apres une mutation:

- `PATCH /me/`: refaire `GET /me/` ou merger les champs envoyes.
- Upload/set-main/delete photo: refaire `GET /me/`.
- Verification submit: refaire `GET /me/verification/` et `GET /me/`.
- Privacy PUT: refaire `GET /user-settings/privacy-preferences` et `GET /me/`.
- Notification PUT: remplacer localement par la reponse.
- Block/unblock: refaire `GET /user-settings/blocks`.

### Validation frontend a appliquer avant appel backend

- Bio <= 500 caracteres.
- Max 3 interets.
- Chaque interet <= 50 caracteres.
- Age min/max entre 18 et 99, min <= max.
- Distance entre 5 et 100 km.
- Photo: JPEG/JPG/PNG, <= 5 MB.
- Document verification: JPEG/JPG/PNG/PDF, <= 10 MB.
- Ne pas permettre plus de 1 photo non-premium ou 6 photos premium.
- Toujours envoyer `selfie_code_used` pour le selfie.

## Exemple sequence complete page Profil

1. Au montage de la page:
   - `GET /api/v1/user-profiles/me/`
   - `GET /api/v1/user-profiles/premium-status/`
   - `GET /api/v1/user-profiles/me/verification/`
2. Si l'utilisateur ouvre "Modifier":
   - Initialiser le formulaire avec les champs plats de `profile`.
   - Sauvegarder par `PATCH /api/v1/user-profiles/me/`.
   - Rafraichir `GET /api/v1/user-profiles/me/`.
3. Si l'utilisateur ajoute une photo:
   - Verifier limites premium.
   - `POST multipart /api/v1/user-profiles/me/photos/` avec `file`.
   - Rafraichir `GET /api/v1/user-profiles/me/`.
4. Si l'utilisateur lance la verification:
   - Afficher le `verification_code`.
   - Pour chaque document: generer URL signee, PUT vers Firebase, conserver `file_path_on_storage`.
   - Soumettre la liste via `/submit-documents/`.
   - Rafraichir verification.
5. Si l'utilisateur ouvre preferences:
   - Charger `privacy-preferences`, `notification-preferences`, `blocks`.
   - Sauvegarder chaque section via son endpoint dedie.

## Risques backend connus a integrer dans l'UX

- Plusieurs docs anciennes du repo sont obsoletes pour les profils. Se fier a ce document et au code source audite.
- Les endpoints `delete-account` et `export-data` ne font qu'accuser reception.
- La modification de `display_name`, `birth_date`, `email`, `phone_number` n'est pas exposee par `profiles/`.
- Les statistiques `profile_views` et `likes_received` existent en DB mais ne sont pas exposees par API profil.
- Le tri des likes recus n'est pas base sur la date de like.
- Les champs `verified_only` et `online_only` existent en DB mais ne sont pas exposables via `ProfileSerializer`/`ProfileCreateUpdateSerializer`.
- `distance_from_me_km` retourne actuellement `null` dans les serializers profil publics et prives.
- Le backend ne fournit pas de fallback image si `photos=[]`. Le frontend doit gerer un avatar placeholder local.
- Aucune route publique actuelle pour modifier l'ordre ou la legende d'une photo deja uploadee.

## Checklist d'implementation frontend

- Utiliser strictement `/api/v1/user-profiles/...` et `/api/v1/user-settings/...`.
- Implementer une page Profil capable d'afficher et modifier les champs plats reels du serializer.
- Gerer les photos avec `file` en multipart et rafraichissement apres mutation.
- Implementer le workflow verification en trois etapes: statut, URL signee + PUT Firebase, soumission.
- Afficher les sections premium avec degradation non-premium et CTA abonnement.
- Integrer les preferences confidentialite, notifications et blocages si elles sont dans la page Profil.
- Ne pas utiliser les endpoints obsoletes listes plus haut.
- Ne pas supposer que les reponses de mutation retournent toujours le profil complet.
- Prevoir placeholders pour distance `null`, photos vides et statistiques non exposees.
