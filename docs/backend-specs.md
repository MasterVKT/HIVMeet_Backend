# Spécifications Fonctionnelles Backend - HIVMeet

## 1. Vue d'Ensemble du Backend

### 1.1 Objectifs du Backend

- Développer une infrastructure sécurisée et évolutive pour l'application HIVMeet
- Gérer efficacement les données sensibles des utilisateurs
- Fournir des API performantes et bien documentées pour le frontend
- Assurer la confidentialité des données et la sécurité des utilisateurs
- Implémenter les logiques métier complexes indépendamment du frontend

### 1.2 Architecture Globale

- **Modèle d'architecture**: API REST avec authentification JWT
- **Environnements**:
  - Développement
  - Recette
  - Production
- **Infrastructure**:
  - Services cloud hautement disponibles
  - Mise à l'échelle automatique
  - Sauvegardes chiffrées quotidiennes

### 1.3 Technologies Cibles

- **Langage de programmation**: Node.js/Express ou Django REST Framework
- **Base de données**:
  - Principale: PostgreSQL
  - Cache: Redis
  - Stockage médias: Solution cloud (AWS S3 ou équivalent)
- **Services d'authentification**: Firebase Auth
- **Surveillance et logging**: ELK Stack (Elasticsearch, Logstash, Kibana)

## 2. Gestion des Utilisateurs et Authentification

### 2.1 Service d'Authentification

#### 2.1.1 Création de Compte

**Endpoints**
- `POST /api/auth/register`
  - **Entrée**:
    ```json
    {
      "email": "string", // Format validé par regex
      "password": "string", // Hachage côté backend
      "birthdate": "YYYY-MM-DD", // Validation d'âge (18+)
      "phone": "string" // Optionnel, format international
    }
    ```
  - **Traitement**:
    - Validation des entrées
    - Vérification d'unicité de l'email
    - Hachage sécurisé du mot de passe (Bcrypt avec salt)
    - Création du compte Firebase Auth
    - Génération de token de confirmation email
  - **Réponse**:
    - Code 201: Création réussie
    - Code 400: Données invalides (détails des erreurs)
    - Code 409: Email déjà utilisé

**Processus de vérification email**
- Génération token unique sécurisé (expiration 24h)
- Envoi email avec lien de confirmation
- Endpoint `GET /api/auth/verify-email/:token`
- Redirection vers création de profil après confirmation
- Suppression automatique après 30 jours si non confirmé

#### 2.1.2 Connexion

**Endpoints**
- `POST /api/auth/login`
  - **Entrée**:
    ```json
    {
      "email": "string",
      "password": "string",
      "remember_me": boolean // Optionnel
    }
    ```
  - **Traitement**:
    - Authentification via Firebase Auth
    - Vérification du statut du compte
    - Journalisation de la connexion (IP, device)
    - Détection d'activité suspecte
  - **Réponse**:
    - Code 200: Authentification réussie avec tokens
    - Code 401: Identifiants invalides
    - Code 403: Compte non vérifié/suspendu

**Sécurité de session**
- Tokens JWT avec rotation
  - Access token (15min)
  - Refresh token (7 jours ou 30 jours si "remember me")
- Invalidation des tokens à la déconnexion
- Liste noire de tokens révoqués (Redis)
- Détection de connexions multiples suspectes

#### 2.1.3 Gestion du Mot de Passe

**Endpoints**
- `POST /api/auth/forgot-password`
  - **Entrée**: `{ "email": "string" }`
  - **Traitement**:
    - Génération token unique (expiration 1h)
    - Envoi email avec lien de réinitialisation
    - Journalisation de la demande
  - **Réponse**:
    - Code 200: Email envoyé (même si compte inexistant)

- `POST /api/auth/reset-password`
  - **Entrée**:
    ```json
    {
      "token": "string",
      "new_password": "string"
    }
    ```
  - **Traitement**:
    - Validation du token
    - Vérification de la force du mot de passe
    - Mise à jour du mot de passe
    - Invalidation de toutes les sessions actives
  - **Réponse**:
    - Code 200: Réinitialisation réussie
    - Code 400: Token invalide/expiré ou mot de passe faible

