# 📚 API Resources - Documentation Frontend

## 📋 Vue d'Ensemble

Le module Resources gère le contenu éducatif multilingue de l'application, incluant les articles, catégories, le feed personnalisé, et le système d'interaction avec le contenu.

## 🏗️ Architecture du Contenu

### Principe de Fonctionnement
**Logique Métier :**
- Contenu éducatif spécialisé pour la communauté VIH+
- Articles multilingues (français/anglais)
- Catégorisation thématique du contenu
- Feed personnalisé selon les intérêts utilisateur
- Système d'interaction (likes, partages, favoris)

### Types de Contenu
1. **Articles Éducatifs** : Contenu informatif médical/social
2. **Témoignages** : Histoires personnelles de la communauté
3. **Actualités** : Nouvelles recherches et avancées
4. **Guides Pratiques** : Conseils et ressources utiles
5. **FAQ** : Questions fréquemment posées

## 📰 Endpoints de Contenu

### 1. Liste des Catégories

**Endpoint :** `GET /content/categories`

**Paramètres de Requête :**
```
language: "fr|en"
```

**Réponse Succès (200) :**
```json
{
  "categories": [
    {
      "id": "uuid",
      "name": "Santé et Bien-être",
      "name_en": "Health and Wellness",
      "description": "Articles sur la santé physique et mentale",
      "description_en": "Articles about physical and mental health",
      "icon_url": "https://storage.googleapis.com/icons/health.png",
      "color": "#4CAF50",
      "article_count": 45,
      "order": 1,
      "is_featured": true
    },
    {
      "id": "uuid",
      "name": "Relations et Intimité",
      "name_en": "Relationships and Intimacy",
      "description": "Conseils pour les relations amoureuses",
      "article_count": 32,
      "order": 2
    },
    {
      "id": "uuid",
      "name": "Témoignages",
      "name_en": "Testimonials",
      "description": "Histoires personnelles de notre communauté",
      "article_count": 67,
      "order": 3
    }
  ]
}
```

**Logique d'Implémentation Frontend :**
- Interface en grille avec icônes colorées
- Affichage du nombre d'articles par catégorie
- Support multilingue automatique
- Mise en avant des catégories featured
- Navigation intuitive vers les contenus

### 2. Articles par Catégorie

**Endpoint :** `GET /content/`

**Paramètres de Requête :**
```
category_id: uuid (optionnel)
language: "fr|en"
page: 1
per_page: 20
sort: "recent|popular|trending"
featured_only: false
```

**Réponse Succès (200) :**
```json
{
  "articles": [
    {
      "id": "uuid",
      "title": "Vivre sereinement avec le VIH au quotidien",
      "title_en": "Living peacefully with HIV in daily life",
      "summary": "Découvrez des conseils pratiques pour maintenir une qualité de vie optimale...",
      "summary_en": "Discover practical tips to maintain optimal quality of life...",
      "featured_image_url": "https://storage.googleapis.com/articles/health-daily.jpg",
      "category": {
        "id": "uuid",
        "name": "Santé et Bien-être"
      },
      "author": {
        "name": "Dr. Marie Dubois",
        "title": "Infectiologue",
        "avatar_url": "https://storage.googleapis.com/authors/dr-dubois.jpg"
      },
      "reading_time_minutes": 8,
      "published_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-18T14:30:00Z",
      "view_count": 1240,
      "like_count": 89,
      "is_featured": true,
      "is_liked_by_user": false,
      "tags": ["quotidien", "conseils", "santé"]
    }
  ],
  "pagination": { /* ... */ }
}
```

**Logique d'Implémentation Frontend :**
- Cards attrayantes avec image, titre et résumé
- Indicateurs visuels (temps de lecture, popularité)
- Filtrage par catégorie et tri dynamique
- Lazy loading avec pagination infinie
- Bookmarking et système de likes

### 3. Article Détaillé

**Endpoint :** `GET /content/{article_id}`

**Paramètres de Requête :**
```
language: "fr|en"
```

