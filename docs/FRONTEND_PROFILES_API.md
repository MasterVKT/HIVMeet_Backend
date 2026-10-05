# 👤 API Profiles - Documentation Frontend

## 📋 Vue d'Ensemble

Le module Profiles gère les profils utilisateur complets, incluant les informations personnelles, les photos, les préférences de recherche, la géolocalisation et le système de vérification d'identité.

> **Contrat Phase 2.** La source API de référence est
> [API_DOCUMENTATION.md](API_DOCUMENTATION.md), complétée par le contrat
> [KYC v1](kyc/KYC_V1_CONTRACT.openapi.yaml). Les anciennes descriptions
> d'URLs Firebase/directes et de routes sans `/me/` dans ce document sont
> remplacées par les sections photo et KYC ci-dessous. Ne jamais persister une
> URL de média, une URL PUT KYC, un code de défi ou une référence de stockage.

## 🏗️ Architecture des Profils

### Structure des Données
**Principe :**
- Profil utilisateur séparé des données d'authentification
- Photos privées stockées par le backend; seules des routes API authentifiées
  sont retournées, jamais une URL directe de bucket
- Géolocalisation pour le matching par proximité
- Système de vérification d'identité multi-étapes
- Préférences de recherche personnalisables

### Relations
- Un profil par utilisateur (OneToOne)
- Plusieurs photos par profil (OneToMany)
- Une vérification par utilisateur (OneToOne)

## 📱 Endpoints de Gestion des Profils

### 1. Récupération du Profil Utilisateur

**Endpoint :** `GET /user-profiles/me`

**Headers Requis :**
```
Authorization: Bearer <access_token>
```

