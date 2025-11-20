# 🔐 Instructions Complètes - Authentification Hybride Frontend

## 🎯 Objectif

Implémenter le système d'authentification hybride Firebase Auth + Django JWT pour l'application HIVMeet Flutter, permettant une connexion sécurisée et l'accès à toutes les APIs du backend.

## 📋 Architecture du Système d'Authentification

### Principe de Fonctionnement

**Flux Général :**
1. **Connexion Firebase** : L'utilisateur se connecte via Firebase Auth
2. **Récupération Token Firebase** : Obtention du token Firebase ID
3. **Échange de Token** : Envoi du token Firebase au backend Django
4. **Réception Tokens JWT** : Le backend retourne des tokens JWT Django
5. **Utilisation APIs** : Tous les appels API utilisent le token JWT Django

### États d'Authentification

**États Possibles :**
- `DISCONNECTED` : Aucune authentification
- `FIREBASE_CONNECTED` : Connecté à Firebase mais pas encore échangé
- `TOKENS_EXCHANGED` : Tokens JWT Django obtenus
- `FULLY_AUTHENTICATED` : Prêt pour utiliser les APIs

## 🏗️ Structure d'Implémentation

### 1. Service d'Authentification Centralisé

**Objectif :** Créer un service unique qui gère tout le flux d'authentification.

**Fonctionnalités Requises :**

1. **Initialisation Firebase**
   - Configurer Firebase Auth avec les paramètres du projet
   - Établir les listeners d'état d'authentification
   - Gérer les changements d'utilisateur automatiquement

2. **Gestion des États**
   - Maintenir l'état actuel d'authentification
   - Notifier les autres parties de l'application des changements
   - Persister l'état entre les redémarrages d'application

3. **Stockage Sécurisé des Tokens**
   - Utiliser Flutter Secure Storage pour les tokens JWT
   - Chiffrer les données sensibles
   - Gérer l'expiration et le nettoyage des tokens

### 2. Gestion de l'Échange de Tokens

**Processus Détaillé :**

**Phase 1 : Vérification Utilisateur Firebase**
- Vérifier si un utilisateur est connecté à Firebase Auth
- Si non connecté, rediriger vers l'écran de connexion
- Si connecté, procéder à la phase 2

**Phase 2 : Récupération Token Firebase**
- Appeler la méthode `getIdToken()` de Firebase Auth
- Gérer le cas où le token a expiré (re-authentification)
- Vérifier que le token n'est pas null ou vide
- Logger l'obtention du token pour le debugging

**Phase 3 : Appel Endpoint d'Échange**
- Préparer la requête HTTP POST vers `/api/v1/auth/firebase-exchange/`
- Inclure le token Firebase dans le corps de la requête
- Définir les headers appropriés (Content-Type: application/json)
- Gérer les timeouts et erreurs de connexion

**Phase 4 : Traitement de la Réponse**
- Analyser le code de statut HTTP de la réponse
- Parser le JSON de réponse
- Extraire les tokens `access` et `refresh`
- Extraire les informations utilisateur
- Stocker les données de manière sécurisée

**Phase 5 : Gestion des Erreurs**
- Code 400 (`MISSING_TOKEN`) : Problème dans l'envoi du token
- Code 401 (`INVALID_FIREBASE_TOKEN`) : Token Firebase invalide ou expiré
- Code 404 (`USER_NOT_FOUND`) : Utilisateur inexistant, rediriger vers inscription
- Code 500 (`INTERNAL_ERROR`) : Erreur serveur, réessayer plus tard

### 3. Intercepteur de Requêtes

**Objectif :** Automatiser l'ajout du token JWT à toutes les requêtes API.

**Fonctionnalités :**

1. **Injection Automatique du Token**
   - Intercepter toutes les requêtes sortantes vers l'API
   - Ajouter automatiquement l'header `Authorization: Bearer <access_token>`
   - Exclure les endpoints qui ne nécessitent pas d'authentification

2. **Gestion de l'Expiration**
   - Détecter les réponses 401 (token expiré)
   - Tenter automatiquement le refresh du token
   - Relancer la requête originale avec le nouveau token
   - Gérer l'échec du refresh (redirection vers connexion)

3. **Gestion du Refresh Token**
   - Appeler l'endpoint `/api/v1/auth/refresh-token/` avec le refresh token
   - Mettre à jour le access token stocké
   - Gérer l'expiration du refresh token (re-authentification complète)

### 4. Interface Utilisateur d'Authentification

**Écrans Requis :**

