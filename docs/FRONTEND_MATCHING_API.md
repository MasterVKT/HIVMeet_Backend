# 💕 API Matching - Documentation Frontend

> ## Contrat d’interactions actif
>
> Une action de découverte renvoie un `interaction_id` stable tant qu’elle reste
> active. Le même swipe est idempotent. Après un rewind ou une révocation, une
> nouvelle action reçoit un nouvel `interaction_id` : le client doit toujours
> utiliser celui de la réponse la plus récente pour le rewind explicite.
>
> Un profil ne peut avoir qu’une interaction active par utilisateur. Les
> historiques masquent par défaut les lignes révoquées ; `interaction_type` vaut
> `like`, `super_like` ou `dislike`, afin que le client affiche distinctement un
> Super Like. Aucun endpoint existant ni quota n’est modifié.

## 📋 Vue d'Ensemble

Le module Matching gère le système de découverte de profils, les likes/dislikes, l'algorithme de matching, et les fonctionnalités premium associées (super likes, boosts, rewind).

## 🏗️ Architecture du Matching

### Principe de Fonctionnement
**Logique Métier :**
- Algorithme de matching basé sur la géolocalisation et les préférences
- Système de likes mutuels pour créer des matches
- Fonctionnalités premium pour améliorer la visibilité
- Limitation des likes quotidiens pour les utilisateurs gratuits
- Cache intelligent pour éviter les répétitions

### États des Interactions
1. **Aucune interaction** : Profil jamais vu
2. **Like envoyé** : En attente de réciprocité
3. **Dislike/Pass** : Profil écarté temporairement
4. **Match** : Like mutuel, conversation possible
5. **Super Like** : Like premium avec notification

## 🔍 Endpoints de Découverte

### 1. Profils à Découvrir

**Endpoint :** `GET /discovery/`

**Paramètres de Requête :**
```
page: 1
per_page: 10
latitude: 48.8566 (optionnel)
longitude: 2.3522 (optionnel)
```

**Principe d'Algorithme :**
1. Filtrage selon les préférences de l'utilisateur (âge, genre, distance)
2. Exclusion des profils déjà likés/dislikés
3. Exclusion des utilisateurs bloqués
4. Boost des profils vérifiés et récemment actifs
5. Tri par score de compatibilité et proximité

**Réponse Succès (200) :**
```json
{
  "profiles": [
    {
      "id": "uuid",
      "display_name": "Sarah",
      "age": 28,
      "distance_km": 5.2,
      "photos": [
        {
          "photo_url": "https://...",
          "thumbnail_url": "https://...",
          "is_main": true
        }
      ],
      "bio": "Amoureuse de la nature et des voyages...",
      "interests": ["voyage", "randonnée", "photographie"],
      "is_verified": true,
      "is_online": false,
      "last_active": "2024-01-20T10:30:00Z",
      "compatibility_score": 85,
      "mutual_interests": ["voyage", "photographie"]
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 150,
    "has_next": true
  }
}
```

**Logique d'Implémentation Frontend :**
- Implémenter le lazy loading pour charger les profils à la demande
- Précharger 2-3 profils en avance pour une navigation fluide
- Gérer le cache local pour éviter les rechargements
- Afficher le score de compatibilité et les intérêts communs
- Implémenter les gestes de swipe (gauche/droite)

### 2. Configuration des Filtres de Découverte

**Endpoint :** `POST /discovery/filters`

**Données Requises :**
```json
{
  "age_min": 25,
  "age_max": 35,
  "distance_max_km": 50,
  "genders": ["female", "non_binary"],
  "relationship_types": ["long_term", "casual"],
  "interests": ["voyage", "cuisine"], // Optionnel
  "verified_only": false, // Premium
  "online_only": false // Premium
}
```

**Réponse Succès (200) :**
```json
{
  "message": "Filters updated successfully",
  "estimated_profiles": 1240
}
```

**Logique d'Implémentation Frontend :**
- Utiliser des sliders pour l'âge et la distance
- Interface toggle pour les options premium
- Estimation en temps réel du nombre de profils disponibles
- Sauvegarde automatique des préférences
- Alerte si les filtres sont trop restrictifs

## 💝 Système de Likes et Matches

### 3. Envoyer un Like

**Endpoint :** `POST /matches/`

**Données Requises :**
```json
{
  "target_profile_id": "uuid",
  "action": "like",
  "like_type": "regular" // ou "super"
}
```

