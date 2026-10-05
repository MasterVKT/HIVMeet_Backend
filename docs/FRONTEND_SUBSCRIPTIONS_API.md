# 💳 API Subscriptions - Documentation Frontend

## 📋 Vue d'Ensemble

Le module Subscriptions gère les abonnements premium, l'intégration avec MyCoolPay, les fonctionnalités premium, et la gestion des paiements et webhooks.

## 🏗️ Architecture des Abonnements

### Principe de Fonctionnement
**Logique Métier :**
- Intégration avec MyCoolPay pour les paiements
- Plans d'abonnements flexibles (mensuel/annuel)
- Fonctionnalités premium par niveaux
- Gestion automatique des renouvellements
- Webhooks pour synchronisation des paiements

### États d'Abonnement
1. **Gratuit** : Fonctionnalités de base
2. **Premium Trial** : Période d'essai
3. **Premium Active** : Abonnement actif
4. **Premium Expiré** : Grâce période avant désactivation
5. **Premium Annulé** : Annulation en fin de période

## 💰 Plans et Tarification

### 1. Liste des Plans Disponibles

**Endpoint :** `GET /subscriptions/plans/`

**Headers :** `Authorization: Bearer …`, `Accept-Language: fr|en`.

La devise vient du profil (`AUTO`, `XAF`, `EUR`) et non d'un paramètre de
requête. `AUTO` utilise le pays du profil, sans coordonnées précises.

