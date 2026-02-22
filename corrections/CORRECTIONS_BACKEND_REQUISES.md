# Corrections Backend Requises

**Date:** 25 décembre 2025  
**Analysé par:** GitHub Copilot  
**Frontend Version:** Flutter/Dart

## 📋 Résumé Exécutif

Lors de l'analyse des logs backend et du code frontend, nous avons identifié plusieurs problèmes qui nécessitent des corrections côté backend Django pour assurer le bon fonctionnement de l'application HIVMeet.

## 🔴 Problèmes Critiques Identifiés

### 1. Problème d'Authentification sur l'Endpoint de Découverte

**Logs Backend:**
```
ERROR 2025-12-25 12:24:13,625 utils 3584 1772 API Error: NotAuthenticated - Informations d'authentification non fournies. - Path: /api/v1/discovery/ - Method: GET
WARNING 2025-12-25 12:24:13,626 log 3584 1772 Unauthorized: /api/v1/discovery/
WARNING 2025-12-25 12:24:13,626 basehttp 3584 1772 "GET /api/v1/discovery/ HTTP/1.1" 401 192
```

**Description:**
L'endpoint `/api/v1/discovery/` retourne une erreur 401 (Unauthorized) même après une authentification réussie via Firebase. Le frontend a réussi à obtenir les tokens JWT (`POST /api/v1/auth/firebase-exchange/` retourne 200), mais l'appel à l'endpoint de découverte échoue immédiatement après.

**Impact:**
- Les utilisateurs ne peuvent pas accéder à la page de découverte
- L'application affiche une page blanche ou une erreur
- Fonctionnalité principale de l'application non utilisable

**Solutions Proposées:**

#### Option 1: Vérifier les Permissions de l'Endpoint
```python
# Dans views.py ou le fichier approprié
from rest_framework.permissions import IsAuthenticated

class DiscoveryProfilesView(APIView):
    permission_classes = [IsAuthenticated]  # Vérifier que cette classe est correcte
    
    def get(self, request):
        # Vérifier que request.user est bien authentifié
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"error": "Non authentifié"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        # Suite du code...
```

#### Option 2: Vérifier le Middleware d'Authentification JWT
```python
# Dans settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # S'assurer que cette ligne est présente et active
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

#### Option 3: Déboguer l'Authentification
Ajouter des logs pour comprendre pourquoi l'authentification échoue :
```python
import logging
logger = logging.getLogger(__name__)