**Réponse Succès (200) :**
```json
{
  "article": {
    "id": "uuid",
    "title": "Vivre sereinement avec le VIH au quotidien",
    "content": "# Introduction\n\nVivre avec le VIH aujourd'hui n'est plus ce que c'était...\n\n## Section 1: Traitements modernes\n\nLes thérapies antirétrovirales actuelles...",
    "featured_image_url": "https://storage.googleapis.com/articles/health-daily.jpg",
    "images": [
      {
        "url": "https://storage.googleapis.com/articles/treatment-chart.jpg",
        "caption": "Évolution des traitements",
        "alt_text": "Graphique montrant l'amélioration des traitements"
      }
    ],
    "category": { /* ... */ },
    "author": { /* ... */ },
    "reading_time_minutes": 8,
    "published_at": "2024-01-15T10:00:00Z",
    "view_count": 1241,
    "like_count": 89,
    "is_liked_by_user": false,
    "is_bookmarked_by_user": false,
    "related_articles": [
      {
        "id": "uuid",
        "title": "Nutrition et VIH",
        "summary": "L'importance d'une alimentation équilibrée..."
      }
    ],
    "sources": [
      {
        "title": "OMS - Recommandations VIH 2023",
        "url": "https://who.int/hiv/recommendations-2023"
      }
    ]
  }
}
```

**Logique d'Implémentation Frontend :**
- Rendu markdown du contenu avec styles
- Interface de lecture optimisée (typographie, espacement)
- Barre de progression de lecture
- Actions rapides (like, bookmark, partage)
- Articles similaires en fin de lecture
- Mode sombre/clair pour le confort de lecture

### 4. Feed Personnalisé

**Endpoint :** `GET /feed/`

**Paramètres de Requête :**
```
page: 1
per_page: 10
algorithm: "personalized|trending|recent"
```

**Principe d'Algorithme :**
1. Analyse des catégories préférées de l'utilisateur
2. Prise en compte de l'historique de lecture
3. Boost des articles récents et populaires
4. Évitement des doublons déjà lus
5. Diversification du contenu proposé

**Réponse Succès (200) :**
```json
{
  "feed_items": [
    {
      "id": "uuid",
      "type": "article",
      "article": { /* article complet */ },
      "reason": "Basé sur votre intérêt pour 'Santé et Bien-être'",
      "score": 0.85,
      "position": 1
    },
    {
      "id": "uuid",
      "type": "trending",
      "article": { /* ... */ },
      "reason": "Populaire cette semaine",
      "score": 0.72,
      "position": 2
    }
  ],
  "pagination": { /* ... */ },
  "personalization_info": {
    "user_interests": ["santé", "relations", "témoignages"],
    "reading_history_count": 23,
    "algorithm_version": "2.1"
  }
}
```

**Logique d'Implémentation Frontend :**
- Interface de feed social avec cards dynamiques
- Algorithme de recommandation explicable
- Pull-to-refresh pour nouveau contenu
- Indicateurs de personnalisation
- Feedback utilisateur pour améliorer les recommandations

## 👍 Système d'Interaction

### 5. Liker un Article

**Endpoint :** `POST /content/{article_id}/like`

**Headers Requis :**
```
Authorization: Bearer <access_token>
```

**Réponse Succès (201/200) :**
```json
{
  "liked": true,
  "like_count": 90,
  "message": "Article ajouté à vos favoris"
}
```

**Logique d'Implémentation Frontend :**
- Animation de cœur avec feedback visuel
- Mise à jour immédiate du compteur
- Synchronisation avec la liste des favoris
- Optimistic UI avec rollback si erreur

### 6. Bookmarker un Article

**Endpoint :** `POST /content/{article_id}/bookmark`

**Réponse Succès (201/200) :**
```json
{
  "bookmarked": true,
  "message": "Article sauvegardé pour plus tard"
}
```

**Logique d'Implémentation Frontend :**
- Icône de bookmark avec état visuel
- Collection organisée des articles sauvegardés
- Accès rapide depuis le profil utilisateur
- Catégorisation des bookmarks

### 7. Partager un Article

**Endpoint :** `POST /content/{article_id}/share`

**Données Requises :**
```json
{
  "platform": "native|whatsapp|telegram|email",
  "recipient_id": "uuid" // Pour partage interne
}
```

**Principe d'Implémentation :**
- Partage natif avec le système d'exploitation
- Liens d'article préformatés avec métadonnées
- Tracking des partages pour analytics
- Partage interne entre utilisateurs de l'app

## 📊 Analytics et Statistiques

### 8. Statistiques de Lecture

**Endpoint :** `GET /content/reading-stats`

