# 🔍 API DISCOVERY FILTERS - DOCUMENTATION

**Version** : 1.0  
**Date** : 29 décembre 2025  
**Module** : Matching / Discovery

---

## 📋 VUE D'ENSEMBLE

Cette documentation décrit les nouveaux endpoints pour la gestion des filtres de découverte dans HIVMeet. Ces endpoints permettent aux utilisateurs de personnaliser leurs critères de recherche et d'obtenir des profils correspondant à leurs préférences.

---

## 🔐 AUTHENTIFICATION

Tous les endpoints nécessitent une authentification JWT valide :

```
Authorization: Bearer <firebase_id_token>
```
continue
---

## 📡 ENDPOINTS

### 1. Mettre à jour les filtres de découverte

**Endpoint** : `PUT /api/v1/discovery/filters`  
**Authentification** : Requise  
**Description** : Sauvegarde les préférences de filtrage de l'utilisateur.

#### Requête

**Headers** :
```
Content-Type: application/json
Authorization: Bearer <firebase_id_token>
```

**Body** (tous les champs sont optionnels) :
```json
{
  "age_min": 25,
  "age_max": 40,
  "distance_max_km": 50,
  "genders": ["female", "non-binary"],
  "relationship_types": ["serious", "casual"],
  "verified_only": false,
  "online_only": false
}
```

#### Paramètres

| Paramètre | Type | Obligatoire | Valeurs | Description |
|-----------|------|-------------|---------|-------------|
| `age_min` | Integer | Non | 18-99 | Âge minimum recherché |
| `age_max` | Integer | Non | 18-99 | Âge maximum recherché |
| `distance_max_km` | Integer | Non | 5-100 | Distance maximale en kilomètres |
| `genders` | Array[String] | Non | `["male", "female", "non_binary", "trans_male", "trans_female", "other"]` ou `["all"]` | Genres recherchés |
| `relationship_types` | Array[String] | Non | `["friendship", "long_term", "short_term", "casual"]` ou `["all"]` | Types de relation recherchés |
| `verified_only` | Boolean | Non | `true` / `false` | Afficher uniquement les profils vérifiés |
| `online_only` | Boolean | Non | `true` / `false` | Afficher uniquement les profils en ligne |

#### Réponses

**Succès (200 OK)** :
```json
{
  "status": "success",
  "message": "Filtres mis à jour avec succès",
  "filters": {
    "age_min": 25,
    "age_max": 40,
    "distance_max_km": 50,
    "genders": ["female", "non-binary"],
    "relationship_types": ["serious", "casual"],
    "verified_only": false,
    "online_only": false
  }
}
```

**Erreur de validation (400 Bad Request)** :
```json
{
  "error": true,
  "message": "Validation error",
  "details": {
    "age_min": ["Minimum age must be less than or equal to maximum age."]
  }
}
```

**Non authentifié (401 Unauthorized)** :
```json
{
  "error": true,
  "message": "Authentication required"
}
```

**Profil non trouvé (404 Not Found)** :
```json
{
  "error": true,
  "message": "Profile not found."
}
```

#### Exemple d'appel (cURL)

```bash
curl -X PUT https://api.hivmeet.com/api/v1/discovery/filters \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "age_min": 25,
    "age_max": 35,
    "distance_max_km": 30,
    "genders": ["female"],
    "relationship_types": ["serious"],
    "verified_only": true,
    "online_only": false
  }'
```

#### Exemple d'appel (Dart/Flutter)

```dart
Future<void> updateDiscoveryFilters({
  int? ageMin,
  int? ageMax,
  int? distanceMaxKm,
  List<String>? genders,
  List<String>? relationshipTypes,
  bool? verifiedOnly,
  bool? onlineOnly,
}) async {
  final response = await http.put(
    Uri.parse('$baseUrl/api/v1/discovery/filters'),
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $firebaseToken',
    },
    body: jsonEncode({
      if (ageMin != null) 'age_min': ageMin,
      if (ageMax != null) 'age_max': ageMax,
      if (distanceMaxKm != null) 'distance_max_km': distanceMaxKm,
      if (genders != null) 'genders': genders,
      if (relationshipTypes != null) 'relationship_types': relationshipTypes,
      if (verifiedOnly != null) 'verified_only': verifiedOnly,
      if (onlineOnly != null) 'online_only': onlineOnly,
    }),
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    print('Filters updated: ${data['filters']}');
  } else {
    throw Exception('Failed to update filters');
  }
}
```

---

### 2. Récupérer les filtres actuels

**Endpoint** : `GET /api/v1/discovery/filters/get`  
**Authentification** : Requise  
**Description** : Récupère les préférences de filtrage actuelles de l'utilisateur.

#### Requête

**Headers** :
```
Authorization: Bearer <firebase_id_token>
```