### 2.2 Gestion des Profils

#### 2.2.1 Création et Modification de Profil

**Endpoints**
- `POST /api/users/profile`
  - **Entrée**:
    ```json
    {
      "display_name": "string", // 3-30 caractères
      "location": {
        "city": "string",
        "country": "string",
        "hide_exact_location": boolean
      },
      "preference": {
        "min_age": number, // 18-99
        "max_age": number, // 18-99
        "max_distance": number, // 5-100km
        "relation_type": "string", // enum des types
        "genders": ["string"] // tableau des genres
      },
      "bio": "string", // max 500 caractères
      "interests": ["string"] // max 3 intérêts
    }
    ```
  - **Traitement**:
    - Validation complète des champs
    - Filtrage anti-langage offensant
    - Géocodage de la localisation
    - Sauvegarde dans la base de données
  - **Réponse**:
    - Code 201: Profil créé
    - Code 400: Données invalides

- `PUT /api/users/profile`
  - Structure similaire au POST mais pour mise à jour
  - Validation des modifications autorisées
  - Journalisation des changements significatifs

#### 2.2.2 Gestion des Photos

**Endpoints**
- `POST /api/users/photos`
  - **Entrée**: Formulaire multipart avec l'image
  - **Traitement**:
    - Validation du type de fichier (JPG, PNG uniquement)
    - Validation de la taille (max 5MB)
    - Vérification des dimensions (min 400x400)
    - Optimisation et redimensionnement
    - Scan de contenu inapproprié
    - Stockage sécurisé avec référence en BDD
  - **Réponse**:
    - Code 201: Photo uploadée avec URL
    - Code 400: Fichier invalide

- `PUT /api/users/photos/:id`
  - Mise à jour des métadonnées (principale, ordre)
  - Récupération des URLs signées pour accès temporaire

- `DELETE /api/users/photos/:id`
  - Suppression logique puis physique après délai
  - Vérification qu'au moins une photo reste (si principale)

#### 2.2.3 Vérification de Compte

**Processus backend**
- `POST /api/users/verification/request`
  - Création d'une demande de vérification
  - Génération d'un code unique pour selfie

- `POST /api/users/verification/upload`
  - Upload sécurisé de documents (identité, médical)
  - Stockage chiffré avec accès restreint
  - État "en attente de vérification"

- `POST /api/users/verification/selfie`
  - Validation du code affiché
  - Comparaison automatique avec photo d'identité
  - Mise en file d'attente pour vérification manuelle

**Processus de modération**
- API d'administration pour vérificateurs
- Déchiffrement temporaire pour vérification
- Suppression immédiate des données sensibles après vérification
- Attribution du badge "vérifié" avec date d'expiration (6 mois)

## 3. Services de Matchmaking et Découverte

### 3.1 Algorithme de Découverte

#### 3.1.1 Logique de Filtrage et Suggestion

**Critères et implémentation**
- **Filtre principal**:
  ```sql
  WHERE
    age BETWEEN user_min_age AND user_max_age
    AND distance <= user_max_distance
    AND gender IN user_preferred_genders
    AND (relation_type = user_relation_type OR user_relation_type = 'all')
    AND user_id NOT IN blocked_users
    AND user_id NOT IN already_seen_users
  ```

- **Facteurs de score**:
  - Compatibilité de préférences (50%)
  - Activité récente du profil (20%)
  - Intérêts communs (15%)
  - Statut de vérification (10%)
  - Complétude du profil (5%)

- **Calcul de distance**:
  - Calcul de distance géospatiale optimisé
  - Mise en cache des résultats fréquents
  - Intervalle de mise à jour de 1h pour localisation

#### 3.1.2 Endpoints de Découverte

