# 🎯 IMPLÉMENTATION DES FILTRES DE DÉCOUVERTE - BACKEND

## 📋 RÉSUMÉ DU PROBLÈME

**Situation actuelle** : Le frontend envoie bien les filtres de recherche au backend via `PUT /api/v1/discovery/filters`, mais ces filtres ne sont **PAS appliqués** lors de la récupération des profils via `GET /api/v1/discovery/profiles`. 

**Résultat** : L'utilisateur modifie ses filtres (âge, distance, genre, etc.), mais continue de voir **TOUS** les profils sans aucun filtrage.

## ✅ SOLUTION À IMPLÉMENTER (Option A)

**Le backend doit appliquer automatiquement les filtres sauvegardés de l'utilisateur lors de chaque requête de profils de découverte.**

---

## 🔧 MODIFICATIONS REQUISES

### 1️⃣ Endpoint : `PUT /api/v1/discovery/filters`

#### 📍 Statut actuel
- ✅ Reçoit les filtres du frontend
- ❌ Les sauvegarde probablement mais ne les utilise pas ensuite

#### 🎯 Ce qui doit être fait

**Sauvegarder les préférences de filtrage pour l'utilisateur connecté** dans la base de données.

**Structure des données reçues** (corps de la requête) :
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

**Actions à effectuer** :
1. Valider les données reçues
2. Sauvegarder dans le modèle utilisateur (ex: `UserProfile.search_preferences`)
3. Retourner une confirmation de succès

**Exemple de réponse attendue** :
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

---

### 2️⃣ Endpoint : `GET /api/v1/discovery/profiles`

#### 📍 Statut actuel
- ✅ Retourne une liste de profils
- ❌ **Ne tient PAS compte des filtres sauvegardés**
- Reçoit uniquement : `page` et `page_size`

#### 🎯 Ce qui doit être fait

**Appliquer AUTOMATIQUEMENT les filtres sauvegardés de l'utilisateur** lors de la récupération des profils.

**Paramètres de requête reçus** :
```
GET /api/v1/discovery/profiles?page=1&page_size=20
```

**Logique de filtrage à implémenter** :

```python
def get_discovery_profiles(request):
    user = request.user
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    
    # 1. Récupérer les filtres sauvegardés de l'utilisateur
    filters = user.profile.search_preferences  # ou équivalent selon votre modèle
    
    # 2. Construire la requête de base
    profiles_query = UserProfile.objects.exclude(user=user)  # Exclure l'utilisateur lui-même
    
    # 3. APPLIQUER LES FILTRES
    
    # Filtre d'âge
    if filters.get('age_min'):
        profiles_query = profiles_query.filter(age__gte=filters['age_min'])
    if filters.get('age_max'):
        profiles_query = profiles_query.filter(age__lte=filters['age_max'])
    
    # Filtre de distance (nécessite calcul géographique)
    if filters.get('distance_max_km'):
        # Utiliser une fonction de distance géographique
        # Exemple avec PostGIS ou équivalent
        user_location = user.profile.location
        max_distance = filters['distance_max_km'] * 1000  # convertir en mètres
        profiles_query = profiles_query.filter(
            location__distance_lte=(user_location, max_distance)
        )
    
    # Filtre de genre
    if filters.get('genders') and 'all' not in filters['genders']:
        profiles_query = profiles_query.filter(gender__in=filters['genders'])
    
    # Filtre de type de relation
    if filters.get('relationship_types') and 'all' not in filters['relationship_types']:
        profiles_query = profiles_query.filter(
            relationship_type__in=filters['relationship_types']
        )
    
    # Filtre : profils vérifiés uniquement
    if filters.get('verified_only', False):
        profiles_query = profiles_query.filter(is_verified=True)
    
    # Filtre : en ligne uniquement
    if filters.get('online_only', False):
        # Considérer "en ligne" si dernière activité < 5 minutes
        from django.utils import timezone
        from datetime import timedelta
        cutoff_time = timezone.now() - timedelta(minutes=5)
        profiles_query = profiles_query.filter(last_seen__gte=cutoff_time)
    
    # 4. Exclure les profils déjà vus/likés/dislikés
    # (selon votre logique métier)
    already_interacted = Interaction.objects.filter(
        user=user
    ).values_list('target_user_id', flat=True)
    profiles_query = profiles_query.exclude(user__id__in=already_interacted)
    
    # 5. Appliquer la pagination
    from django.core.paginator import Paginator
    paginator = Paginator(profiles_query, page_size)
    profiles_page = paginator.get_page(page)
    
    # 6. Sérialiser et retourner
    serialized_profiles = [serialize_profile(p) for p in profiles_page]
    
    return JsonResponse({
        'results': serialized_profiles,
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'total_pages': paginator.num_pages
    })
```