1. **Écran de Connexion**
   - Champs email et mot de passe
   - Bouton de connexion avec loading state
   - Option "Se souvenir de moi"
   - Liens vers inscription et mot de passe oublié
   - Gestion des erreurs d'authentification

2. **Écran d'Inscription**
   - Champs requis selon les spécifications API
   - Validation en temps réel des données
   - Création du compte Firebase puis Django
   - Gestion des erreurs (email déjà utilisé, etc.)

3. **Écran de Chargement**
   - Affiché pendant l'échange de tokens
   - Indicateur de progression
   - Possibilité d'annuler l'opération
   - Messages informatifs pour l'utilisateur

## 🔄 Logiques d'Implémentation Détaillées

### Logique de Connexion

**Étape 1 : Validation des Entrées Utilisateur**
- Vérifier que l'email est au format valide
- Vérifier que le mot de passe respecte les critères minimum
- Afficher les erreurs de validation en temps réel
- Désactiver le bouton de connexion si les données sont invalides

**Étape 2 : Authentification Firebase**
- Appeler `signInWithEmailAndPassword` de Firebase Auth
- Gérer les erreurs spécifiques de Firebase (compte non vérifié, mot de passe incorrect, etc.)
- Afficher les messages d'erreur appropriés à l'utilisateur
- Mettre à jour l'état de l'interface (loading, success, error)

**Étape 3 : Échange de Token Automatique**
- Dès que la connexion Firebase réussit, déclencher l'échange de token
- Afficher un indicateur de progression pour cette phase
- Ne pas permettre à l'utilisateur d'accéder à l'application avant la fin de l'échange
- Stocker tous les tokens et informations utilisateur reçus

**Étape 4 : Navigation Post-Connexion**
- Vérifier si le profil utilisateur est complet
- Rediriger vers la création de profil si nécessaire
- Rediriger vers l'écran principal si tout est configuré
- Initialiser les services qui dépendent de l'authentification

### Logique de Gestion des Tokens

**Stockage des Tokens :**
- Utiliser une clé unique pour chaque type de token
- Préfixer les clés avec l'identifiant de l'application
- Inclure un timestamp de création pour gérer l'expiration
- Chiffrer les tokens avant stockage

**Vérification de Validité :**
- Vérifier l'expiration avant chaque utilisation
- Parser le JWT pour extraire les informations d'expiration
- Implémenter une marge de sécurité (refresh 2-3 minutes avant expiration)
- Gérer les cas de corruption ou modification des tokens

**Processus de Refresh :**
- Détecter automatiquement les tokens expirés
- Utiliser le refresh token pour obtenir un nouveau access token
- Mettre à jour le stockage avec les nouveaux tokens
- Notifier les autres composants du changement

### Logique de Gestion des Erreurs

**Catégorisation des Erreurs :**

1. **Erreurs de Connexion :**
   - Pas de connexion internet
   - Serveur inaccessible
   - Timeout de requête
   - Action : Afficher message de retry, proposer réessayer

2. **Erreurs d'Authentification :**
   - Credentials invalides
   - Compte suspendu
   - Email non vérifié
   - Action : Afficher message spécifique, rediriger si nécessaire

3. **Erreurs de Token :**
   - Token Firebase expiré
   - Token JWT invalide
   - Refresh token expiré
   - Action : Re-authentification automatique ou manuelle

4. **Erreurs Serveur :**
   - Erreur interne (500)
   - Service indisponible (503)
   - Action : Retry automatique avec backoff exponentiel

### Logique de Synchronisation

**Synchronisation Firebase ↔ Backend :**
- Écouter les changements d'état Firebase Auth
- Synchroniser automatiquement avec l'état backend
- Gérer les cas de désynchronisation
- Implémenter une réconciliation périodique

**Gestion Multi-Onglets :**
- Partager l'état d'authentification entre onglets/instances
- Synchroniser les tokens entre les instances de l'application
- Gérer la déconnexion depuis une autre instance

## 📱 Intégration avec l'Interface Utilisateur

### State Management

**États Globaux à Gérer :**
- `AuthenticationState` : État courant de l'authentification
- `UserState` : Informations de l'utilisateur connecté
- `TokenState` : État et validité des tokens
- `LoadingState` : États de chargement des opérations d'auth

**Notifications d'État :**
- Notifier tous les écrans des changements d'authentification
- Mettre à jour automatiquement l'interface selon l'état
- Gérer les redirections automatiques selon l'état

### Navigation Conditionnelle

**Logique de Navigation :**
- Vérifier l'état d'authentification avant chaque navigation
- Rediriger automatiquement vers la connexion si non authentifié
- Maintenir la destination prévue pour redirection post-connexion
- Gérer les deep links avec authentification requise

