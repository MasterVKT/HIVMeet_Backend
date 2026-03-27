# Problème de Rate Limiting - Trop de requêtes (429)

## Description du Problème

Lors de l'utilisation de l'application HIVMeet, un problème de "Too Many Requests" a été détecté côté backend. Lorsque l'utilisateur effectue plusieurs actions de "like" rapidement, le serveur renvoie une erreur HTTP 429, ce qui empêche l'utilisateur de continuer à swiper les profils.

### Logs Backend

```
WARNING 2026-03-21 04:06:29,720 log 19272 13076 Too Many Requests: /api/v1/discovery/interactions/like
WARNING 2026-03-21 04:06:29,721 basehttp 19272 13076 "POST /api/v1/discovery/interactions/like HTTP/1.1" 429 54
WARNING 2026-03-21 04:06:42,837 log 19272 8044 Too Many Requests: /api/v1/discovery/interactions/like
WARNING 2026-03-21 04:06:42,838 basehttp 19272 8044 "POST /api/v1/discovery/interactions/like HTTP/1.1" 429 54
```

### Logs Frontend

Le frontend ne semble pas gérer correctement cette erreur, ce qui pourrait entraîner un comportement inattendu dans l'interface utilisateur.

## Analyse du Problème

### 1. Cause Racine
Le serveur backend applique une limite de taux (rate limiting) sur l'endpoint `/api/v1/discovery/interactions/like` qui est trop restrictive pour une utilisation normale de l'application.

### 2. Comportement Actuel
- Les actions de "dislike" fonctionnent correctement (retour HTTP 201)
- Les actions de "like" échouent avec une erreur 429 (Too Many Requests)
- L'utilisateur ne peut pas effectuer d'autres actions de like pendant un certain temps

### 3. Comparaison avec les Dislikes
Les logs montrent que les dislikes sont traités avec succès :
```
"POST /api/v1/discovery/interactions/dislike HTTP/1.1" 201 75
```

## Impact sur l'Utilisateur

1. L'utilisateur ne peut pas liker les profils rapidement
2. Lorsque la limite est atteinte, les actions de like échouent silencieusement
3. L'expérience utilisateur est dégradée
4. Le système de matching est affecté

## Solutions Proposées

### Solution 1 : Ajuster la limite de taux côté backend

**Niveau:** Backend
**Priorité:** Haute

Modifier les paramètres de rate limiting pour l'endpoint de like :

```python
# Dans les paramètres de l'application Django
RATELIMIT_USER_LIKE_PATTERN = "user_like_%(ip)s"  # ou %(user_id)s
RATELIMIT_USER_LIKE_RATE = "30/m"  # 30 likes par minute par utilisateur
```

### Solution 2 : Mise en cache côté client

**Niveau:** Frontend
**Priorité:** Moyenne

Implémenter une file d'attente côté client pour les actions de like afin de:
- Limiter le nombre de requêtes envoyées par minute
- Gérer les erreurs 429 de manière plus élégante
- Informer l'utilisateur de la limitation

### Solution 3 : Différenciation des limites

**Niveau:** Backend
**Priorité:** Moyenne

Différencier les limites de taux pour les différentes actions :
- Likes: 30 par minute
- Dislikes: 50 par minute
- Ou basé sur le type d'utilisateur (premium/guest)

### Solution 4 : Feedback utilisateur

**Niveau:** Frontend
**Priorité:** Moyenne

Ajouter un feedback visuel pour informer l'utilisateur :
- Quand la limite est atteinte
- Combien de temps il doit attendre
- Suggestions alternatives

## Recommandations Techniques

### Backend
1. Ajuster les paramètres de `django-ratelimit` pour les endpoints de like
2. Considérer l'utilisation d'identifiants utilisateurs plutôt que d'adresses IP pour le rate limiting
3. Créer des profils de rate limiting différents selon le type d'action

### Frontend
1. Implémenter une logique de throttling côté client
2. Gérer les erreurs 429 avec des messages utilisateur appropriés
3. Désactiver temporairement le bouton de like après une erreur 429

## Priorités de Mise en Œuvre

1. **Immédiat**: Ajuster la limite de taux côté backend pour permettre une utilisation normale
2. **Court terme**: Améliorer la gestion des erreurs côté frontend
3. **Moyen terme**: Implémenter une logique de file d'attente et de throttling

## Fichiers à Modifier

### Backend
- `apps/discovery/views.py` - Paramètres de rate limiting
- `hivmeet_backend/settings.py` - Configuration globale de rate limiting
- `apps/discovery/rate_limits.py` - (si existe) Configuration spécifique

### Frontend
- `lib/presentation/blocs/discovery/discovery_bloc.dart` - Gestion des erreurs
- `lib/presentation/widgets/cards/swipe_card.dart` - Feedback utilisateur
- `lib/domain/usecases/match/like_profile.dart` - Gestion des erreurs 429

## Tests à Mettre en Place

1. Test de charge pour valider les nouvelles limites
2. Test de l'expérience utilisateur avec des taux limités
3. Test de la gestion des erreurs côté frontend

## Conclusion

Le problème de "Too Many Requests" est dû à une limite de taux trop restrictive sur les actions de like côté backend. Bien que le rate limiting soit important pour la sécurité de l'application, il doit être équilibré avec une expérience utilisateur optimale. La solution implique à la fois des ajustements côté backend et des améliorations côté frontend pour gérer efficacement cette limitation.