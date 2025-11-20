# 🔗 Guide d'Intégration Frontend HIVMeet

## 📋 Vue d'Ensemble

Ce document constitue la documentation technique complète pour l'intégration du frontend Flutter avec le backend HIVMeet. Il détaille toutes les APIs, logiques métier, et principes d'implémentation nécessaires pour une intégration sans erreurs.

## 🏗️ Architecture Générale

### Base URL de l'API
```
Production: https://api.hivmeet.com/api/v1/
Staging: https://staging-api.hivmeet.com/api/v1/
Development: http://localhost:8000/api/v1/
```

### Format des Réponses
Toutes les réponses API suivent un format JSON standardisé :

**Succès :**
```json
{
  "data": { ... },
  "message": "Optionnel",
  "pagination": { ... } // Si applicable
}
```

**Erreur :**
```json
{
  "error": true,
  "message": "Description de l'erreur",
  "details": { ... }, // Détails spécifiques
  "code": "ERROR_CODE"
}
```

## 🔐 Authentification et Sécurité

### Système d'Authentification Hybride
Le backend utilise un système hybride Firebase Auth + JWT :

1. **Firebase Auth** : Authentification primaire
2. **JWT Backend** : Tokens pour les APIs internes
3. **Synchronisation** : Les comptes sont synchronisés entre Firebase et Django

### Flow d'Authentification
1. Inscription/Connexion via Firebase Auth
2. Récupération du token Firebase ID
3. Échange du token Firebase contre des tokens JWT backend
4. Utilisation des tokens JWT pour toutes les requêtes API

### Headers Requis
```
Authorization: Bearer <jwt_access_token>
Content-Type: application/json
Accept: application/json
Accept-Language: fr|en
```

## 📱 Applications et Modules

### [📑 Module Authentication](FRONTEND_AUTH_API.md)
- Inscription et connexion
- Gestion des tokens
- Vérification email
- Réinitialisation mot de passe
- Tokens FCM pour notifications

### [👤 Module Profiles](FRONTEND_PROFILES_API.md)
- Gestion des profils utilisateur
- Upload et gestion des photos
- Système de vérification
- Préférences et paramètres
- Géolocalisation

### [💕 Module Matching](FRONTEND_MATCHING_API.md)
- Découverte de profils
- Système de likes/dislikes
- Algorithme de matching
- Fonctionnalités premium (super likes, boosts)
- Filtres de recherche

### [💬 Module Messaging](FRONTEND_MESSAGING_API.md)
- Messagerie temps réel
- Gestion des conversations
- Messages multimédias
- Appels audio/vidéo
- Indicateurs de frappe

### [💳 Module Subscriptions](FRONTEND_SUBSCRIPTIONS_API.md)
- Plans d'abonnement
- Gestion premium
- Intégration MyCoolPay
- Fonctionnalités premium
- Webhooks et synchronisation

### [📚 Module Resources](FRONTEND_RESOURCES_API.md)
- Contenu éducatif
- Articles et catégories
- Feed personnalisé
- Système de likes
- Contenu multilingue

## 🔄 Gestion des Erreurs Globales

### Codes d'Erreur Standardisés
- `AUTHENTICATION_REQUIRED` : Token manquant ou invalide
- `PERMISSION_DENIED` : Accès non autorisé
- `VALIDATION_ERROR` : Données invalides
- `RATE_LIMIT_EXCEEDED` : Limite dépassée
- `SERVER_ERROR` : Erreur serveur
- `NOT_FOUND` : Ressource non trouvée
- `PREMIUM_REQUIRED` : Fonctionnalité premium requise

### Stratégies de Gestion
1. **Erreurs d'authentification** : Redirection vers login
2. **Erreurs réseau** : Retry automatique avec backoff
3. **Erreurs de validation** : Affichage des erreurs spécifiques
4. **Erreurs premium** : Redirection vers upgrade

## 🌐 Internationalisation

### Langues Supportées
- `fr` : Français (défaut)
- `en` : Anglais

### Implémentation
- Header `Accept-Language` pour chaque requête
- Réponses localisées automatiquement
- Messages d'erreur traduits

## 📊 Pagination et Performance

### Format de Pagination
```json
{
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "pages": 8,
    "has_next": true,
    "has_previous": false
  }
}
```

### Optimisations Recommandées
- Pagination pour toutes les listes
- Cache local des données statiques
- Lazy loading des images
- Compression des requêtes

## 🔔 Système de Notifications

### Types de Notifications
1. **Push Notifications** : Via Firebase Cloud Messaging
2. **In-App Notifications** : WebSocket ou polling
3. **Emails** : Notifications importantes

### Configuration FCM
- Registration des tokens via `/auth/fcm-token`
- Gestion des topics pour notifications groupées
- Personnalisation selon les préférences utilisateur

## 🛡️ Sécurité et Bonnes Pratiques

### Validation Côté Client
- Validation des champs avant envoi
- Sanitisation des entrées utilisateur
- Vérification des formats (email, téléphone, etc.)

### Gestion des Données Sensibles
- Chiffrement des données locales sensibles
- Pas de stockage des mots de passe
- Rotation automatique des tokens

### Rate Limiting
- Respect des limites par endpoint
- Gestion gracieuse des erreurs 429
- Backoff exponentiel pour les retries

## 🔄 États et Synchronisation

### Gestion d'État Recommandée
1. **État local** : Interface utilisateur
2. **Cache local** : Données fréquemment utilisées
3. **Synchronisation** : Périodique avec le backend
4. **État hors ligne** : Actions en attente

### Patterns de Synchronisation
- **Optimistic updates** : MAJ immédiate avec rollback si erreur
- **Conflict resolution** : Gestion des conflits de données
- **Background sync** : Synchronisation en arrière-plan

## 📈 Monitoring et Analytics

### Métriques Recommandées
- Temps de réponse des APIs
- Taux d'erreur par endpoint
- Utilisation des fonctionnalités
- Performance de l'interface

### Debugging
- Logs détaillés des requêtes API
- Tracking des erreurs avec contexte
- Métriques de performance utilisateur

## 🚀 Déploiement et Environnements

### Environnements
- **Development** : Tests et développement
- **Staging** : Tests d'intégration
- **Production** : Utilisateurs finaux

### Configuration par Environnement
- URLs API différentes
- Clés Firebase spécifiques
- Paramètres de debug/logging
- Certificats SSL

## 📞 Support et Maintenance

### Versioning API
- Versioning sémantique
- Rétrocompatibilité garantie
- Documentation des changements
- Migration guides

### Support Technique
- Documentation détaillée par module
- Exemples d'intégration
- Guide de troubleshooting
- Contact support technique

---

## 📚 Documentation Détaillée par Module

Pour chaque module, consultez la documentation spécifique :

1. **[Authentication API](FRONTEND_AUTH_API.md)** - Authentification et gestion des utilisateurs
2. **[Profiles API](FRONTEND_PROFILES_API.md)** - Gestion des profils et photos
3. **[Matching API](FRONTEND_MATCHING_API.md)** - Système de matching et découverte
4. **[Messaging API](FRONTEND_MESSAGING_API.md)** - Messagerie et appels
5. **[Subscriptions API](FRONTEND_SUBSCRIPTIONS_API.md)** - Abonnements premium
6. **[Resources API](FRONTEND_RESOURCES_API.md)** - Contenu éducatif

Chaque documentation module contient :
- Endpoints disponibles
- Formats de données
- Logiques métier spécifiques
- Cas d'usage et workflows
- Gestion d'erreurs spécifiques
- Principes d'implémentation frontend 