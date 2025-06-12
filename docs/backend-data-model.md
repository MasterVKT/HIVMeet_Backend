# Modèle de Données Backend - HIVMeet

## 1. Vue d'Ensemble

Ce document détaille l'architecture de données backend de l'application HIVMeet, une plateforme de rencontres sécurisée pour personnes vivant avec le VIH. Le modèle présenté établit les fondations pour un stockage efficace, sécurisé et performant des données utilisateur tout en respectant les exigences strictes en matière de confidentialité.

### 1.1 Principes Fondamentaux

- **Sécurité par conception**: Protection des données sensibles à tous les niveaux
- **Orienté NoSQL**: Exploitation optimale des capacités de Firestore
- **Performance d'abord**: Optimisation pour les requêtes fréquentes
- **Évolutivité**: Structure adaptée à la croissance de l'application
- **Conformité réglementaire**: Architecture respectant RGPD, HIPAA et autres normes

### 1.2 Technologies et Plateformes

- **Base de données principale**: Cloud Firestore (NoSQL)
- **Stockage de médias**: Firebase Storage
- **Authentification**: Firebase Authentication
- **Exécution de logique**: Cloud Functions for Firebase

### 1.3 Organisation Générale

L'architecture de données s'articule autour de collections principales qui représentent les entités fondamentales de l'application:

- **users**: Données d'authentification et informations de compte
- **profiles**: Informations publiques et préférences de matching
- **matches**: Relations entre utilisateurs et statut
- **messages**: Conversations entre utilisateurs
- **verifications**: Processus de vérification d'identité
- **subscriptions**: Gestion des abonnements premium
- **resources**: Contenu informatif et éducatif

## 2. Modèles de Données Détaillés

### 2.1 Collection `users`

Cette collection centralise les informations d'authentification et d'identification des utilisateurs.

#### 2.1.1 Structure

```
users/{userId}
├── id: String                    # UID Firebase Auth (clé primaire)
├── email: String                 # Email de l'utilisateur
├── realName: String              # Nom réel (accès restreint)
├── pseudonym: String             # Nom d'affichage public
├── isVerified: Boolean           # Statut de vérification global
├── verificationStatus: String    # 'pending', 'verified', 'rejected'
├── isPremium: Boolean            # Statut d'abonnement
├── premiumUntil: Timestamp       # Date d'expiration premium
├── lastActive: Timestamp         # Dernière activité
├── createdAt: Timestamp          # Date de création 
├── updatedAt: Timestamp          # Date de mise à jour
├── blockedUsers: Array<String>   # Liste des utilisateurs bloqués
├── notificationSettings: Map     # Configuration des notifications
├── isEmailVerified: Boolean      # Vérification de l'email
├── role: String                  # 'user' ou 'admin'
└── deviceTokens: Array<String>   # Tokens FCM pour notifications
```

#### 2.1.2 Considérations de Conception

**Protection des données personnelles**:
- Le champ `realName` est strictement contrôlé avec accès limité aux administrateurs et au propriétaire
- Séparation des données d'identification (`users`) et de présentation (`profiles`)
- Aucune donnée médicale sensible n'est stockée directement dans ce document

**Efficacité opérationnelle**:
- Duplication stratégique de `isVerified` et `isPremium` pour accélérer les requêtes fréquentes
- Horodatages pour suivi d'activité et expiration de service
- Liste de blocage intégrée pour filtrage rapide

**Flexibilité et évolution**:
- Structure de notifications paramétrable sans modification de schéma
- Ajout de rôles pour permissions graduées
- Support multi-appareil via tableau de tokens

#### 2.1.3 Stratégie d'Indexation

**Index simples prioritaires**:
- `isVerified`: Filtrage des utilisateurs vérifiés
- `verificationStatus`: Gestion des files d'attente de modération
- `isPremium`: Statistiques et filtrage premium
- `lastActive`: Tri par activité récente
- `email`: Recherche par email pour récupération

**Index composites**:
- `isVerified` + `lastActive`: Recherche optimisée de profils actifs vérifiés
- `role` + `lastActive`: Surveillance d'activité administrative

#### 2.1.4 Règles de Sécurité

```javascript
match /users/{userId} {
  allow read: if request.auth != null && 
             (request.auth.uid == userId || isAdmin());
             
  allow update: if request.auth != null && 
               (request.auth.uid == userId) &&
               // Empêcher modification des champs sensibles
               !request.resource.data.diff(resource.data)
                .affectedKeys().hasAny(['isVerified', 'verificationStatus', 
                                        'isPremium', 'premiumUntil', 'role']);
                                        
  // Seuls les admins peuvent modifier les statuts sensibles
  allow update: if request.auth != null && isAdmin();
  
  // Création uniquement via Cloud Functions après inscription Firebase Auth
  allow create, delete: if false;
}
```

