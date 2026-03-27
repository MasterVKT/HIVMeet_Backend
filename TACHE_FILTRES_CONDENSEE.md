# 📋 TÂCHE KANBAN : Filtres de Découverte (Version Condensée)

## 🎯 Objectif
Audit + Tests + Documentation Frontend des filtres de découverte backend.

## 🔍 Checklist Fonctionnalités à Vérifier

### Filtres Principaux
- [ ] **Filtre d'Âge** (`age_min`, `age_max`)
- [ ] **Filtre de Distance** (`distance_max_km`)
- [ ] **Filtre de Genre** (`genders`)
- [ ] **Filtre Type Relation** (`relationship_types`)
- [ ] **Filtre Vérifiés** (`verified_only`)
- [ ] **Filtre En Ligne** (`online_only`)

### Compatibilité Mutuelle
- [ ] **Genre Mutuel** : A voit B si B cherche le genre de A
- [ ] **Âge Mutuel** : Vérification croisée des préférences d'âge

### Exclusions
- [ ] Bloqués exclus
- [ ] Déjà vus (likes/dislikes) exclus
- [ ] Auto-exclusion (soi-même)

### Limites Quotidiennes
- [ ] Compteur likes (10/jour gratuit, illimité premium)
- [ ] Compteur super likes (1/jour gratuit, 5/jour premium)
- [ ] Reset à minuit UTC

## 📁 Fichiers à Examiner

```
matching/
├── views_discovery.py      # Endpoints HTTP
├── services.py             # RecommendationService
├── daily_likes_service.py  # Limites quotidiennes
├── serializers.py          # Validation filtres
└── models.py               # Like, Match, etc.

profiles/
├── models.py               # Profile avec préférences
└── serializers.py          # SearchFilterSerializer
```

## 🧪 Tests Déterministes (Structure)

```python
# Principe : GIVEN/WHEN/THEN
class TestAgeFilter:
    def test_age_filter_returns_only_profiles_in_range(self):
        """A(25-35) → Voir seulement profils âge 25-35"""
        
class TestMutualGender:
    def test_male_sees_female_who_seeks_male(self):
        """Homme A voit Femme B qui cherche les hommes"""
        
class TestCombinations:
    def test_multiple_filters(self):
        """Âge + Genre + Distance + Vérifié = Tous vrais"""
```

## 📚 Documentation à Générer

1. `FILTER_BACKEND_SPECIFICATION_FRONTEND.md` - Specification complète
2. `FILTER_BACKEND_CONTRACT_FRONTEND.md` - Contrat JSON par endpoint

## ✅ Résultat Attendu

- Backend 100% opérationnel
- Tests déterministes ≥80% couverture
- ZÉRO régression
- Documentation Frontend complète

## 🚀 Instructions

**Lancer directement en ACT MODE** avec cette version condenseée.
