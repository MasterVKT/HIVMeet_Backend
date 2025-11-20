# 🔐 API Authentication - Documentation Frontend

## 📋 Vue d'Ensemble

Le module Authentication gère l'authentification hybride Firebase + JWT, l'inscription, la connexion, et la gestion des tokens pour l'accès aux APIs du backend HIVMeet.

## 🏗️ Architecture d'Authentification

### Système Hybride Firebase + JWT

**Principe :** 
- Firebase Auth pour l'authentification primaire (sécurité, réinitialisation passwords)
- JWT Django pour l'autorisation aux APIs internes
- Synchronisation automatique entre Firebase et Django

**Workflow Principal :**
1. Utilisateur s'inscrit/connecte via Firebase
2. Frontend récupère le token Firebase ID
3. Backend valide le token Firebase et crée/met à jour l'utilisateur Django
4. Backend retourne des tokens JWT (access + refresh)
5. Frontend utilise les tokens JWT pour toutes les requêtes API

## 🔑 Endpoints d'Authentification

### 1. Inscription Utilisateur

**Endpoint :** `POST /auth/register`

**Principe d'Implémentation :**
1. Créer d'abord le compte Firebase côté frontend
2. Récupérer le token Firebase ID
3. Envoyer les informations d'inscription avec le token Firebase au backend
4. Le backend valide le token et crée l'utilisateur Django
5. Retourne les tokens JWT pour les futures requêtes

**Données Requises :**
```json
{
  "email": "user@example.com",
  "password": "motdepasse123",
  "display_name": "John Doe",
  "birth_date": "1990-01-15",
  "phone_number": "+33123456789"
}
```

**Réponse Succès (201) :**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "message": "Registration successful. Please verify your email."
}
```

**Logique d'Implémentation Frontend :**
- Valider l'âge (18+ obligatoire) avant l'envoi
- Créer le compte Firebase en premier
- Gérer les erreurs de validation spécifiques
- Rediriger vers la vérification email

### 2. Connexion Utilisateur

**Endpoint :** `POST /auth/login`

**Principe d'Implémentation :**
1. Authentifier via Firebase Auth
2. Récupérer le token Firebase ID
3. Envoyer le token au backend pour obtenir les tokens JWT
4. Gérer l'option "Remember Me" pour la durée des tokens

**Données Requises :**
```json
{
  "email": "user@example.com",
  "password": "motdepasse123",
  "remember_me": false
}
```

**Réponse Succès (200) :**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "John Doe",
    "is_verified": true,
    "is_premium": false,
    "email_verified": true
  },
  "token": "jwt_access_token"
}
```

**Logique d'Implémentation Frontend :**
- Gérer les états de connexion (loading, error, success)
- Vérifier le statut de vérification email
- Rediriger selon l'état du profil utilisateur
- Implémenter la reconnexion automatique

### 3. Vérification Email

**Endpoint :** `GET /auth/verify-email/{verification_token}`

**Principe d'Implémentation :**
1. L'utilisateur clique sur le lien reçu par email
2. Le frontend extrait le token de l'URL
3. Appel à l'API pour vérifier le token
4. Mise à jour de l'état de vérification

**Réponse Succès (200) :**
```json
{
  "message": "Email verified successfully. You can now log in."
}
```

**Logique d'Implémentation Frontend :**
- Extraire le token des paramètres d'URL
- Afficher un écran de vérification en cours
- Gérer les cas d'erreur (token expiré, invalide)
- Rediriger vers l'écran de connexion après succès

### 4. Réinitialisation Mot de Passe

**Endpoint :** `POST /auth/forgot-password`

**Principe d'Implémentation :**
1. Utiliser Firebase Auth pour la réinitialisation
2. Notifier le backend de la demande (pour analytics)
3. Gérer le workflow de réinitialisation côté Firebase

**Données Requises :**
```json
{
  "email": "user@example.com"
}
```

**Réponse Succès (200) :**
```json
{
  "message": "Password reset email sent."
}
```

### 5. Rafraîchissement Token

**Endpoint :** `POST /auth/refresh-token`

**Principe d'Implémentation :**
1. Utiliser le refresh token pour obtenir un nouveau access token
2. Implémenter la rotation automatique des tokens
3. Gérer l'expiration des refresh tokens

**Données Requises :**
```json
{
  "refresh_token": "jwt_refresh_token"
}
```

**Réponse Succès (200) :**
```json
{
  "access_token": "new_jwt_access_token",
  "refresh_token": "new_jwt_refresh_token"
}
```

**Logique d'Implémentation Frontend :**
- Implémenter l'intercepteur de requêtes pour refresh automatique
- Gérer les cas d'erreur de refresh (redirect vers login)
- Stocker les nouveaux tokens de manière sécurisée

### 6. Déconnexion

**Endpoint :** `POST /auth/logout`

**Principe d'Implémentation :**
1. Invalider les tokens côté backend
2. Déconnecter de Firebase Auth
3. Nettoyer le cache local et les données utilisateur

**Headers Requis :**
```
Authorization: Bearer <access_token>
```