### 2.2 Collection `profiles`

Cette collection stocke les informations publiques des profils utilisateurs et leurs préférences de matching.

#### 2.2.1 Structure

```
profiles/{profileId} // (profileId = userId)
├── userId: String                # Référence à l'utilisateur
├── birthDate: Timestamp          # Date de naissance
├── age: Number                   # Âge calculé (dénormalisation)
├── bio: String                   # Description personnelle
├── location: GeoPoint            # Coordonnées géographiques
├── city: String                  # Ville de résidence
├── country: String               # Pays de résidence
├── interests: Array<String>      # Centres d'intérêt (max 3)
├── relationshipType: String      # Type de relation recherchée
├── photos: {                     # Structure photos
│   ├── main: String              # URL photo principale
│   ├── others: Array<String>     # URLs photos secondaires
│   └── private: Array<String>    # Album privé (premium)
│   }
├── searchPreferences: {          # Préférences de recherche
│   ├── ageRange: {min, max}      # Plage d'âge recherchée
│   ├── distance: Number          # Distance max (km)
│   ├── relationshipType: String  # Type de relation
│   └── genders: Array<String>    # Genres recherchés
│   }
├── lastActive: Timestamp         # Dernière activité
├── isHidden: Boolean             # Mode privé (premium)
└── visibilitySettings: Map       # Paramètres avancés
```

#### 2.2.2 Considérations de Conception

**Optimisation de recherche**:
- Champ `age` précalculé pour éviter les calculs répétitifs lors des requêtes
- `location` stocké comme GeoPoint pour permettre des requêtes géospatiales efficaces
- Structure hiérarchique des préférences pour faciliter les mises à jour partielles

**Gestion des médias**:
- Seules les URL des photos sont stockées ici, les fichiers réels étant dans Firebase Storage
- Séparation structurelle entre photo principale, secondaires et privées
- Les chemins suivent une convention standardisée: `profiles/{userId}/main.jpg`

**Contrôle de visibilité**:
- Champ `isHidden` comme indicateur principal de visibilité
- `visibilitySettings` extensible pour options premium avancées
- Duplication de `lastActive` depuis `users` pour performance des requêtes

#### 2.2.3 Stratégie d'Indexation

**Index prioritaires**:
- Index géospatial sur `location` pour recherche par proximité
- Index sur `age` pour filtrage par âge
- Index sur `relationshipType` pour filtrage par type de relation
- Index sur `interests` (array-contains) pour recherche par intérêts

**Index composites**:
- `country` + `city` pour recherche géographique hiérarchique
- `age` + `isHidden` pour filtrage des profils visibles par âge
- `relationshipType` + `lastActive` pour profils récemment actifs par type

#### 2.2.4 Règles de Sécurité

```javascript
match /profiles/{profileId} {
  // Lecture par utilisateurs authentifiés et vérifiés
  allow read: if request.auth != null && 
             (isUserVerified() || request.auth.uid == profileId || isAdmin()) &&
             // Vérifier que l'utilisateur n'est pas bloqué par le profil consulté
             !isUserBlocked(profileId, request.auth.uid);
             
  // Mise à jour par le propriétaire uniquement
  allow update: if request.auth != null && 
               request.auth.uid == profileId &&
               // Validation des contraintes métier
               request.resource.data.bio.size() <= 500 &&
               request.resource.data.interests.size() <= 3;
               
  // Création uniquement par Cloud Functions
  allow create, delete: if false;
}
```

### 2.3 Collection `matches`

Cette collection gère les relations entre utilisateurs, incluant likes et matches confirmés.

#### 2.3.1 Structure

```
matches/{matchId}
├── id: String                   # Identifiant unique du match
├── users: Array<String>         # IDs des deux utilisateurs
├── createdAt: Timestamp         # Date de création
├── status: String               # 'pending', 'active', 'blocked', 'deleted'
├── pendingUser: String          # Utilisateur qui a initié (pour likes)
├── targetUser: String           # Utilisateur cible (pour likes)
├── lastMessageAt: Timestamp     # Horodatage dernier message
├── lastMessagePreview: String   # Aperçu du dernier message
├── unreadCount: Map<String, Number> # Compteurs de non-lus par utilisateur
└── isActive: Boolean            # Indicateur d'activité
```

