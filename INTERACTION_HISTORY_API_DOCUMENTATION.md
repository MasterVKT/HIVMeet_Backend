# Documentation API - Historique des Interactions

## Vue d'ensemble

Cette documentation décrit les nouveaux endpoints de l'API permettant aux utilisateurs de gérer leur historique d'interactions (likes, super likes, passes) dans HIVMeet.

## Base URL

Tous les endpoints sont préfixés par : `/api/v1/discovery/interactions/`

## Authentification

Tous les endpoints nécessitent une authentification Firebase valide via un token JWT dans le header :

```
Authorization: Bearer <firebase_token>
```

---

## 1. Liste des Likes

Récupère la liste paginée des profils que l'utilisateur a aimés.

### Endpoint

```
GET /api/v1/discovery/interactions/my-likes
```

### Paramètres de requête (optionnels)

| Paramètre | Type | Description | Défaut |
|-----------|------|-------------|---------|
| `page` | integer | Numéro de la page | 1 |
| `page_size` | integer | Nombre d'éléments par page | 20 |
| `matched_only` | boolean | Filtrer uniquement les likes qui ont matché | false |

### Exemples de requête

```http
# Récupérer tous les likes (page 1)
GET /api/v1/discovery/interactions/my-likes

# Récupérer uniquement les matches
GET /api/v1/discovery/interactions/my-likes?matched_only=true

# Pagination personnalisée
GET /api/v1/discovery/interactions/my-likes?page=2&page_size=50
```