**Réponse Succès (200) :**
```json
{
  "user_reading_stats": {
    "total_articles_read": 45,
    "total_reading_time_minutes": 360,
    "favorite_categories": [
      {
        "category": "Santé et Bien-être",
        "article_count": 18
      },
      {
        "category": "Relations et Intimité", 
        "article_count": 12
      }
    ],
    "reading_streak_days": 7,
    "last_read_at": "2024-01-20T16:30:00Z"
  },
  "achievements": [
    {
      "id": "first_article",
      "title": "Premier Article",
      "description": "Félicitations pour votre première lecture !",
      "unlocked_at": "2024-01-10T14:00:00Z"
    },
    {
      "id": "health_expert",
      "title": "Expert Santé",
      "description": "10+ articles lus dans la catégorie Santé",
      "unlocked_at": "2024-01-18T11:00:00Z"
    }
  ]
}
```

**Logique d'Implémentation Frontend :**
- Dashboard personnel de lecture avec graphiques
- Système de badges et achievements
- Tracking des streaks de lecture quotidienne
- Recommandations basées sur les habitudes

### 9. Recherche de Contenu

**Endpoint :** `GET /content/search`

**Paramètres de Requête :**
```
q: "traitement VIH"
category_id: uuid (optionnel)
language: "fr|en"
page: 1
per_page: 20
sort: "relevance|recent|popular"
```

**Réponse Succès (200) :**
```json
{
  "results": [
    {
      "type": "article",
      "article": { /* ... */ },
      "relevance_score": 0.95,
      "highlighted_text": "...nouveaux <mark>traitements VIH</mark> disponibles..."
    }
  ],
  "search_suggestions": [
    "traitement antirétroviral",
    "effets secondaires VIH",
    "prévention VIH"
  ],
  "filters_applied": {
    "category": "Santé et Bien-être",
    "language": "fr"
  },
  "total_results": 23
}
```

**Logique d'Implémentation Frontend :**
- Barre de recherche avec suggestions automatiques
- Filtres avancés par catégorie et date
- Highlighting des termes recherchés
- Historique des recherches récentes
- Sauvegarde des recherches fréquentes

## 🔄 Synchronisation et Cache

### Stratégie de Cache
**Principe d'Implémentation :**
- Cache local des articles récemment lus
- Mise à jour incrémentale du contenu
- Préchargement des articles populaires
- Synchronisation en arrière-plan
- Mode hors ligne avec contenu mis en cache

### Mise à Jour du Contenu
- Polling périodique pour nouveau contenu
- Notifications push pour articles importants
- Indicateurs de nouveau contenu disponible
- Sync différentielle pour optimiser la bande passante

## 🌍 Internationalisation

### Gestion Multilingue
**Principe d'Implémentation :**
- Détection automatique de la langue préférée
- Fallback intelligent (fr → en ou vice versa)
- Interface de changement de langue
- Adaptation culturelle du contenu
- Traduction des métadonnées (catégories, tags)

### Localisation du Contenu
- Contenu adapté aux réglementations locales
- Ressources spécifiques par région/pays
- Contacts et ressources d'aide localisés
- Prise en compte des différences culturelles

## 📱 Fonctionnalités Mobiles Spécifiques

### Mode Lecture Optimisé
- Interface épurée pour la lecture
- Ajustement automatique de la luminosité
- Support du mode sombre pour le confort nocturne
- Taille de police configurable
- Marque-pages automatiques (position de lecture)

### Accessibilité
- Support des lecteurs d'écran
- Contraste élevé pour malvoyants
- Navigation clavier/vocale
- Texte alternatif pour toutes les images
- Respect des standards WCAG 2.1

## 🚨 Gestion d'Erreurs Spécifiques

### Erreurs de Contenu
- **Article non trouvé** : Redirection vers contenu similaire
- **Contenu expiré** : Message informatif avec alternatives
- **Langue non disponible** : Fallback automatique
- **Ressource supprimée** : Notification avec explication

### Erreurs de Réseau
- **Connexion lente** : Mode dégradé avec images compressées
- **Hors ligne** : Accès au contenu mis en cache
- **Échec de synchronisation** : Retry automatique en arrière-plan
- **Limite de données** : Options de compression

## 💡 Recommandations UX

### Engagement Utilisateur
- **Onboarding** : Guide des catégories et fonctionnalités
- **Gamification** : Système de points et badges de lecture
- **Social Features** : Discussions et commentaires (modérés)
- **Personnalisation** : Interface adaptable aux préférences

### Rétention et Fidélisation
- **Notifications intelligentes** : Nouveau contenu selon les intérêts
- **Séries d'articles** : Contenu structuré en plusieurs parties
- **Newsletter hebdomadaire** : Résumé du contenu populaire
- **Communauté** : Espaces d'échange et témoignages

Cette documentation couvre tous les aspects du module Resources nécessaires pour une intégration frontend complète avec le backend HIVMeet. 