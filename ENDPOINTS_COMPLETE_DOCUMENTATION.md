# Documentation Complète des Endpoints - HIVMeet Backend

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

### GET `/api/v1/conversations/`
- **Description** : Liste des conversations
- **Rôle** : Affichage de la liste des conversations
- **Query Parameters** :
  - `status` : Statut des conversations (archived, etc.)
- **Réponse** (200) :
  ```json
  {
    "conversations": [
      {
        "id": "uuid",
        "match": {
          "id": "uuid",
          "user": {
            "id": "uuid",
            "username": "string",
            "photos": []
          }
        },
        "last_message": {
          "content": "string",
          "sent_at": "datetime",
          "sender_id": "uuid"
        },
        "unread_count": 3
      }
    ]
  }
  ```

---

### GET `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : Récupère les messages d'une conversation
- **Rôle** : Affichage de l'historique des messages
- **Query Parameters** :
  - `limit` : Nombre de messages (défaut: 50)
  - `before_message_id` : ID du message pour la pagination
- **Réponse** (200) :
  ```json
  {
    "messages": [
      {
        "id": "uuid",
        "content": "string",
        "sender_id": "uuid",
        "sent_at": "datetime",
        "is_read": true,
        "media_url": "string"
      }
    ]
  }
  ```

---

### POST `/api/v1/conversations/{conversation_id}/messages/`
- **Description** : Envoie un message dans une conversation
- **Rôle** : Envoi de messages texte
- **Requête** :
  ```json
  {
    "content": "string"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "message": {
      "id": "uuid",
      "content": "string",
      "sender_id": "uuid",
      "sent_at": "datetime",
      "is_read": false
    }
  }
  ```

---

### POST `/api/v1/conversations/{conversation_id}/messages/media/`
- **Description** : Envoie un message média (Premium)
- **Rôle** : Fonctionnalité premium pour envoyer photos/vidéos
- **Requête** : FormData avec fichier média
- **Réponse** (201) :
  ```json
  {
    "message": {
      "id": "uuid",
      "content": "string",
      "media_url": "string",
      "sender_id": "uuid",
      "sent_at": "datetime"
    }
  }
  ```

---

### PUT `/api/v1/conversations/{conversation_id}/messages/mark-as-read/`
- **Description** : Marque les messages comme lus
- **Rôle** : Mise à jour du statut de lecture
- **Requête** :
  ```json
  {
    "message_ids": ["uuid1", "uuid2"]
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "message": "Messages marqués comme lus"
  }
  ```

---

### DELETE `/api/v1/conversations/{conversation_id}/messages/{message_id}/`
- **Description** : Supprime un message
- **Rôle** : Gestion des messages envoyés
- **Requête** : Aucune
- **Réponse** (204) : Aucun contenu

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
- **Description** : Liste des plans d'abonnement disponibles
- **Rôle** : Affichage des options premium
- **Réponse** (200) :
  ```json
  {
    "plans": [
      {
        "id": "uuid",
        "name": "string",
        "description": "string",
        "price": 9.99,
        "currency": "EUR",
        "duration_days": 30,
        "features": [
          "rewind",
          "super_like",
          "boost"
        ]
      }
    ]
  }
  ```

---

### GET `/api/v1/subscriptions/current/`
- **Description** : Abonnement actuel de l'utilisateur
- **Rôle** : Affichage du statut d'abonnement
- **Réponse** (200) :
  ```json
  {
    "subscription": {
      "id": "uuid",
      "plan": {
        "id": "uuid",
        "name": "string"
      },
      "status": "active",
      "started_at": "datetime",
      "expires_at": "datetime",
      "auto_renew": true
    }
  }
  ```

---

### POST `/api/v1/subscriptions/purchase/`
- **Description** : Achète un abonnement
- **Rôle** : Processus d'achat premium
- **Requête** :
  ```json
  {
    "plan_id": "uuid",
    "payment_method": "card",
    "payment_token": "string"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "subscription": {
      "id": "uuid",
      "status": "active",
      "expires_at": "datetime"
    },
    "payment": {
      "id": "uuid",
      "status": "completed"
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