class DiscoveryProfilesView(APIView):
    def get(self, request):
        logger.info(f"🔍 Request user: {request.user}")
        logger.info(f"🔍 Is authenticated: {request.user.is_authenticated}")
        logger.info(f"🔍 Auth header: {request.META.get('HTTP_AUTHORIZATION')}")
        
        if not request.user.is_authenticated:
            logger.error("❌ Utilisateur non authentifié")
            return Response(
                {"error": "Non authentifié"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        # Suite du code...
```

**Tests à Effectuer:**
1. Vérifier que l'endpoint `/api/v1/auth/firebase-exchange/` génère bien des tokens JWT valides
2. Tester l'endpoint `/api/v1/discovery/profiles` avec un token JWT valide en utilisant Postman ou curl
3. Vérifier les logs pour voir si le token est correctement reçu et décodé

```bash
# Test avec curl
curl -H "Authorization: Bearer <TOKEN_JWT>" http://localhost:8000/api/v1/discovery/profiles?page=1&page_size=5
```

---

### 2. Endpoint Inconnu: `/api/v1/discovery/` vs `/api/v1/discovery/profiles`

**Logs Backend:**
```
WARNING 2025-12-25 12:24:25,284 log 3584 7124 Not Found: /api/v1/api/v1/discovery/profiles
```

**Description:**
Le log montre une erreur 404 pour `/api/v1/discovery/profiles`. Cela suggère que soit :
- L'endpoint n'existe pas dans les URLs Django
- Le routage est mal configuré
- L'endpoint attendu est différent

**Note:** Le problème de double `/api/v1/` a été corrigé côté frontend.

**Solutions Proposées:**

#### Vérifier la Configuration des URLs
```python
# Dans urls.py
from django.urls import path
from . import views

urlpatterns = [
    # S'assurer que cet endpoint existe
    path('api/v1/discovery/profiles', views.DiscoveryProfilesView.as_view(), name='discovery-profiles'),
    # OU
    path('api/v1/discovery/', views.DiscoveryView.as_view(), name='discovery'),
]
```

#### Standardiser les Endpoints
Selon la documentation API, l'endpoint devrait être `/api/v1/discovery/profiles`. Vérifier que :
- L'URL est correctement déclarée dans `urls.py`
- Le view associé existe et fonctionne
- Les paramètres de requête (`page`, `page_size`) sont bien gérés

**Tests à Effectuer:**
```bash
# Tester l'endpoint avec authentification
curl -H "Authorization: Bearer <TOKEN_JWT>" \
     "http://localhost:8000/api/v1/discovery/profiles?page=1&page_size=5"
```

---

### 3. Endpoint Conversations Non Trouvé

**Logs Backend:**
```
WARNING 2025-12-25 12:24:50,011 log 3584 10948 Not Found: /api/v1/api/v1/conversations/
WARNING 2025-12-25 12:24:50,012 basehttp 3584 10948 "GET /api/v1/api/v1/conversations/?page=1&page_size=20&status=all HTTP/1.1" 404 5318
```

**Description:**
Similaire au problème précédent, l'endpoint `/api/v1/conversations/` retourne une erreur 404.

**Note:** Le problème de double `/api/v1/` a été corrigé côté frontend.

**Solutions Proposées:**

#### Vérifier l'Existence de l'Endpoint
```python
# Dans urls.py
urlpatterns = [
    path('api/v1/conversations/', views.ConversationsListView.as_view(), name='conversations-list'),
    # Vérifier aussi les endpoints de messages
    path('api/v1/conversations/<uuid:conversation_id>/messages/', 
         views.MessagesListView.as_view(), 
         name='conversation-messages'),
]
```

#### Vérifier les Permissions
```python
class ConversationsListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        status = request.query_params.get('status', 'all')
        
        # Récupérer les conversations de l'utilisateur
        conversations = Conversation.objects.filter(
            participants=request.user
        )
        
        # Filtrer selon le statut
        if status == 'unread':
            conversations = conversations.filter(unread_count__gt=0)
        elif status == 'archived':
            conversations = conversations.filter(is_archived=True)
        
        # Pagination
        paginator = Paginator(conversations, page_size)
        conversations_page = paginator.get_page(page)
        
        serializer = ConversationSerializer(conversations_page, many=True)
        return Response({
            'results': serializer.data,
            'count': paginator.count,
            'next': conversations_page.has_next(),
            'previous': conversations_page.has_previous()
        })
```

**Tests à Effectuer:**
```bash
# Tester l'endpoint conversations
curl -H "Authorization: Bearer <TOKEN_JWT>" \
     "http://localhost:8000/api/v1/conversations/?page=1&page_size=20&status=all"
```

---

## ⚠️ Problèmes Secondaires

### 4. Warning: pkg_resources Deprecated

**Logs Backend:**
```
D:\Projets\HIVMeet\env\Lib\site-packages\rest_framework_simplejwt\__init__.py:1: UserWarning: pkg_resources is deprecated as an API
```

**Description:**
La bibliothèque `rest_framework_simplejwt` utilise une API dépréciée (`pkg_resources`) qui sera supprimée dans Setuptools<81.

**Impact:**
- Aucun impact fonctionnel immédiat
- Préparer la migration pour éviter des problèmes futurs

**Solution:**
Mettre à jour `rest_framework_simplejwt` vers la dernière version qui n'utilise plus `pkg_resources` :
```bash
pip install --upgrade djangorestframework-simplejwt
```

---

## 📝 Actions Recommandées

### Priorité HAUTE (À faire immédiatement)

1. **Déboguer l'authentification sur `/api/v1/discovery/profiles`**
   - Ajouter des logs détaillés
   - Vérifier que les tokens JWT sont correctement validés
   - Tester avec Postman pour isoler le problème

2. **Vérifier l'existence des endpoints**
   - `/api/v1/discovery/profiles` (GET)
   - `/api/v1/conversations/` (GET)
   - Confirmer que ces routes existent dans `urls.py`

3. **Tester l'authentification end-to-end**
   ```python
   # Script de test backend
   import requests
   
   # 1. Obtenir un token
   response = requests.post(
       'http://localhost:8000/api/v1/auth/firebase-exchange/',
       json={'idToken': '<FIREBASE_TOKEN>'}
   )
   token = response.json()['access']
   
   # 2. Tester discovery
   response = requests.get(
       'http://localhost:8000/api/v1/discovery/profiles',
       headers={'Authorization': f'Bearer {token}'},
       params={'page': 1, 'page_size': 5}
   )
   print(f"Discovery Status: {response.status_code}")
   print(f"Discovery Response: {response.json()}")
   
   # 3. Tester conversations
   response = requests.get(
       'http://localhost:8000/api/v1/conversations/',
       headers={'Authorization': f'Bearer {token}'},
       params={'page': 1, 'page_size': 20, 'status': 'all'}
   )
   print(f"Conversations Status: {response.status_code}")
   print(f"Conversations Response: {response.json()}")
   ```

### Priorité MOYENNE

4. **Mettre à jour les dépendances**
   - `djangorestframework-simplejwt`
   - Vérifier les autres packages pour des mises à jour de sécurité

5. **Améliorer les logs**
   - Ajouter plus de contexte dans les messages d'erreur
   - Inclure l'ID utilisateur dans les logs d'authentification
   - Logger les headers d'authentification (sans exposer les tokens)

### Priorité BASSE

6. **Documentation**
   - Documenter tous les endpoints API
   - Créer des exemples de requêtes
   - Documenter le processus d'authentification Firebase → JWT

---

## 🔍 Informations de Débogage Utiles

### Vérification de la Configuration Django

```python
# Dans un shell Django (python manage.py shell)
from django.urls import get_resolver

# Lister toutes les URLs
resolver = get_resolver()
for pattern in resolver.url_patterns:
    print(pattern)

# Vérifier un endpoint spécifique
from django.urls import resolve
try:
    match = resolve('/api/v1/discovery/profiles')
    print(f"View: {match.func.__name__}")
    print(f"URL name: {match.url_name}")
except:
    print("URL not found")
```

### Logs à Activer

```python
# Dans settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'rest_framework': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'rest_framework_simplejwt': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

---

## 📞 Contact et Support

Pour toute question ou clarification sur ces corrections, référez-vous à :
- Documentation API: `API_DOCUMENTATION.md`
- Configuration Backend: `CONFIGURATION_BACKEND_FIREBASE.md`
- Guide de test: `GUIDE_TEST_COMPLET.md`

---

## ✅ Checklist de Validation

Après avoir effectué les corrections, valider :

- [ ] L'endpoint `/api/v1/discovery/profiles` fonctionne avec authentification
- [ ] L'endpoint `/api/v1/conversations/` fonctionne avec authentification
- [ ] Les tokens JWT sont correctement validés
- [ ] Les logs backend ne montrent plus d'erreurs 401 ou 404
- [ ] Le frontend peut charger la page de découverte
- [ ] Le frontend peut charger la page de messages
- [ ] Les tests unitaires backend passent
- [ ] Les tests d'intégration passent

---

**Note:** Toutes les corrections côté frontend ont été effectuées (suppression de la duplication `/api/v1/` dans les endpoints). Le problème résiduel est maintenant strictement côté backend.