---

## 📊 STRUCTURE DU MODÈLE DE DONNÉES

### Modèle `UserProfile` ou équivalent

Assurez-vous d'avoir un champ pour stocker les préférences de recherche :

```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # ... autres champs (nom, bio, photos, etc.)
    
    # Préférences de recherche (peut être un JSONField)
    search_preferences = models.JSONField(default=dict, blank=True)
    # Structure attendue :
    # {
    #     "age_min": 18,
    #     "age_max": 65,
    #     "distance_max_km": 50,
    #     "genders": ["all"],
    #     "relationship_types": ["all"],
    #     "verified_only": False,
    #     "online_only": False
    # }
    
    # Champs nécessaires pour le filtrage
    age = models.IntegerField()
    gender = models.CharField(max_length=20)  # "male", "female", "non-binary", etc.
    relationship_type = models.CharField(max_length=20)  # "serious", "casual", etc.
    is_verified = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    location = models.PointField(geography=True, null=True)  # Pour calcul de distance
```

---

## 🧪 TESTS À EFFECTUER

### Test 1 : Sauvegarde des filtres
```bash
curl -X PUT http://localhost:8000/api/v1/discovery/filters \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
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

**Résultat attendu** : Statut 200, confirmation de sauvegarde

### Test 2 : Récupération de profils filtrés
```bash
curl -X GET "http://localhost:8000/api/v1/discovery/profiles?page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

**Résultat attendu** :
- Tous les profils retournés doivent avoir entre 25 et 35 ans
- Tous les profils doivent être des femmes
- Tous les profils doivent être vérifiés
- Tous les profils doivent être dans un rayon de 30 km
- Aucun profil avec qui l'utilisateur a déjà interagi

### Test 3 : Modification des filtres et rechargement
```bash
# Modifier les filtres
curl -X PUT http://localhost:8000/api/v1/discovery/filters \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "age_min": 18,
    "age_max": 99,
    "distance_max_km": 100,
    "genders": ["all"],
    "relationship_types": ["all"],
    "verified_only": false,
    "online_only": false
  }'

# Recharger les profils
curl -X GET "http://localhost:8000/api/v1/discovery/profiles?page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

**Résultat attendu** : Beaucoup plus de profils retournés (filtres très larges)

---

## 🔍 LOGS ET DEBUGGING

### Côté Backend - Logs recommandés

Ajoutez des logs pour faciliter le debugging :

```python
import logging
logger = logging.getLogger(__name__)

def get_discovery_profiles(request):
    user = request.user
    filters = user.profile.search_preferences
    
    logger.info(f"[DISCOVERY] User {user.id} requesting profiles")
    logger.info(f"[DISCOVERY] Filters applied: {filters}")
    
    # ... logique de filtrage ...
    
    logger.info(f"[DISCOVERY] Found {profiles_query.count()} profiles matching filters")
    logger.info(f"[DISCOVERY] Returning page {page} with {len(serialized_profiles)} profiles")
```

### Côté Frontend - Logs existants

Le frontend émet déjà des logs détaillés :

```
🔄 DEBUG MatchRepositoryImpl: Mise à jour des filtres de recherche
   - Âge: 25 - 40
   - Distance max: 50 km
   - Genres: [female, non-binary]
   - Types de relation: [serious]
   - Vérifiés uniquement: false
   - En ligne uniquement: false
✅ DEBUG MatchRepositoryImpl: Filtres mis à jour avec succès
   ⚠️  Le backend doit maintenant appliquer ces filtres automatiquement

🔄 DEBUG DiscoveryBloc: Filtres mis à jour, rechargement des profils...
🔄 DEBUG MatchRepositoryImpl: getDiscoveryProfiles - limit: 5
   ℹ️  Les filtres sauvegardés doivent être appliqués automatiquement par le backend
```

---

## ⚡ OPTIMISATIONS RECOMMANDÉES

### 1. Indexation de la base de données
```sql
CREATE INDEX idx_userprofile_age ON userprofile(age);
CREATE INDEX idx_userprofile_gender ON userprofile(gender);
CREATE INDEX idx_userprofile_is_verified ON userprofile(is_verified);
CREATE INDEX idx_userprofile_last_seen ON userprofile(last_seen);
CREATE INDEX idx_userprofile_location ON userprofile USING GIST(location);
```

### 2. Cache des filtres utilisateur
```python
from django.core.cache import cache