#### 2.3.2 Considérations de Conception

**Structure hybride évolutive**:
- Gère à la fois les likes unidirectionnels (`status: 'pending'`) et les matches (`status: 'active'`)
- Structure permettant l'évolution vers des types de relations plus complexes
- Support des états temporaires et permanents (blocage, suppression)

**Convention d'ID déterministe**:
- Pour les likes: `{initiatorId}_like_{targetId}`
- Pour les matches: `{smallerId}_{largerId}` (ordre alphabétique)
- Permet d'éviter les doublons et de vérifier facilement l'existence

**Dénormalisation stratégique**:
- `lastMessagePreview` et `lastMessageAt` dupliqués depuis la collection `messages`
- Compteurs `unreadCount` maintenus pour éviter des requêtes supplémentaires
- `isActive` comme indicateur booléen pour filtrage rapide

#### 2.3.3 Stratégie d'Indexation

**Index simples**:
- `users` (array-contains) pour retrouver tous les matches d'un utilisateur
- `status` pour filtrage par état
- `lastMessageAt` pour tri par activité récente
- `isActive` pour filtrage rapide

**Index composites critiques**:
- `targetUser` + `status` pour visualiser les likes reçus
- `pendingUser` + `status` pour suivre les likes envoyés
- `status` + `createdAt` pour tri chronologique par type
- `users` + `lastMessageAt` pour messages récents par conversation

#### 2.3.4 Règles de Sécurité

```javascript
match /matches/{matchId} {
  // Lecture uniquement par participants
  allow read: if request.auth != null && 
             request.auth.uid in resource.data.users;
             
  // Modifications limitées aux changements de statut par participants
  allow update: if request.auth != null && 
               request.auth.uid in resource.data.users &&
               request.resource.data.diff(resource.data)
                .affectedKeys().hasOnly(['status']);
                
  // Création et suppression via Cloud Functions uniquement
  allow create, delete: if false;
}
```

### 2.4 Collection `messages`

Cette collection stocke les conversations entre utilisateurs.

#### 2.4.1 Structure

```
messages/{messageId}
├── matchId: String             # Référence au match correspondant
├── senderId: String            # ID de l'expéditeur
├── content: String             # Contenu du message
├── type: String                # 'text', 'image', etc.
├── mediaUrl: String            # URL du média (optionnel)
├── readAt: Map<String, Timestamp> # Horodatage de lecture par utilisateur
├── createdAt: Timestamp        # Date d'envoi
├── isDeleted: Boolean          # Indicateur de suppression
└── reactionEmojis: Map<String, String> # Réactions par utilisateur
```

#### 2.4.2 Considérations de Conception

**Conception orientée performance**:
- Référence explicite au `matchId` pour requêtes efficaces sans jointures
- Horodatage `createdAt` pour tri chronologique naturel
- Structure de `readAt` comme map pour éviter documents annexes

**Flexibilité des types de contenu**:
- Support de différents types de messages via le champ `type`
- Les médias sont référencés mais stockés dans Firebase Storage
- Structure extensible pour futurs types de contenu

**Gestion de la confidentialité**:
- Support de suppression logique via `isDeleted`
- Sans purge immédiate pour modération et conformité légale
- Relation stricte avec la collection `matches` pour contrôle d'accès

#### 2.4.3 Stratégie d'Indexation

**Index principaux**:
- `matchId` pour retrouver tous les messages d'une conversation
- `senderId` pour filtrage par expéditeur
- `createdAt` pour tri chronologique
- `type` pour filtrage par type de message

**Index composites essentiels**:
- `matchId` + `createdAt` pour pagination chronologique des messages
- `matchId` + `type` pour filtrer les types de médias dans une conversation
- `senderId` + `createdAt` pour historique des messages envoyés

#### 2.4.4 Règles de Sécurité

```javascript
match /messages/{messageId} {
  // Fonction utilitaire pour vérifier l'appartenance au match
  function isParticipantInMatch(matchId) {
    return request.auth.uid in get(/databases/$(database)/documents/matches/$(matchId)).data.users;
  }

  // Lecture uniquement par participants à la conversation
  allow read: if request.auth != null && 
             isParticipantInMatch(resource.data.matchId);
             
  // Création avec validation stricte
  allow create: if request.auth != null && 
               isParticipantInMatch(request.resource.data.matchId) &&
               request.auth.uid == request.resource.data.senderId &&
               request.resource.data.content.size() <= 1000 &&
               // Restriction médias aux premium
               (request.resource.data.type == 'text' || isUserPremium());
               
  // Mise à jour limitée aux statuts de lecture
  allow update: if request.auth != null && 
               isParticipantInMatch(resource.data.matchId) &&
               // Uniquement mise à jour du statut de lecture
               request.resource.data.diff(resource.data)
                .affectedKeys().hasOnly(['readAt']);
                
  // Suppression logique uniquement
  allow delete: if false;
}
```

