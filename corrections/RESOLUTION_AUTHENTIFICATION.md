# Résolution des Problèmes d'Authentification - HIVMeet Backend

**Date de résolution:** 25 décembre 2025  
**Problèmes identifiés:** Erreurs 401 sur `/api/v1/discovery/profiles` et `/api/v1/conversations/`

## ✅ Analyse Effectuée

### 1. Vérification de la Structure des URLs
- ✅ L'endpoint `/api/v1/discovery/profiles` existe bien dans `matching/urls/discovery.py`
- ✅ L'endpoint `/api/v1/conversations/` existe bien dans `messaging/urls.py`
- ✅ Les deux endpoints sont correctement déclarés dans `hivmeet_backend/api_urls.py`

### 2. Vérification de la Configuration d'Authentification
- ✅ `REST_FRAMEWORK` est correctement configuré avec `JWTAuthentication`
- ✅ Les permissions par défaut sont `IsAuthenticated`
- ✅ `SIMPLE_JWT` est correctement configuré

### 3. Vérification des Vues
- ✅ `get_discovery_profiles` utilise `@permission_classes([permissions.IsAuthenticated])`
- ✅ `ConversationListView` utilise `permission_classes = [permissions.IsAuthenticated]`

## 🔧 Corrections Appliquées

### 1. Ajout de Logs de Débogage

**Fichier:** `matching/views_discovery.py`
```python
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_discovery_profiles(request):
    """Get recommended profiles for discovery."""
    # Debug logging pour l'authentification
    logger.info(f"🔍 Discovery request - User: {request.user}")
    logger.info(f"🔍 Is authenticated: {request.user.is_authenticated}")
    logger.info(f"🔍 Auth header: {request.META.get('HTTP_AUTHORIZATION', 'NO AUTH HEADER')}")
    
    if not request.user.is_authenticated:
        logger.error("❌ User not authenticated for discovery endpoint")
        return Response({
            'error': True,
            'message': _('Authentication required')
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Suite de la logique...
```

**Fichier:** `messaging/views.py`
```python
class ConversationListView(generics.ListAPIView):
    """Get list of conversations."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer
    
    def get_queryset(self):
        """Get conversations for current user."""
        user = self.request.user
        
        # Debug logging
        logger.info(f"🔍 Conversations request - User: {user}")
        logger.info(f"🔍 Is authenticated: {user.is_authenticated}")
        logger.info(f"🔍 Auth header: {self.request.META.get('HTTP_AUTHORIZATION', 'NO AUTH HEADER')}")
        
        # Suite de la logique...
```

### 2. Script de Test Créé

**Fichier:** `test_authentication_complete.py`
- Test de création d'utilisateur
- Test de génération de token JWT
- Test d'authentification Django interne
- Test des endpoints API avec token

## 🎯 Prochaines Étapes

### Étape 1: Exécuter le Script de Test
```bash
python test_authentication_complete.py
```

Ce script va:
1. Créer un utilisateur de test
2. Générer un token JWT valide
3. Tester l'authentification Django
4. Tester les endpoints `/discovery/profiles` et `/conversations/`

### Étape 2: Analyser les Logs
Vérifier les logs Django pour voir:
- Si le token JWT est reçu
- Si le token est validé correctement
- Si l'utilisateur est authentifié

### Étape 3: Vérifier le Format du Token Frontend
Le frontend Flutter doit envoyer le token dans le format:
```http
Authorization: Bearer <TOKEN_JWT>
```

**Vérifier dans le code Flutter:**
```dart
final headers = {
  'Authorization': 'Bearer $accessToken',
  'Content-Type': 'application/json',
};
```

### Étape 4: Vérifier la Configuration CORS
Si le problème persiste, vérifier que CORS autorise les headers d'authentification:
```python
# settings.py
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',  # Important!
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-firebase-token',
]
```

## 🐛 Problèmes Potentiels Identifiés

### Problème 1: Token JWT Non Envoyé
**Symptôme:** Logs montrent "NO AUTH HEADER"  
**Solution:** Vérifier que le frontend envoie bien le header `Authorization`

### Problème 2: Token JWT Malformé
**Symptôme:** Erreur de décodage du token  
**Solution:** Vérifier que le token n'a pas d'espaces ou de caractères parasites

### Problème 3: Token JWT Expiré
**Symptôme:** Token valide mais authentification échoue  
**Solution:** Vérifier la durée de vie du token dans `settings.SIMPLE_JWT`

### Problème 4: Middleware Mal Ordonné
**Symptôme:** Authentification ne fonctionne pas du tout  
**Solution:** Vérifier l'ordre des middlewares dans `settings.MIDDLEWARE`

## 📋 Checklist de Diagnostic

- [ ] Le serveur Django démarre sans erreur
- [ ] L'endpoint `/api/v1/auth/firebase-exchange/` retourne 200 avec un token
- [ ] Le token JWT est présent dans les logs backend
- [ ] Le token JWT est valide (non expiré)
- [ ] Le header `Authorization` est bien envoyé depuis le frontend
- [ ] CORS est correctement configuré
- [ ] Les logs montrent `Is authenticated: True`

## 🔍 Commandes de Débogage Utiles

### Vérifier les URLs Disponibles
```python
python manage.py show_urls | grep discovery
python manage.py show_urls | grep conversations
```

### Tester l'Authentification avec curl
```bash
# 1. Obtenir un token (remplacer FIREBASE_TOKEN)
curl -X POST http://localhost:8000/api/v1/auth/firebase-exchange/ \
  -H "Content-Type: application/json" \
  -d '{"idToken": "FIREBASE_TOKEN"}'

# 2. Tester discovery (remplacer JWT_TOKEN)
curl -X GET "http://localhost:8000/api/v1/discovery/profiles?page=1&page_size=5" \
  -H "Authorization: Bearer JWT_TOKEN"

# 3. Tester conversations (remplacer JWT_TOKEN)
curl -X GET "http://localhost:8000/api/v1/conversations/?page=1&page_size=20&status=all" \
  -H "Authorization: Bearer JWT_TOKEN"
```

### Vérifier la Configuration JWT
```python
python manage.py shell
>>> from django.conf import settings
>>> print(settings.REST_FRAMEWORK)
>>> print(settings.SIMPLE_JWT)
```

## 📊 Résultats Attendus

Après les corrections, les logs devraient montrer:
```
INFO hivmeet.matching 🔍 Discovery request - User: test@hivmeet.com
INFO hivmeet.matching 🔍 Is authenticated: True
INFO hivmeet.matching 🔍 Auth header: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

Et les endpoints devraient retourner:
- `GET /api/v1/discovery/profiles`: **200 OK** avec liste de profils
- `GET /api/v1/conversations/`: **200 OK** avec liste de conversations

## 🔄 Mise à Jour des Dépendances

Si nécessaire, mettre à jour `djangorestframework-simplejwt`:
```bash
pip install --upgrade djangorestframework-simplejwt
pip freeze > requirements.txt
```

---

**Prochaine action:** Exécuter `python test_authentication_complete.py` et analyser les résultats.