# 📋 TÂCHE KANBAN : Vérification et Implémentation Complète des Filtres de Découverte Backend

## 🎯 Titre de la Tâche

**"Audit, Implémentation et Tests Déterministes des Filtres de Profil dans la Page de Découverte - Backend 100% Opérationnel + Documentation Frontend Complète"**

---

## 📝 Description Détaillée

### Objectif Principal

Cette tâche consiste à :

1. **Audit Complet** : Vérifier que **TOUTES** les fonctionnalités de filtres de profils dans la page de découverte sont **implémentées et 100% fonctionnelles** côté backend
2. **Implémentation des Manquants** : Identifier et implémenter chaque fonctionnalité qui n'est pas encore développée
3. **Tests Déterministes** : Créer des tests approfondis, efficaces et **totalement déterministes** pour chaque fonctionnalité individuelle et leurs combinaisons
4. **Automatisation des Corrections** : Correction automatique des erreurs avec vérification systématique à chaque niveau
5. **Régression Testing** : Tests systématiques à chaque étape pour garantir **100% de certitude** de non-régression
6. **Documentation Frontend** : Génération de fichiers markdown détaillés et structurés contenant **l'intégralité des éléments backend** nécessaires au frontend pour implémenter les filtres

---

## 🔍 PHASE 1 : ANALYSE ET AUDIT (Étapes Préliminaires)

### 1.1 Inventaire des Fonctionnalités Attendues

Selon les spécifications (`docs/API_DOCUMENTATION.md`, `docs/backend-specs.md`, `docs/API_DISCOVERY_FILTERS.md`), les fonctionnalités de filtre suivantes doivent exister :

#### A. Filtres Principaux de Recherche

| # | Fonctionnalité | Description | Endpoint Backend | Statut à Vérifier |
|---|----------------|-------------|------------------|-------------------|
| 1 | **Filtre d'Âge** | `age_min` et `age_max` (18-99 ans) | `PUT /api/v1/discovery/filters` | ❓ |
| 2 | **Filtre de Distance** | `distance_max_km` (5-100 km) | `PUT /api/v1/discovery/filters` | ❓ |
| 3 | **Filtre de Genre** | `genders` (male, female, non_binary, etc.) | `PUT /api/v1/discovery/filters` | ❓ |
| 4 | **Filtre Type de Relation** | `relationship_types` (friendship, long_term, short_term, casual) | `PUT /api/v1/discovery/filters` | ❓ |
| 5 | **Filtre Vérifiés Uniquement** | `verified_only` (bool) | `PUT /api/v1/discovery/filters` | ❓ |
| 6 | **Filtre En Ligne Uniquement** | `online_only` (bool) | `PUT /api/v1/discovery/filters` | ❓ |

#### B. Filtres de Compatibilité Mutuelle

| # | Fonctionnalité | Description | Implémentation | Statut à Vérifier |
|---|----------------|-------------|-----------------|-------------------|
| 7 | **Compatibilité Genre Mutuelle** | L'utilisateur A voit B seulement si B cherche le genre de A | `services.py` | ❓ |
| 8 | **Compatibilité Âge Mutuelle** | L'utilisateur A voit B seulement si les préférences d'âge sont compatibles | `services.py` | ❓ |

#### C. Fonctionnalités de Gestion des Limites

| # | Fonctionnalité | Description | Endpoint | Statut à Vérifier |
|---|----------------|-------------|----------|-------------------|
| 9 | **Compteur de Likes Quotidiens** | Limite 10/jour (gratuit), illimité (premium) | `DailyLikesService` | ❓ |
| 10 | **Compteur de Super Likes** | 1/jour (gratuit), 5/jour (premium) | `DailyLikesService` | ❓ |
| 11 | **Reset Quotidien** | Réinitialisation à minuit UTC | `DailyLikesService` | ❓ |

#### D. Fonctionnalités d'Exclusion