### 2.5 Collection `verifications`

Cette collection gère le processus de vérification d'identité et de statut médical.

#### 2.5.1 Structure

```
verifications/{userId}
├── userId: String              # ID utilisateur (même que document ID)
├── idDocumentUrl: String       # URL document d'identité (chiffré)
├── medicalDocumentUrl: String  # URL document médical (chiffré)
├── selfieUrl: String           # URL photo selfie avec code
├── verificationCode: String    # Code unique pour vérification
├── status: String              # 'pending', 'approved', 'rejected'
├── submittedAt: Timestamp      # Date de soumission
├── reviewedAt: Timestamp       # Date de révision
├── reviewedBy: String          # ID de l'admin vérificateur
├── rejectionReason: String     # Motif de rejet (si applicable)
├── expiresAt: Timestamp        # Date d'expiration de la vérification
└── documentTypes: Array<String> # Types de documents fournis
```

#### 2.5.2 Considérations de Conception

**Sécurité renforcée**:
- URLs des documents sensibles chiffrées côté serveur
- Processus de vérification en plusieurs étapes avec code unique
- Traçabilité complète avec horodatages et identifiants d'administrateur

**Cycle de vie géré**:
- État initial `pending` lors de la soumission
- États finaux `approved` ou `rejected` après révision
- Date d'expiration pour re-vérification périodique

**Conformité réglementaire**:
- Structure permettant audit complet du processus
- Documentation des motifs de rejet pour transparence
- Absence de stockage direct de données médicales dans Firestore

#### 2.5.3 Stratégie d'Indexation

**Index critiques**:
- `status` pour filtrage par statut de vérification
- `submittedAt` pour traitement chronologique des demandes
- `expiresAt` pour détection des vérifications expirées
- `reviewedBy` pour audit des actions administrateurs

**Index composites**:
- `status` + `submittedAt` pour priorisation de la file d'attente
- `status` + `expiresAt` pour gestion des expiration par catégorie

#### 2.5.4 Règles de Sécurité

```javascript
match /verifications/{userId} {
  // Lecture limitée à l'utilisateur concerné et aux administrateurs
  allow read: if request.auth != null && 
             (request.auth.uid == userId || isAdmin());
             
  // Création/mise à jour initiale par l'utilisateur
  allow create, update: if request.auth != null && 
                       request.auth.uid == userId &&
                       // Seuls certains champs peuvent être modifiés
                       request.resource.data.diff(resource.data || {})
                        .affectedKeys().hasOnly(['idDocumentUrl', 'medicalDocumentUrl', 
                                                'selfieUrl', 'verificationCode']);
                                                
  // Mise à jour du statut par administrateurs uniquement
  allow update: if request.auth != null && 
               isAdmin() &&
               // Administrateurs peuvent modifier le statut et ajouter des notes
               request.resource.data.diff(resource.data)
                .affectedKeys().hasAny(['status', 'reviewedAt', 'reviewedBy', 
                                       'rejectionReason', 'expiresAt']);
                                       
  allow delete: if false;
}
```

### 2.6 Collection `subscriptions`

Cette collection gère les abonnements premium des utilisateurs.

#### 2.6.1 Structure

```
subscriptions/{userId}
├── userId: String               # ID utilisateur (même que document ID)
├── isActive: Boolean            # État d'activation de l'abonnement
├── plan: String                 # 'monthly', 'annual'
├── startDate: Timestamp         # Date de début
├── endDate: Timestamp           # Date d'expiration
├── autoRenew: Boolean           # Renouvellement automatique
├── paymentMethod: String        # Méthode de paiement utilisée
├── transactionHistory: Array<Map> # Historique des transactions
├── price: Number                # Montant payé
├── currency: String             # Devise (EUR, USD, etc.)
├── cancellationReason: String   # Motif d'annulation (si applicable)
├── features: Array<String>      # Fonctionnalités débloquées
├── boostsRemaining: Number      # Nombre de boosts disponibles
├── superLikesRemaining: Number  # Nombre de super likes disponibles
├── lastRenewalAttempt: Timestamp # Dernière tentative de renouvellement
├── createdAt: Timestamp         # Date de création
└── updatedAt: Timestamp         # Date de mise à jour
```

