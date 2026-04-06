# Specification Complete des Filtres Backend pour Frontend Flutter

## 1. Vue d'ensemble

Cette specification couvre l'integration frontend des filtres de decouverte backend:

- Endpoint de sauvegarde des filtres utilisateur
- Endpoint de lecture des filtres utilisateur
- Endpoint de recuperation des profils de decouverte
- Regles backend appliquees en discovery (compatibilite mutuelle + exclusions)
- Gestion des limites quotidiennes (likes et super likes)

Base URL:

- Development: http://localhost:8000
- Prefix API: /api/v1

Authentification requise sur tous les endpoints ci-dessous:

- Header Authorization: Bearer <access_token>

## 2. Endpoints API

### 2.1 PUT /api/v1/discovery/filters

Description:

- Met a jour les filtres de recherche de l'utilisateur authentifie.

Headers requis:

- Authorization: Bearer <token>
- Content-Type: application/json

Body JSON:

```json
{
  "age_min": 25,
  "age_max": 40,
  "distance_max_km": 50,
  "genders": ["female", "non_binary"],
  "relationship_types": ["long_term", "casual"],
  "verified_only": true,
  "online_only": false
}
```

Notes:

- Les champs sont partiels (vous pouvez envoyer seulement les champs a modifier).
- all est accepte dans les tableaux (par ex. ["all"]) et est normalise en [].
- [] signifie aucun filtre (tous).

Reponse 200:

```json
{
  "status": "success",
  "message": "Filters updated successfully",
  "filters": {
    "age_min": 25,
    "age_max": 40,
    "distance_max_km": 50,
    "genders": [],
    "relationship_types": ["long_term", "casual"],
    "verified_only": true,
    "online_only": false
  }
}
```

Erreurs:

- 400 validation_error (details inclus)
- 401 authentication required
- 404 profile not found
- 500 internal error

---

### 2.2 GET /api/v1/discovery/filters/get

Description:

- Retourne les filtres actuellement enregistres pour l'utilisateur authentifie.

Reponse 200:

```json
{
  "status": "success",
  "filters": {
    "age_min": 18,
    "age_max": 99,
    "distance_max_km": 25,
    "genders": [],
    "relationship_types": [],
    "verified_only": false,
    "online_only": false
  }
}
```

Erreurs:

- 401 authentication required
- 404 profile not found

---

### 2.3 GET /api/v1/discovery/profiles

Description:

- Retourne une page de profils recommandes en appliquant tous les filtres backend et les exclusions.

Query params:

- page (default: 1)
- page_size (default: 10, max backend: 50)

Exemple:

- /api/v1/discovery/profiles?page=1&page_size=10

Reponse 200:

```json
{
  "count": 10,
  "next": "?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "user_id": "uuid",
      "display_name": "Alex",
      "age": 31,
      "bio": "...",
      "city": "Paris",
      "country": "France",
      "photos": ["https://..."],
      "interests": ["sport"],
      "relationship_types_sought": ["long_term"],
      "is_verified": true,
      "is_online": true,
      "distance_km": null
    }
  ],
  "daily_likes_remaining": 9,
  "daily_likes_limit": 10,
  "daily_likes_used_today": 1,
  "daily_likes_reset_at": "2026-03-28T00:00:00+00:00",
  "is_premium": false,
  "super_likes_remaining": 1
}
```

Erreurs:

- 401 authentication required

---

### 2.4 GET /api/v1/discovery/interactions/status

Description:

- Retourne l'etat des compteurs quotidiens de l'utilisateur.

Reponse 200:

```json
{
  "daily_likes_remaining": 10,
  "daily_likes_limit": 10,
  "super_likes_remaining": 1,
  "super_likes_limit": 1,
  "is_premium": false,
  "reset_at": "2026-03-28T00:00:00+00:00",
  "likes_used_today": 0,
  "super_likes_used_today": 0
}
```

## 3. Regles backend appliquees en discovery

## 3.1 Filtres principaux

- Age: age_min <= age <= age_max
- Distance: profile dans la zone <= distance_max_km
- Genre: profile.gender dans genders (si genders non vide)
- Relation: overlap entre relationship_types et relationship_types_sought du profile cible (ou profile cible ouvert [])
- verified_only: inclure uniquement user.is_verified=true
- online_only: inclure uniquement last_active <= 5 minutes