| # | Fonctionnalité | Description | Implémentation | Statut à Vérifier |
|---|----------------|-------------|----------------|-------------------|
| 12 | **Exclusion Profils Bloqués** | Ne pas montrer les utilisateurs bloqués | `services.py` | ❓ |
| 13 | **Exclusion Profils Déjà Vus** | Ne pas montrer après like/dislike/rewind | `InteractionHistory` | ❓ |
| 14 | **Exclusion Auto-Blocked** | Ne pas montrer si l'autre a bloqué | `services.py` | ❓ |
| 15 | **Exclusion Profil Propre** | Ne pas se montrer à soi-même | `services.py` | ❓ |

### 1.2 Analyse du Code Existant

#### Fichiers à Examiner

```
matching/
├── views_discovery.py      # Endpoints HTTP
├── services.py             # Logique RecommendationService, MatchingService
├── daily_likes_service.py # Gestion des limites quotidiennes
├── interaction_service.py  # Gestion des interactions
├── serializers.py          # Validation et sérialisation
├── urls_discovery.py       # Routing des URLs
└── models.py              # Modèles Like, Match, etc.

profiles/
├── models.py              # Profile avec champs de filtres
├── serializers.py         # Validation des préférences
└── views.py               # Endpoints de profil
```

#### Points d'Audit Spécifiques

1. **RecommendationService.get_recommendations()** :
   - ❏ Filtre d'âge implémenté ?
   - ❏ Filtre de distance implémenté ?
   - ❏ Filtre de genre implémenté ?
   - ❏ Filtre relationship_types implémenté ?
   - ❏ Filtre verified_only implémenté ?
   - ❏ Filtre online_only implémenté ?
   - ❏ Compatibilité mutuelle genre vérifiée ?
   - ❏ Compatibilité mutuelle âge vérifiée ?
   - ❏ Exclusions (bloqués, déjà vus, etc.) appliquées ?

2. **SearchFilterSerializer** :
   - ❏ Validation de age_min < age_max ?
   - ❏ Validation de distance_max_km (5-100) ?
   - ❏ Validation des genres valides ?
   - ❏ Conversion "all" → [] ?

3. **Endpoints** :
   - ❏ GET /api/v1/discovery/profiles - Applique les filtres ?
   - ❏ PUT /api/v1/discovery/filters - Sauvegarde correctement ?
   - ❏ GET /api/v1/discovery/filters/get - Retourne les filtres ?

---

## 🔧 PHASE 2 : IMPLÉMENTATION DES FONCTIONNALITÉS MANQUANTES

### 2.1 Checklist d'Implémentation

Pour chaque fonctionnalité manquante identifiée dans l'audit :

- [ ] **Implémenter la fonctionnalité**
- [ ] **Vérifier qu'elle compile sans erreur**
- [ ] **Créer un test unitaire déterministe**
- [ ] **Exécuter le test et vérifier qu'il passe**
- [ ] **Documenter l'implémentation**

### 2.2 Règles de Compatibilité Mutuelle (IMPORTANT)

Le système de découverte **DOIT** respecter la compatibilité mutuelle :

```
Règle 1 - Genre :
   A voit B SI ET SEULEMENT SI :
   - B.genders_sought CONTIENT A.gender OU B.genders_sought = []

Règle 2 - Âge :
   A voit B SI ET SEULEMENT SI :
   - B.age_min_preference ≤ A.age ≤ B.age_max_preference
   - A.age_min_preference ≤ B.age ≤ A.age_max_preference

Règle 3 - Distance :
   A voit B SI ET SEULEMENT SI :
   - distance(A, B) ≤ A.distance_max_km

Règle 4 - Type de Relation :
   A voit B SI ET SEULEMENT SI :
   - A.relationship_types_sought INTERSECTE B.relationship_types_sought
   - OU A.relationship_types_sought = []
   - OU B.relationship_types_sought = []
```

### 2.3 Format des Réponses API

Chaque filtre doit retourner dans la réponse :
```json
{
  "age_min": 25,
  "age_max": 40,
  "distance_max_km": 50,
  "genders": ["female", "non-binary"],
  "relationship_types": ["serious", "casual"],
  "verified_only": true,
  "online_only": false
}
```