#### 2.6.2 Considérations de Conception

**Gestion complète du cycle de vie**:
- Statuts clairs pour le suivi d'état (`isActive`, `autoRenew`)
- Dates précises pour contrôle d'accès et facturation
- Historique intégré pour traçabilité financière

**Personnalisation par plan**:
- Structure flexible pour différents types d'abonnements
- Compteurs de fonctionnalités consommables (boosts, super likes)
- Liste explicite des fonctionnalités activées pour évolution future

**Intégration système de paiement**:
- Conservation des informations de transaction sans données sensibles
- Support multi-devises
- Traçabilité des tentatives de renouvellement pour diagnostic

#### 2.6.3 Stratégie d'Indexation

**Index principaux**:
- `isActive` pour filtrage des abonnements actifs
- `endDate` pour détection des expiration imminentes
- `plan` pour statistiques et analyse

**Index composites utiles**:
- `isActive` + `endDate` pour notifications de renouvellement
- `autoRenew` + `endDate` pour traitement des renouvellements automatiques
- `userId` + `isActive` pour vérification rapide d'éligibilité

#### 2.6.4 Règles de Sécurité

```javascript
match /subscriptions/{userId} {
  // Lecture limitée à l'utilisateur concerné et aux administrateurs
  allow read: if request.auth != null && 
             (request.auth.uid == userId || isAdmin());
             
  // Modifications uniquement par système de paiement (Cloud Functions)
  allow write: if false;
}
```

### 2.7 Collection `resources`

Cette collection centralise le contenu informatif et éducatif de l'application.

#### 2.7.1 Structure

```
resources/{resourceId}
├── id: String                  # Identifiant unique
├── title: String               # Titre de la ressource
├── content: String             # Contenu principal
├── type: String                # 'article', 'video', 'link', 'contact'
├── category: String            # Catégorie thématique
├── tags: Array<String>         # Mots-clés pour recherche
├── imageUrl: String            # Image d'illustration
├── externalLink: String        # Lien externe (si applicable)
├── authorName: String          # Auteur ou source
├── isVerified: Boolean         # Validation par expert
├── language: String            # 'fr', 'en', etc.
├── publicationDate: Timestamp  # Date de publication
├── lastUpdated: Timestamp      # Date de mise à jour
├── viewCount: Number           # Nombre de consultations
└── isPremium: Boolean          # Accès premium uniquement
```

#### 2.7.2 Considérations de Conception

**Flexibilité de contenu**:
- Support de multiples types de ressources dans une structure unifiée
- Métadonnées riches pour catégorisation et recherche
- Structure multilingue native

**Qualité et confiance**:
- Indicateur de vérification par expert médical
- Attribution claire de la source
- Historique de mises à jour pour traçabilité

**Expérience utilisateur optimisée**:
- Champ `viewCount` pour mesurer la popularité
- Distinction claire entre contenu gratuit et premium
- Support de médias riches via URLs externes

#### 2.7.3 Stratégie d'Indexation

**Index principaux**:
- `type` pour filtrage par type de ressource
- `category` pour navigation par catégorie
- `tags` (array-contains) pour recherche par mot-clé
- `language` pour filtrage linguistique

**Index composites utiles**:
- `language` + `category` pour navigation localisée
- `isPremium` + `publicationDate` pour tri chronologique par niveau d'accès
- `isVerified` + `viewCount` pour contenu populaire vérifié

#### 2.7.4 Règles de Sécurité

```javascript
match /resources/{resourceId} {
  // Lecture par tous les utilisateurs authentifiés
  // (avec vérification premium si nécessaire)
  allow read: if request.auth != null && 
             (!resource.data.isPremium || isUserPremium());
             
  // Modification uniquement par administrateurs
  allow write: if request.auth != null && isAdmin();
}
```

## 3. Relations Entre Modèles

### 3.1 Mappings d'Identité

Les relations entre collections suivent une stratégie claire d'identifiants:

**Utilisateur et profil (1:1)**:
- Document `users/{userId}` lié à `profiles/{userId}` avec le même identifiant
- Permet de récupérer facilement le profil associé à un utilisateur
- Simplifie les règles de sécurité et les requêtes

**Utilisateur et vérification (1:1)**:
- Document `verifications/{userId}` utilise également l'ID utilisateur
- Garantit l'unicité du processus de vérification par utilisateur
- Facilite les vérifications d'autorisation

**Utilisateur et abonnement (1:1)**:
- Document `subscriptions/{userId}` suit la même convention
- Assure qu'un utilisateur ne peut avoir qu'un seul abonnement actif
- Simplifie la vérification du statut premium