**Paramètres** : Aucun

#### Réponses

**Succès (200 OK)** :
```json
{
  "filters": {
    "age_min": 25,
    "age_max": 40,
    "distance_max_km": 50,
    "genders": ["female", "non-binary"],
    "relationship_types": ["serious", "casual"],
    "verified_only": false,
    "online_only": false
  }
}
```

**Note** : Si un filtre contient une liste vide `[]`, cela signifie "tous" (pas de filtre appliqué).
- `"genders": []` → Tous les genres
- `"relationship_types": []` → Tous les types de relation

**Non authentifié (401 Unauthorized)** :
```json
{
  "error": true,
  "message": "Authentication required"
}
```

**Profil non trouvé (404 Not Found)** :
```json
{
  "error": true,
  "message": "Profile not found."
}
```

#### Exemple d'appel (cURL)

```bash
curl -X GET https://api.hivmeet.com/api/v1/discovery/filters/get \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### Exemple d'appel (Dart/Flutter)

```dart
Future<Map<String, dynamic>> getDiscoveryFilters() async {
  final response = await http.get(
    Uri.parse('$baseUrl/api/v1/discovery/filters/get'),
    headers: {
      'Authorization': 'Bearer $firebaseToken',
    },
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    return data['filters'];
  } else {
    throw Exception('Failed to get filters');
  }
}
```

---

### 3. Récupérer les profils de découverte (MODIFIÉ)

**Endpoint** : `GET /api/v1/discovery/profiles`  
**Authentification** : Requise  
**Description** : Récupère une liste de profils correspondant aux filtres sauvegardés de l'utilisateur.

#### ⚠️ CHANGEMENT IMPORTANT

**AVANT** : Les filtres n'étaient PAS appliqués → tous les profils retournés  
**MAINTENANT** : Les filtres sauvegardés sont **automatiquement appliqués**

#### Requête

**Headers** :
```
Authorization: Bearer <firebase_id_token>
```

**Query Parameters** :
```
?page=1&page_size=20
```

| Paramètre | Type | Obligatoire | Valeur par défaut | Description |
|-----------|------|-------------|-------------------|-------------|
| `page` | Integer | Non | 1 | Numéro de page |
| `page_size` | Integer | Non | 10 | Nombre de profils par page (max: 50) |

#### Réponses

**Succès (200 OK)** :
```json
{
  "count": 10,
  "next": "?page=2&page_size=20",
  "previous": null,
  "results": [
    {
      "user_id": "0e3f0c6d-fea6-4933-a52a-2454e5fc72a7",
      "display_name": "Sophie",
      "age": 28,
      "bio": "Passionnée de voyages et de photographie...",
      "city": "Paris",
      "country": "France",
      "photos": [
        {
          "url": "https://storage.googleapis.com/...",
          "thumbnail_url": "https://storage.googleapis.com/...",
          "is_main": true
        }
      ],
      "interests": ["voyages", "photographie", "yoga"],
      "relationship_types_sought": ["serious", "long_term"],
      "is_verified": true,
      "is_online": false,
      "distance_km": 12.5
    }
  ]
}
```

#### Filtrage automatique appliqué

Les profils retournés respectent automatiquement :
1. ✅ Âge entre `age_min` et `age_max`
2. ✅ Distance ≤ `distance_max_km`
3. ✅ Genre dans `genders` (si non vide)
4. ✅ Type de relation dans `relationship_types` (si non vide)
5. ✅ `is_verified = true` si `verified_only = true`
6. ✅ `is_online = true` si `online_only = true`
7. ✅ Profils avec lesquels l'utilisateur n'a pas encore interagi

#### Exemple d'appel (cURL)

```bash
curl -X GET "https://api.hivmeet.com/api/v1/discovery/profiles?page=1&page_size=20" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### Exemple d'appel (Dart/Flutter)

```dart
Future<List<Profile>> getDiscoveryProfiles({
  int page = 1,
  int pageSize = 20,
}) async {
  final response = await http.get(
    Uri.parse('$baseUrl/api/v1/discovery/profiles?page=$page&page_size=$pageSize'),
    headers: {
      'Authorization': 'Bearer $firebaseToken',
    },
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    return (data['results'] as List)
        .map((json) => Profile.fromJson(json))
        .toList();
  } else {
    throw Exception('Failed to load profiles');
  }
}
```

---

## 🔄 WORKFLOW COMPLET

### Scénario d'utilisation typique

```
1. Utilisateur ouvre l'écran de filtres
   ↓
2. App appelle GET /api/v1/discovery/filters/get
   → Récupère les filtres actuels
   ↓
3. Utilisateur modifie les filtres (âge, distance, etc.)
   ↓
4. App appelle PUT /api/v1/discovery/filters
   → Sauvegarde les nouveaux filtres
   ↓
5. App navigue vers l'écran de découverte
   ↓
6. App appelle GET /api/v1/discovery/profiles
   → Reçoit les profils filtrés automatiquement
```