## 3.2 Compatibilites mutuelles

- Genre mutuel:
  - A voit B si B.genders_sought contient A.gender, ou B.genders_sought == []
- Age mutuel:
  - B doit accepter l'age de A
  - A doit accepter l'age de B

## 3.3 Exclusions

Le backend exclut systematiquement:

- Le profil de l'utilisateur lui-meme
- Les profils deja likes/dislikes/interactions actives
- Les profils bloques par l'utilisateur
- Les profils qui ont bloque l'utilisateur
- Les profils inactifs, non verifies email, masques, ou hors discovery

## 4. Limites quotidiennes

## 4.1 Likes

- Gratuit: 10/jour
- Premium: illimite

## 4.2 Super likes

- Gratuit: 1/jour
- Premium: 5/jour

## 4.3 Reset

- Reset quotidien a minuit UTC

## 5. Modeles de donnees Flutter (Dart)

```dart
class DiscoveryFilters {
  final int ageMin;
  final int ageMax;
  final int distanceMaxKm;
  final List<String> genders;
  final List<String> relationshipTypes;
  final bool verifiedOnly;
  final bool onlineOnly;

  const DiscoveryFilters({
    required this.ageMin,
    required this.ageMax,
    required this.distanceMaxKm,
    required this.genders,
    required this.relationshipTypes,
    required this.verifiedOnly,
    required this.onlineOnly,
  });

  Map<String, dynamic> toJson() => {
    'age_min': ageMin,
    'age_max': ageMax,
    'distance_max_km': distanceMaxKm,
    'genders': genders,
    'relationship_types': relationshipTypes,
    'verified_only': verifiedOnly,
    'online_only': onlineOnly,
  };

  factory DiscoveryFilters.fromJson(Map<String, dynamic> json) {
    final filters = json['filters'] ?? json;
    return DiscoveryFilters(
      ageMin: filters['age_min'] as int,
      ageMax: filters['age_max'] as int,
      distanceMaxKm: filters['distance_max_km'] as int,
      genders: List<String>.from(filters['genders'] as List? ?? const []),
      relationshipTypes: List<String>.from(
        filters['relationship_types'] as List? ?? const [],
      ),
      verifiedOnly: filters['verified_only'] as bool? ?? false,
      onlineOnly: filters['online_only'] as bool? ?? false,
    );
  }
}
```

## 6. Service Flutter d'integration (Dart)

```dart
class DiscoveryService {
  final Dio dio;

  DiscoveryService(this.dio);

  Future<DiscoveryFilters> getFilters() async {
    final res = await dio.get('/api/v1/discovery/filters/get');
    return DiscoveryFilters.fromJson(res.data as Map<String, dynamic>);
  }

  Future<DiscoveryFilters> updateFilters(DiscoveryFilters filters) async {
    final res = await dio.put(
      '/api/v1/discovery/filters',
      data: filters.toJson(),
    );
    return DiscoveryFilters.fromJson(res.data as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> getDiscoveryProfiles({
    int page = 1,
    int pageSize = 10,
  }) async {
    final res = await dio.get(
      '/api/v1/discovery/profiles',
      queryParameters: {
        'page': page,
        'page_size': pageSize,
      },
    );
    return res.data as Map<String, dynamic>;
  }
}
```

## 7. Codes d'erreur et gestion frontend

Recommandation de mapping frontend:

- 400: afficher erreurs de validation par champ
- 401: renvoyer vers refresh token/login
- 403: fonctionnalite interdite
- 404: ressource absente
- 429: limite quotidienne atteinte (afficher reset_at)
- 500: erreur serveur generique

## 8. Cas limites importants

- age_min > age_max: 400
- age hors [18,99]: 400
- distance_max_km hors [5,100]: 400
- genders contient valeur inconnue: 400
- relationship_types contient valeur inconnue: 400
- genders == []: tous genres
- relationship_types == []: tous types
- genders == ["all"]: normalise en []
- relationship_types == ["all"]: normalise en []
