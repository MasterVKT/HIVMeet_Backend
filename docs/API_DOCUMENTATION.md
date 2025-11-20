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

### POST `/api/v1/auth/register`
- **Description** : Crée un nouveau compte utilisateur
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
- **Description** : Échange un token Firebase contre des tokens JWT
- **Requête** :
  ```json
  { "firebase_token": "string" }
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
- **Description** : Enregistre le token FCM pour notifications push
- **Requête** : `{ "fcm_token": "string" }`
- **Réponse** (201) : `{ "message": "Token FCM enregistré" }`

---

## Profils Utilisateurs

### GET `/api/v1/user-profiles/me/`
- **Description** : Récupère le profil de l'utilisateur connecté
- **Réponse** (200) : Profil complet utilisateur

---

### PUT `/api/v1/user-profiles/me/`
- **Description** : Met à jour le profil utilisateur
- **Requête** : bio, birthdate, gender, location, preferences
- **Réponse** (200) : Profil mis à jour

---

### GET `/api/v1/user-profiles/{user_id}/`
- **Description** : Récupère le profil d'un autre utilisateur

---

### POST `/api/v1/user-profiles/me/photos/`
- **Description** : Upload d'une photo de profil (multipart/form-data)
- **Réponse** (201) : Détails de la photo

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
- **Description** : Statut de vérification

---

### POST `/api/v1/user-profiles/me/verification/generate-upload-url/`
- **Description** : Génère une URL signée d'upload de documents

---

### POST `/api/v1/user-profiles/me/verification/submit-documents/`
- **Description** : Soumet les documents de vérification

---

## Découverte et Matching

### GET `/api/v1/discovery/`
- **Description** : Profils recommandés pour découverte
- **Query** : `page`, `page_size`

---

### GET `/api/v1/discovery/profiles`
- **Description** : Alias de `/api/v1/discovery/`

---

### POST `/api/v1/discovery/interactions/like`
- **Description** : Like un profil
- **Requête** : `{ "target_user_id": "uuid" }`

---

### POST `/api/v1/discovery/interactions/dislike`
- **Description** : Dislike un profil

---

### POST `/api/v1/discovery/interactions/superlike`
- **Description** : Super-like (Premium)

---

### POST `/api/v1/discovery/interactions/rewind`
- **Description** : Annule le dernier swipe (Premium)

---

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
- **Description** : Supprime (unmatch) un match

---

## Messagerie

### GET `/api/v1/conversations/`
- **Description** : Liste des conversations

---

### GET `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : Messages d'une conversation

---

### POST `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : Envoi d'un message

---

### POST `/api/v1/conversations/{conversation_id}/messages/media/`
- **Description** : Envoi d'un média (Premium)

---

### PUT `/api/v1/conversations/{conversation_id}/messages/mark-as-read/`
- **Description** : Marque comme lus

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
- **Description** : Liste des plans

---

### GET `/api/v1/subscriptions/current/`
- **Description** : Abonnement actuel

---

### POST `/api/v1/subscriptions/purchase/`
- **Description** : Achète un abonnement

---

### POST `/api/v1/subscriptions/current/cancel/`
- **Description** : Annule l'abonnement courant

---

### POST `/api/v1/subscriptions/current/reactivate/`
- **Description** : Réactive l'abonnement

---

## Paramètres Utilisateur

### GET `/api/v1/user-settings/notification-preferences`
### PUT `/api/v1/user-settings/notification-preferences`

### GET `/api/v1/user-settings/privacy-preferences`
### PUT `/api/v1/user-settings/privacy-preferences`

### GET `/api/v1/user-settings/blocks`
### POST `/api/v1/user-settings/blocks/{user_id}`

### POST `/api/v1/user-settings/delete-account`

### GET `/api/v1/user-settings/export-data`

---

## Webhooks

### POST `/api/v1/webhooks/payments/mycoolpay/`
- **Description** : Webhook MyCoolPay

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