### 3.2 Relations Complexes

**Utilisateurs et matches (N:M)**:
- Chaque document dans `matches` contient un tableau `users` avec exactement deux IDs
- Index array-contains permet de retrouver tous les matches d'un utilisateur
- Convention d'ID déterministe prévient les doublons

**Matches et messages (1:N)**:
- Chaque message contient une référence `matchId` à sa conversation parente
- Index sur `matchId` + `createdAt` optimise le chargement paginé
- L'absence de sous-collections évite les problèmes d'orphelins

### 3.3 Cardinalité et Contraintes

**Contraintes de cardinalité**:
- Un utilisateur a exactement un profil
- Un utilisateur a au maximum un document de vérification
- Un utilisateur a au maximum un abonnement
- Un utilisateur peut avoir de nombreux matches (N)
- Un match peut avoir de nombreux messages (N)
- Un match a exactement deux participants

**Contraintes d'intégrité**:
- L'existence du document `users` est vérifiée avant création du profil
- Les messages ne peuvent être créés que dans le contexte d'un match existant
- Les likes/matches suivent un workflow précis pour éviter les états incohérents

## 4. Stratégies de Dénormalisation

### 4.1 Principes de Dénormalisation

La dénormalisation est appliquée stratégiquement pour optimiser les performances:

**Critères de décision**:
- Fréquence d'accès aux données
- Coût des jointures implicites
- Fréquence de mise à jour
- Impact sur l'expérience utilisateur

**Types de dénormalisation utilisés**:
- Duplication de valeurs calculées
- Agrégation de compteurs
- Stockage d'aperçus
- Mise en cache de résultats de requêtes complexes

### 4.2 Exemples Clés de Dénormalisation

**Âge dans les profils**:
- L'âge est calculé à partir de la date de naissance et stocké dans `profiles.age`
- Mise à jour quotidienne via Cloud Function planifiée
- Élimine le calcul à chaque requête de matching
- Permet l'indexation directe pour filtrage par âge

**Statut de vérification dans les utilisateurs**:
- Le champ `isVerified` dans `users` duplique l'information de `verifications`
- Mise à jour atomique lors de l'approbation/rejet
- Permet des requêtes de filtrage sans jointure
- Critique pour les performances du matching

**Aperçu de message dans les matches**:
- Les champs `lastMessagePreview` et `lastMessageAt` dans `matches`
- Mis à jour à chaque nouveau message
- Permet d'afficher la liste des conversations sans requêtes multiples
- Évite le chargement de la collection messages pour l'aperçu

**Compteurs de messages non lus**:
- Map `unreadCount` dans les matches stocke les compteurs par utilisateur
- Incrémenté à l'envoi, réinitialisé à la lecture
- Évite de compter les messages non lus à chaque ouverture
- Critique pour l'affichage des badges de notification

### 4.3 Maintien de la Cohérence

La cohérence des données dénormalisées est assurée par:

**Cloud Functions déclenchées automatiquement**:
- Trigger sur création de message pour mettre à jour l'aperçu et compteurs
- Trigger sur vérification approuvée pour mettre à jour `isVerified`
- Fonction planifiée pour mettre à jour les âges

**Transactions Firestore**:
- Opérations atomiques pour modifications multi-documents
- Garantie de cohérence même en cas d'erreur partielle
- Utilisées pour les opérations critiques (création de match, approbation)

**Validation côté client**:
- Vérifications préliminaires avant soumission
- Réduction des états temporairement incohérents
- Amélioration de l'expérience utilisateur

## 5. Sécurité et Protection des Données

### 5.1 Architecture de Sécurité Multicouche

La protection des données repose sur plusieurs niveaux complémentaires:

**Authentification et autorisation**:
- Identification forte via Firebase Auth
- Vérification token JWT pour chaque requête
- Principe du moindre privilège dans les règles Firestore
- Validation contextuelle (appartenance à conversation, propriété de profil)

**Compartimentalisation des données**:
- Séparation stricte des données d'authentification et de profil
- Isolation des documents médicaux dans Storage
- Contrôle d'accès granulaire par collection et document

**Chiffrement des données sensibles**:
- Chiffrement natif au repos dans Firestore
- Chiffrement additionnel pour les URLs de documents sensibles
- Chiffrement en transit via HTTPS/TLS

### 5.2 Protection des Données Médicales

Les documents médicaux bénéficient de protections spécifiques:

