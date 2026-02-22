# ⚠️ PROBLÈME BACKEND - Erreur 403 Forbidden

**Date**: 29 Décembre 2025  
**Type**: Backend - Permissions Django  
**Criticité**: ⚠️ BLOQUANT - Empêche l'affichage des likes reçus

---

## 🔴 Symptômes observés

### Frontend
```
Exception CAUGHT BY WIDGETS LIBRARY:
Bad state: GetIt: Object/factory with type Dio is not registered inside GetIt.
```
**Status**: ✅ **CORRIGÉ** - Remplacé `Dio` par `ApiClient`

### Backend (Logs)
```log
WARNING 2025-12-29 12:30:49,504 log 24488 9832 Forbidden: /api/v1/user-profiles/likes-received/
WARNING 2025-12-29 12:30:49,506 basehttp 24488 9832 "GET /api/v1/user-profiles/likes-received/?page=1&page_size=1 HTTP/1.1" 403 132
```

**Status**: ❌ **NÉCESSITE CORRECTION BACKEND**

---

## 🔍 Analyse du problème backend

### Endpoint concerné
```
GET /api/v1/user-profiles/likes-received/
```

### Erreur HTTP
```
403 Forbidden - Accès refusé
```

### Contexte
- L'utilisateur est **authentifié** (token JWT valide)
- L'endpoint `/api/v1/matches/` fonctionne correctement (200 OK)
- Seul l'endpoint `likes-received` retourne 403

---

## 🛠️ Causes possibles

### 1. **Permission Django manquante** (Très probable)
Le ViewSet/View de `likes-received` a probablement une permission trop restrictive.

**Fichiers à vérifier** :
```python
# backend/apps/discovery/views.py ou similaire
class LikesReceivedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # ← Vérifier cette ligne
```

**Causes possibles** :
- Permission `IsAdminUser` au lieu de `IsAuthenticated`
- Permission custom trop restrictive
- Absence de permission (défaut à `AllowAny` puis refusé par middleware)

### 2. **Méthode HTTP non autorisée**
Le ViewSet autorise peut-être seulement POST mais pas GET.

**À vérifier** :
```python
class LikesReceivedViewSet(viewsets.ViewSet):
    http_method_names = ['post']  # ← Si seulement POST, GET sera refusé
```

### 3. **Middleware de sécurité**
Un middleware Django peut bloquer l'accès basé sur :
- Adresse IP
- User agent
- Rate limiting dépassé
- CORS mal configuré

### 4. **Token JWT incomplet**
Le token peut manquer de claims nécessaires pour cet endpoint spécifique.

---

## ✅ Solutions proposées

### Solution 1 : Corriger les permissions Django (RECOMMANDÉE)

**Fichier** : `backend/apps/discovery/views.py` ou équivalent

```python
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

class LikesReceivedViewSet(ModelViewSet):
    """
    API pour récupérer les likes reçus par l'utilisateur connecté
    """
    permission_classes = [IsAuthenticated]  # ✅ Permission correcte
    
    def get_queryset(self):
        # Filtrer uniquement les likes reçus par l'utilisateur connecté
        return Like.objects.filter(target_user=self.request.user)
```

**Changements** :
- ✅ Remplacer `IsAdminUser` par `IsAuthenticated` si nécessaire
- ✅ S'assurer que `permission_classes` est bien défini
- ✅ Filtrer les données par `request.user` pour la sécurité

### Solution 2 : Autoriser la méthode GET

**Si le ViewSet utilise `http_method_names`** :

```python
class LikesReceivedViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'head', 'options']  # ✅ Autoriser GET
```

### Solution 3 : Vérifier les URLs Django

**Fichier** : `backend/apps/discovery/urls.py` ou `backend/config/urls.py`

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LikesReceivedViewSet

router = DefaultRouter()
router.register(r'likes-received', LikesReceivedViewSet, basename='likes-received')

urlpatterns = [
    path('api/v1/user-profiles/', include(router.urls)),
]
```

**Vérifications** :
- ✅ L'URL est bien enregistrée dans le router
- ✅ Le basename est correct
- ✅ Pas de conflit avec d'autres routes

### Solution 4 : Logs de débogage Django

**Activer les logs détaillés** dans `settings.py` :

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

**Puis redémarrer** et observer les logs pour voir :
- Quelle permission échoue
- Quel middleware bloque
- Le traceback complet de l'erreur 403

---

## 🧪 Tests de validation

### Test 1 : Vérifier les permissions

**Backend - Shell Django** :
```bash
python manage.py shell
```

```python
from apps.discovery.views import LikesReceivedViewSet
from apps.accounts.models import User

# Vérifier les permissions configurées
viewset = LikesReceivedViewSet()
print(viewset.permission_classes)  # Devrait afficher [<class 'rest_framework.permissions.IsAuthenticated'>]

# Vérifier qu'un utilisateur peut accéder à ses likes
user = User.objects.first()
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

factory = APIRequestFactory()
request = factory.get('/api/v1/user-profiles/likes-received/')
force_authenticate(request, user=user)