**Principe d'Implémentation :**
1. Vérifier les limites quotidiennes de likes
2. Créer l'interaction dans la base de données
3. Vérifier s'il y a réciprocité pour créer un match
4. Envoyer une notification push si match
5. Mettre à jour les statistiques

**Réponse Succès (200) :**
```json
{
  "result": "match", // ou "like_sent"
  "match_id": "uuid", // si match
  "daily_likes_remaining": 8,
  "super_likes_remaining": 2,
  "message": "It's a match!"
}
```

**Logique d'Implémentation Frontend :**
- Animation de swipe vers la droite
- Affichage immédiat du résultat (optimistic UI)
- Popup de célébration en cas de match
- Mise à jour du compteur de likes restants
- Redirection vers la conversation si match

### 4. Envoyer un Dislike/Pass

**Endpoint :** `POST /matches/`

**Données Requises :**
```json
{
  "target_profile_id": "uuid",
  "action": "dislike"
}
```

**Réponse Succès (200) :**
```json
{
  "result": "dislike_sent",
  "message": "Profile passed"
}
```

**Logique d'Implémentation Frontend :**
- Animation de swipe vers la gauche
- Transition fluide vers le profil suivant
- Pas de feedback visuel excessif (discret)
- Possibilité de rewind (fonctionnalité premium)

### 5. Liste des Matches

**Endpoint :** `GET /matches/`

**Paramètres de Requête :**
```
page: 1
per_page: 20
filter: "all|new|active"
```

**Réponse Succès (200) :**
```json
{
  "matches": [
    {
      "id": "uuid",
      "matched_profile": {
        "id": "uuid",
        "display_name": "Emma",
        "age": 26,
        "photos": [
          {
            "photo_url": "https://...",
            "is_main": true
          }
        ]
      },
      "created_at": "2024-01-20T14:30:00Z",
      "last_message": {
        "content": "Salut ! Comment ça va ?",
        "sender_name": "Emma",
        "sent_at": "2024-01-20T15:45:00Z"
      },
      "unread_count": 2,
      "is_new": true
    }
  ],
  "pagination": { /* ... */ }
}
```

**Logique d'Implémentation Frontend :**
- Tri par activité récente (derniers messages)
- Badge de notification pour nouveaux matches
- Preview du dernier message
- Compteur de messages non lus
- Lazy loading avec pull-to-refresh

## 🌟 Fonctionnalités Premium

### 6. Super Like

**Endpoint :** `POST /matches/super-like`

**Données Requises :**
```json
{
  "target_profile_id": "uuid"
}
```

**Principe d'Implémentation :**
- Vérifier l'abonnement premium de l'utilisateur
- Décrémenter le compteur de super likes quotidiens
- Envoyer une notification push spéciale au destinataire
- Affichage prioritaire dans la pile du destinataire

**Réponse Succès (200) :**
```json
{
  "result": "super_like_sent",
  "super_likes_remaining": 4,
  "message": "Super like sent!"
}
```

**Logique d'Implémentation Frontend :**
- Animation spéciale (étoile bleue)
- Confirmation avant envoi (ressource limitée)
- Feedback visuel distinctif
- Compteur de super likes restants

### 7. Boost de Profil

**Endpoint :** `POST /matches/boost`

**Principe d'Implémentation :**
- Activer le boost pour 30 minutes
- Augmenter la visibilité du profil dans la découverte
- Afficher le profil en priorité aux autres utilisateurs
- Fournir des statistiques en temps réel

**Réponse Succès (200) :**
```json
{
  "boost": {
    "id": "uuid",
    "expires_at": "2024-01-20T16:30:00Z",
    "estimated_views": 50
  },
  "boosts_remaining": 2,
  "message": "Your profile is now boosted!"
}
```

**Logique d'Implémentation Frontend :**
- Timer visuel du boost actif
- Statistiques en temps réel (vues, likes obtenus)
- Interface de gestion des boosts
- Notifications push des résultats

### 8. Rewind (Annuler le Dernier Swipe)

**Endpoint :** `POST /matches/rewind`

**Principe d'Implémentation :**
- Annuler la dernière interaction (like ou dislike)
- Remettre le profil dans la pile de découverte
- Décrémenter le compteur de rewinds quotidiens
- Fonctionnalité limitée aux utilisateurs premium

**Réponse Succès (200) :**
```json
{
  "result": "rewind_successful",
  "rewinds_remaining": 2,
  "restored_profile": {
    "id": "uuid",
    "display_name": "Alex"
  }
}
```