**Stockage sécurisé**:
- Fichiers stockés dans Firebase Storage dans un bucket dédié
- Règles de sécurité strictes limitant l'accès aux administrateurs
- Chemins de fichiers non prédictibles avec composante aléatoire

**Processus de vérification**:
- Documents accessibles uniquement pendant le processus de vérification
- Suppression programmée après validation
- Aucune donnée médicale détaillée stockée dans Firestore

**Documentation et audit**:
- Journal complet des accès administratifs
- Traçabilité des actions de vérification
- Conservation des métadonnées pour conformité sans les documents eux-mêmes

### 5.3 Règles de Sécurité Globales

Des fonctions d'aide sont utilisées dans les règles de sécurité pour centraliser la logique:

```javascript
// Fonctions de vérification communes
function isAdmin() {
  return request.auth != null && 
         exists(/databases/$(database)/documents/users/$(request.auth.uid)) &&
         get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';
}

function isUserVerified() {
  return request.auth != null && 
         exists(/databases/$(database)/documents/users/$(request.auth.uid)) &&
         get(/databases/$(database)/documents/users/$(request.auth.uid)).data.isVerified == true;
}

function isUserPremium() {
  return request.auth != null && 
         exists(/databases/$(database)/documents/users/$(request.auth.uid)) &&
         get(/databases/$(database)/documents/users/$(request.auth.uid)).data.isPremium == true &&
         get(/databases/$(database)/documents/users/$(request.auth.uid)).data.premiumUntil > request.time;
}

function isUserBlocked(profileId, userId) {
  return exists(/databases/$(database)/documents/users/$(profileId)) &&
         userId in get(/databases/$(database)/documents/users/$(profileId)).data.blockedUsers;
}
```

## 6. Optimisation des Performances

### 6.1 Stratégies d'Indexation Avancées

L'indexation est optimisée pour les requêtes les plus fréquentes:

**Identification des requêtes critiques**:
- Recherche de profils compatibles (matching)
- Chargement des conversations récentes
- Pagination des messages dans une conversation
- Vérification des likes reçus (premium)

**Création d'index composites ciblés**:
- Index composites définis dans `firestore.indexes.json`
- Optimisation pour les parcours de collections avec filtres multiples
- Support prioritaire des tris (date, proximité) avec filtres

**Évitement de l'over-indexation**:
- Analyse des patterns de requête réels via monitoring
- Suppression des index inutilisés
- Limitation des champs indexés aux nécessités absolues

### 6.2 Stratégies de Requêtes Efficaces

Les patterns de requêtes suivent des principes d'optimisation:

**Requêtes paginées**:
- Utilisation systématique de `limit()` pour contrôler la taille des résultats
- Implémentation de curseurs avec `startAfter()` pour pagination efficace
- Préchargement intelligent du lot suivant pour expérience fluide

**Requêtes composées optimisées**:
- Utilisation de `array-contains` pour recherche dans les tableaux
- Limitation des opérations `in` aux cas nécessaires (max 10 valeurs)
- Combinaison judicieuse de filtres d'égalité et d'inégalité

**Stratégies de cache**:
- Persistance côté client activée pour données fréquemment consultées
- TTL adapté par type de donnée (profils: 1h, ressources: 24h)
- Invalidation sélective sur mise à jour

### 6.3 Optimisation des Écritures

Les opérations d'écriture sont optimisées pour la performance et la cohérence:

**Batching et transactions**:
- Opérations en lot pour modifications multi-documents
- Transactions atomiques pour maintenir la cohérence
- Limitation de la taille des batches (max 500 opérations)

**Mise à jour partielle**:
- Utilisation de `update()` plutôt que `set()` quand possible
- Mise à jour ciblée des champs modifiés uniquement
- Structures imbriquées pour mises à jour granulaires (`photos.main`)

**Gestion des contentions**:
- Évitement des hotspots (documents fréquemment mis à jour)
- Distribution temporelle des opérations planifiées
- Stratégies de retry avec backoff exponentiel

## 7. Cloud Functions et Logique Métier

### 7.1 Déclencheurs Firestore

Les principales Cloud Functions déclenchées par Firestore:

**Triggers utilisateur**:
- `onUserCreate`: Initialisation du profil après création de compte
- `onUserDelete`: Nettoyage des données associées (profil, matches, messages)
- `onUserUpdate`: Propagation des changements critiques (nom, visibilité)

**Triggers de matching**:
- `onMatchCreate`: Initialisation de la conversation, notifications
- `onMatchUpdate`: Gestion des changements de statut (blocage, suppression)

