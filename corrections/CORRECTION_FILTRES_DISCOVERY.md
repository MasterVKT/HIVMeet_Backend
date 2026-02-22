# 🔧 Corrections Filtres Discovery - HIVMeet

## 📋 Problèmes Identifiés

### ❌ **Problème 1: Filtres non sauvegardés (Frontend)**

**Symptôme** : Quand on modifie les filtres et qu'on revient sur la page, les valeurs par défaut sont affichées au lieu des valeurs actuelles.

**Cause** : [filters_page.dart](lib/presentation/pages/discovery/filters_page.dart) ligne 31
```dart
// TODO: Charger les préférences actuelles
_ageRange = const RangeValues(25, 40);  // ❌ Valeurs statiques
_maxDistance = 50;                       // ❌ Valeurs statiques
_relationshipType = 'all';               // ❌ Valeurs statiques
```

Les filtres ne sont **jamais chargés** depuis le profil utilisateur ou le backend.

---

### ❌ **Problème 2: Aucun profil ne passe le filtre `relationship_type` (Backend)**

**Logs Backend** :
```
INFO services After mutual gender compatibility: 5 profiles
INFO services After relationship type filter (['long_term', 'friendship']): 0 profiles  ← ⚠️
INFO services 📊 Total profiles after all filters: 0
```

**Analyse** :
1. **5 profils** passent tous les filtres (âge, distance, genre)
2. Le filtre `relationship_type` les **élimine tous**
3. Résultat : **0 profils**

