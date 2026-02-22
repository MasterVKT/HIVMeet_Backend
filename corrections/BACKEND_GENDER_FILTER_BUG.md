# 🔴 PROBLÈME BACKEND : Discovery Page Vide

## 📊 Symptôme

La page Découverte retourne **0 profils** même si des profils compatibles existent dans la BD.

**Frontend logs :**
```
I/flutter: 🔄 DEBUG MatchRepositoryImpl: Payload complet: {count: 0, next: null, previous: null, results: []}
I/flutter: 📊 Count backend: 0
```

**Logs Backend :**
```
After user's gender filter (seeking ['male']): 6 profiles
After mutual gender compatibility (target seeks female): 0 profiles ← ❌ TOUS LES PROFILS FILTRÉS!
```

---

## 🔍 Cause Racine

**Les profils males n'ont PAS le filtre de compatibilité de genre !**

Chaque profil male devrait avoir :
```json
{
  "user_id": "clement.fernandez",
  "gender": "male",
  "gender_sought": "female",  ← ❌ MANQUANT POUR TOUS LES PROFILS MALES
  "relationship_types_sought": ["long_term", "friendship", "casual"]
}
```

Mais actuellement, ils ont seulement `relationship_types_sought` sans `gender_sought`.

**Résultat :** Marie cherche des hommes → 6 trouvés ✅ → Mais aucun ne cherche les femmes ❌ → 0 compatibles

---

## 🛠️ CORRECTION REQUISE (Backend)

### Option 1 : Ajouter directement le filtre aux profils males existants

**SQL :**
```sql
UPDATE profiles_profile 
SET gender_sought = 'female'  -- Ou JSON field si appropriate
WHERE gender = 'male' AND gender_sought IS NULL;
```

### Option 2 : Modifier le script de création des profils

**Fichier :** `create_male_profiles.py` (ou équivalent)

**Avant :**
```python
profile_data = {
    'gender': 'male',
    'relationship_types_sought': ['long_term', 'friendship', 'casual'],
    # ❌ gender_sought manquant!
}
```

**Après :**
```python
profile_data = {
    'gender': 'male',
    'gender_sought': 'female',  # ✅ AJOUTÉ
    'relationship_types_sought': ['long_term', 'friendship', 'casual'],
}
```

### Option 3 : Corriger le filtrage backend

**Fichier :** `services/discovery.py` ou équivalent

**Le problème :** Le backend filtre `gender_sought` mais certains profils l'ont NULL.

**Solution :**
```python
def get_recommendations(user_id, limit=20):
    # Avant: Filtre strict qui exclut les profils sans gender_sought
    # Après: Assuming default compatibility si gender_sought is null/empty
    
    profiles = profiles.filter(
        Q(gender_sought__isnull=True) | Q(gender_sought='female')  # Default à female si null
    )
```

---

## ✅ TEST REQUIS

Une fois la correction appliquée, tester :

```bash
# 1. Vérifier que les profils ont le filtre
SELECT user_id, gender, gender_sought FROM profiles_profile WHERE gender='male' LIMIT 5;

# 2. Relancer l'app et vérifier les logs
# Attendu:
# After mutual gender compatibility (target seeks female): 6 profiles ✅ (au lieu de 0)
```

---

## 📝 Détails Techniques

### Logique du Filtrage

Le backend applique **2 filtres de compatibilité de genre** :

1. **User → Target :** Marie cherche `['male']` → 6 profils males trouvés ✅
2. **Target → User :** Chaque male doit chercher `['female']` → ❌ Aucun n'a ce filtre

**Résultat :** 0 profils compatibles

### Données Actuelles

```json
{
  "user_id": "clement.fernandez",
  "gender": "male",
  "relationship_types_sought": ["long_term", "friendship", "casual"],
  // ❌ gender_sought: NULL ou manquant
}
```

### Données Attendues

```json
{
  "user_id": "clement.fernandez",
  "gender": "male",
  "gender_sought": "female",  // ✅ REQUIS
  "relationship_types_sought": ["long_term", "friendship", "casual"]
}
```

---

## 🎯 Action Requise

**URGENT** - Appliquer une des 3 corrections ci-dessus pour que la page Découverte retourne des profils.

**Responsable :** Équipe Backend  
**Impact :** Découverte page inutilisable tant que ce problème persiste

---

## 📋 Logs Complets de Diagnostic

```
INFO 2026-01-19 15:23:45,769 services get_recommendations - User: marie.claire@test.com
INFO 2026-01-19 15:23:45,785 services 🚫 Excluding 27 profiles:
INFO 2026-01-19 15:23:45,785 services    - Active interactions (is_revoked=False): 16
INFO 2026-01-19 15:23:45,785 services    - Legacy likes: 13
INFO 2026-01-19 15:23:45,785 services    - Legacy dislikes: 13

INFO 2026-01-19 15:23:45,792 services 📊 After base filters: 20 profiles
INFO 2026-01-19 15:23:45,795 services    After user's age filter (30-50): 16 profiles
INFO 2026-01-19 15:23:45,800 services    After user's gender filter (seeking ['male']): 6 profiles ✅
INFO 2026-01-19 15:23:45,805 services    After mutual gender compatibility (target seeks female): 0 profiles ❌ PROBLÈME!
INFO 2026-01-19 15:23:45,809 services    After relationship type filter: 0 profiles
INFO 2026-01-19 15:23:45,825 services 📊 Total profiles after all filters: 0
```

---

**Status :** 🔴 BLOQUANT - Discovery Page inutilisable  
**Date :** 19 janvier 2026