**Triggers de messages**:
- `onMessageCreate`: Mise à jour des aperçus, compteurs, notifications
- `onMessageUpdate`: Gestion des indicateurs de lecture

**Triggers de vérification**:
- `onVerificationUpdate`: Mise à jour du statut utilisateur après approbation/rejet
- `onVerificationCreate`: Planification de la vérification et notifications

### 7.2 Endpoints HTTP

Les principaux endpoints API exposés via Cloud Functions:

**API de matching**:
- `getRecommendedProfiles`: Algorithme complexe de recommandation
- `processSuperLike`: Traitement prioritaire des super likes
- `activateBoost`: Activation de boost de visibilité temporaire

**API de paiement**:
- `createPaymentSession`: Initialisation transaction MyCoolPay
- `processPaymentWebhook`: Traitement des notifications de paiement
- `cancelSubscription`: Gestion des annulations d'abonnement

**API de modération**:
- `reviewVerification`: Interface pour approbation/rejet de vérification
- `moderateContent`: Traitement des signalements de contenu
- `suspendUser`: Actions administratives sur comptes problématiques

### 7.3 Fonctions Planifiées

Les tâches récurrentes gérées par Cloud Functions planifiées:

**Maintenance quotidienne**:
- `updateAgeValues`: Recalcul des âges à partir des dates de naissance
- `cleanupExpiredVerifications`: Suppression des documents expirés
- `purgeOldMessages`: Archivage des messages anciens (premium > 200, gratuit > 50)

**Processus de facturation**:
- `processSubscriptionRenewals`: Tentative de renouvellement des abonnements
- `sendRenewalReminders`: Notifications avant expiration (7j, 3j, 1j)
- `downgradeExpiredAccounts`: Rétrogradation des comptes expirés

**Analytics et reporting**:
- `generateDailyStats`: Calcul des métriques d'utilisation
- `weeklyAdminReport`: Génération rapport administrateur
- `calculateUserRetention`: Analyse de rétention par cohorte

## 8. Limitations et Quotas

### 8.1 Limites Fonctionnelles

**Utilisateurs gratuits**:
- 20 likes par période de 24h
- 1 photo de profil
- Messages texte uniquement
- 50 messages stockés par conversation
- 100 profils bloqués maximum

**Utilisateurs premium**:
- Likes illimités
- Jusqu'à 6 photos
- Appels vidéo limités à 30 minutes
- 1 boost gratuit par mois
- 3 super likes par jour
- 200 messages stockés par conversation

### 8.2 Limites Techniques

**Contraintes Firestore**:
- Taille maximum document: 1 MiB
- 20k écritures par seconde par collection
- 1 écriture par seconde par document
- 500 opérations par transaction/batch
- 100 conditions par requête

**Stratégies d'adaptation**:
- Fragmentation des documents volumineux
- Distribution temporelle des écritures fréquentes
- Modèle de données évitant les hotspots
- Capping explicite des éléments à cardinalité potentiellement infinie

## 9. Évolution et Maintenance

### 9.1 Stratégie de Migration

**Principes pour l'évolution du schéma**:
- Compatibilité arrière pour les clients existants
- Migrations progressives avec versions parallèles
- Validations des données lors des accès

**Processus de migration**:
1. Déployer le code supportant ancien et nouveau schéma
2. Migrer les données par lots (fonction planifiée)
3. Vérifier l'intégrité post-migration
4. Supprimer le support de l'ancien schéma après période de transition

### 9.2 Surveillance et Maintenance

**Métriques clés surveillées**:
- Latence des requêtes principales
- Taux d'utilisation des quotas Firestore
- Répartition des coûts par collection
- Fréquence et nature des erreurs

**Processus de maintenance**:
- Revue hebdomadaire des performances
- Optimisation des requêtes problématiques
- Ajustement des index selon patterns d'utilisation
- Nettoyage périodique des données obsolètes

## 10. Conclusion

Le modèle de données backend de HIVMeet est conçu pour offrir un équilibre optimal entre performance, sécurité et flexibilité. Ses caractéristiques principales sont:

1. **Architecture NoSQL optimisée** pour les patterns d'accès spécifiques à une application de rencontres
2. **Protection multicouche des données sensibles**, particulièrement importantes dans le contexte médical
3. **Dénormalisation stratégique** pour maximiser les performances des requêtes fréquentes
4. **Évolutivité intégrée** permettant l'ajout futur de fonctionnalités sans refonte majeure
5. **Séparation claire des préoccupations** entre les différentes collections

Cette structure de données fournit une base solide pour le développement du MVP tout en posant les fondations pour l'évolution future de l'application.
