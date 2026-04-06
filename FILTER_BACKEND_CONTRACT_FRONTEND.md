# Contrat d'Interface Backend -> Frontend pour les Filtres Discovery

## 1. Contrat JSON - Requete PUT /api/v1/discovery/filters

| Cle | Type | Nullable | Plage / Valeurs |
|---|---|---|---|
| age_min | int | Non | 18-99 |
| age_max | int | Non | 18-99 |
| distance_max_km | int | Non | 5-100 |
| genders | string[] | Non | [] ou enum valide ou ["all"] |
| relationship_types | string[] | Non | [] ou enum valide ou ["all"] |
| verified_only | bool | Non | true/false |
| online_only | bool | Non | true/false |

Notes:

- Champs partiels autorises en PUT.
- all est accepte en entree puis normalise cote backend vers [].

## 2. Contrat JSON - Reponse succes PUT

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

## 3. Contrat JSON - Reponse succes GET /api/v1/discovery/filters/get

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

## 4. Valeurs enum

## 4.1 Genders

- male
- female
- non_binary
- trans_male
- trans_female
- other
- prefer_not_to_say

## 4.2 Relationship Types

- friendship
- long_term
- short_term
- casual

## 5. Contrat erreur standard (filtres)

400 Bad Request:

```json
{
  "error": true,
  "message": "Validation error",
  "details": {
    "genders": ["Invalid gender values: invalid_gender"],
    "relationship_types": ["Invalid relationship types: unknown_type"]
  }
}
```

404 Profile absent:

```json
{
  "error": true,
  "message": "Profile not found."
}
```

401 Auth absente/invalide:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

## 6. Discovery Profiles - Contrat de sortie

Endpoint: GET /api/v1/discovery/profiles

```json
{
  "count": 10,
  "next": "?page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "user_id": "uuid",
      "display_name": "Alex",
      "age": 30,
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

## 7. Regles metier contractuelles cote frontend

- [] pour genders signifie tous les genres.
- [] pour relationship_types signifie tous les types.
- Compatibilites mutuelles appliquees serveur (genre + age).
- Exclusions appliquees serveur (self, bloques, deja interagis, etc.).
- online_only est base sur une fenetre de 5 minutes de last_active.

## 8. Cas limites obligatoires

| Cas | Comportement backend |
|---|---|
| age_min > age_max | 400 |
| age_min < 18 | 400 |
| age_max > 99 | 400 |
| distance_max_km < 5 | 400 |
| distance_max_km > 100 | 400 |
| genders invalide | 400 |
| relationship_types invalide | 400 |
| genders = [] | Pas de filtre genre |
| relationship_types = [] | Pas de filtre relation |
| genders = ["all"] | Normalise en [] |
| relationship_types = ["all"] | Normalise en [] |

## 9. Limites quotidiennes (contrat fonctionnel)

- Likes:
  - Gratuit: 10/jour
  - Premium: illimite
- Super likes:
  - Gratuit: 1/jour
  - Premium: 5/jour
- Reset:
  - Minuit UTC