view = LikesReceivedViewSet.as_view({'get': 'list'})
response = view(request)
print(response.status_code)  # Devrait afficher 200
```

### Test 2 : cURL direct

**Depuis le terminal** :
```bash
# Récupérer le token JWT
TOKEN="<votre_token_jwt>"

# Tester l'endpoint
curl -X GET "http://localhost:8000/api/v1/user-profiles/likes-received/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -v
```

**Résultat attendu** :
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [...]
}
```

### Test 3 : Django Admin

1. **Se connecter** à l'admin Django : `http://localhost:8000/admin/`
2. **Aller** dans "Permissions" ou "Groups"
3. **Vérifier** que l'utilisateur de test a les permissions nécessaires

---

## 📋 Checklist de correction

- [ ] **Backend** : Vérifier `permission_classes` dans `LikesReceivedViewSet`
- [ ] **Backend** : S'assurer que `IsAuthenticated` est utilisé (pas `IsAdminUser`)
- [ ] **Backend** : Vérifier que GET est autorisé dans `http_method_names`
- [ ] **Backend** : Confirmer que l'URL est bien enregistrée dans les URLs
- [ ] **Backend** : Ajouter des logs pour identifier la cause exacte du 403
- [ ] **Backend** : Tester l'endpoint avec cURL + token JWT
- [ ] **Backend** : Vérifier les middlewares de sécurité (CORS, rate limiting)
- [ ] **Frontend** : Tester après correction backend

---

## 🔧 Correction frontend déjà appliquée

### Problème résolu : Dio non enregistré dans GetIt

**Erreur** :
```
Bad state: GetIt: Object/factory with type Dio is not registered inside GetIt.
```

**Solution appliquée** :
1. ✅ Remplacé `Dio` par `ApiClient` dans `InteractionHistoryRepositoryImpl`
2. ✅ Modifié `injection.dart` : `InteractionHistoryRepositoryImpl(getIt<ApiClient>())`
3. ✅ Supprimé toutes les références à `DioException` (géré par ApiClient)
4. ✅ Supprimé l'import `import 'package:dio/dio.dart';` inutilisé

**Fichiers modifiés** :
- [`lib/data/repositories/interaction_history_repository_impl.dart`](d:\Projets\HIVMeet\hivmeet\lib\data\repositories\interaction_history_repository_impl.dart)
- [`lib/injection.dart`](d:\Projets\HIVMeet\hivmeet\lib\injection.dart)

---

## 📊 Impact utilisateur

### Avant correction
- ❌ Crash de l'application en allant dans "Profils passés"
- ❌ Erreur GetIt visible à l'utilisateur
- ❌ Impossible d'utiliser la fonctionnalité

### Après correction frontend
- ✅ Plus de crash GetIt
- ⚠️ Toujours bloqué par 403 backend (likes-received)
- ⏳ En attente de correction backend

### Après correction complète (frontend + backend)
- ✅ Navigation fluide vers "Profils passés"
- ✅ Affichage des likes/passes depuis l'API réelle
- ✅ Fonctionnalité d'annulation de pass opérationnelle
- ✅ Réapparition des profils révoqués dans Discovery

---

## 📞 Prochaines étapes

### Immédiat
1. **Backend** : Appliquer la Solution 1 (corriger les permissions)
2. **Backend** : Redémarrer le serveur Django
3. **Frontend** : Relancer l'application et tester

### Court terme
- Ajouter des tests unitaires pour l'endpoint `likes-received`
- Documenter les permissions requises pour chaque endpoint
- Créer un script de vérification des permissions

### Long terme
- Standardiser les permissions sur tous les endpoints
- Ajouter un système de monitoring des erreurs 403
- Créer un middleware de logging des refus d'accès

---

## 📝 Notes techniques

### Structure attendue de la réponse API

**Endpoint** : `GET /api/v1/user-profiles/likes-received/`

**Réponse attendue** :
```json
{
  "count": 10,
  "next": "http://localhost:8000/api/v1/user-profiles/likes-received/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid-123",
      "user_id": "uuid-user",
      "username": "john_doe",
      "profile_photo": "https://example.com/photo.jpg",
      "age": 28,
      "city": "Paris",
      "liked_at": "2025-12-29T12:00:00Z"
    }
  ]
}
```

### Mapping frontend existant

Le frontend attend cette structure et la mappe via `InteractionHistoryRepositoryImpl` :
- `username` → `displayName`
- `profile_photo` → `mainPhotoUrl`
- `user_id` → `id`

---

## ✅ Statut final

| Composant | Statut | Action requise |
|-----------|--------|----------------|
| **Frontend GetIt** | ✅ Corrigé | Aucune |
| **Frontend Repository** | ✅ Corrigé | Aucune |
| **Backend 403** | ❌ À corriger | Modifier permissions Django |
| **Tests** | ⏳ En attente | Tester après correction backend |

---

**Créé par** : GitHub Copilot  
**Référence** : Issue de navigation "Profils passés" - 29/12/2025  
**Priorité** : 🔴 HAUTE - Bloque une fonctionnalité majeure