**Note** : `genders: []` ou `relationship_types: []` signifie "tous" (pas de filtre).

---

## 🧪 PHASE 3 : CRÉATION DES TESTS DÉTERMINISTES

### 3.1 Principes des Tests Déterministes

Un test **déterministe** signifie :

✅ **GARANTIES ABSOLUES** :
- Si le test **passe** → La fonctionnalité **fonctionne à 100%**
- Si le test **échoue** → La fonctionnalité **ne fonctionne pas**
- **ZÉRO faux positifs** possibles
- **ZÉRO faux négatifs** possibles

❌ **Interdit** :
- Pas de tests avec `assertTrue` ou `assertFalse` seuls
- Pas de tests qui dépendent de données aléatoires
- Pas de tests avec des valeurs limites non vérifiées

### 3.2 Structure des Tests

#### A. Tests Unitaires par Fonctionnalité

```python
# tests/test_discovery_filters.py

class TestAgeFilter:
    """Tests déterministes pour le filtre d'âge."""
    
    def test_age_filter_returns_profiles_within_range(self):
        """
        GIVEN: Un utilisateur avec age_min=25, age_max=35
        WHEN: Il demande des profils de découverte
        THEN: TOUS les profils retournés ont un âge entre 25 et 35 ans
        """
        # Setup : Créer utilisateurs de test avec âges précis
        # Action : Appeler get_recommendations
        # Assert : Vérifier CHAQUE profil retourné
        
    def test_age_filter_excludes_profiles_outside_range(self):
        """
        GIVEN: Un utilisateur avec age_min=25, age_max=35
        WHEN: Il demande des profils de découverte
        THEN: AUCUN profil avec âge < 25 ou > 35 n'est retourné
        """
        
    def test_age_filter_boundary_18_years_old(self):
        """
        GIVEN: Un utilisateur avec age_min=18
        WHEN: Il demande des profils de découverte
        THEN: Un profil de 18 ans EST retourné
        """
        
    def test_age_filter_boundary_99_years_old(self):
        """
        GIVEN: Un utilisateur avec age_max=99
        WHEN: Il demande des profils de découverte
        THEN: Un profil de 99 ans EST retourné
        """
```

#### B. Tests de Compatibilité Mutuelle

```python
class TestMutualGenderCompatibility:
    """Tests pour la compatibilité mutuelle de genre."""
    
    def test_mutual_gender_male_sees_female_who_seeks_male(self):
        """
        GIVEN: Homme A (gender=male) cherchant "female"
              Femme B (genders_sought=["male"])
        WHEN: A demande la découverte
        THEN: B EST dans les résultats
        
    def test_mutual_gender_male_does_not_see_female_who_seeks_female_only(self):
        """
        GIVEN: Homme A (gender=male)
              Femme B (genders_sought=["female"]) - ne cherche pas les hommes
        WHEN: A demande la découverte
        THEN: B N'EST PAS dans les résultats
        
    def test_mutual_gender_user_with_empty_genders_sought_sees_all(self):
        """
        GIVEN: Homme A (genders_sought=[])
        WHEN: A demande la découverte
        THEN: Tous les genres SONT visibles pour A
        """
```

#### C. Tests de Combinaison de Filtres

```python
class TestFilterCombinations:
    """Tests des combinaisons de filtres."""
    
    def test_combination_age_gender_distance(self):
        """
        GIVEN: Filtres: age=25-35, gender=female, distance=50km
        WHEN: Demande de découverte
        THEN: 
          - Chaque profil a un âge entre 25-35
          - Chaque profil est de genre female
          - Chaque profil est à ≤ 50km
          - ET les trois conditions sont TOUTES vraies
        """
        
    def test_combination_verified_and_online(self):
        """
        GIVEN: Filtres: verified_only=true, online_only=true
        WHEN: Demande de découverte
        THEN:
          - Chaque profil est vérifié
          - Chaque profil est en ligne
          - Les deux conditions sont vraies
        """
```

### 3.3 Scénarios de Test Complets