### Réponse réussie (200 OK)

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/discovery/interactions/my-likes?page=2",
  "previous": null,
  "results": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "interaction_type": "like",
      "profile": {
        "user_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "username": "john_doe",
        "age": 28,
        "city": "Paris",
        "profile_photo": "https://example.com/photos/john.jpg",
        "gender": "male",
        "bio": "Passionate about travel and music"
      },
      "is_match": true,
      "created_at": "2024-01-15T14:30:00Z",
      "is_revoked": false,
      "revoked_at": null
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678902",
      "interaction_type": "super_like",
      "profile": {
        "user_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "username": "jane_smith",
        "age": 25,
        "city": "Lyon",
        "profile_photo": "https://example.com/photos/jane.jpg",
        "gender": "female",
        "bio": "Art lover and coffee addict"
      },
      "is_match": false,
      "created_at": "2024-01-14T10:15:00Z",
      "is_revoked": false,
      "revoked_at": null
    }
  ]
}
```

### Codes de statut

- `200 OK` : Requête réussie
- `401 Unauthorized` : Token d'authentification manquant ou invalide
- `500 Internal Server Error` : Erreur serveur

---

## 2. Liste des Passes

Récupère la liste paginée des profils que l'utilisateur a passés (dislike).

### Endpoint

```
GET /api/v1/discovery/interactions/my-passes
```

### Paramètres de requête (optionnels)

| Paramètre | Type | Description | Défaut |
|-----------|------|-------------|---------|
| `page` | integer | Numéro de la page | 1 |
| `page_size` | integer | Nombre d'éléments par page | 20 |

### Exemple de requête

```http
GET /api/v1/discovery/interactions/my-passes?page=1&page_size=20
```

### Réponse réussie (200 OK)

```json
{
  "count": 18,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "c3d4e5f6-a7b8-9012-cdef-123456789013",
      "interaction_type": "dislike",
      "profile": {
        "user_id": "d4e5f6a7-b8c9-0123-def1-234567890123",
        "username": "bob_martin",
        "age": 32,
        "city": "Marseille",
        "profile_photo": "https://example.com/photos/bob.jpg",
        "gender": "male",
        "bio": "Tech enthusiast"
      },
      "is_match": false,
      "created_at": "2024-01-13T16:45:00Z",
      "is_revoked": false,
      "revoked_at": null
    }
  ]
}
```

### Codes de statut

- `200 OK` : Requête réussie
- `401 Unauthorized` : Token d'authentification manquant ou invalide
- `500 Internal Server Error` : Erreur serveur

---

## 3. Révoquer une interaction

Permet à l'utilisateur d'annuler une interaction précédente (like, super like ou dislike). Le profil réapparaîtra dans les recommandations.

### Endpoint

```
POST /api/v1/discovery/interactions/<interaction_id>/revoke
```

### Paramètres d'URL

| Paramètre | Type | Description |
|-----------|------|-------------|
| `interaction_id` | UUID | ID de l'interaction à révoquer |

### Corps de la requête

Aucun corps requis.

### Exemple de requête

```http
POST /api/v1/discovery/interactions/a1b2c3d4-e5f6-7890-abcd-ef1234567890/revoke
Authorization: Bearer <firebase_token>
```

### Réponse réussie (200 OK)

```json
{
  "message": "Interaction révoquée avec succès",
  "interaction": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "interaction_type": "like",
    "profile": {
      "user_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "username": "john_doe",
      "age": 28,
      "city": "Paris",
      "profile_photo": "https://example.com/photos/john.jpg",
      "gender": "male",
      "bio": "Passionate about travel and music"
    },
    "is_match": true,
    "created_at": "2024-01-15T14:30:00Z",
    "is_revoked": true,
    "revoked_at": "2024-01-16T09:22:00Z"
  }
}
```

### Réponses d'erreur

#### 404 Not Found
```json
{
  "error": "Interaction non trouvée"
}
```

#### 400 Bad Request
```json
{
  "error": "Cette interaction a déjà été révoquée"
}
```

### Codes de statut

- `200 OK` : Interaction révoquée avec succès
- `400 Bad Request` : Interaction déjà révoquée
- `404 Not Found` : Interaction introuvable
- `401 Unauthorized` : Token d'authentification manquant ou invalide
- `500 Internal Server Error` : Erreur serveur

### Comportement

Lorsqu'une interaction est révoquée :
1. Le champ `is_revoked` est mis à `True`
2. Le champ `revoked_at` est mis à jour avec la date/heure actuelle
3. Le profil cible réapparaîtra dans les recommandations futures
4. Si l'interaction était un **like qui a matché** :
   - Le match reste intact (pas de suppression automatique)
   - L'utilisateur peut toujours converser avec la personne
   - Seule l'interaction dans l'historique est marquée comme révoquée

---

## 4. Statistiques d'interaction

Récupère des statistiques détaillées sur l'historique d'interactions de l'utilisateur.

### Endpoint

```
GET /api/v1/discovery/interactions/stats
```

### Paramètres de requête

Aucun.

### Exemple de requête

```http
GET /api/v1/discovery/interactions/stats
Authorization: Bearer <firebase_token>
```

### Réponse réussie (200 OK)

```json
{
  "total_likes": 42,
  "total_super_likes": 8,
  "total_dislikes": 18,
  "total_matches": 15,
  "like_to_match_ratio": 0.357,
  "total_interactions_today": 12,
  "daily_limit": 50,
  "remaining_today": 38,
  "most_active_day": "Monday",
  "average_daily_interactions": 8.5
}
```

### Description des champs

| Champ | Type | Description |
|-------|------|-------------|
| `total_likes` | integer | Nombre total de likes (actifs, non révoqués) |
| `total_super_likes` | integer | Nombre total de super likes (actifs) |
| `total_dislikes` | integer | Nombre total de dislikes (actifs) |
| `total_matches` | integer | Nombre total de matches |
| `like_to_match_ratio` | float | Ratio de conversion likes → matches (0-1) |
| `total_interactions_today` | integer | Nombre d'interactions aujourd'hui |
| `daily_limit` | integer | Limite quotidienne de likes pour l'utilisateur |
| `remaining_today` | integer | Nombre de likes restants aujourd'hui |
| `most_active_day` | string | Jour de la semaine le plus actif |
| `average_daily_interactions` | float | Moyenne d'interactions par jour |

### Codes de statut

- `200 OK` : Requête réussie
- `401 Unauthorized` : Token d'authentification manquant ou invalide
- `500 Internal Server Error` : Erreur serveur

---

## Modèle de données : InteractionHistory

### Structure

```python
class InteractionHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    target_user = models.ForeignKey(User, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=20)  # 'like', 'super_like', 'dislike'
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
```

### Types d'interaction

- `like` : Like standard
- `super_like` : Super like (avec notification)
- `dislike` : Pass/Dislike

### Contraintes

- Un utilisateur ne peut avoir qu'**une seule interaction active** (non révoquée) avec un profil donné
- Contrainte unique : `unique_together = ('user', 'target_user')` WHERE `is_revoked = False`

---

## Cas d'usage

### 1. Voir tous ses likes actifs

```javascript
const response = await fetch('/api/v1/discovery/interactions/my-likes', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
const data = await response.json();
console.log(`J'ai liké ${data.count} profils`);
```

### 2. Voir uniquement ses matches

```javascript
const response = await fetch('/api/v1/discovery/interactions/my-likes?matched_only=true', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
const matches = await response.json();
```

### 3. Annuler un like accidentel

```javascript
const interactionId = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
const response = await fetch(`/api/v1/discovery/interactions/${interactionId}/revoke`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});

if (response.ok) {
  console.log('Like annulé, le profil réapparaîtra');
}
```

### 4. Consulter ses statistiques

```javascript
const response = await fetch('/api/v1/discovery/interactions/stats', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
const stats = await response.json();
console.log(`Taux de match : ${(stats.like_to_match_ratio * 100).toFixed(1)}%`);
```

---

## Pagination

Tous les endpoints de liste utilisent la pagination standard de Django REST Framework.

### Paramètres

- `page` : Numéro de la page (défaut: 1)
- `page_size` : Nombre d'éléments par page (défaut: 20, max: 100)

### Format de réponse

```json
{
  "count": 42,          // Nombre total d'éléments
  "next": "url",        // URL de la page suivante (null si dernière page)
  "previous": "url",    // URL de la page précédente (null si première page)
  "results": [...]      // Tableau des résultats
}
```

---

## Gestion des erreurs

### Format standard d'erreur

```json
{
  "error": "Message d'erreur descriptif"
}
```

### Codes HTTP utilisés

| Code | Signification |
|------|---------------|
| 200 | Succès |
| 400 | Requête invalide (ex: interaction déjà révoquée) |
| 401 | Non authentifié |
| 404 | Ressource non trouvée |
| 500 | Erreur serveur |

---

## Intégration avec le système existant

### Compatibilité

Le système d'historique des interactions **coexiste** avec les modèles existants :

- **Like** : Toujours créé lors d'un like
- **Dislike** : Toujours créé lors d'un dislike
- **Match** : Toujours créé lors d'un match mutuel
- **InteractionHistory** : Enregistrement supplémentaire pour l'historique et la révocation

### Recommandations

Les profils sont filtrés des recommandations si :
- Une interaction **active** (non révoquée) existe
- OU un ancien Like/Dislike existe (système legacy)

### Migration des données

Les interactions existantes dans les tables `Like` et `Dislike` continuent de fonctionner normalement. Le nouveau système `InteractionHistory` commence à enregistrer à partir de son activation.

---

## Notes importantes

1. **Révocation et matches** : Révoquer un like qui a matché ne supprime pas le match. Les utilisateurs peuvent toujours converser.

2. **Limite quotidienne** : Les statistiques incluent le nombre d'interactions restantes selon la limite quotidienne de l'utilisateur (Premium vs Free).

3. **Performance** : Les requêtes utilisent des index optimisés sur `(user, is_revoked, created_at)`.

4. **Confidentialité** : Un utilisateur ne peut voir que ses propres interactions, jamais celles des autres.

---

## Support

Pour toute question ou problème concernant cette API, consultez :
- Documentation principale : `API_DOCUMENTATION.md`
- Plan de développement : `backend-dev-plan.md`
- Spécifications d'interface : `Document de Spécification Interface - HIVMeet.txt`