def get_user_filters(user_id):
    cache_key = f'user_filters_{user_id}'
    filters = cache.get(cache_key)
    
    if filters is None:
        user_profile = UserProfile.objects.get(user_id=user_id)
        filters = user_profile.search_preferences
        cache.set(cache_key, filters, timeout=3600)  # 1 heure
    
    return filters

def update_user_filters(user_id, filters):
    # Sauvegarder en DB
    user_profile = UserProfile.objects.get(user_id=user_id)
    user_profile.search_preferences = filters
    user_profile.save()
    
    # Invalider le cache
    cache_key = f'user_filters_{user_id}'
    cache.delete(cache_key)
```

### 3. Calcul de distance efficace (PostGIS)
```python
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

def filter_by_distance(profiles_query, user_location, max_distance_km):
    return profiles_query.annotate(
        distance=Distance('location', user_location)
    ).filter(
        distance__lte=D(km=max_distance_km)
    ).order_by('distance')
```

---

## 📝 VALEURS PAR DÉFAUT

Si un utilisateur n'a pas encore défini de filtres, utiliser ces valeurs par défaut :

```python
DEFAULT_FILTERS = {
    'age_min': 18,
    'age_max': 99,
    'distance_max_km': 50,
    'genders': ['all'],
    'relationship_types': ['all'],
    'verified_only': False,
    'online_only': False
}
```

---

## 🎯 CHECKLIST D'IMPLÉMENTATION

- [ ] Créer/Modifier le modèle pour stocker `search_preferences`
- [ ] Implémenter `PUT /api/v1/discovery/filters` pour sauvegarder les filtres
- [ ] Modifier `GET /api/v1/discovery/profiles` pour appliquer les filtres automatiquement
- [ ] Implémenter le filtre d'âge (age_min, age_max)
- [ ] Implémenter le filtre de distance (distance_max_km)
- [ ] Implémenter le filtre de genre (genders)
- [ ] Implémenter le filtre de type de relation (relationship_types)
- [ ] Implémenter le filtre "vérifiés uniquement" (verified_only)
- [ ] Implémenter le filtre "en ligne uniquement" (online_only)
- [ ] Exclure les profils avec lesquels l'utilisateur a déjà interagi
- [ ] Ajouter des logs de debugging
- [ ] Créer des index sur les colonnes filtrées
- [ ] Tester tous les scénarios (voir section Tests)
- [ ] Vérifier les performances avec un grand nombre de profils

---

## 🚨 POINTS D'ATTENTION

1. **Calcul de distance** : Nécessite PostGIS ou une solution équivalente pour les calculs géographiques efficaces

2. **Performances** : Avec plusieurs filtres combinés, optimiser les requêtes (indexation, explain analyze)

3. **Profils épuisés** : Si les filtres sont trop restrictifs, l'utilisateur peut ne plus voir de profils. Gérer ce cas :
   ```json
   {
     "results": [],
     "count": 0,
     "message": "Aucun profil ne correspond à vos critères. Essayez d'élargir vos filtres."
   }
   ```

4. **Cohérence des données** : S'assurer que tous les profils ont les champs nécessaires (âge, genre, location, etc.)

5. **Valeur "all"** : Quand `genders: ["all"]` ou `relationship_types: ["all"]`, ne PAS appliquer ce filtre

---

## 📞 QUESTIONS / CLARIFICATIONS NÉCESSAIRES

Si vous avez besoin de clarifications sur :
- La structure exacte de votre modèle de données
- Les endpoints existants
- La gestion de la géolocalisation
- Les interactions déjà enregistrées (likes, dislikes)

N'hésitez pas à adapter ce document selon votre architecture spécifique.

---

## ✅ VALIDATION

Une fois l'implémentation terminée, vous devriez pouvoir :

1. ✅ Modifier les filtres dans l'app mobile
2. ✅ Voir immédiatement les profils filtrés correspondants
3. ✅ Constater que les profils affichés respectent TOUS les critères choisis
4. ✅ Élargir les filtres et voir plus de profils
5. ✅ Restreindre les filtres et voir moins de profils

---

**Date de création** : 29 décembre 2025  
**Version Frontend** : Prête et testée  
**Version Backend** : À implémenter selon ce document