- `GET /api/discover/profiles`
  - **Paramètres**:
    ```
    ?limit=20
    &offset=0
    &filter[verified_only]=boolean
    &filter[relation_type]=string
    &filter[min_age]=number
    &filter[max_age]=number
    &filter[max_distance]=number
    ```
  - **Traitement**:
    - Application des filtres utilisateur
    - Application filtres de sécurité (blocages)
    - Génération du batch de profils
    - Exclusion des profils déjà vus récemment
  - **Réponse**:
    - Batch de profils avec pagination
    - Méta-informations (total, prochaine page)
    - Cache-Control adapté

### 3.2 Système de Likes et Matches

#### 3.2.1 Gestion des Interactions

**Endpoints**
- `POST /api/discover/like`
  - **Entrée**: `{ "target_user_id": "string" }`
  - **Traitement**:
    - Vérification des limites quotidiennes
      - Utilisateurs standards: 20 likes/24h
      - Utilisateurs vérifiés: 30 likes/24h
      - Utilisateurs premium: illimités
    - Enregistrement de l'action
    - Vérification de match potentiel
  - **Réponse**:
    - Code 201: Like enregistré
    - Code 200: Match créé (détails du match)
    - Code 429: Limite atteinte

- `POST /api/discover/dislike`
  - **Entrée**: `{ "target_user_id": "string" }`
  - **Traitement**:
    - Enregistrement en historique temporaire (30 jours)
    - Pas de limite quotidienne
  - **Réponse**:
    - Code 201: Dislike enregistré

- `POST /api/discover/superlike` (Premium)
  - **Entrée**: `{ "target_user_id": "string" }`
  - **Traitement**:
    - Vérification des limites (3/jour)
    - Priorité accrue dans la file du destinataire
    - Notification spéciale
  - **Réponse**:
    - Code 201: Superlike enregistré
    - Code 429: Limite atteinte

#### 3.2.2 Gestion des Matches

**Endpoints**
- `GET /api/matches`
  - **Paramètres**:
    ```
    ?limit=20
    &offset=0
    &status=active|pending
    &sort=recent|activity
    ```
  - **Traitement**:
    - Récupération selon filtres
    - Inclusion des métadonnées (dernier message, etc.)
  - **Réponse**:
    - Liste de matches avec pagination
    - Statut de chaque match
    - Information sur non-lus

- `DELETE /api/matches/:id`
  - Suppression logique du match
  - Conservation de l'historique (raisons analytiques)
  - Blocage de nouveau match pendant période définie

#### 3.2.3 Premium Features Backend

**Fonctionnalités exclusives**
- `GET /api/discover/likes-received` (Premium)
  - Récupération des utilisateurs ayant liké le profil
  - Pagination et filtrage

- `POST /api/discover/rewind` (Premium)
  - Annulation du dernier swipe
  - Limite de 3 par jour
  - Expiration après 5 minutes

- `POST /api/discover/boost` (Premium)
  - Activation du boost (30 minutes)
  - Calcul du prochain boost gratuit disponible
  - Métriques d'efficacité en temps réel

## 4. Système de Messagerie

### 4.1 Gestion des Conversations

#### 4.1.1 Structure et Endpoints

**Modèle de données**
- Conversations:
  - ID unique
  - Participants (2 utilisateurs)
  - Date de création
  - Date dernier message
  - État (active, archivée)

- Messages:
  - ID unique
  - ID conversation
  - Contenu
  - Type (texte, média-premium)
  - Horodatage
  - État (envoyé, délivré, lu)
  - Métadonnées (taille, format)

**Endpoints**
- `GET /api/messages/conversations`
  - **Paramètres**:
    ```
    ?limit=20
    &offset=0
    &status=active|archived
    ```
  - **Traitement**:
    - Récupération des conversations
    - Inclusion du dernier message
    - Comptage des non-lus
  - **Réponse**:
    - Liste paginée des conversations
    - Métadonnées complètes