**Réponse Succès (200) :**
```json
{
  "message": "Logged out successfully."
}
```

### 7. Registration Token FCM

**Endpoint :** `POST /auth/fcm-token`

**Principe d'Implémentation :**
1. Obtenir le token FCM depuis Firebase Messaging
2. Envoyer le token au backend avec les métadonnées de l'appareil
3. Gérer la mise à jour du token lors du refresh

**Données Requises :**
```json
{
  "token": "fcm_token_string",
  "device_id": "unique_device_id",
  "platform": "android|ios"
}
```

**Réponse Succès (201) :**
```json
{
  "message": "FCM token registered successfully."
}
```

## 🔒 Gestion des Tokens

### Durée de Vie des Tokens
- **Access Token** : 15 minutes
- **Refresh Token** : 7 jours (ou 30 jours avec "remember me")

### Stockage Sécurisé
**Principes d'Implémentation :**
- Utiliser le stockage sécurisé natif de la plateforme
- Chiffrer les tokens avant stockage
- Ne jamais stocker les tokens en plain text
- Nettoyer les tokens lors de la déconnexion

### Rotation Automatique
**Logique d'Implémentation :**
- Intercepter les requêtes API pour détecter les tokens expirés (401)
- Utiliser le refresh token pour obtenir de nouveaux tokens
- Retry automatique de la requête originale avec le nouveau token
- Gérer les cas d'échec de refresh (redirect vers login)

## 🔄 États d'Authentification

### États Possibles
1. **Non Authentifié** : Aucun token valide
2. **Authentifié** : Tokens valides, email non vérifié
3. **Vérifié** : Tokens valides, email vérifié
4. **Premium** : Utilisateur avec abonnement actif
5. **Suspendu** : Compte suspendu ou banni

### Gestion des Transitions d'État
**Logique d'Implémentation :**
- Maintenir un state management global pour l'authentification
- Écouter les changements d'état Firebase
- Synchroniser avec l'état backend via des appels API
- Gérer les redirections selon l'état

## 🚨 Gestion d'Erreurs Spécifiques

### Erreurs d'Inscription
- **Email déjà utilisé** : Proposer la connexion
- **Âge insuffisant** : Message d'erreur explicite
- **Données invalides** : Validation field par field

### Erreurs de Connexion
- **Compte non vérifié** : Proposer le renvoi d'email
- **Mot de passe incorrect** : Proposer la réinitialisation
- **Compte suspendu** : Afficher la raison et contact support

### Erreurs de Token
- **Token expiré** : Refresh automatique
- **Token invalide** : Forcer la déconnexion
- **Refresh échoué** : Redirect vers login

## 📱 Intégration Firebase

### Configuration Firebase
**Principe d'Implémentation :**
- Utiliser le fichier `google-services.json` fourni
- Configurer Firebase Auth avec les bonnes méthodes
- Gérer les états de connexion Firebase
- Synchroniser avec l'état backend Django

### Méthodes d'Authentification
- **Email/Password** : Méthode principale
- **Vérification Email** : Obligatoire pour utiliser l'app
- **Réinitialisation** : Via Firebase Auth

## 🔔 Notifications Push

### Configuration FCM
**Principe d'Implémentation :**
- Demander les permissions de notification
- Obtenir le token FCM
- Envoyer le token au backend via `/auth/fcm-token`
- Gérer le refresh du token

### Types de Notifications
1. **Nouveaux matches** : Notification push
2. **Nouveaux messages** : Notification push avec preview
3. **Likes reçus** : Notification groupée
4. **Abonnement** : Notifications de facturation

## 🔐 Sécurité et Bonnes Pratiques

### Validation Côté Client
- Valider l'email avant envoi
- Vérifier l'âge (18+)
- Sanitiser les entrées utilisateur
- Gérer les caractères spéciaux dans les noms

### Gestion des Sessions
- Implémenter la déconnexion automatique après inactivité
- Gérer les connexions multiples
- Invalider les sessions sur changement de mot de passe

### Protection des Données
- Ne jamais logger les tokens
- Utiliser HTTPS pour toutes les communications
- Implémenter la détection de jailbreak/root

## 📊 Métriques et Analytics

### Événements à Tracker
- Inscription réussie/échouée
- Connexion réussie/échouée
- Vérification email
- Utilisation des tokens FCM
- Erreurs d'authentification

### Données de Performance
- Temps de connexion
- Taux de succès d'inscription
- Fréquence de refresh des tokens
- Utilisation des notifications push

## 🔧 Debugging et Troubleshooting

### Logs Recommandés
- États des tokens (sans les valeurs)
- Erreurs de validation
- Réponses d'erreur API
- Changements d'état d'authentification

### Cas d'Erreur Courants
1. **Token Firebase expiré** : Re-authentifier
2. **Backend inaccessible** : Mode hors ligne
3. **Email non vérifié** : Workflow de vérification
4. **Compte suspendu** : Affichage du message support

Cette documentation couvre tous les aspects de l'authentification nécessaires pour une intégration frontend réussie avec le backend HIVMeet. 