# Documentation Complète des Endpoints - HIVMeet Backend

> **Archivage KYC v0 :** les sections historiques KYC de ce document ne sont
> pas contractuelles. Le seul contrat KYC est
> `docs/kyc/KYC_V1_CONTRACT.openapi.yaml`, complété par
> `docs/kyc/KYC_PHASE_0_GOVERNANCE.md`. En particulier,
> `generate-upload-url/` et `submit-documents/` retournent `410`
> `kyc_legacy_endpoint_deprecated`; aucun chemin de stockage, URL de lecture
> ou code selfie ne doit être implémenté à partir de ce document.

## Table des Matières
1. [Authentification](#authentification)
2. [Profils Utilisateurs](#profils-utilisateurs)
3. [Découverte et Matching](#découverte-et-matching)
4. [Messagerie](#messagerie)
5. [Appels](#appels)
6. [Ressources et Contenu](#ressources-et-contenu)
7. [Abonnements Premium](#abonnements-premium)
8. [Paramètres Utilisateur](#paramètres-utilisateur)
9. [Webhooks](#webhooks)
10. [Monitoring](#monitoring)
11. [Documentation API](#documentation-api)

---

## Authentification

### POST `/api/v1/auth/register`
- **Description** : Crée un nouveau compte utilisateur
- **Rôle** : Inscription d'un nouvel utilisateur dans l'application
- **Requête** :
  ```json
  {
    "email": "string",
    "password": "string",
    "username": "string",
    "birthdate": "YYYY-MM-DD",
    "gender": "string"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "user": {
      "id": "uuid",
      "email": "string",
      "username": "string",
      "created_at": "datetime"
    },
    "token": "jwt_token"
  }
  ```
- **Erreurs** :
  - 400 : Email déjà utilisé, données invalides

---

### GET `/api/v1/auth/verify-email/{verification_token}`
- **Description** : Vérifie l'email d'un utilisateur
- **Rôle** : Confirmation de l'adresse email lors de l'inscription
- **Requête** : Aucune (GET avec token dans l'URL)
- **Réponse** (200) :
  ```json
  {
    "verified": true,
    "message": "Email vérifié avec succès"
  }
  ```
- **Erreurs** :
  - 400 : Token invalide ou expiré

---

### POST `/api/v1/auth/login`
- **Description** : Authentifie un utilisateur avec email et mot de passe
- **Rôle** : Connexion utilisateur et génération de tokens
- **Requête** :
  ```json
  {
    "email": "string",
    "password": "string",
    "remember_me": false
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "token": "jwt_token",
    "refresh_token": "refresh_token",
    "user": {
      "id": "uuid",
      "email": "string",
      "username": "string"
    }
  }
  ```
- **Erreurs** :
  - 401 : Identifiants invalides

---

### POST `/api/v1/auth/firebase-exchange/`
- **Description** : Échange un token Firebase contre des tokens Django JWT
- **Rôle** : Intégration avec Firebase Authentication
- **Requête** :
  ```json
  {
    "firebase_token": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "token": "jwt_token",
    "refresh_token": "refresh_token",
    "user": {
      "id": "uuid",
      "email": "string",
      "username": "string"
    }
  }
  ```
- **Erreurs** :
  - 400 : Token Firebase invalide
  - 404 : Utilisateur non trouvé

---

### POST `/api/v1/auth/forgot-password`
- **Description** : Demande de réinitialisation de mot de passe
- **Rôle** : Envoi d'un email de réinitialisation
- **Requête** :
  ```json
  {
    "email": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "message": "Email de réinitialisation envoyé"
  }
  ```

---

### POST `/api/v1/auth/reset-password`
- **Description** : Réinitialise le mot de passe avec un token
- **Rôle** : Changement de mot de passe après demande de réinitialisation
- **Requête** :
  ```json
  {
    "token": "string",
    "new_password": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "message": "Mot de passe réinitialisé avec succès"
  }
  ```

---

### POST `/api/v1/auth/refresh-token`
- **Description** : Rafraîchit un token d'accès expiré
- **Rôle** : Renouvellement automatique des tokens
- **Requête** :
  ```json
  {
    "refresh_token": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "token": "new_jwt_token"
  }
  ```

---

### POST `/api/v1/auth/logout`
- **Description** : Déconnecte l'utilisateur
- **Rôle** : Invalidation des tokens et déconnexion
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "message": "Déconnexion réussie"
  }
  ```

---

### POST `/api/v1/auth/fcm-token`
- **Description** : Enregistre le token FCM pour les notifications push
- **Rôle** : Configuration des notifications push
- **Requête** :
  ```json
  {
    "fcm_token": "string"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "message": "Token FCM enregistré"
  }
  ```

---

## Profils Utilisateurs

### GET `/api/v1/user-profiles/me/`
- **Description** : Récupère le profil de l'utilisateur connecté
- **Rôle** : Affichage du profil personnel
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "id": "uuid",
    "user": {
      "id": "uuid",
      "email": "string",
      "username": "string"
    },
    "bio": "string",
    "birthdate": "YYYY-MM-DD",
    "gender": "string",
    "photos": [
      {
        "id": "uuid",
        "url": "string",
        "is_main": true
      }
    ],
    "location": {
      "latitude": 0.0,
      "longitude": 0.0,
      "city": "string"
    },
    "preferences": {
      "age_min": 18,
      "age_max": 50,
      "gender_preference": "string",
      "distance_max": 50
    }
  }
  ```

---

### PUT `/api/v1/user-profiles/me/`
- **Description** : Met à jour le profil de l'utilisateur connecté
- **Rôle** : Modification des informations personnelles
- **Requête** :
  ```json
  {
    "bio": "string",
    "birthdate": "YYYY-MM-DD",
    "gender": "string",
    "location": {
      "latitude": 0.0,
      "longitude": 0.0
    },
    "preferences": {
      "age_min": 18,
      "age_max": 50,
      "gender_preference": "string",
      "distance_max": 50
    }
  }
  ```
- **Réponse** (200) : Même format que GET

---

### GET `/api/v1/user-profiles/{user_id}/`
- **Description** : Récupère le profil d'un autre utilisateur
- **Rôle** : Affichage des profils dans la découverte
- **Requête** : Aucune
- **Réponse** (200) : Même format que GET /me/ (avec restrictions selon les paramètres de confidentialité)

---

### POST `/api/v1/user-profiles/me/photos/`
- **Description** : Upload d'une nouvelle photo
- **Rôle** : Ajout de photos au profil
- **Requête** : FormData avec fichier image
- **Réponse** (201) :
  ```json
  {
    "id": "uuid",
    "url": "string",
    "is_main": false
  }
  ```

---

### PUT `/api/v1/user-profiles/me/photos/{photo_id}/set-main/`
- **Description** : Définit une photo comme photo principale
- **Rôle** : Sélection de la photo de profil principale
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "message": "Photo principale mise à jour"
  }
  ```

---

### DELETE `/api/v1/user-profiles/me/photos/{photo_id}/`
- **Description** : Supprime une photo
- **Rôle** : Gestion des photos du profil
- **Requête** : Aucune
- **Réponse** (204) : Aucun contenu

---

### GET `/api/v1/user-profiles/likes-received/`
- **Description** : Liste des likes reçus (Premium)
- **Rôle** : Fonctionnalité premium pour voir qui vous a liké
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "likes": [
      {
        "user": {
          "id": "uuid",
          "username": "string",
          "photos": []
        },
        "liked_at": "datetime"
      }
    ]
  }
  ```

---

### GET `/api/v1/user-profiles/super-likes-received/`
- **Description** : Liste des super-likes reçus (Premium)
- **Rôle** : Fonctionnalité premium pour voir les super-likes
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "super_likes": [
      {
        "user": {
          "id": "uuid",
          "username": "string",
          "photos": []
        },
        "super_liked_at": "datetime"
      }
    ]
  }
  ```

---

### GET `/api/v1/user-profiles/premium-status/`
- **Description** : Statut des fonctionnalités premium
- **Rôle** : Vérification des fonctionnalités disponibles
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "is_premium": true,
    "features": {
      "rewind": true,
      "super_like": true,
      "boost": true,
      "see_likes": true
    },
    "subscription": {
      "plan": "string",
      "expires_at": "datetime"
    }
  }
  ```

---

### GET `/api/v1/user-profiles/me/verification/`
- **Description** : Statut de vérification du profil
- **Rôle** : Gestion de la vérification d'identité
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "is_verified": false,
    "verification_status": "pending",
    "submitted_at": "datetime"
  }
  ```

---

### POST `/api/v1/user-profiles/me/verification/generate-upload-url/`
- **Description** : Génère une URL d'upload pour les documents de vérification
- **Rôle** : Préparation de l'upload de documents
- **Requête** :
  ```json
  {
    "document_type": "identity_card"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "upload_url": "string",
    "expires_at": "datetime"
  }
  ```

---

### POST `/api/v1/user-profiles/me/verification/submit-documents/`
- **Description** : Soumet les documents de vérification
- **Rôle** : Finalisation de la vérification d'identité
- **Requête** :
  ```json
  {
    "document_urls": ["url1", "url2"]
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "message": "Documents soumis pour vérification"
  }
  ```

---

## Découverte et Matching

### GET `/api/v1/discovery/profiles`
- **Description** : Liste des profils recommandés pour la découverte
- **Rôle** : Affichage des profils à swiper
- **Query Parameters** :
  - `page` : Numéro de page (défaut: 1)
  - `page_size` : Taille de page (défaut: 10, max: 50)
- **Réponse** (200) :
  ```json
  {
    "count": 100,
    "next": "?page=2",
    "previous": null,
    "results": [
      {
        "id": "uuid",
        "user": {
          "id": "uuid",
          "username": "string"
        },
        "bio": "string",
        "age": 25,
        "distance": 5.2,
        "photos": [
          {
            "id": "uuid",
            "url": "string",
            "is_main": true
          }
        ],
        "last_active": "datetime"
      }
    ]
  }
  ```

---

### POST `/api/v1/discovery/interactions/like`
- **Description** : Like un profil
- **Rôle** : Interaction positive avec un profil
- **Requête** :
  ```json
  {
    "target_user_id": "uuid"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "is_match": true,
    "match": {
      "id": "uuid",
      "user": {
        "id": "uuid",
        "username": "string"
      }
    }
  }
  ```

---

### POST `/api/v1/discovery/interactions/dislike`
- **Description** : Dislike un profil
- **Rôle** : Interaction négative avec un profil
- **Requête** :
  ```json
  {
    "target_user_id": "uuid"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "message": "Profil disliké"
  }
  ```

---

### POST `/api/v1/discovery/interactions/superlike`
- **Description** : Super-like un profil (Premium)
- **Rôle** : Fonctionnalité premium pour attirer l'attention
- **Requête** :
  ```json
  {
    "target_user_id": "uuid"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "is_match": true,
    "match": {
      "id": "uuid",
      "user": {
        "id": "uuid",
        "username": "string"
      }
    }
  }
  ```

---

### POST `/api/v1/discovery/interactions/rewind`
- **Description** : Annule le dernier swipe (Premium)
- **Rôle** : Fonctionnalité premium pour corriger une erreur
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "profile": {
      "id": "uuid",
      "user": {
        "id": "uuid",
        "username": "string"
      }
    }
  }
  ```

---

### GET `/api/v1/discovery/interactions/liked-me`
- **Description** : Liste des utilisateurs qui vous ont liké (Premium)
- **Rôle** : Fonctionnalité premium pour voir les likes reçus
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "likes": [
      {
        "user": {
          "id": "uuid",
          "username": "string",
          "photos": []
        },
        "liked_at": "datetime"
      }
    ]
  }
  ```

---

### POST `/api/v1/discovery/boost/activate`
- **Description** : Active le boost de profil (Premium)
- **Rôle** : Fonctionnalité premium pour augmenter la visibilité
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "message": "Boost activé",
    "expires_at": "datetime"
  }
  ```

---

### GET `/api/v1/matches/`
- **Description** : Liste des matches
- **Rôle** : Affichage des connexions établies
- **Query Parameters** :
  - `page` : Numéro de page
  - `page_size` : Taille de page
- **Réponse** (200) :
  ```json
  {
    "count": 10,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "uuid",
        "user": {
          "id": "uuid",
          "username": "string",
          "photos": []
        },
        "matched_at": "datetime",
        "last_message": {
          "content": "string",
          "sent_at": "datetime"
        }
      }
    ]
  }
  ```

---

### DELETE `/api/v1/matches/{match_id}`
- **Description** : Supprime un match (unmatch)
- **Rôle** : Suppression d'une connexion établie
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "message": "Match supprimé"
  }
  ```

---

## Messagerie

> Section réécrite le 2026-07-31 d'après le code (`messaging/views.py`,
> `messaging/serializers.py`, `messaging/urls.py`). Les réponses de liste sont
> paginées au format DRF standard `{count, next, previous, results}` — il n'y a
> **pas** d'enveloppe `{"conversations": [...]}` ni `{"messages": [...]}`.

### GET `/api/v1/conversations/`
- **Description** : Liste paginée des conversations
- **Rôle** : Affichage de la liste des conversations
- **Query Parameters** :
  - `status` : `all` (défaut) | `unread` | `archived`. Toute autre valeur → **400**.
    `archived` renvoie une liste vide (archivage non persisté).
  - `page` : défaut `1`
  - `page_size` : défaut `20`, max `50`
- **Réponse** (200) :
  ```json
  {
    "count": 5,
    "next": "http://.../api/v1/conversations/?page=2",
    "previous": null,
    "results": [
      {
        "conversation_id": "uuid",
        "id": "uuid",
        "other_user": {
          "user_id": "uuid",
          "display_name": "string",
          "main_photo_url": "string|null",
          "is_online": true,
          "last_active": "datetime"
        },
        "last_message": {
          "message_id": "uuid",
          "content_preview": "string",
          "sender_id": "uuid",
          "sent_at": "datetime",
          "is_read_by_me": false
        },
        "unread_count_for_me": 3,
        "created_at": "datetime",
        "last_message_at": "datetime",
        "last_activity_at": "datetime"
      }
    ]
  }
  ```
  Le champ de non-lus s'appelle `unread_count_for_me` (pas `unread_count`).

---

### GET `/api/v1/conversations/unread-count/`
- **Description** : Total de messages non lus, toutes conversations confondues
- **Rôle** : Badge global de l'onglet Messages
- **Query Parameters** : aucun
- **Réponse** (200) :
  ```json
  {
    "unread_count": 7
  }
  ```
  Somme calculée côté serveur sur **toutes** les conversations actives et non
  masquées — contrairement à une somme faite sur la première page de
  `GET /api/v1/conversations/`, qui plafonne à `page_size`.

---

### DELETE `/api/v1/conversations/{conversation_id}/`
- **Description** : Masque la conversation pour le participant appelant
- **Rôle** : « Supprimer » une conversation côté utilisateur uniquement
- **Réponse** (204) : Aucun contenu. Idempotent.
  La conversation redevient visible à la réception d'un nouveau message.

---

### GET `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : Récupère les messages d'une conversation (curseur)
- **Rôle** : Affichage de l'historique des messages
- **Query Parameters** :
  - `limit` : défaut `50`, max `50` (alias accepté : `page_size`)
  - `before_message_id` : curseur UUID. Curseur inconnu → **400**.
- **Réponse** (200) :
  ```json
  {
    "count": 120,
    "next": "?before_message_id=uuid&limit=50",
    "previous": null,
    "results": [
      {
        "message_id": "uuid",
        "id": "uuid",
        "client_message_id": "string",
        "conversation_id": "uuid",
        "sender_id": "uuid",
        "is_mine": true,
        "content": "string",
        "message_type": "text",
        "media_url": "string|null",
        "media_type": "image|video|audio|null",
        "media_thumbnail_url": "string|null",
        "status": "sent|delivered|read",
        "sent_at": "datetime",
        "created_at": "datetime",
        "delivered_at": "datetime|null",
        "read_at": "datetime|null",
        "read_at_by_recipient": "datetime|null",
        "is_sending": false
      }
    ],
    "has_more": true,
    "show_premium_prompt": false
  }
  ```
  Les messages sont triés du plus récent au plus ancien. Un `GET` ne modifie
  jamais l'état de lecture.

---

### POST `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : Envoie un message texte
- **Rôle** : Envoi de messages texte
- **Requête** :
  ```json
  {
    "client_message_id": "string (requis, max 100)",
    "content": "string (requis, max 1000)",
    "type": "text"
  }
  ```
  `type` autre que `text` → **400** (les médias passent par l'endpoint multipart).
  Un `client_message_id` déjà utilisé renvoie le message existant (idempotence).
- **Réponse** (201) : l'objet message complet, au format décrit ci-dessus
  (pas d'enveloppe `{"message": {...}}`).

---

### POST `/api/v1/conversations/{conversation_id}/messages/media/`
- **Description** : Envoie un message média (Premium)
- **Rôle** : Fonctionnalité premium pour envoyer photos/vidéos/audio
- **Requête** : `multipart/form-data`
  - `media_file` : fichier, max 10 Mo
  - `media_type` : `image` (défaut) | `video` | `audio`
  - `text` : légende optionnelle, max 500
  - `client_message_id` : optionnel
- **Réponse** (201) : l'objet message complet
- **Erreurs** : **403** si non premium, **400** si fichier invalide

---

### PUT `/api/v1/conversations/{conversation_id}/messages/mark-as-read/`
- **Description** : Marque comme lus les messages entrants jusqu'à un curseur
- **Rôle** : Mise à jour du statut de lecture
- **Requête** :
  ```json
  {
    "last_read_message_id": "uuid (optionnel)"
  }
  ```
  Il n'y a **pas** de paramètre `message_ids`. Sans `last_read_message_id`,
  tous les messages entrants non lus sont marqués. Un curseur qui n'est pas un
  message entrant de cette conversation → **400**.
- **Réponse** (200) :
  ```json
  {
    "messages_marked": 3,
    "unread_count_for_me": 0,
    "read_at": "datetime"
  }
  ```
  `read_at` n'est présent que si `messages_marked > 0`.

---

### PUT `/api/v1/conversations/{conversation_id}/messages/{message_id}/read/`
- **Description** : Marque un seul message entrant comme lu
- **Réponse** (200) :
  ```json
  {
    "message": "Message marked as read",
    "messages_marked": 1,
    "unread_count_for_me": 0,
    "read_at": "datetime"
  }
  ```

---

### DELETE `/api/v1/conversations/{conversation_id}/messages/{message_id}/`
- **Description** : Supprime un message (soft delete, côté appelant seulement)
- **Rôle** : Gestion des messages envoyés
- **Requête** : Aucune
- **Réponse** (204) : Aucun contenu
- **Erreurs** : **403** si l'appelant n'est pas participant

---

### POST `/api/v1/conversations/{conversation_id}/typing/`
- **Description** : Signale que l'utilisateur est en train d'écrire
- **Requête** :
  ```json
  {
    "is_typing": true
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "is_typing": true
  }
  ```
  Diffuse également `typing.indicator` au groupe WebSocket de la conversation.
  Le frontend privilégie la voie WebSocket (`typing.start` / `typing.stop`).

---

### GET `/api/v1/conversations/{conversation_id}/presence/`
- **Description** : État de présence de l'autre participant
- **Réponse** (200) :
  ```json
  {
    "participant": {
      "user_id": "uuid",
      "is_online": true,
      "last_active": "datetime",
      "is_typing": false
    }
  }
  ```
  `is_online` est vrai si `last_active` date de moins de 5 minutes.

---

### WebSocket

Deux canaux, documentés en détail dans
`docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` :

| Canal | Portée | Événements serveur → client |
|---|---|---|
| `/ws/conversations/{conversation_id}/` | une conversation ouverte | `message.created`, `message.read`, `message.delivered`, `typing.indicator`, `presence.update`, `incoming_call`, `call_update`, `ice.candidate`, `webrtc.offer`, `webrtc.answer`, `pong`, `error` |
| `/ws/notifications/` | toute la session | `new_match`, `like`, `super_like`, `new_message`, `message_read`, `message_delivered`, `incoming_call`, `call_update`, `pong`, `error` |

Auth : header `Authorization: Bearer <jwt>` ou fallback `?token=<jwt>`.
Le JWT n'est validé qu'à la connexion (pas de refresh in-band) : le client doit
se reconnecter avec un token frais à l'expiration.

`new_message` est livré à la fois par WebSocket et par push FCM : dédupliquer
sur `message_id` (le `notification_id` FCM vaut `msg_<message_id>`).

---

## Appels

### POST `/api/v1/calls/initiate`
- **Description** : Initie un appel
- **Rôle** : Démarrage d'un appel audio/vidéo
- **Requête** :
  ```json
  {
    "target_user_id": "uuid",
    "call_type": "audio"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "call": {
      "id": "uuid",
      "call_type": "audio",
      "status": "initiating",
      "created_at": "datetime"
    }
  }
  ```

---

### POST `/api/v1/calls/{call_id}/answer`
- **Description** : Répond à un appel
- **Rôle** : Acceptation d'un appel entrant
- **Requête** :
  ```json
  {
    "answer": true
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "call": {
      "id": "uuid",
      "status": "active"
    }
  }
  ```

---

### POST `/api/v1/calls/{call_id}/ice-candidate`
- **Description** : Ajoute un candidat ICE pour WebRTC
- **Rôle** : Configuration de la connexion WebRTC
- **Requête** :
  ```json
  {
    "candidate": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "message": "Candidat ICE ajouté"
  }
  ```

---

### POST `/api/v1/calls/{call_id}/terminate`
- **Description** : Termine un appel
- **Rôle** : Fin d'un appel en cours
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "message": "Appel terminé"
  }
  ```

---

### POST `/api/v1/calls/initiate-premium/`
- **Description** : Initie un appel premium (Premium)
- **Rôle** : Fonctionnalité premium pour appels haute qualité
- **Requête** :
  ```json
  {
    "target_user_id": "uuid",
    "call_type": "video"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "call": {
      "id": "uuid",
      "call_type": "video",
      "status": "initiating",
      "premium_features": true
    }
  }
  ```

---

## Ressources et Contenu

### GET `/api/v1/content/resource-categories`
- **Description** : Liste des catégories de ressources
- **Rôle** : Affichage des catégories disponibles
- **Réponse** (200) :
  ```json
  {
    "categories": [
      {
        "id": "uuid",
        "name": "string",
        "description": "string",
        "icon": "string"
      }
    ]
  }
  ```

---

### GET `/api/v1/content/resources`
- **Description** : Liste des ressources
- **Rôle** : Affichage du contenu éducatif
- **Query Parameters** :
  - `category_id` : Filtre par catégorie
  - `search` : Recherche textuelle
- **Réponse** (200) :
  ```json
  {
    "resources": [
      {
        "id": "uuid",
        "title": "string",
        "content": "string",
        "category": {
          "id": "uuid",
          "name": "string"
        },
        "created_at": "datetime",
        "is_favorite": false
      }
    ]
  }
  ```

---

### GET `/api/v1/content/resources/{resource_id}`
- **Description** : Détails d'une ressource
- **Rôle** : Affichage du contenu complet d'une ressource
- **Réponse** (200) :
  ```json
  {
    "id": "uuid",
    "title": "string",
    "content": "string",
    "category": {
      "id": "uuid",
      "name": "string"
    },
    "created_at": "datetime",
    "is_favorite": false,
    "related_resources": []
  }
  ```

---

### POST `/api/v1/content/resources/{resource_id}/favorite`
- **Description** : Ajoute/retire une ressource des favoris
- **Rôle** : Gestion des ressources favorites
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "is_favorite": true,
    "message": "Ressource ajoutée aux favoris"
  }
  ```

---

### GET `/api/v1/content/favorites`
- **Description** : Liste des ressources favorites
- **Rôle** : Affichage des ressources sauvegardées
- **Réponse** (200) :
  ```json
  {
    "favorites": [
      {
        "id": "uuid",
        "title": "string",
        "category": {
          "id": "uuid",
          "name": "string"
        },
        "added_at": "datetime"
      }
    ]
  }
  ```

---

### POST `/api/v1/feed/posts`
- **Description** : Crée un nouveau post dans le feed
- **Rôle** : Publication de contenu communautaire
- **Requête** :
  ```json
  {
    "content": "string",
    "media_urls": ["url1", "url2"]
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "post": {
      "id": "uuid",
      "content": "string",
      "author": {
        "id": "uuid",
        "username": "string"
      },
      "created_at": "datetime",
      "likes_count": 0,
      "comments_count": 0
    }
  }
  ```

---

### GET `/api/v1/feed/posts`
- **Description** : Liste des posts du feed
- **Rôle** : Affichage du contenu communautaire
- **Query Parameters** :
  - `page` : Numéro de page
  - `page_size` : Taille de page
- **Réponse** (200) :
  ```json
  {
    "posts": [
      {
        "id": "uuid",
        "content": "string",
        "author": {
          "id": "uuid",
          "username": "string"
        },
        "created_at": "datetime",
        "likes_count": 5,
        "comments_count": 2,
        "is_liked": false
      }
    ]
  }
  ```

---

### POST `/api/v1/feed/posts/{post_id}/like`
- **Description** : Like/unlike un post
- **Rôle** : Interaction avec le contenu communautaire
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "is_liked": true,
    "likes_count": 6
  }
  ```

---

### POST `/api/v1/feed/posts/{post_id}/comments`
- **Description** : Ajoute un commentaire à un post
- **Rôle** : Interaction avec le contenu communautaire
- **Requête** :
  ```json
  {
    "content": "string"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "comment": {
      "id": "uuid",
      "content": "string",
      "author": {
        "id": "uuid",
        "username": "string"
      },
      "created_at": "datetime"
    }
  }
  ```

---

### GET `/api/v1/feed/posts/{post_id}/comments`
- **Description** : Liste des commentaires d'un post
- **Rôle** : Affichage des commentaires
- **Réponse** (200) :
  ```json
  {
    "comments": [
      {
        "id": "uuid",
        "content": "string",
        "author": {
          "id": "uuid",
          "username": "string"
        },
        "created_at": "datetime"
      }
    ]
  }
  ```

---

## Abonnements Premium

### GET `/api/v1/subscriptions/plans/`
- **Description** : Liste paginée des deux plans actifs (`hivmeet_monthly`
  à 7,99 EUR et `hivmeet_annual` à 57,99 EUR)
- **Rôle** : Affichage des options premium
- **Réponse** (200) :
  ```json
  {
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
      {
        "plan_id": "hivmeet_monthly",
        "name": "Abonnement Mensuel",
        "description": "Accès complet aux fonctionnalités Premium pendant un mois",
        "price": "7.99",
        "currency": "EUR",
        "base_price": "7.99",
        "base_currency": "EUR",
        "billing_interval": "month",
        "monthly_equivalent": "7.99",
        "savings_percentage": 0,
        "recommended": false,
        "features": {
          "unlimited_likes": true,
          "can_see_likers": true,
          "can_rewind": true,
          "daily_rewinds_count": 5
        }
      }
    ]
  }
  ```

---

### GET `/api/v1/subscriptions/payment-capabilities/`
- **Description** : Disponibilité sûre de MyCoolPay et devises activées
- **Authentification** : Bearer JWT requis
- **Réponse** (200) :
  ```json
  {
    "provider": "mycoolpay",
    "available": true,
    "callback_verification_available": true,
    "enabled_currencies": ["XAF", "EUR"],
    "default_currency": "XAF",
    "effective_currency": "XAF"
  }
  ```

---

### GET `/api/v1/subscriptions/current/`
- **Description** : Abonnement actuel de l'utilisateur
- **Rôle** : Affichage du statut d'abonnement
- **Réponse** (200) :
  ```json
  {
    "subscription_id": "provider-reference",
    "plan_id": "hivmeet_monthly",
    "plan_name": "Abonnement Mensuel",
    "status": "active",
    "current_period_start": "datetime",
    "current_period_end": "datetime",
    "auto_renew": true,
    "cancel_at_period_end": false,
    "features_summary": { "daily_rewinds_count": 5 }
  }
  ```

---

### POST `/api/v1/subscriptions/purchase/`
- **Description** : Achète un abonnement
- **Rôle** : Processus d'achat premium
- **Header recommandé** : `Idempotency-Key` (8 à 64 caractères sûrs)
- **Requête** :
  ```json
  {
    "plan_id": "hivmeet_monthly",
    "phone_number": "+237699009900",
    "language": "fr"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "payment_id": "uuid",
    "payment_url": "https://my-coolpay.com/payment/checkout/...",
    "payment_status": "pending",
    "amount": "5241",
    "currency": "XAF",
    "idempotent_replay": false
  }
  ```

Une répétition avec la même clé et le même plan renvoie la transaction
existante en 200. Une réutilisation pour un autre plan renvoie 409.

---

### GET `/api/v1/subscriptions/payments/{payment_id}/`
- **Description** : Statut backend authentifié d'une transaction MyCoolPay
- **Réponse** (200) :
  ```json
  {
    "payment_id": "uuid",
    "payment_status": "succeeded",
    "fulfilled": true,
    "subscription_id": "provider-reference",
    "activated_at": "datetime",
    "subscription": {
      "subscription_id": "provider-reference",
      "plan_id": "hivmeet_monthly",
      "status": "active",
      "current_period_start": "datetime",
      "current_period_end": "datetime"
    }
  }
  ```

---

### POST `/api/v1/subscriptions/current/cancel/`
- **Description** : Annule l'abonnement actuel
- **Rôle** : Gestion de l'abonnement
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "message": "Abonnement annulé",
    "expires_at": "datetime"
  }
  ```

---

### POST `/api/v1/subscriptions/current/reactivate/`
- **Description** : Réactive l'abonnement
- **Rôle** : Gestion de l'abonnement
- **Requête** : Aucune
- **Réponse** (200) :
  ```json
  {
    "message": "Abonnement réactivé",
    "expires_at": "datetime"
  }
  ```

---

### POST `/api/v1/subscriptions/current/modify/`
- **Description** : Modifie l'abonnement actuel (changement de plan / upgrade / downgrade)
- **Rôle** : Gestion de l'abonnement
- **Authentification** : Bearer JWT requis
- **Headers** : `Accept-Language: fr|en`
- **Requête** :
  ```json
  {
    "new_plan_id": "hivmeet_annual",
    "proration": true
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "subscription_id": "sub_external_id",
    "plan_id": "hivmeet_annual",
    "plan_name": "HIVMeet Premium Annuel",
    "status": "active",
    "current_period_start": "datetime",
    "current_period_end": "datetime",
    "auto_renew": true,
    "cancel_at_period_end": false,
    "features_summary": { ... },
    "proration": {
      "credit_amount": 3.50,
      "charge_amount": 0.00,
      "currency": "EUR",
      "prorated_period_start": "datetime",
      "prorated_period_end": "datetime"
    }
  }
  ```
- **Erreurs** :
  - 400 `invalid_plan` — plan introuvable ou inactif
  - 400 `no_active_subscription` — pas d'abonnement actif
  - 400 `same_plan` — même plan que le courant
  - 402 `payment_required` — paiement requis et moyen de paiement invalide
  - 401 — non authentifié

---

## Paramètres Utilisateur

### GET `/api/v1/user-settings/notification-preferences`
- **Description** : Préférences de notification
- **Rôle** : Configuration des notifications
- **Réponse** (200) :
  ```json
  {
    "notifications": {
      "new_matches": true,
      "new_messages": true,
      "likes": true,
      "super_likes": true,
      "promotional": false
    }
  }
  ```

---

### PUT `/api/v1/user-settings/notification-preferences`
- **Description** : Met à jour les préférences de notification
- **Rôle** : Configuration des notifications
- **Requête** :
  ```json
  {
    "notifications": {
      "new_matches": true,
      "new_messages": true,
      "likes": true,
      "super_likes": true,
      "promotional": false
    }
  }
  ```
- **Réponse** (200) : Même format que GET

---

### GET `/api/v1/user-settings/privacy-preferences`
- **Description** : Préférences de confidentialité
- **Rôle** : Configuration de la confidentialité
- **Réponse** (200) :
  ```json
  {
    "privacy": {
      "profile_visibility": "public",
      "show_online_status": true,
      "show_last_active": true,
      "allow_messages_from": "matches_only"
    }
  }
  ```

---

### PUT `/api/v1/user-settings/privacy-preferences`
- **Description** : Met à jour les préférences de confidentialité
- **Rôle** : Configuration de la confidentialité
- **Requête** :
  ```json
  {
    "privacy": {
      "profile_visibility": "public",
      "show_online_status": true,
      "show_last_active": true,
      "allow_messages_from": "matches_only"
    }
  }
  ```
- **Réponse** (200) : Même format que GET

---

### GET `/api/v1/user-settings/blocks`
- **Description** : Liste des utilisateurs bloqués
- **Rôle** : Gestion des utilisateurs bloqués
- **Réponse** (200) :
  ```json
  {
    "blocked_users": [
      {
        "id": "uuid",
        "username": "string",
        "blocked_at": "datetime"
      }
    ]
  }
  ```

---

### POST `/api/v1/user-settings/blocks/{user_id}`
- **Description** : Bloque/débloque un utilisateur
- **Rôle** : Gestion des utilisateurs bloqués
- **Requête** :
  ```json
  {
    "action": "block"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "message": "Utilisateur bloqué"
  }
  ```

---

### POST `/api/v1/user-settings/delete-account`
- **Description** : Supprime le compte utilisateur
- **Rôle** : Suppression définitive du compte
- **Requête** :
  ```json
  {
    "password": "string",
    "reason": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "message": "Compte supprimé"
  }
  ```

---

### GET `/api/v1/user-settings/export-data`
- **Description** : Exporte les données personnelles
- **Rôle** : Conformité RGPD
- **Réponse** (200) :
  ```json
  {
    "download_url": "string",
    "expires_at": "datetime"
  }
  ```

---

## Webhooks

### POST `/api/v1/webhooks/payments/mycoolpay/`
- **Description** : Webhook pour les notifications de paiement MyCoolPay
- **Rôle** : Traitement des notifications de paiement
- **Requête** : Format spécifique MyCoolPay
- **Réponse** (200) :
  ```json
  {
    "status": "processed"
  }
  ```

---

## Monitoring

### GET `/health/`
- **Description** : Vérification de santé complète de l'application
- **Rôle** : Monitoring de l'état du système
- **Réponse** (200) :
  ```json
  {
    "status": "healthy",
    "timestamp": "datetime",
    "services": {
      "database": "healthy",
      "cache": "healthy",
      "firebase": "healthy"
    }
  }
  ```

---

### GET `/health/simple/`
- **Description** : Vérification de santé simple
- **Rôle** : Health check rapide
- **Réponse** (200) :
  ```json
  {
    "status": "ok"
  }
  ```

---

### GET `/health/ready/`
- **Description** : Vérification de disponibilité
- **Rôle** : Readiness check pour Kubernetes
- **Réponse** (200) :
  ```json
  {
    "ready": true
  }
  ```

---

### GET `/metrics/`
- **Description** : Métriques de l'application
- **Rôle** : Monitoring des performances
- **Réponse** (200) :
  ```json
  {
    "active_users": 1500,
    "total_matches": 25000,
    "messages_sent": 100000,
    "system_uptime": 86400
  }
  ```

---

## Documentation API

### GET `/swagger/`
- **Description** : Documentation Swagger de l'API
- **Rôle** : Interface de documentation interactive
- **Réponse** : Page HTML Swagger UI

---

### GET `/redoc/`
- **Description** : Documentation ReDoc de l'API
- **Rôle** : Interface de documentation alternative
- **Réponse** : Page HTML ReDoc

---

## Codes d'Erreur Communs

### 400 - Bad Request
```json
{
  "error": true,
  "message": "Description de l'erreur",
  "details": {
    "field": ["Erreur spécifique"]
  }
}
```

### 401 - Unauthorized
```json
{
  "error": true,
  "message": "Token d'authentification invalide ou manquant"
}
```

### 403 - Forbidden
```json
{
  "error": true,
  "message": "Accès refusé - Fonctionnalité premium requise"
}
```

### 404 - Not Found
```json
{
  "error": true,
  "message": "Ressource non trouvée"
}
```

### 500 - Internal Server Error
```json
{
  "error": true,
  "message": "Erreur interne du serveur"
}
```

---

## Authentification

Tous les endpoints (sauf ceux d'authentification) nécessitent un header d'autorisation :

```
Authorization: Bearer <jwt_token>
```

## Pagination

Les endpoints de liste utilisent la pagination avec les paramètres :
- `page` : Numéro de page (défaut: 1)
- `page_size` : Taille de page (défaut: 10, max: 50)

Format de réponse paginée :
```json
{
  "count": 100,
  "next": "?page=2",
  "previous": null,
  "results": [...]
}
```

## Internationalisation

L'API supporte l'internationalisation avec le header :
```
Accept-Language: fr
```

Les messages d'erreur et les contenus sont traduits selon la langue demandée.

---

*Documentation générée le : 2024-12-19*
*Version de l'API : v1*
