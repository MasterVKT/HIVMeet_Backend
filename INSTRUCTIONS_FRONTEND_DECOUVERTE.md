# 📱 INSTRUCTIONS FRONTEND - Problème de découverte vide

**Date** : 29 Décembre 2025  
**Destinataire** : Agent AI Frontend (Flutter)  
**Contexte** : Résolution du problème de page de découverte vide

---

## 🔍 Problème signalé par l'utilisateur

L'utilisateur rapporte que :
1. ❌ La page de découverte (page d'accueil) est vide - aucun profil ne s'affiche
2. ❌ La liste des profils likés est vide
3. ❌ La liste des profils écartés (passés) est vide
4. ❌ Les filtres ne semblent pas fonctionner (aucun effet visible)

---

## ✅ Diagnostic Backend (RÉSOLU)

Le backend a été entièrement diagnostiqué et corrigé :

### Problème #1 : Données historiques manquantes (✅ RÉSOLU)
- **Cause** : Les anciennes interactions (likes/passes) n'étaient pas dans la nouvelle table `InteractionHistory`
- **Solution** : Migration des données effectuée avec succès
- **Résultat** : Les endpoints d'historique retournent maintenant les bonnes données

### Problème #2 : Manque de profils correspondants (⚠️ DONNÉES)
- **Cause** : Pas assez de profils de test correspondant aux critères de l'utilisateur
- **Impact** : La découverte est vide car il n'y a **littéralement aucun profil** correspondant aux filtres
- **Solution backend** : Ajout de profils de test supplémentaires (en cours)

---

## 📊 État des endpoints

| Endpoint | Status | Description |
|----------|--------|-------------|
| `GET /api/v1/discovery/interactions/my-likes` | ✅ OK | Retourne la liste des profils likés |
| `GET /api/v1/discovery/interactions/my-passes` | ✅ OK | Retourne la liste des profils écartés |
| `GET /api/v1/discovery/interactions/stats` | ✅ OK | Retourne les statistiques d'interactions |
| `POST /api/v1/discovery/interactions/<uuid>/revoke` | ✅ OK | Révoque une interaction |
| `GET /api/v1/discovery/profiles` | ✅ OK | Retourne la liste des profils recommandés (peut être vide si aucun profil ne correspond) |

**Tous les endpoints fonctionnent correctement !**

---

## 🎯 Vérifications à effectuer côté Frontend

### 1. Gestion des listes vides

#### Page "Profils likés" (`/api/v1/discovery/interactions/my-likes`)

**Vérifier** :
- ✅ L'endpoint est bien appelé avec le bon token d'authentification
- ✅ La réponse est bien parsée (format pagination : `{count, next, previous, results}`)
- ✅ Un écran vide avec message approprié s'affiche si `results` est vide

**Comportement attendu** :
```dart
// Exemple de réponse
{
  "count": 6,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "...",
      "target_user": {
        "id": "...",
        "display_name": "Lucas",
        "age": 35,
        // ...
      },
      "interaction_type": "like",
      "created_at": "2025-12-28T14:19:55.261049Z",
      "is_revoked": false
    },
    // ... autres profils
  ]
}
```

**Action si vide** :
```dart
if (response.results.isEmpty) {
  // Afficher un message approprié :
  // "Vous n'avez pas encore liké de profils"
  // ou "Vos likes apparaîtront ici"
}
```

#### Page "Profils écartés" (`/api/v1/discovery/interactions/my-passes`)

**Identique à la page "Profils likés"**, avec message adapté :
- "Vous n'avez pas encore écarté de profils"
- "Les profils que vous passez apparaîtront ici"

#### Page de découverte (`/api/v1/discovery/profiles`)

**Vérifier** :
- ✅ L'endpoint est bien appelé avec pagination
- ✅ Les filtres de préférences sont bien synchronisés avec le backend
- ✅ Un message approprié s'affiche si la liste est vide

**Comportement attendu si vide** :

```dart
if (response.results.isEmpty) {
  // Afficher un écran avec icône et message :
  // "Aucun profil ne correspond à vos critères"
  // 
  // Avec suggestions :
  // - "Élargissez vos filtres de découverte"
  // - Bouton vers "Modifier mes préférences"
}
```

---

### 2. Synchronisation des filtres

**IMPORTANT** : Vérifier que les filtres de découverte sont bien envoyés au backend !

#### Filtres supportés par le backend

Le backend applique automatiquement ces filtres basés sur le profil utilisateur :

**Récupérés depuis** : `GET /api/v1/user-profiles/me/`

```json
{
  "profile": {
    "age_min_preference": 30,
    "age_max_preference": 50,
    "distance_max_km": 25,
    "genders_sought": ["male"],
    "relationship_types_sought": ["long_term", "friendship"],
    "verified_only": false,
    "online_only": false
  }
}
```

#### Mise à jour des filtres

**Endpoint** : `PATCH /api/v1/user-profiles/me/`

**Vérifier** :
- ✅ Quand l'utilisateur modifie les filtres dans l'app, un PATCH est bien envoyé
- ✅ Après modification, la page de découverte est rechargée
- ✅ Les valeurs affichées dans l'UI correspondent aux valeurs du backend

**Exemple de PATCH** :
```dart
// Élargir la distance
await api.patch('/api/v1/user-profiles/me/', {
  'distance_max_km': 50,  // Au lieu de 25
});

// Recharger la découverte
await loadDiscoveryProfiles();
```

---

### 3. Bouton de révocation d'interaction

**Endpoint** : `POST /api/v1/discovery/interactions/<uuid>/revoke`

**Vérifier** :
- ✅ Le bouton "Annuler" ou "Révoquer" fonctionne sur les profils likés/passés
- ✅ Après révocation, le profil disparaît de la liste
- ✅ Un message de confirmation s'affiche
- ✅ Le profil réapparaît dans la découverte (si compatible avec les filtres)

**Flow attendu** :

```dart
// Dans la liste des likes
onRevokeLike(interactionId) async {
  final response = await api.post(
    '/api/v1/discovery/interactions/$interactionId/revoke',
  );
  
  if (response.statusCode == 200) {
    // Retirer de la liste locale
    setState(() {
      likes.removeWhere((like) => like.id == interactionId);
    });
    
    // Afficher message
    showSnackBar('Like révoqué. Le profil réapparaîtra dans la découverte.');
  }
}
```

---

### 4. Gestion des erreurs

**Vérifier la gestion de ces cas** :

#### Erreur 401 - Non authentifié
```json
{
  "error": true,
  "message": "Authentication required"
}
```
**Action** : Rediriger vers la page de connexion

#### Erreur 403 - Premium requis (pour likes reçus)
```json
{
  "error": true,
  "message": "Cette fonctionnalité nécessite un abonnement premium"
}
```
**Action** : Afficher popup Premium

#### Erreur 404 - Interaction non trouvée
```json
{
  "error": true,
  "message": "Interaction not found"
}
```
**Action** : Recharger la liste

---

### 5. Pull-to-refresh

**Vérifier** :
- ✅ Le pull-to-refresh fonctionne sur toutes les listes (découverte, likes, passes)
- ✅ Un indicateur de chargement s'affiche
- ✅ Les données sont bien rechargées depuis le backend (pas de cache)

```dart
RefreshIndicator(
  onRefresh: () async {
    await loadDiscoveryProfiles(forceRefresh: true);
  },
  child: DiscoveryList(...),
)
```

---

### 6. Affichage des statistiques

**Endpoint** : `GET /api/v1/discovery/interactions/stats`

**Réponse attendue** :
```json
{
  "total_likes": 6,
  "total_super_likes": 0,
  "total_passes": 4,
  "total_active": 10,
  "total_revoked": 0
}
```

**Vérifier** :
- ✅ Ces stats sont affichées quelque part dans l'app (page profil, page stats, etc.)
- ✅ Les chiffres correspondent aux données réelles
- ✅ Les stats sont mises à jour après chaque action

---

## 🧪 Tests à effectuer

### Test 1 : Navigation vers "Profils passés"

1. Ouvrir l'application
2. Naviguer vers la page "Profils passés" ou "Historique"
3. **Attendu** : Liste de 4 profils (Adrian, Max, Marcus, Marc)
4. Cliquer sur un profil
5. **Attendu** : Affichage des détails du profil

### Test 2 : Navigation vers "Profils likés"

1. Naviguer vers la page "Profils likés" ou "Mes likes"
2. **Attendu** : Liste de 6 profils (Lucas, David, Antoine, Paul, Samuel, Thomas)
3. Vérifier que les photos et infos s'affichent correctement

### Test 3 : Révocation d'un like

1. Dans la liste des profils likés, sélectionner un profil
2. Cliquer sur "Annuler le like" ou "Révoquer"
3. **Attendu** : 
   - Message de confirmation "Like révoqué"
   - Le profil disparaît de la liste
   - La liste des likes passe de 6 à 5

### Test 4 : Modification des filtres

1. Naviguer vers "Paramètres" ou "Filtres de découverte"
2. Modifier un filtre (ex: distance de 25 km → 50 km)
3. Sauvegarder
4. **Attendu** : 
   - Requête PATCH envoyée au backend
   - Page de découverte rechargée
   - Nouveaux profils s'affichent (si disponibles)

### Test 5 : Découverte vide

1. Avec les filtres actuels de Marie (30-50 ans, male, 25 km)
2. Page de découverte
3. **Attendu** : 
   - Écran vide avec message
   - "Aucun profil ne correspond à vos critères"
   - Bouton "Modifier mes filtres"

---

## 🎨 Recommandations UI/UX

### Écran vide - Découverte

```
┌─────────────────────────────────────┐
│                                     │
│           🔍                        │
│                                     │
│   Aucun profil disponible          │
│                                     │
│   Nous n'avons pas trouvé de       │
│   profils correspondant à vos      │
│   critères de recherche.           │
│                                     │
│   ┌─────────────────────────────┐  │
│   │  Modifier mes filtres       │  │
│   └─────────────────────────────┘  │
│                                     │
│   Suggestions :                    │
│   • Élargir la distance             │
│   • Élargir la tranche d'âge       │
│   • Ajouter plus de genres         │
│                                     │
└─────────────────────────────────────┘
```

### Écran vide - Profils likés

```
┌─────────────────────────────────────┐
│                                     │
│           💚                        │
│                                     │
│   Aucun like pour le moment        │
│                                     │
│   Commencez à liker des profils    │
│   pour les retrouver ici !         │
│                                     │
│   ┌─────────────────────────────┐  │
│   │  Découvrir des profils      │  │
│   └─────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

### Écran vide - Profils passés

```
┌─────────────────────────────────────┐
│                                     │
│           ⏭️                         │
│                                     │
│   Aucun profil passé               │
│                                     │
│   Les profils que vous passez      │
│   apparaîtront ici. Vous pourrez   │
│   les réviser plus tard !          │
│                                     │
│   ┌─────────────────────────────┐  │
│   │  Découvrir des profils      │  │
│   └─────────────────────────────┘  │
│                                     │
└─────────────────────────────────────┘
```

---

## 🔧 Code snippets utiles

### Chargement des likes avec gestion d'erreur

```dart
Future<void> loadMyLikes() async {
  try {
    setState(() => isLoading = true);
    
    final response = await api.get(
      '/api/v1/discovery/interactions/my-likes',
      queryParameters: {'page': 1, 'page_size': 20},
    );
    
    if (response.statusCode == 200) {
      final data = response.data;
      setState(() {
        likes = (data['results'] as List)
            .map((json) => InteractionHistory.fromJson(json))
            .toList();
        hasMore = data['next'] != null;
      });
    } else if (response.statusCode == 401) {
      // Non authentifié
      navigateToLogin();
    }
  } catch (e) {
    showError('Impossible de charger vos likes');
  } finally {
    setState(() => isLoading = false);
  }
}
```

### Révocation avec feedback utilisateur

```dart
Future<void> revokeInteraction(String interactionId) async {
  // Demander confirmation
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('Révoquer ce like ?'),
      content: Text('Le profil réapparaîtra dans votre découverte.'),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: Text('Annuler'),
        ),
        TextButton(
          onPressed: () => Navigator.pop(context, true),
          child: Text('Confirmer'),
        ),
      ],
    ),
  );
  
  if (confirmed != true) return;
  
  try {
    final response = await api.post(
      '/api/v1/discovery/interactions/$interactionId/revoke',
    );
    
    if (response.statusCode == 200) {
      setState(() {
        likes.removeWhere((like) => like.id == interactionId);
      });
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Like révoqué avec succès')),
      );
    }
  } catch (e) {
    showError('Erreur lors de la révocation');
  }
}
```

### Mise à jour des filtres

```dart
Future<void> updateDiscoveryFilters({
  int? distanceMaxKm,
  int? ageMin,
  int? ageMax,
  List<String>? gendersSought,
}) async {
  try {
    final updates = {};
    if (distanceMaxKm != null) updates['distance_max_km'] = distanceMaxKm;
    if (ageMin != null) updates['age_min_preference'] = ageMin;
    if (ageMax != null) updates['age_max_preference'] = ageMax;
    if (gendersSought != null) updates['genders_sought'] = gendersSought;
    
    final response = await api.patch(
      '/api/v1/user-profiles/me/',
      data: updates,
    );
    
    if (response.statusCode == 200) {
      // Recharger la découverte
      await loadDiscoveryProfiles(forceRefresh: true);
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Filtres mis à jour')),
      );
    }
  } catch (e) {
    showError('Impossible de mettre à jour les filtres');
  }
}
```

---

## ✅ Checklist de vérification

### Affichage
- [ ] Les listes vides affichent un message approprié
- [ ] Les profils s'affichent correctement dans les listes
- [ ] Les photos se chargent
- [ ] Les informations (âge, bio, etc.) sont visibles

### Navigation
- [ ] Navigation vers "Profils likés" fonctionne
- [ ] Navigation vers "Profils passés" fonctionne
- [ ] Navigation vers "Découverte" fonctionne
- [ ] Retour en arrière fonctionne

### Actions
- [ ] Révocation d'un like fonctionne
- [ ] Révocation d'un pass fonctionne
- [ ] Pull-to-refresh recharge les données
- [ ] Modification des filtres met à jour la découverte

### Gestion d'erreurs
- [ ] Erreur 401 redirige vers login
- [ ] Erreur 403 affiche popup Premium
- [ ] Erreur réseau affiche message approprié
- [ ] Timeout géré correctement

### Performance
- [ ] Pagination fonctionne (chargement page suivante)
- [ ] Les images sont mises en cache
- [ ] Pas de freeze de l'UI pendant les requêtes
- [ ] Pull-to-refresh ne crée pas de doublon

---

## 📊 Résumé

### Côté Backend
✅ **TOUT EST CORRIGÉ**
- Migration des données effectuée
- Endpoints testés et fonctionnels
- Logique de filtrage vérifiée

### Côté Frontend
⚠️ **VÉRIFICATIONS NÉCESSAIRES**
- Affichage des listes vides
- Synchronisation des filtres
- Gestion des erreurs
- UI/UX pour les cas edge

### Données de test
⚠️ **EN COURS**
- Ajout de profils supplémentaires pour avoir des résultats de découverte

---

**Préparé par** : GitHub Copilot (Claude Sonnet 4.5)  
**Date** : 29 Décembre 2025  
**Pour** : Agent AI Frontend Flutter  
**Statut** : ✅ **PRÊT POUR IMPLÉMENTATION**