#### Scénario 1 : Filtre d'Âge Complet
| # | Test | Données | Résultat Attendu | Déterministe ? |
|---|------|---------|------------------|----------------|
| 1 | Profil dans la plage | A: 25-35, B: 30 ans | B visible | ✅ |
| 2 | Profil en dessous min | A: 25-35, B: 24 ans | B invisible | ✅ |
| 3 | Profil au-dessus max | A: 25-35, B: 36 ans | B invisible | ✅ |
| 4 | Profil à la limite min | A: 25-35, B: 25 ans | B visible | ✅ |
| 5 | Profil à la limite max | A: 25-35, B: 35 ans | B visible | ✅ |

#### Scénario 2 : Filtre de Genre Complet
| # | Test | Données | Résultat Attendu | Déterministe ? |
|---|------|---------|------------------|----------------|
| 1 | Genre unique trouvé | A cherche [female], B: female | B visible | ✅ |
| 2 | Genre unique non trouvé | A cherche [female], B: male | B invisible | ✅ |
| 3 | Multi-genres | A cherche [female, male], B: male | B visible | ✅ |
| 4 | Tous les genres | A cherche [], B: n'importe | B visible | ✅ |
| 5 | Compatibilité mutuelle | A: male, cherche [female], B: female, cherche [male] | A→B: Non, B→A: Non | ✅ |

#### Scénario 3 : Filtre de Distance Complet
| # | Test | Données | Résultat Attendu | Déterministe ? |
|---|------|---------|------------------|----------------|
| 1 | Dans la distance | A: 50km, B: 30km | B visible | ✅ |
| 2 | Exactement à la limite | A: 50km, B: 50km | B visible | ✅ |
| 3 | Au-delà de la limite | A: 50km, B: 51km | B invisible | ✅ |
| 4 | Distance 0 (même lieu) | A: 50km, B: 0km | B visible | ✅ |

#### Scénario 4 : Combinaison Multi-Filtres
| # | Test | Filtres | Résultat Attendu | Déterministe ? |
|---|------|---------|------------------|----------------|
| 1 | Tous les filtres stricts | age:25-35, gender:female, dist:30km, verified:true | Un seul profil | ✅ |
| 2 | Filtres larges | age:18-99, gender:[], dist:100km | Beaucoup de profils | ✅ |
| 3 | Filtres contradictoires | age:25-35, mais B: 40 ans | Zéro résultat | ✅ |

### 3.4 Exécution des Tests

```bash
# Exécuter TOUS les tests de filtres
python -m pytest tests/test_discovery_filters.py -v --tb=short

# Exécuter avec couverture
python -m pytest tests/test_discovery_filters.py --cov=matching --cov-report=term-missing

# Exécuter un test spécifique
python -m pytest tests/test_discovery_filters.py::TestAgeFilter::test_age_filter_returns_profiles_within_range -v
```

---

## 🔄 PHASE 4 : CORRECTION AUTOMATISÉE DES ERREURS

### 4.1 Workflow de Correction

Pour **CHAQUE** erreur rencontrée :

```
1. IDENTIFICATION
   ↓
2. ANALYSE (cause racine)
   ↓
3. CORRECTION (code)
   ↓
4. VÉRIFICATION (le code compile)
   ↓
5. TEST (test unitaire)
   ↓
   ├── ÉCHEC → Retour à l'étape 3
   └── SUCCÈS → Étape 6
   ↓
6. RÉGRESSION (tests existants)
   ↓
   ├── ÉCHEC → Retour à l'étape 3
   └── SUCCÈS → Étape 7
   ↓
7. DOCUMENTATION (logs, comments)
   ↓
8. VALIDATION FINALE
```

### 4.2 Automatisation des Vérifications

#### Script de Validation Automatique