### Gestion des Données Utilisateur

**Cache Local :**
- Mettre en cache les informations utilisateur essentielles
- Synchroniser avec le serveur périodiquement
- Gérer l'expiration du cache
- Nettoyer le cache à la déconnexion

**Persistance :**
- Persister l'état d'authentification entre redémarrages
- Maintenir les préférences utilisateur
- Gérer la migration de données entre versions

## 🔒 Sécurité et Bonnes Pratiques

### Principes de Sécurité

1. **Protection des Tokens :**
   - Ne jamais logger les tokens complets
   - Utiliser le stockage sécurisé natif
   - Implémenter une expiration automatique
   - Nettoyer les tokens à la déconnexion

2. **Validation Côté Client :**
   - Valider tous les inputs avant envoi au serveur
   - Implémenter des timeouts raisonnables
   - Gérer les tentatives de brute force (rate limiting)
   - Valider les réponses serveur

3. **Gestion des Sessions :**
   - Implémenter une déconnexion automatique après inactivité
   - Gérer les connexions multiples
   - Invalider les sessions lors de changements critiques

### Debugging et Monitoring

**Logs Recommandés :**
- États de transition d'authentification
- Erreurs d'authentification (sans données sensibles)
- Tentatives d'échange de tokens
- Performance des opérations d'auth

**Métriques à Tracker :**
- Temps de connexion moyen
- Taux de succès d'authentification
- Fréquence de refresh des tokens
- Erreurs d'API d'authentification

## 🚀 Flux d'Implémentation Recommandé

### Phase 1 : Base d'Authentification
1. Configurer Firebase Auth dans l'application
2. Créer le service d'authentification centralisé
3. Implémenter le stockage sécurisé des tokens
4. Créer les écrans de base (connexion, inscription)

### Phase 2 : Échange de Tokens
1. Implémenter la logique d'échange Firebase → Django JWT
2. Gérer tous les cas d'erreur de l'échange
3. Tester avec différents scénarios utilisateur
4. Valider la persistance des tokens

### Phase 3 : Intercepteur de Requêtes
1. Créer l'intercepteur HTTP pour injection automatique
2. Implémenter la logique de refresh automatique
3. Gérer les cas d'échec de refresh
4. Tester avec toutes les APIs de l'application

### Phase 4 : Intégration Complète
1. Intégrer avec le state management global
2. Implémenter la navigation conditionnelle
3. Ajouter les fonctionnalités avancées (remember me, etc.)
4. Optimiser les performances et l'UX

### Phase 5 : Tests et Validation
1. Tester tous les scénarios d'authentification
2. Valider la sécurité et la persistance
3. Tester la synchronisation multi-instances
4. Valider l'intégration avec toutes les fonctionnalités app

## 📋 Checklist de Validation

### Tests d'Authentification
- [ ] Connexion avec credentials valides
- [ ] Gestion des credentials invalides
- [ ] Inscription nouveau utilisateur
- [ ] Vérification email après inscription
- [ ] Réinitialisation mot de passe
- [ ] Déconnexion et nettoyage des données

### Tests d'Échange de Tokens
- [ ] Échange réussi Firebase → Django JWT
- [ ] Gestion token Firebase expiré
- [ ] Gestion utilisateur inexistant backend
- [ ] Gestion erreurs serveur
- [ ] Retry automatique en cas d'échec réseau

### Tests de Persistance
- [ ] Tokens persistés entre redémarrages
- [ ] Reconnexion automatique au démarrage
- [ ] Nettoyage complet à la déconnexion
- [ ] Gestion expiration tokens stockés

### Tests d'Intégration API
- [ ] Injection automatique token dans requêtes
- [ ] Refresh automatique token expiré
- [ ] Gestion échec refresh (redirection connexion)
- [ ] Fonctionnement avec toutes les APIs

### Tests de Sécurité
- [ ] Tokens stockés de manière sécurisée
- [ ] Pas de logs de tokens complets
- [ ] Validation inputs utilisateur
- [ ] Gestion timeouts et rate limiting

## 🎯 Résultat Attendu

Une fois l'implémentation complète, l'application devra :
- Connecter automatiquement l'utilisateur au démarrage si tokens valides
- Gérer transparentement l'échange Firebase → Django JWT
- Injecter automatiquement les tokens JWT dans toutes les requêtes API
- Refresh automatiquement les tokens expirés
- Rediriger vers connexion seulement si nécessaire
- Maintenir une session stable et sécurisée

L'utilisateur ne devra plus voir d'erreurs 401 et toutes les fonctionnalités de l'application seront accessibles après une connexion réussie. 