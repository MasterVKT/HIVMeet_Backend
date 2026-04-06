# PHASE 1 - Audit Filtres Discovery

**Tâche Kanban**: `acc33` | **Fichier ref**: `TACHE_KANBAN_FILTRES_DECOUVERTE.md`

## OBJECTIF
Auditer les 15 filtres de découverte côté backend.

## 15 FONCTIONNALITÉS À VÉRIFIER

| # | Filtre | Description | Fichier à vérifier |
|---|--------|-------------|-------------------|
| 1 | Age | age_min/age_max (18-99) | services.py |
| 2 | Distance | distance_max_km (5-100) | services.py |
| 3 | Genre | genders (male/female/etc.) | services.py |
| 4 | Relation | relationship_types | services.py |
| 5 | Verified | verified_only | services.py |
| 6 | Online | online_only | services.py |
| 7 | Compat.Genre | A voit B si B cherche genre A | services.py |
| 8 | Compat.Age | Préférences age mutuelles | services.py |
| 9 | Likes/Jour | 10 gratuit, illimité premium | daily_likes_service.py |
| 10 | Super Likes | 1 gratuit, 5 premium | daily_likes_service.py |
| 11 | Reset UTC | Minuit chaque jour | daily_likes_service.py |
| 12 | Excl.Bloqués | Profiles bloqués exclus | services.py |
| 13 | Excl.Vus | Already liked/disliked | interaction_service.py |
| 14 | Excl.AutoBloc | Si l'autre a bloqué | services.py |
| 15 | Excl.Propre | Ne pas se montrer | services.py |

## FICHIERS À EXAMINER
- `matching/services.py` - RecommendationService.get_recommendations()
- `matching/views_discovery.py` - Endpoints HTTP
- `matching/serializers.py` - SearchFilterSerializer validation
- `matching/daily_likes_service.py` - Limites quotidiennes
- `matching/interaction_service.py` - Historique interactions
- `matching/models.py` - Like, Match, InteractionHistory
- `profiles/models.py` - Profile avec champs filtres
- `profiles/serializers.py` - Validation préférences

## RÈGLES COMPATIBILITÉ MUTUELLE

```
Genre: A voit B si (B.genders_sought contient A.gender) OU (B.genders_sought = [])
Age: A voit B si (B.age_min <= A.age <= B.age_max) ET (A.age_min <= B.age <= A.age_max)
Dist: A voit B si distance(A,B) <= A.distance_max_km
Rel:  A voit B si intersection(A.types, B.types) OU [] dans l'un
```

## FORMAT ATTENDU
```json
{"age_min":25,"age_max":40,"distance_max_km":50,"genders":["female"],"relationship_types":["long_term"],"verified_only":false,"online_only":false}
```

## LIVRABLES
1. Rapport: ✅OK / ⚠️Defectueux / ❌Manquant par filtre
2. Pour chaque problème: description + cause + correction
3. Liste priorisée corrections Phase 2