```python
# scripts/validate_filters.py
"""
Script de validation automatique des filtres de découverte.
Exécute tous les tests et génère un rapport.
"""

def validate_all():
    """Validation complète du système de filtres."""
    results = {
        'age_filter': run_tests('tests/test_age_filter.py'),
        'gender_filter': run_tests('tests/test_gender_filter.py'),
        'distance_filter': run_tests('tests/test_distance_filter.py'),
        'compatibility': run_tests('tests/test_compatibility.py'),
        'combinations': run_tests('tests/test_combinations.py'),
        'exclusions': run_tests('tests/test_exclusions.py'),
    }
    
    all_passed = all(r['passed'] for r in results.values())
    
    if not all_passed:
        # AUTOMATIQUE : Générer rapport d'erreurs
        generate_error_report(results)
        return False, results
    
    # AUTOMATIQUE : Générer rapport de succès
    generate_success_report(results)
    return True, results
```

### 4.3 Critères de Validation

| Critère | Description | Seuil Minimum |
|---------|-------------|----------------|
| Tests unitaires passent | 100% des tests passent | 100% |
| Couverture de code | % du code testé | ≥ 80% |
| Temps de réponse | Latence endpoint | ≤ 500ms |
| Aucun avertissement | Warnings Django | 0 |

---

## 📊 PHASE 5 : TESTS DE RÉGRESSION SYSTÉMATIQUES

### 5.1 Ensemble de Tests de Régression

```python
# tests/test_regression_discovery.py

REGRESSION_TESTS = [
    # Tests existants qui doivent continuer à passer
    'test_like_profile_success',
    'test_dislike_profile_success',
    'test_superlike_premium_only',
    'test_match_creation',
    'test_daily_limit_enforcement',
    'test_block_exclusion',
    'test_self_exclusion',
    # ... ajouter tous les tests existants
]
```

### 5.2 Exécution de la Régression

```bash
# Avant chaque modification, exécuter la régression
python -m pytest tests/ -v --tb=short -k "not test_new_feature"

# Après chaque modification, vérifier que rien n'est cassé
python -m pytest tests/ -v --tb=short
```

### 5.3 Protection Contre la Régression

**RÈGLE ABSOLUE** :
> ❌ **ZÉRO régression acceptée**
> 
> Si un test existant échoue après une modification :
> 1. La modification est **REJETÉE**
> 2. Retour à l'état précédent
> 3. Correction obligatoire avant de continuer

---

## 📚 PHASE 6 : DOCUMENTATION FRONTEND

### 6.1 Fichiers à Générer

À la fin de cette tâche, **DEUX fichiers markdown** doivent être créés :

#### Fichier 1 : `FILTER_BACKEND_SPECIFICATION_FRONTEND.md`

```markdown
# Spécification Complète des Filtres Backend pour Frontend Flutter

## 📋 Table des Matières
1. Vue d'Ensemble
2. Endpoints API
3. Modèles de Données
4. Scénarios d'Utilisation
5. Codes d'Erreur
6. Exemples de Code Dart
7. Notes Importantes
```

#### Fichier 2 : `FILTER_BACKEND_CONTRACT_FRONTEND.md`

```markdown
# Contrat d'Interface Backend → Frontend pour les Filtres

## 🎯 Contrat JSON
```

### 6.2 Contenu du Fichier 1 (Spécification Complète)

#### Section A : Endpoints API Complets

```
PUT /api/v1/discovery/filters
GET /api/v1/discovery/filters/get
GET /api/v1/discovery/profiles
```

Pour CHAQUE endpoint :

```markdown
### PUT /api/v1/discovery/filters

#### Description
[Sauvegarde les filtres de recherche de l'utilisateur]

#### Headers Requis
- Authorization: Bearer <token>
- Content-Type: application/json

#### Corps de la Requête
{
  "age_min": Number,      // 18-99
  "age_max": Number,       // 18-99
  "distance_max_km": Number, // 5-100
  "genders": Array,       // ["male", "female", ...] ou ["all"]
  "relationship_types": Array, // ["friendship", "long_term", ...] ou ["all"]
  "verified_only": Boolean,
  "online_only": Boolean
}

#### Réponse 200 OK
{
  "status": "success",
  "message": "Filtres mis à jour avec succès",
  "filters": { ... }
}

#### Codes d'Erreur
- 400: Validation error (détails dans "details")
- 401: Authentication required
- 404: Profile not found
- 500: Server error
```