- `GET /api/messages/conversations/:id`
  - **Paramètres**:
    ```
    ?limit=50
    &before=timestamp
    ```
  - **Traitement**:
    - Récupération des messages par lot
    - Pagination inversée (plus récents d'abord)
    - Marquage automatique comme lus
  - **Réponse**:
    - Messages avec pagination
    - État de la conversation

#### 4.1.2 Envoi et Réception

**Endpoints**
- `POST /api/messages/conversations/:id`
  - **Entrée**:
    ```json
    {
      "content": "string", // texte, max 1000 caractères
      "type": "text" // enum des types possibles
    }
    ```
  - **Traitement**:
    - Validation du contenu (filtrage liens, inapproprié)
    - Vérification des limites de stockage
    - Enregistrement en base de données
    - Déclenchement de notification push
  - **Réponse**:
    - Code 201: Message créé
    - Code 400: Contenu invalide
    - Code 403: Limites atteintes

- `PUT /api/messages/:id/read`
  - Marquage de messages comme lus
  - Propagation du statut

- `DELETE /api/messages/:id`
  - Suppression côté utilisateur uniquement
  - Conservation pour modération

### 4.2 Système de Notifications

#### 4.2.1 Architecture de Notifications

**Types et canaux**
- **Push notifications**:
  - Firebase Cloud Messaging (Android)
  - Apple Push Notification Service (iOS)
  - Service Worker (Web)

- **Types de notifications**:
  - Match: priorité haute
  - Message: priorité moyenne
  - Like: priorité basse (premium)
  - Système: priorité variable

**Endpoints**
- `POST /api/notifications/register-device`
  - Enregistrement token FCM/APNS
  - Liaison compte-device

- `GET /api/notifications/settings`
  - Récupération préférences

- `PUT /api/notifications/settings`
  - Mise à jour préférences
  - Validation des permissions

#### 4.2.2 Logique de Déclenchement

**Backend processing**
- Files d'attente pour notifications
  - Priorité d'envoi selon type
  - Batch processing pour optimisation
  - Limites par utilisateur/temps

- Règles intelligentes
  - Fenêtres temporelles (heures actives)
  - Regroupement de notifications similaires
  - Suppression de doublons

- Templating dynamique
  - Personnalisation du contenu
  - Localisation selon langue utilisateur
  - Données contextuelles incluses

### 4.3 Appels Audio/Vidéo (Premium)

#### 4.3.1 Infrastructure

**Architecture**
- WebRTC pour communication P2P
- Serveurs STUN/TURN pour NAT traversal
- Signaling server pour établissement connexion

**Endpoints**
- `POST /api/calls/initiate`
  - **Entrée**:
    ```json
    {
      "target_user_id": "string",
      "type": "audio|video",
      "offer_sdp": "string"
    }
    ```
  - **Traitement**:
    - Vérification du statut premium
    - Vérification disponibilité destinataire
    - Création session d'appel
    - Transmission offre via signaling
  - **Réponse**:
    - Code 201: Appel initié
    - Code 403: Non autorisé (non premium)

- `PUT /api/calls/:id/answer`
  - Acceptation de l'appel
  - Échange de paramètres de connexion

- `PUT /api/calls/:id/ice-candidate`
  - Échange de candidats ICE pour connexion

- `PUT /api/calls/:id/end`
  - Terminaison de l'appel
  - Enregistrement des métriques

#### 4.3.2 Limitations et Monitoring

**Gestion des ressources**
- Limite de durée (30 minutes)
  - Minuteur côté serveur
  - Notifications à 5 minutes de la fin
  - Option d'extension payante

- Qualité de service
  - Monitoring en temps réel
  - Métriques de qualité (latence, perte paquets)
  - Adaptation dynamique

- Sécurité
  - Chiffrement bout-en-bout
  - Validation des participants
  - Détection d'abus

## 5. Modération et Sécurité

### 5.1 Système de Signalement

#### 5.1.1 Traitement des Signalements

**Endpoints**
- `POST /api/reports`
  - **Entrée**:
    ```json
    {
      "target_type": "user|message|content",
      "target_id": "string",
      "reason": "string", // enum des raisons
      "details": "string", // optionnel
      "evidence": ["string"] // URLs captures d'écran
    }
    ```
  - **Traitement**:
    - Validation du rapport
    - Assignation niveau priorité
    - Mise en file d'attente modération
    - Mesures automatiques si seuil atteint
  - **Réponse**:
    - Code 201: Signalement créé
    - Code 400: Données invalides

**Processus backend**
- Système de scoring automatique
  - Historique utilisateur signalé
  - Historique utilisateur signalant
  - Mots-clés détectés
  - Patterns de comportement

- File d'attente modération
  - Prioritisation par gravité
  - Distribution aux modérateurs
  - SLA selon type de signalement

#### 5.1.2 Actions de Modération

**Types d'actions**
- **Automatiques**:
  - Suspension préventive compte (cas graves)
  - Limitation fonctionnalités (cas modérés)
  - Filtrage contenu détecté

- **Manuelles via API admin**:
  - `PUT /api/admin/moderation/users/:id/action`
    - Actions: warning, restrict, suspend, ban
    - Durée configurable
    - Raison et commentaires internes
    - Notification à l'utilisateur

  - `PUT /api/admin/moderation/content/:id/action`
    - Actions: hide, delete, flag
    - Application immédiate

### 5.2 Système de Blocage

#### 5.2.1 Gestion des Blocages

**Endpoints**
- `POST /api/users/blocks`
  - **Entrée**: `{ "blocked_user_id": "string" }`
  - **Traitement**:
    - Validation des IDs
    - Vérification limite (max 100 par utilisateur)
    - Enregistrement blocage bidirectionnel
    - Suppression match si existant
  - **Réponse**:
    - Code 201: Blocage créé
    - Code 429: Limite atteinte

- `GET /api/users/blocks`
  - Liste des utilisateurs bloqués
  - Pagination et recherche
  - Date de blocage

- `DELETE /api/users/blocks/:id`
  - Vérification délai (min 24h)
  - Suppression du blocage
  - Autorisation re-matching après délai

#### 5.2.2 Effets du Blocage

**Implémentation backend**
- **Exclusion de découverte**:
  ```sql
  WHERE target_id NOT IN (
    SELECT blocked_id FROM blocks WHERE user_id = current_user_id
    UNION
    SELECT user_id FROM blocks WHERE blocked_id = current_user_id
  )
  ```

- **Messagerie**:
  - Suppression logique de conversations
  - Marquage spécial pour administrateurs
  - Conservation pour modération (durée limitée)

- **Notifications**:
  - Suppression de toute notification mutuelle
  - Désactivation mentions

### 5.3 Protection des Données Sensibles

#### 5.3.1 Gestion du Statut Sérologique

**Stockage sécurisé**
- Cloisonnement base de données spécifique
- Chiffrement au repos (AES-256)
- Accès restreint (authentification multi-facteurs)
- Journalisation complète de tous accès

**Processus de vérification**
- Isolation du traitement documents médicaux
- Destruction immédiate après vérification
- Stockage uniquement du statut vérifié (booléen)
- Date d'expiration de vérification (90 jours)

**Confidentialité**
- Aucun partage ou exposition externe
- Aucune utilisation pour recommandations
- Politique stricte de non-discrimination

## 6. Gestion de Contenu et Ressources

### 6.1 Fil d'Actualité

#### 6.1.1 Publication et Modération

**Endpoints**
- `POST /api/feed/posts`
  - **Entrée**:
    ```json
    {
      "content": "string", // max 500 caractères
      "image": "string", // URL ou base64
      "tags": ["string"], // optionnel
      "allow_comments": boolean
    }
    ```
  - **Traitement**:
    - Validation du contenu
    - Filtrage anti-spam/inapproprié
    - Mise en file d'attente modération
    - État "en attente" 
  - **Réponse**:
    - Code 202: En attente de modération
    - Code 400: Contenu invalide

- `GET /api/feed/posts`
  - **Paramètres**:
    ```
    ?limit=20
    &offset=0
    &tag=string
    &sort=recent|popular
    ```
  - **Traitement**:
    - Filtrage par approbation modération
    - Tri chronologique inverse
    - Métriques d'engagement
  - **Réponse**:
    - Liste paginée des publications
    - Méta-information (total, pages)

#### 6.1.2 Interactions

**Endpoints**
- `POST /api/feed/posts/:id/like`
  - Toggle like/unlike
  - Comptage et mise à jour

- `POST /api/feed/posts/:id/comments`
  - **Entrée**: `{ "content": "string" }` // max 200 caractères
  - Validation et filtrage
  - Approbation automatique ou manuelle

- `GET /api/feed/posts/:id/comments`
  - Pagination et tri
  - Information modération

### 6.2 Ressources Informatives

#### 6.2.1 Gestion du Contenu

**Structure de données**
- **Catégories**:
  - ID, nom, description, icône
  - Hiérarchie parent/enfant
  - Ordre d'affichage

- **Articles**:
  - ID, titre, contenu, auteur
  - Catégorie, tags
  - Date publication, mise à jour
  - Méta (temps lecture, niveau)
  - État (brouillon, publié, archivé)

- **Ressources**:
  - Type (article, vidéo, lien)
  - Langue(s) disponible(s)
  - Version (contrôle par version)
  - Validation médicale (oui/non)

**Endpoints**
- `GET /api/resources/categories`
  - Arborescence complète
  - Statistiques de contenu

- `GET /api/resources/articles`
  - **Paramètres**:
    ```
    ?category_id=string
    &tags=string,string
    &search=string
    &lang=fr|en
    ```
  - Recherche full-text
  - Filtrage multicritères
  - Contenu localisé selon préférence

- `GET /api/resources/articles/:id`
  - Contenu complet
  - Suggestions connexes
  - Tracking anonymisé de lecture

#### 6.2.2 Système de Favoris

**Endpoints**
- `POST /api/resources/favorites`
  - **Entrée**: `{ "resource_id": "string", "type": "article|video|link" }`
  - Ajout aux favoris
  - Synchronisation multi-device

- `GET /api/resources/favorites`
  - Liste personnalisée
  - Filtrage par type
  - Option téléchargement offline

- `DELETE /api/resources/favorites/:id`
  - Suppression simple
  - Conservation statistiques anonymes

## 7. Gestion des Abonnements Premium

### 7.1 Processus d'Abonnement

#### 7.1.1 Intégration Paiement

**Endpoints**
- `GET /api/subscriptions/plans`
  - Liste des plans disponibles
  - Prix localisés selon région
  - Fonctionnalités incluses
  - Promotions actives

- `POST /api/subscriptions/purchase`
  - **Entrée**:
    ```json
    {
      "plan_id": "string",
      "payment_method": "string",
      "payment_token": "string", // de MyCoolPay
      "coupon": "string" // optionnel
    }
    ```
  - **Traitement**:
    - Validation du token de paiement
    - Création abonnement MyCoolPay
    - Attribution droits premium
    - Génération facture
  - **Réponse**:
    - Code 201: Abonnement créé
    - Code 400: Erreur paiement/validation

- `GET /api/subscriptions/current`
  - État de l'abonnement
  - Date renouvellement
  - Fonctionnalités actives
  - Historique factures

#### 7.1.2 Gestion du Cycle de Vie

**Endpoints**
- `PUT /api/subscriptions/cancel`
  - **Traitement**:
    - Annulation fin de période
    - Conservation accès jusqu'à expiration
    - Enquête motif annulation
    - Offres de rétention
  - **Réponse**:
    - Date fin effective
    - Fonctionnalités conservées

- `PUT /api/subscriptions/reactivate`
  - Réactivation si dans période de grâce
  - Mise à jour système paiement

- `POST /api/subscriptions/change-plan`
  - **Entrée**: `{ "new_plan_id": "string" }`
  - Calcul prorata
  - Application immédiate

### 7.2 Gestion des Fonctionnalités Premium

#### 7.2.1 Contrôle d'Accès

**Architecture backend**
- **Service de droits**:
  - Vérification temps réel
  - Cache Redis (TTL 5min)
  - Hiérarchie de permissions

- **Guard middleware**:
  ```javascript
  async function premiumGuard(req, res, next) {
    const isPremium = await subscriptionService.checkUserPremium(req.user.id);
    if (!isPremium) {
      return res.status(403).json({
        error: "premium_required",
        message: "Cette fonctionnalité nécessite un abonnement premium"
      });
    }
    next();
  }
  ```

- **Limites dynamiques**:
  - Configuration par type d'abonnement
  - Compteurs en base Redis
  - Réinitialisation périodique

#### 7.2.2 Fonctionnalités à Limitation

**Implémentation**
- **Boost**:
  - `POST /api/premium/boost/activate`
  - Vérification disponibilité
  - Démarrage minuteur 30min
  - Calcul prochain boost gratuit
  - Tracking efficacité

- **Super likes**:
  - Compteur journalier Redis
  - Réinitialisation à minuit local
  - Notification épuisement/recharge

- **Rewind**:
  - Validation fenêtre temporelle (5min)
  - Limite quotidienne (3)
  - Conservation historique complet

## 8. Supervision et Analytics

### 8.1 Monitoring Applicatif

#### 8.1.1 Métriques Techniques

**Implémentation**
- **Performance**:
  - Temps de réponse API (p50, p95, p99)
  - Taux d'erreurs
  - Utilisation ressources
  - Latence base de données

- **Disponibilité**:
  - Heartbeat services
  - Vérification endpoints critiques
  - Détection dégradation

- **Sécurité**:
  - Tentatives authentification suspectes
  - Patterns d'accès anormaux
  - Scanning vulnérabilités

#### 8.1.2 Alerting

**Système d'alerte**
- **Niveaux de criticité**:
  - P1: Interruption service (intervention immédiate)
  - P2: Dégradation majeure (intervention <30min)
  - P3: Problème mineur (intervention <4h)
  - P4: Optimisation (planifiée)

- **Canaux**:
  - Slack/Teams (notifications temps réel)
  - Email (récapitulatifs)
  - SMS/Appel (P1 uniquement)
  - Système de rotation astreinte

### 8.2 Analytics Métier

#### 8.2.1 Événements et Métriques

**Structure**
- **Événements utilisateurs**:
  - Session (début, fin, durée)
  - Navigation (page vue, durée, origine)
  - Interaction (like, message, action)
  - Conversion (inscription, premium)

- **Métriques agrégées**:
  - DAU/MAU (utilisateurs actifs)
  - Rétention (1j, 7j, 28j)
  - Taux de conversion
  - Engagement (actions/session)

**Endpoints**
- `POST /api/analytics/events`
  - **Entrée**:
    ```json
    {
      "event_type": "string",
      "properties": {},
      "timestamp": "ISO-8601"
    }
    ```
  - Validation et enrichissement
  - Stockage asynchrone

#### 8.2.2 Reporting

**Capacités**
- **Rapports automatisés**:
  - Tableau de bord quotidien
  - Rapport hebdomadaire (KPIs principaux)
  - Rapport mensuel détaillé
  - Alertes de variations significatives

- **Segmentation**:
  - Par cohorte (date inscription)
  - Par localisation
  - Par type d'utilisateur
  - Par comportement

- **Data warehouse**:
  - ETL quotidien
  - Anonymisation
  - Conservation limitée données identifiantes

## 9. Architecture Technique Détaillée

### 9.1 Modèle de Données

#### 9.1.1 Schéma Base de Données

**Principales entités**
- **Users**:
  ```sql
  CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    birthdate DATE NOT NULL,
    phone VARCHAR(20),
    account_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_expiry TIMESTAMP
  );
  ```

- **Profiles**:
  ```sql
  CREATE TABLE profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    display_name VARCHAR(30) NOT NULL,
    bio TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    hide_exact_location BOOLEAN DEFAULT FALSE,
    relation_type VARCHAR(50),
    min_age_preference INT DEFAULT 18,
    max_age_preference INT DEFAULT 99,
    max_distance INT DEFAULT 25,
    premium_until TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
  );
  ```

- **Autres tables principales**:
  - Photos (références user_id, type, URL, ordre)
  - Likes (user_id, target_id, timestamp, type)
  - Matches (id, user1_id, user2_id, created_at, status)
  - Messages (id, match_id, sender_id, content, status)
  - Blocks (user_id, blocked_id, reason, timestamp)
  - Subscriptions (user_id, plan_id, status, start_date, end_date)

#### 9.1.2 Indexation et Performance

**Stratégies**
- **Indexation**:
  ```sql
  -- Index pour recherche géospatiale
  CREATE INDEX idx_user_location ON user_locations USING GIST (coordinates);
  
  -- Index multicritères pour découverte
  CREATE INDEX idx_profile_search ON profiles (
    relation_type, 
    EXTRACT(YEAR FROM AGE(birthdate)), 
    gender, 
    verification_status
  );
  
  -- Index pour messages
  CREATE INDEX idx_messages_match_id ON messages (match_id, created_at DESC);
  ```

- **Partitionnement**:
  - Messages par tranche temporelle (mois)
  - Événements analytics par jour
  - Données archivées par année

- **Caching**:
  - Profils fréquemment consultés
  - Résultats de matchmaking
  - Compteurs et limites
  - Sessions et tokens

### 9.2 Sécurité et Conformité

#### 9.2.1 Protection des Données

**Mesures techniques**
- **Chiffrement**:
  - Données personnelles chiffrées (AES-256)
  - Documents sensibles ségrégués
  - Communications TLS 1.3 uniquement
  - Certificats à rotation régulière

- **Anonymisation**:
  - Séparation données identification/usage
  - Pseudonymisation pour analytics
  - Minimisation données conservées
  - Purge automatique selon durées légales

#### 9.2.2 Conformité RGPD/CCPA

**Fonctionnalités techniques**
- `GET /api/users/data-export`
  - Export complet données utilisateur
  - Format structuré (JSON/CSV)
  - Documentation des champs

- `POST /api/users/data-deletion`
  - Suppression complète ou partielle
  - Cascade sur entités liées
  - Conservation légale minimale
  - Rapports d'achèvement

- `GET /api/privacy/settings`
  - Paramètres granulaires de confidentialité
  - Gestion consentements par catégorie
  - Journal des modifications

## 10. Intégrations Externes

### 10.1 Systèmes Tiers

#### 10.1.1 Intégration MyCoolPay

**Configuration**
- API keys sécurisées par environnement
- Webhook pour notifications asynchrones
- Réconciliation automatique transactions

**Endpoints**
- `POST /api/payment/webhook`
  - Traitement événements paiement
  - Vérification signature sécurité
  - Mise à jour statut abonnement

- `GET /api/payment/methods`
  - Liste méthodes enregistrées
  - Statut validité

- `POST /api/payment/methods`
  - Enregistrement nouveau moyen paiement
  - Tokenisation via SDK

#### 10.1.2 Services Cartographiques

**Intégration**
- Géocodage adresses (ville → coordonnées)
- Calcul distances optimisé
- Masquage localisation exacte
- Validation de zones géographiques

**Cache et optimisation**
- Mise en cache géocodage (TTL 30 jours)
- Précalcul matrices de distance
- Actualisation position utilisateur (1h max)