### Code Flutter complet

```dart
class DiscoveryService {
  final String baseUrl;
  final String firebaseToken;

  // 1. Récupérer les filtres actuels
  Future<DiscoveryFilters> getCurrentFilters() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/v1/discovery/filters/get'),
      headers: {'Authorization': 'Bearer $firebaseToken'},
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return DiscoveryFilters.fromJson(data['filters']);
    }
    throw Exception('Failed to get filters');
  }

  // 2. Mettre à jour les filtres
  Future<void> updateFilters(DiscoveryFilters filters) async {
    final response = await http.put(
      Uri.parse('$baseUrl/api/v1/discovery/filters'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $firebaseToken',
      },
      body: jsonEncode(filters.toJson()),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update filters');
    }
  }

  // 3. Récupérer les profils filtrés
  Future<List<Profile>> getFilteredProfiles({int page = 1}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/v1/discovery/profiles?page=$page&page_size=20'),
      headers: {'Authorization': 'Bearer $firebaseToken'},
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['results'] as List)
          .map((json) => Profile.fromJson(json))
          .toList();
    }
    throw Exception('Failed to load profiles');
  }
}
```

---

## 📝 NOTES IMPORTANTES

### Valeur "all" pour les filtres

Lorsque l'utilisateur sélectionne "Tous" dans l'interface :

**Frontend envoie** :
```json
{
  "genders": ["all"],
  "relationship_types": ["all"]
}
```

**Backend sauvegarde** :
```json
{
  "genders": [],
  "relationship_types": []
}
```

**Backend retourne** (dans GET /filters/get) :
```json
{
  "genders": ["all"],
  "relationship_types": ["all"]
}
```

→ Le backend convertit automatiquement les listes vides en `["all"]` pour la cohérence avec le frontend.

### Critère "en ligne"

Un utilisateur est considéré **en ligne** si sa dernière activité date de moins de 5 minutes :
```python
is_online = (now - user.last_active) < 5 minutes
```

### Ordre de priorité des résultats

Les profils sont retournés dans cet ordre :
1. 🚀 Profils boostés (premium)
2. 🕐 Dernière activité (plus récent en premier)
3. ✅ Profils vérifiés
4. 📋 Profils complets (bio + photos)

### Valeurs par défaut

Si l'utilisateur n'a jamais défini de filtres :
```json
{
  "age_min": 18,
  "age_max": 99,
  "distance_max_km": 25,
  "genders": ["all"],
  "relationship_types": ["all"],
  "verified_only": false,
  "online_only": false
}
```

---

## 🐛 GESTION DES ERREURS

### Erreurs communes

| Code | Message | Cause | Solution |
|------|---------|-------|----------|
| 400 | Validation error | Données invalides (ex: age_min > age_max) | Vérifier les valeurs avant envoi |
| 401 | Authentication required | Token manquant ou invalide | Authentifier l'utilisateur |
| 404 | Profile not found | Profil utilisateur inexistant | S'assurer que le profil est créé |
| 500 | Internal server error | Erreur serveur | Contacter le support |

### Exemple de gestion d'erreur (Dart)

```dart
try {
  await updateFilters(newFilters);
  showSuccess('Filtres mis à jour');
} on HttpException catch (e) {
  if (e.statusCode == 400) {
    showError('Données invalides : ${e.message}');
  } else if (e.statusCode == 401) {
    // Rediriger vers la connexion
    navigateToLogin();
  } else {
    showError('Erreur serveur');
  }
}
```

---

## 🔒 SÉCURITÉ

1. **Authentification obligatoire** : Tous les endpoints nécessitent un token Firebase valide
2. **Validation des données** : Toutes les entrées sont validées côté serveur
3. **Isolation des données** : Chaque utilisateur ne peut modifier que ses propres filtres
4. **Logs de sécurité** : Toutes les opérations sont journalisées

---

## 📊 LIMITES ET QUOTAS

| Ressource | Limite | Description |
|-----------|--------|-------------|
| Requêtes/minute | 60 | Maximum de requêtes par utilisateur |
| `page_size` maximum | 50 | Nombre max de profils par page |
| `distance_max_km` maximum | 100 | Distance maximale en km |
| `age_min` minimum | 18 | Âge minimum légal |
| `age_max` maximum | 99 | Âge maximum accepté |

---

## 📞 SUPPORT

En cas de problème :
1. Vérifier la documentation API
2. Consulter les logs de l'application
3. Tester avec le script : `python test_discovery_filters.py`
4. Contacter l'équipe backend

---

**Version de l'API** : v1  
**Dernière mise à jour** : 29 décembre 2025  
**Auteur** : Équipe Backend HIVMeet