**Réponse Succès (200) :**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "plan_id": "hivmeet_monthly",
      "name": "HIVMeet Premium Mensuel",
      "description": "Accès complet aux fonctionnalités premium",
      "price": "7.99",
      "currency": "EUR",
      "base_price": "7.99",
      "base_currency": "EUR",
      "billing_interval": "month",
      "monthly_equivalent": "7.99",
      "trial_period_days": 7,
      "features": {
        "unlimited_likes": true,
        "can_see_likers": true,
        "can_rewind": true,
        "daily_rewinds_count": 5,
        "monthly_boosts_count": 1,
        "daily_super_likes_count": 5,
        "media_messaging_enabled": true,
        "audio_video_calls_enabled": true
      },
      "savings_percentage": 0,
      "most_popular": false,
      "recommended": false
    },
    {
      "plan_id": "hivmeet_annual",
      "name": "HIVMeet Premium Annuel",
      "price": "57.99",
      "currency": "EUR",
      "base_price": "57.99",
      "base_currency": "EUR",
      "billing_interval": "year",
      "monthly_equivalent": "4.83",
      "features": { /* ... */ },
      "savings_percentage": 40,
      "most_popular": true,
      "recommended": true
    }
  ]
}
```

**Logique d'Implémentation Frontend :**
- Affichage comparatif des plans avec avantages
- Mise en évidence du plan le plus populaire
- Calcul et affichage des économies annuelles
- Support multilingue et multi-devise
- Interface d'upgrade attrayante

### Capacités de paiement

**Endpoint :** `GET /subscriptions/payment-capabilities/`

Retourne `available`, `callback_verification_available`, les devises activées
et la devise effective, sans exposer aucune clé MyCoolPay. Le frontend doit
consulter ce contrat avant d'autoriser la validation du formulaire.

### 2. Abonnement Actuel de l'Utilisateur

**Endpoint :** `GET /subscriptions/current/`

**Headers Requis :**
```
Authorization: Bearer <access_token>
```

**Réponse Succès (200) :**
```json
{
  "subscription_id": "provider-reference",
  "plan_id": "hivmeet_monthly",
  "plan_name": "Abonnement Mensuel",
  "status": "active",
  "current_period_start": "2026-09-13T00:00:00Z",
  "current_period_end": "2026-10-13T00:00:00Z",
  "auto_renew": true,
  "cancel_at_period_end": false,
  "scheduled_change": null,
  "features_summary": {
    "unlimited_likes": true,
    "can_see_likers": true,
    "can_rewind": true,
    "daily_rewinds_count": 5,
    "monthly_boosts_count": 1,
    "daily_super_likes_count": 5,
    "media_messaging_enabled": true,
    "audio_video_calls_enabled": true
  }
}
```

Sans abonnement actif, le même schéma est renvoyé avec `status: "none"`,
les identifiants et dates à `null`, et tous les droits à `false` ou `0`.

**Logique d'Implémentation Frontend :**
- Dashboard de gestion de l'abonnement
- Compteurs visuels des fonctionnalités utilisées
- Indicateur de renouvellement automatique
- Informations de facturation claire
- Actions de gestion (annuler, modifier)

## 🛒 Processus d'Achat

### 3. Initiation d'Abonnement

**Endpoint :** `POST /subscriptions/purchase/`

**Header obligatoire pour Flutter :**
`Idempotency-Key: <identifiant unique de tentative>`. La clé est persistée
avant l'appel et réutilisée pour toute reprise de la même tentative.

**Données Requises :**
```json
{
  "plan_id": "hivmeet_monthly",
  "phone_number": "+237699009900",
  "language": "fr"
}
```

**Principe d'Implémentation MyCoolPay :**
1. Création de la session de paiement MyCoolPay
2. Redirection vers l'interface de paiement sécurisée
3. Gestion du retour utilisateur (succès/échec)
4. Webhook de confirmation du paiement
5. Activation automatique de l'abonnement

**Réponse Succès (201) :**
```json
{
  "payment_id": "uuid",
  "payment_url": "https://my-coolpay.com/payment/checkout/...",
  "payment_status": "pending",
  "amount": "5241",
  "currency": "XAF",
  "idempotent_replay": false
}
```

**Logique d'Implémentation Frontend :**
- Interface de sélection de plan claire
- Redirection seamless vers MyCoolPay
- Gestion des timeouts de session
- Feedback utilisateur pendant le processus
- Gestion des erreurs de paiement

### 4. Validation du Paiement

**Endpoint :** `GET /subscriptions/payments/{payment_id}/`

**Principe d'Implémentation :**
- Vérification du statut du paiement MyCoolPay
- Activation de l'abonnement si paiement réussi
- Mise à jour du statut utilisateur
- Synchronisation des fonctionnalités premium

**Réponse Succès (200) :**
```json
{
  "payment_id": "uuid",
  "payment_status": "succeeded",
  "fulfilled": true,
  "subscription_id": "provider-reference",
  "activated_at": "2026-09-13T16:45:00Z",
  "subscription": {
    "subscription_id": "provider-reference",
    "plan_id": "hivmeet_monthly",
    "status": "active",
    "current_period_start": "2026-09-13T16:45:00Z",
    "current_period_end": "2026-10-13T16:45:00Z"
  }
}
```

**Logique d'Implémentation Frontend :**
- Polling du statut après retour de MyCoolPay
- Animation de confirmation d'activation
- Tour guidé des nouvelles fonctionnalités
- Mise à jour immédiate de l'interface

## 🔄 Gestion de l'Abonnement

### 5. Modification de l'Abonnement

**Endpoint :** `POST /subscriptions/current/modify/`

**Données Requises :**
```json
{
  "new_plan_id": "hivmeet_annual",
  "proration": true
}
```

**Principe d'Implémentation :**
- Calcul de la proratisation automatique
- Mise à jour immédiate ou en fin de période
- Gestion des crédits et débits
- Notification des changements
- Le choix `proration: false` est présenté comme « Changer à la prochaine
  échéance ». Il n'est pas un contrôle de renouvellement automatique et ne
  persiste qu'après confirmation du changement de forfait.

**Réponse Succès (200) :**
```json
{
  "subscription_id": "provider-reference",
  "plan_id": "hivmeet_annual",
  "status": "active",
  "proration": {
    "credit_amount": 3.33,
    "charge_amount": 0.00,
    "currency": "EUR",
    "prorated_period_start": "2026-09-13T16:50:00Z",
    "prorated_period_end": "2026-10-13T00:00:00Z"
  }
}
```

### 6. Annulation de l'Abonnement

**Endpoint :** `POST /subscriptions/current/cancel/`

**Données Requises :**
```json
{
  "reason": "too_expensive"
}
```

**Principe d'Implémentation :**
- Annulation immédiate ou en fin de période
- Conservation de l'accès jusqu'à expiration
- Collecte de feedback pour amélioration
- Offres de rétention si applicable

**Réponse Succès (200) :**
```json
{
  "subscription": {
    "status": "active",
    "cancel_at_period_end": true,
    "canceled_at": "2024-01-20T16:55:00Z",
    "access_until": "2024-02-15T00:00:00Z"
  },
  "retention_offer": {
    "discount_percentage": 25,
    "offer_expires_at": "2024-01-27T16:55:00Z"
  }
}
```

**Logique d'Implémentation Frontend :**
- Workflow de rétention avec offres spéciales
- Explication claire des conséquences
- Option d'annulation différée
- Feedback constructif obligatoire

## 🎁 Fonctionnalités Premium

### 7. Utilisation d'un Boost

**Endpoint :** `POST /subscriptions/use-boost`

**Principe d'Implémentation :**
- Vérification de l'abonnement actif
- Décrément du compteur de boosts
- Activation du boost pour 30 minutes
- Statistiques en temps réel

**Réponse Succès (200) :**
```json
{
  "boost": {
    "id": "uuid",
    "activated_at": "2024-01-20T17:00:00Z",
    "expires_at": "2024-01-20T17:30:00Z",
    "estimated_additional_views": 50
  },
  "boosts_remaining": 0,
  "next_boost_reset": "2024-02-15T00:00:00Z"
}
```

### 8. Utilisation d'un Super Like

**Endpoint :** `POST /subscriptions/use-super-like`

**Données Requises :**
```json
{
  "target_profile_id": "uuid"
}
```

**Logique d'Implémentation Frontend :**
- Vérification des super likes restants
- Interface de confirmation attractive
- Animation spéciale d'envoi
- Notification à l'utilisateur ciblé

### 9. Statistiques Premium

**Endpoint :** `GET /subscriptions/premium-stats`

**Réponse Succès (200) :**
```json
{
  "usage_stats": {
    "likes_sent_this_period": 156,
    "super_likes_used": 23,
    "boosts_used": 3,
    "profile_views_gained": 847,
    "matches_from_premium": 8
  },
  "feature_usage": {
    "who_liked_you_views": 45,
    "media_messages_sent": 67,
    "video_calls_made": 12,
    "rewinds_used": 15
  },
  "period": {
    "start": "2024-01-15T00:00:00Z",
    "end": "2024-02-15T00:00:00Z"
  }
}
```

**Logique d'Implémentation Frontend :**
- Dashboard analytique avec graphiques
- Comparaison avec la période précédente
- Suggestions d'optimisation d'utilisation
- Mise en valeur du ROI de l'abonnement

## 🚨 Gestion d'Erreurs et Sécurité

### Erreurs de Paiement
- **Carte déclinée** : Suggestions alternatives de paiement
- **Fonds insuffisants** : Report avec notification
- **Carte expirée** : Interface de mise à jour guidée
- **Session expirée** : Redirection vers nouveau processus

### Conformité et Sécurité
- Aucun stockage des informations de carte
- Délégation complète à MyCoolPay (PCI-DSS)
- Chiffrement de toutes les communications
- Respect du RGPD pour les données utilisateur

Cette documentation couvre tous les aspects des abonnements nécessaires pour une intégration frontend complète avec le backend HIVMeet et MyCoolPay.