**Causes possibles** :
- Les profils de test n'ont pas de `relationship_types` défini
- Le backend exclut les profils avec `relationship_types=null` ou `[]`
- Le filtre est trop strict (cherche correspondance exacte au lieu d'intersection)

---

### ❌ **Problème 3: Legacy likes/dislikes non filtrés (Backend)**

**Logs Backend** :
```
INFO services 🚫 Excluding 28 profiles:
INFO services    - Active interactions (is_revoked=False): 9  ← Diminue
INFO services    - Legacy likes: 14                          ← CONSTANT
INFO services    - Legacy dislikes: 13                       ← CONSTANT
```

Même après révocation, les "Legacy likes/dislikes" **ne diminuent pas**, confirmant qu'ils ne sont pas filtrés par `is_revoked=False`.

---

## ✅ Solutions

### 1. Charger les Filtres Actuels (Frontend)

**Fichier** : `lib/presentation/pages/discovery/filters_page.dart`

**Problème** : Les filtres ne sont pas chargés depuis le backend.

**Solution** : Utiliser `DiscoveryBloc.state` pour charger les filtres actuels, ou ajouter un use case `GetSearchFilters`.

#### Option A : Charger depuis le Profil Utilisateur (Recommandé)

```dart
@override
void initState() {
  super.initState();
  
  // Charger les préférences depuis le backend
  _loadCurrentFilters();
}

Future<void> _loadCurrentFilters() async {
  // TODO: Créer GetSearchFilters use case
  // Pour l'instant, utiliser des valeurs par défaut raisonnables
  final prefs = context.read<ProfileBloc>().state;
  
  if (prefs is ProfileLoaded) {
    setState(() {
      _ageRange = RangeValues(
        prefs.profile.searchPreferences?.minAge?.toDouble() ?? 18,
        prefs.profile.searchPreferences?.maxAge?.toDouble() ?? 99,
      );
      _maxDistance = prefs.profile.searchPreferences?.maxDistance ?? 50;
      _relationshipType = prefs.profile.searchPreferences?.relationshipTypes.firstOrNull ?? 'all';
      _genders = prefs.profile.searchPreferences?.interestedIn ?? ['all'];
      _verifiedOnly = prefs.profile.searchPreferences?.showVerifiedOnly ?? false;
    });
  }
}
```

#### Option B : Charger via un nouvel endpoint (Plus propre)

Créer un use case `GetSearchFilters` qui appelle `GET /api/v1/discovery/filters` ou `/api/v1/user-profiles/me/` et retourne les filtres actuels.

---

### 2. Corriger l'Envoi des Filtres `relationship_type`

**Fichier** : `lib/presentation/pages/discovery/filters_page.dart` ligne 354-376

**Problème actuel** :
```dart
void _applyFilters() {
  final filters = SearchFilters(
    minAge: _ageRange.start.round(),
    maxAge: _ageRange.end.round(),
    maxDistance: _maxDistance.round(),
    gender: _genders.isNotEmpty ? _genders.first : null,
    interests: null,
  );

  context.read<DiscoveryBloc>().add(UpdateFilters(filters: filters));
  context.pop();
}
```

**Problèmes** :
1. ❌ `relationship_type` n'est **pas envoyé** au backend
2. ❌ `gender` n'est pas correctement géré (liste vs string)

**Solution corrigée** :
```dart
void _applyFilters() {
  // ✅ Gérer "all" comme liste vide pour le backend
  final relationshipTypes = _relationshipType == 'all' ? [] : [_relationshipType];
  final genders = _genders.contains('all') ? [] : _genders;

  final filters = SearchPreferences(
    minAge: _ageRange.start.round(),
    maxAge: _ageRange.end.round(),
    maxDistance: _maxDistance,
    interestedIn: genders,
    relationshipTypes: relationshipTypes,  // ✅ Maintenant envoyé
    showVerifiedOnly: _verifiedOnly,
    showOnlineOnly: false,
  );

  print('🔄 Applying filters:');
  print('   - Age: ${filters.minAge} - ${filters.maxAge}');
  print('   - Distance: ${filters.maxDistance} km');
  print('   - Genders: ${filters.interestedIn}');
  print('   - Relationship types: ${filters.relationshipTypes}');

  context.read<DiscoveryBloc>().add(UpdateFilters(filters: filters));
  context.pop();
}
```

---

### 3. Corriger le Backend - Filtre `relationship_type`

**Fichier Backend** : `services.py` (fonction `get_recommendations`)

**Problème actuel** (hypothèse basée sur les logs) :
```python
# ❌ Code actuel (trop strict)
if user_relationship_types:
    profiles = profiles.filter(
        relationship_types__in=user_relationship_types
    )
```

Cela **exclut** les profils qui ont `relationship_types=null` ou `[]`.

**Solution corrigée** :
```python
# ✅ Code corrigé (permissif)
if user_relationship_types:
    # N'appliquer le filtre QUE si l'utilisateur a spécifié des types
    # Inclure aussi les profils avec relationship_types=null ou vide
    profiles = profiles.filter(
        Q(relationship_types__isnull=True) |
        Q(relationship_types=[]) |
        Q(relationship_types__overlap=user_relationship_types)
    )
```

**Ou plus simple** : Si `relationship_types=[]` (l'utilisateur cherche "Tout"), ne PAS appliquer le filtre :
```python
# ✅ Version simple
if user_relationship_types and len(user_relationship_types) > 0:
    # Seulement filtrer si des types spécifiques sont demandés
    profiles = profiles.filter(
        relationship_types__overlap=user_relationship_types
    )
# Si relationship_types=[], on ne filtre pas (accepte tous les profils)
```

---

### 4. Corriger le Backend - Legacy Likes/Dislikes

**Voir** : [CORRECTION_REVOCATION_BACKEND.md](CORRECTION_REVOCATION_BACKEND.md)

**TL;DR** :
```python
# ❌ AVANT
legacy_likes = UserInteraction.objects.filter(
    user=user,
    interaction_type='like'
)

# ✅ APRÈS
legacy_likes = UserInteraction.objects.filter(
    user=user,
    interaction_type='like',
    is_revoked=False  # ← AJOUTER CETTE CONDITION
)
```

---

## 🧪 Tests à Effectuer

### Test 1 : Sauvegarde des Filtres

1. Ouvrir l'app Flutter
2. Aller dans "Filtres de recherche"
3. Modifier :
   - Âge : 20-30
   - Distance : 25 km
   - Type de relation : "Amitié"
4. Cliquer "Appliquer"
5. Revenir dans "Filtres de recherche"
6. **Vérification** : Les valeurs doivent être **20-30, 25 km, Amitié** (pas les valeurs par défaut)

**Logs Frontend attendus** :
```
I/flutter: 🔄 Applying filters:
I/flutter:    - Age: 20 - 30
I/flutter:    - Distance: 25.0 km
I/flutter:    - Genders: []
I/flutter:    - Relationship types: [friendship]
```

---

### Test 2 : Filtre Relationship Type "Tout"

1. Aller dans "Filtres"
2. Sélectionner "Tout" pour type de relation
3. Appliquer

**Backend attendu** :
```
INFO services After mutual gender compatibility: 5 profiles
INFO services After relationship type filter ([]) or NO FILTER: 5 profiles  ← ✅ Garde les profils
INFO services 📊 Total profiles after all filters: 5
```

---

### Test 3 : Profils Révoqués Réapparaissent

1. Liker un profil
2. Annuler le like
3. Retourner en découverte

**Backend attendu** :
```
INFO services 🚫 Excluding X profiles:
INFO services    - Active interactions (is_revoked=False): 10  ← Diminue
INFO services    - Legacy likes: 10  ← Diminue aussi (ou 0 si migration)
INFO services    - Legacy dislikes: 13
```

Le profil **doit réapparaître** dans la découverte.

---

## 📝 Modifications Nécessaires

### Frontend ✅

**Fichier 1** : `lib/presentation/pages/discovery/filters_page.dart`
- [ ] Charger les filtres actuels depuis le backend dans `initState()`
- [ ] Corriger `_applyFilters()` pour envoyer `relationshipTypes`
- [ ] Gérer "all" comme liste vide `[]`

### Backend ⏳

**Fichier 1** : `services.py` (fonction `get_recommendations`)
- [ ] Corriger le filtre `relationship_type` pour ne PAS éliminer les profils avec `relationship_types=null` ou `[]`
- [ ] Si `relationship_types=[]` (utilisateur cherche "Tout"), ne pas appliquer le filtre

**Fichier 2** : `services.py` (Legacy interactions)
- [ ] Ajouter `is_revoked=False` aux requêtes Legacy likes/dislikes
- [ ] Voir [CORRECTION_REVOCATION_BACKEND.md](CORRECTION_REVOCATION_BACKEND.md)

---

## 📊 Résumé

| Problème | Fichier | Statut |
|----------|---------|--------|
| Filtres non sauvegardés | `filters_page.dart` | ⏳ À corriger |
| `relationship_type` non envoyé | `filters_page.dart` | ⏳ À corriger |
| Filtre trop strict (backend) | `services.py` | ⏳ À corriger |
| Legacy likes non filtrés | `services.py` | ⏳ À corriger |

---

## 🎯 Priorités

1. **URGENT** : Corriger le backend `relationship_type` filter → 0 profils actuellement
2. **IMPORTANT** : Charger les filtres actuels dans filters_page.dart
3. **IMPORTANT** : Envoyer `relationshipTypes` au backend
4. **MOYEN** : Corriger Legacy likes/dislikes

---

## 💡 Notes Additionnelles

### Valeurs par Défaut Recommandées

Quand un utilisateur n'a **jamais configuré ses filtres** :
```dart
_ageRange = RangeValues(18, 99);  // Tout le monde
_maxDistance = 50;                 // 50 km
_relationshipType = 'all';         // Tous types
_genders = ['all'];                // Tous genres
_verifiedOnly = false;             // Non
```

Ces valeurs devraient correspondre aux valeurs par défaut **côté backend** aussi.

### Endpoint Backend Filtres

Assurez-vous que le backend a bien :
- `GET /api/v1/discovery/filters` → Retourne les filtres actuels
- `PUT /api/v1/discovery/filters` → Met à jour les filtres

Ou utilise `/api/v1/user-profiles/me/` avec `search_preferences`.
