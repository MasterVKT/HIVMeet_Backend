# 🔐 Configuration Backend Firebase Auth - HIVMeet

## 📊 Problème Identifié

### Situation Actuelle
- ✅ **Frontend** : Récupère token Firebase Auth correctement
- ✅ **Communication** : Token envoyé au backend dans header `Authorization` 
- ❌ **Backend** : Rejette le token Firebase Auth (erreur 401)

### Logs Backend
```
ERROR: InvalidToken - "Le type de jeton fourni n'est pas valide"
token_class: 'AccessToken', token_type: 'access' 
message: 'Le jeton est invalide ou expiré'
```

**Le backend Django attend un JWT Django, mais reçoit un token Firebase Auth !**

## 🔧 Solutions Possibles

### Option A : Endpoint d'Échange de Token (RECOMMANDÉ)

**Créer un endpoint Django** : `POST /api/v1/auth/firebase-exchange/`

```python
# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken
from firebase_admin import auth
import firebase_admin

@api_view(['POST'])
@permission_classes([AllowAny])
def firebase_token_exchange(request):
    """Échange un token Firebase Auth contre un token JWT Django"""
    try:
        firebase_token = request.data.get('firebase_token')
        
        # Vérifier le token Firebase Auth
        decoded_token = auth.verify_id_token(firebase_token)
        firebase_uid = decoded_token['uid']
        email = decoded_token.get('email')
        
        # Récupérer ou créer l'utilisateur Django
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': email, 'firebase_uid': firebase_uid}
        )
        
        # Générer un token JWT Django
        access_token = AccessToken.for_user(user)
        
        return Response({
            'access': str(access_token),
            'user_id': user.id,
            'email': user.email
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=401)
```

**URL Configuration :**
```python
# urls.py
urlpatterns = [
    path('auth/firebase-exchange/', views.firebase_token_exchange, name='firebase-exchange'),
]
```

### Option B : Validation Directe Firebase Auth

**Modifier le middleware Django** pour accepter les tokens Firebase :

```python
# middleware.py
from firebase_admin import auth
from django.contrib.auth.models import User

class FirebaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            try:
                # Essayer de valider comme token Firebase
                decoded_token = auth.verify_id_token(token)
                firebase_uid = decoded_token['uid']
                email = decoded_token.get('email')
                
                # Récupérer ou créer l'utilisateur
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={'username': email, 'firebase_uid': firebase_uid}
                )
                
                request.user = user
                
            except:
                # Si ce n'est pas un token Firebase, laisser Django gérer
                pass
        
        return self.get_response(request)
```

## 🚀 Test de la Solution Actuelle

### L'application va maintenant :

1. **Récupérer** le token Firebase Auth ✅
2. **Essayer d'échanger** via `POST /auth/firebase-exchange/` 
3. **Si échec** → Utiliser le token Firebase directement
4. **Si succès** → Utiliser le token Django JWT

### Logs Attendus

**Si endpoint existe :**
```
🔑 Token Firebase récupéré: eyJhbGciOiJSUzI1NiIs...
🔄 Tentative échange token Firebase...
✅ Échange token réussi
✅ Token Django utilisé: eyJ0eXAiOiJKV1QiLCJhbGc...
🚀 REQUEST: GET http://10.0.2.2:8000/api/v1/discovery/
✅ RESPONSE: 200 OK
```

**Si endpoint n'existe pas :**
```
🔑 Token Firebase récupéré: eyJhbGciOiJSUzI1NiIs...
🔄 Tentative échange token Firebase...
❌ Erreur échange token: 404
❌ Échec échange token, utilisation Firebase token
🚀 REQUEST: GET http://10.0.2.2:8000/api/v1/discovery/
📊 STATUS: 401 (si backend ne supporte pas Firebase)
```

## 💡 Recommandation

**Implémentez l'Option A** (endpoint d'échange) car :
- ✅ Sécurité renforcée (validation Firebase + JWT Django)
- ✅ Architecture standard
- ✅ Compatibilité avec l'écosystème Django
- ✅ Gestion centralisée des utilisateurs

## 🧪 Test Immédiat

1. **Vérifiez les logs** de l'application Flutter
2. **Si erreur 404** sur `/auth/firebase-exchange/` → Implémentez l'endpoint
3. **Si erreur 401** persistante → Vérifiez la validation Firebase côté Django

---

**L'application HIVMeet est maintenant configurée pour l'échange automatique de tokens !** 🎯 