**Réponse Succès (200) :**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "bio": "Passionné de voyages et de rencontres authentiques...",
  "gender": "male",
  "location": {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "city": "Paris",
    "country": "France",
    "hide_exact_location": false
  },
  "interests": ["voyage", "cuisine", "art"],
  "relationship_types_sought": ["long_term", "friendship"],
  "search_preferences": {
    "age_min": 25,
    "age_max": 35,
    "distance_max_km": 25,
    "genders_sought": ["female", "non_binary"]
  },
  "photos": [
    {
      "id": "uuid",
      "photo_url": "/api/v1/user-profiles/media/photos/<photo_id>/main/",
      "thumbnail_url": "/api/v1/user-profiles/media/photos/<photo_id>/thumbnail/",
      "is_main": true,
      "order": 0,
      "caption": "Photo principale"
    }
  ],
  "visibility_settings": {
    "is_hidden": false,
    "show_online_status": true,
    "allow_profile_in_discovery": true
  },
  "statistics": {
    "profile_views": 125,
    "likes_received": 48
  },
  "verification_status": "verified",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-20T15:30:00Z"
}
```

**Logique d'Implémentation Frontend :**
- Appeler cet endpoint au login pour charger le profil complet
- Mettre en cache les données pour éviter les appels répétés
- Gérer le cas où le profil n'existe pas encore (nouveau utilisateur)
- Afficher les statistiques de manière attrayante

### 2. Création/Mise à Jour du Profil

**Endpoint :** `POST /user-profiles/` (création) ou `PUT /user-profiles/me` (mise à jour)

**Données Requises :**
```json
{
  "bio": "Description personnelle (max 500 caractères)",
  "gender": "male|female|non_binary|trans_male|trans_female|other|prefer_not_to_say",
  "location": {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "city": "Paris",
    "country": "France",
    "hide_exact_location": false
  },
  "interests": ["voyage", "cuisine", "art"],
  "relationship_types_sought": ["long_term", "friendship"],
  "search_preferences": {
    "age_min": 25,
    "age_max": 35,
    "distance_max_km": 25,
    "genders_sought": ["female", "non_binary"]
  },
  "visibility_settings": {
    "is_hidden": false,
    "show_online_status": true,
    "allow_profile_in_discovery": true
  }
}
```

**Réponse Succès (201/200) :**
```json
{
  "message": "Profile updated successfully",
  "profile": { /* profil complet */ }
}
```

**Logique d'Implémentation Frontend :**
- Valider la bio (max 500 caractères)
- Limiter les intérêts à 3 maximum
- Valider les plages d'âge (min ≤ max, entre 18-99)
- Valider la distance (5-100 km)
- Gérer la géolocalisation avec permissions
- Sauvegarder automatiquement les modifications

### 3. Récupération d'un Profil par ID

**Endpoint :** `GET /api/v1/user-profiles/{user_id}/`

**Principe d'Implémentation :**
- Vérifier que l'utilisateur n'est pas bloqué
- Respecter les paramètres de visibilité
- Incrémenter le compteur de vues automatiquement
- Retourner un profil filtré selon les permissions

**Réponse Succès (200) :**
```json
{
  "id": "uuid",
  "display_name": "John",
  "age": 28,
  "bio": "Bio publique...",
  "distance_km": 12,
  "photos": [
    {
      "photo_url": "/api/v1/user-profiles/media/photos/<photo_id>/main/",
      "thumbnail_url": "/api/v1/user-profiles/media/photos/<photo_id>/thumbnail/",
      "is_main": true
    }
  ],
  "interests": ["voyage", "cuisine"],
  "last_active": "2024-01-20T15:30:00Z",
  "is_verified": true,
  "is_premium": false
}
```

**Logique d'Implémentation Frontend :**
- Afficher la distance calculée automatiquement
- Gérer l'état de chargement pendant la récupération
- Implémenter le cache des profils consultés récemment
- Respecter les paramètres de visibilité

## 📸 Gestion des Photos

### 4. Upload de Photo

**Endpoint :** `POST /api/v1/user-profiles/me/photos/`

**Format :** `multipart/form-data`

**Données Requises :**
```
file: File (JPG/PNG, max 5 MiB)
caption: String (optionnel, max 200 caractères)
is_main: Boolean (optionnel)
```

**Principe d'Implémentation :**
1. Valider le fichier côté frontend (format, taille, dimensions)
2. Compresser/redimensionner si nécessaire
3. Upload vers le backend qui gère le stockage privé
4. Le backend génère automatiquement les thumbnails
5. Retourne des routes API authentifiées, sans URL de bucket ni clé de stockage

**Réponse Succès (201) :**
```json
{
  "photo_id": "uuid",
  "url": "/api/v1/user-profiles/media/photos/<photo_id>/main/",
  "thumbnail_url": "/api/v1/user-profiles/media/photos/<photo_id>/thumbnail/",
  "is_main": false,
  "caption": "Photo de voyage",
  "uploaded_at": "2026-10-02T10:00:00Z"
}
```

**Logique d'Implémentation Frontend :**
- Implémenter la validation locale avant upload
- Afficher une progress bar pendant l'upload
- Gérer la rotation automatique selon l'EXIF
- Limiter à 6 photos maximum par profil
- Permettre la réorganisation par drag & drop
- Lire une route photo avec l'authentification normale; elle est refusée pour
  la photo d'autrui dès que le KYC n'est plus actif. Ne pas la stocker dans un
  cache persistant ou des diagnostics.

### 5. Mise à Jour des Photos

**Endpoint :** `PUT /api/v1/user-profiles/me/photos/{photo_id}/`

**Données Modifiables :**
```json
{
  "caption": "Nouvelle légende",
  "is_main": true,
  "order": 1
}
```

**Logique d'Implémentation Frontend :**
- Une seule photo principale autorisée (désactiver les autres automatiquement)
- Permettre la réorganisation avec numéros d'ordre
- Mettre à jour l'interface en temps réel

### 6. Suppression de Photo

**Endpoint :** `DELETE /api/v1/user-profiles/me/photos/{photo_id}/`

**Logique d'Implémentation Frontend :**
- Demander confirmation avant suppression
- Empêcher la suppression de la dernière photo
- Si photo principale supprimée, promouvoir automatiquement la suivante

## ✅ Système de Vérification

> **Contrat KYC v1 canonique :** utiliser exclusivement
> [KYC API v1](kyc/KYC_V1_CONTRACT.openapi.yaml) et le
> [cadrage de phase 0](kyc/KYC_PHASE_0_GOVERNANCE.md). Le serveur expose
> `GET /me/verification/` sans effet de bord, puis `POST start/`,
> `POST upload-intents/`, `POST upload-intents/complete/` et `POST submit/`.
> L'URL PUT émise par une intention est éphémère, ne porte pas de bearer token
> et ne doit jamais être journalisée, analysée, notifiée ou mise en cache.
> Le client ne transmet que les identifiants opaques d'upload à `complete` et
> `submit`; il ne transmet jamais de chemin de stockage. Les routes historiques
> `generate-upload-url/` et `submit-documents/` répondent `410`
> `kyc_legacy_endpoint_deprecated` et ne doivent jamais être intégrées.
>
> Seuls une identité officielle, un document médical ou sérologique de moins
> de 90 jours et un selfie au défi à usage unique sont admis. La revue est
> humaine et interne, sans biométrie ni fournisseur externe. La réalisation
> Flutter complète appartient à la phase 4; ce guide ne constitue pas une
> activation de production.

## 🎯 Préférences et Paramètres

### 9. Mise à Jour des Préférences de Recherche

**Endpoint :** `PUT /user-profiles/search-preferences`

**Données Modifiables :**
```json
{
  "age_min": 25,
  "age_max": 35,
  "distance_max_km": 50,
  "genders_sought": ["female", "non_binary"],
  "relationship_types": ["long_term", "friendship"]
}
```

**Logique d'Implémentation Frontend :**
- Utiliser des sliders pour l'âge et la distance
- Permettre sélection multiple pour les genres
- Valider les contraintes (min ≤ max)
- Sauvegarder automatiquement les modifications

### 10. Paramètres de Visibilité

**Endpoint :** `PUT /user-profiles/visibility-settings`

**Données Modifiables :**
```json
{
  "is_hidden": false,
  "show_online_status": true,
  "allow_profile_in_discovery": true,
  "hide_exact_location": false
}
```

**Fonctionnalités Premium :**
- `is_hidden` : Mode invisible (premium)
- Contrôle granulaire de la visibilité (premium)

## 📍 Géolocalisation

### Principe d'Implémentation Géolocalisation
**Logique Frontend :**
1. Demander les permissions de géolocalisation
2. Récupérer les coordonnées GPS
3. Utiliser un service de géocodage inverse pour obtenir ville/pays
4. Permettre à l'utilisateur de masquer la localisation exacte
5. Mettre à jour la position périodiquement (avec consentement)

**Gestion de la Confidentialité :**
- Option pour masquer la localisation exacte
- Affichage de la ville uniquement si activé
- Distance approximative dans les résultats de recherche
- Possibilité de définir une localisation manuelle

## 🔍 Recherche et Découverte

### 11. Profils Suggérés

**Endpoint :** `GET /user-profiles/suggestions`

**Paramètres de Requête :**
```
page: 1
per_page: 20
```

**Logique d'Algorithme :**
- Filtrage selon les préférences utilisateur
- Exclusion des profils déjà likés/dislikés
- Tri par proximité géographique
- Boost des profils vérifiés
- Rotation pour éviter la répétition

### 12. Recherche Avancée

**Endpoint :** `GET /user-profiles/search`

**Paramètres de Requête :**
```
age_min: 25
age_max: 35
distance_max: 50
interests: "voyage,cuisine"
relationship_type: "long_term"
```

**Fonctionnalités Premium :**
- Filtres avancés (profession, éducation, etc.)
- Recherche par mots-clés dans la bio
- Tri personnalisé des résultats

## 📊 Statistiques et Analytics

### 13. Statistiques du Profil

**Endpoint :** `GET /user-profiles/statistics`

**Réponse :**
```json
{
  "profile_views": {
    "total": 125,
    "last_7_days": 15,
    "trend": "increasing"
  },
  "likes_received": {
    "total": 48,
    "last_7_days": 8
  },
  "matches": {
    "total": 12,
    "last_7_days": 2
  },
  "premium_features": {
    "who_liked_you": 15,
    "boosts_remaining": 2
  }
}
```

**Logique d'Implémentation Frontend :**
- Afficher les statistiques de manière graphique
- Identifier les tendances (croissance/décroissance)
- Suggérer des améliorations du profil
- Promouvoir les fonctionnalités premium

## 🚨 Gestion d'Erreurs Spécifiques

### Erreurs de Validation
- **Bio trop longue** : Compteur de caractères en temps réel
- **Intérêts > 3** : Limitation dans l'interface
- **Photos > 6** : Désactiver le bouton d'ajout
- **Age invalide** : Validation des plages

### Erreurs de Géolocalisation
- **Permission refusée** : Permettre la saisie manuelle
- **Localisation imprécise** : Afficher un avertissement
- **Service indisponible** : Mode dégradé sans géolocalisation

### Erreurs de Vérification
- **Document illisible** : Suggestions d'amélioration
- **Format non supporté** : Liste des formats acceptés
- **Fichier trop volumineux** : Compression automatique

## 🔐 Sécurité et Confidentialité

### Protection des Données Sensibles
**Principe d'Implémentation :**
- Chiffrement des documents de vérification
- Pas de stockage local des informations sensibles
- Anonymisation des données d'analyse
- Respect du RGPD et des réglementations locales

### Modération de contenu
- Détection de contenu inapproprié dans les photos
- Filtrage des mots offensants dans la bio
- Aucun traitement KYC automatisé, biométrique ou par fournisseur externe ;
  la décision KYC relève exclusivement d'une revue humaine interne.
- Signalement automatique des comportements suspects

## 📱 Optimisations Mobile

### Performance
- Lazy loading des photos
- Compression des images selon la connexion
- Cache intelligent des profils consultés
- Synchronisation en arrière-plan

### UX Mobile
- Interface tactile optimisée
- Gestes de navigation intuitifs
- Adaptation à différentes tailles d'écran
- Mode sombre/clair automatique

Cette documentation couvre tous les aspects de la gestion des profils nécessaires pour une intégration frontend complète avec le backend HIVMeet.