#### Section B : Modèles de Données Flutter

```dart
class DiscoveryFilters {
  final int ageMin;
  final int ageMax;
  final int distanceMaxKm;
  final List<String> genders;
  final List<String> relationshipTypes;
  final bool verifiedOnly;
  final bool onlineOnly;
  
  // Constructeurs, validation, sérialisation...
}
```

#### Section C : Guide d'Intégration Flutter

```dart
class DiscoveryService {
  // Méthodes complètes avec gestion d'erreurs
  Future<DiscoveryFilters> getFilters();
  Future<void> updateFilters(DiscoveryFilters filters);
  Future<List<Profile>> getDiscoveryProfiles({int page = 1});
}
```

### 6.3 Contenu du Fichier 2 (Contrat JSON)

```markdown
# Contrat JSON des Filtres

## Filtre → Requête HTTP

| Clé | Type | Nullable | Plage/Valeurs |
|-----|------|----------|---------------|
| age_min | int | Non | 18-99 |
| age_max | int | Non | 18-99 |
| distance_max_km | int | Non | 5-100 |
| genders | string[] | Non | ["all"] ou valeurs valides |
| relationship_types | string[] | Non | ["all"] ou valeurs valides |
| verified_only | bool | Non | true/false |
| online_only | bool | Non | true/false |

## Valeurs Enum

### Genders
- "male"
- "female"
- "non_binary"
- "trans_male"
- "trans_female"
- "other"
- "prefer_not_to_say"

### Relationship Types
- "friendship"
- "long_term"
- "short_term"
- "casual"

## Réponse Standard

```json
{
  "status": "success|error",
  "message": "string",
  "filters": { ... }
}
```

## Cas Limites

| Cas | Comportement |
|-----|-------------|
| age_min > age_max | Erreur 400 |
| distance_max_km < 5 | Erreur 400 |
| genders = [] | Signifie "tous" |
| relationship_types = [] | Signifie "tous" |
```

---

## ✅ PHASE 7 : CHECKLIST FINALE DE VALIDATION

### 7.1 Validation de l'Implémentation

- [ ] **TOUS les filtres sont implémentés**
  - [ ] Filtre d'âge (min/max)
  - [ ] Filtre de distance
  - [ ] Filtre de genre
  - [ ] Filtre de type de relation
  - [ ] Filtre vérifiés uniquement
  - [ ] Filtre en ligne uniquement

- [ ] **Compatibilité mutuelle vérifiée**
  - [ ] Genre mutuel
  - [ ] Âge mutuel
  - [ ] Distance

- [ ] **Exclusions fonctionnelles**
  - [ ] Bloqués exclus
  - [ ] Déjà vus exclus
  - [ ] Auto-exclusion

### 7.2 Validation des Tests

- [ ] **Tests déterministes créés**
  - [ ] Tests pour chaque filtre
  - [ ] Tests de compatibilité
  - [ ] Tests de combinaisons
  - [ ] Tests des limites

- [ ] **Couverture de code**
  - [ ] ≥ 80% de couverture sur services.py
  - [ ] ≥ 80% de couverture sur views_discovery.py

- [ ] **ZÉRO erreur dans les tests**
  - [ ] Tous les tests passent
  - [ ] Pas de warnings

### 7.3 Validation de la Régression

- [ ] **Tests existants passent toujours**
  - [ ] Tests d'authentification
  - [ ] Tests de likes/dislikes
  - [ ] Tests de matches
  - [ ] Tests de limites quotidiennes

### 7.4 Validation de la Documentation

- [ ] **Fichier 1 : Spécification complète créée**
  - [ ] Tous les endpoints documentés
  - [ ] Tous les modèles Flutter fournis
  - [ ] Exemples de code Dart complets

- [ ] **Fichier 2 : Contrat JSON créé**
  - [ ] Types de données exacts
  - [ ] Valeurs enum listées
  - [ ] Codes d'erreur documentés

---