**Logique d'Implémentation Frontend :**
- Bouton de rewind visible après chaque swipe
- Animation de retour en arrière
- Limitation visible du nombre de rewinds
- Confirmation avant utilisation

### 9. Voir Qui M'a Liké

**Endpoint :** `GET /matches/who-liked-me`

**Fonctionnalité Premium Exclusive :**
- Afficher les profils qui ont liké l'utilisateur
- Permettre de liker directement pour créer un match instantané
- Filtrage et tri des likes reçus

**Réponse Succès (200) :**
```json
{
  "likes_received": [
    {
      "profile": {
        "id": "uuid",
        "display_name": "Julie",
        "age": 24,
        "photos": [/* ... */],
        "distance_km": 8.5
      },
      "like_type": "super",
      "received_at": "2024-01-20T12:15:00Z"
    }
  ],
  "total_count": 15,
  "new_likes": 3
}
```

**Logique d'Implémentation Frontend :**
- Grille de profils qui ont liké
- Badge "NEW" pour les nouveaux likes
- Action rapide pour matcher instantanément
- Distinction visuelle des super likes reçus

## 📊 Algorithme et Optimisations

### Score de Compatibilité
**Facteurs Pris en Compte :**
1. **Proximité géographique** (40%) - Distance entre les utilisateurs
2. **Intérêts communs** (25%) - Nombre d'intérêts partagés
3. **Préférences croisées** (20%) - Correspondance des critères de recherche
4. **Activité récente** (10%) - Utilisateurs actifs prioritaires
5. **Statut de vérification** (5%) - Bonus pour les profils vérifiés

### Cache et Performance
**Stratégies d'Optimisation :**
- Cache local des profils consultés
- Préchargement des images en arrière-plan
- Pagination intelligente avec prefetch
- Mise à jour incrémentale des données
- Synchronisation en arrière-plan

## 🎯 Limites et Restrictions

### Utilisateurs Gratuits
- **Likes quotidiens** : 10 swipes par jour
- **Super likes** : non disponibles
- **Rewinds** : 0 par jour
- **Boosts** : 0 par mois
- **Voir qui a liké** : Non disponible

### Utilisateurs Premium
- **Likes quotidiens** : Illimités
- **Super likes** : 5 par jour
- **Rewinds** : 5 par jour
- **Boosts** : 1-5 par mois selon le plan
- **Voir qui a liké** : Accès complet

**Logique d'Implémentation Frontend :**
- Affichage des limites avant qu'elles soient atteintes
- Popup d'upgrade premium quand limites dépassées
- Compteurs visuels des fonctionnalités utilisées
- Reset automatique des compteurs à minuit

## 🚨 Gestion d'Erreurs Spécifiques

### Erreurs de Limite
- **Limite de likes atteinte** : Proposer l'upgrade premium
- **Plus de super likes** : Afficher le reset à minuit
- **Pas de boosts restants** : Rediriger vers l'achat

### Erreurs de Géolocalisation
- **Position introuvable** : Mode découverte par ville
- **Hors zone de service** : Message informatif
- **Permission refusée** : Expliquer l'importance pour le matching

### Erreurs d'Algorithme
- **Aucun profil disponible** : Suggestions d'élargissement des critères
- **Profils épuisés** : Inviter à revenir plus tard
- **Critères trop restrictifs** : Suggestions d'assouplissement

## 🔄 Synchronisation et États

### Synchronisation des Données
**Logique de Mise à Jour :**
- Polling périodique pour les nouveaux matches
- WebSocket pour les interactions en temps réel
- Synchronisation incrémentale des profils
- Cache intelligent avec invalidation

### Gestion des États Hors Ligne
- Mode dégradé avec données mises en cache
- Queue des actions à synchroniser au retour en ligne
- Indicateur de statut de connexion
- Retry automatique des actions échouées

## 📱 Interface et UX

### Gestes de Navigation
**Implémentation Recommandée :**
- **Swipe droite** : Like avec animation fluide
- **Swipe gauche** : Dislike avec transition rapide
- **Tap sur l'étoile** : Super like avec confirmation
- **Tap sur la photo** : Voir le profil complet
- **Double tap** : Zoom sur les photos

### Animations et Feedback
- Animations de swipe fluides (60 FPS)
- Feedback haptique sur les interactions
- Particules et effets pour les matches
- Transitions seamless entre les profils
- Loading states pendant les appels API

Cette documentation couvre tous les aspects du système de matching nécessaires pour une intégration frontend complète avec le backend HIVMeet.
