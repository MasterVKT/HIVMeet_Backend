# API Guidelines - HIVMeet Backend

**Import with**: `@.claude/rules/api-guidelines.md`

---

## URL Conventions

### Structure des URLs

```
/api/v{version}/{resource}/{action}/
```

**Exemples** :
- `/api/v1/user-profiles/me/`
- `/api/v1/discovery/`
- `/api/v1/auth/login/`
- `/api/v1/matches/active/`

### Règles de Nommage

1. **Version** : Toujours inclure `/api/v1/`
2. **Ressources au pluriel** : `user-profiles` pas `user-profile`
3. **Kebab-case** : `user-profiles` pas `user_profiles` ou `userProfiles`
4. **Actions en fin d'URL** : `/me/`, `/active/`, `/set-main/`
5. **Pas de trailing slash** dans les requêtes (mais configuré pour accepter)

### Paramètres d'URL

```python
# ✅ CORRECT - Paramètres de ressource dans l'URL
GET /api/v1/user-profiles/{user_id}/
GET /api/v1/matches/{match_id}/

# ❌ INTERDIT - ID dans query params
GET /api/v1/user-profiles/?user_id=123
```

### Query Parameters

```python
# ✅ CORRECT - Filtres et options dans query params
GET /api/v1/discovery/?age_min=25&age_max=35&page=2
GET /api/v1/messages/?conversation_id=abc&limit=50

# Snake_case pour les query params
```

---

## HTTP Methods

### GET - Récupération

```python
# Liste de ressources
GET /api/v1/user-profiles/
Response: [
    {"id": "uuid1", "username": "user1"},
    {"id": "uuid2", "username": "user2"}
]

# Une ressource spécifique
GET /api/v1/user-profiles/{user_id}/
Response: {"id": "uuid1", "username": "user1", ...}

# Idempotent: même résultat à chaque appel
```

### POST - Création

```python
# Créer une nouvelle ressource
POST /api/v1/user-profiles/
Body: {"username": "newuser", "bio": "..."}
Response (201): {"id": "uuid", "username": "newuser", ...}

# Actions spécifiques
POST /api/v1/matching/like/{user_id}/
Response (201): {"like_id": "uuid", "is_match": false}
```

### PUT - Remplacement complet

```python
# Remplacer entièrement une ressource
PUT /api/v1/user-profiles/me/
Body: {
    "username": "updated",
    "bio": "new bio",
    "birthdate": "1990-01-01",
    "gender": "male"
    # TOUS les champs requis
}
Response (200): {ressource complète mise à jour}
```

### PATCH - Mise à jour partielle

```python
# Mettre à jour seulement certains champs
PATCH /api/v1/user-profiles/me/
Body: {"bio": "Updated bio only"}
Response (200): {ressource avec bio mise à jour}
```

### DELETE - Suppression

```python
# Supprimer une ressource
DELETE /api/v1/user-profiles/me/photos/{photo_id}/
Response (204): No content
```

---

## Status Codes

### Success (2xx)

- **200 OK** : Requête réussie (GET, PUT, PATCH)
- **201 Created** : Ressource créée (POST)
- **204 No Content** : Succès sans contenu (DELETE, certains PUT)

### Client Errors (4xx)

- **400 Bad Request** : Données invalides, validation échouée
- **401 Unauthorized** : Non authentifié (token manquant/invalide)
- **403 Forbidden** : Authentifié mais non autorisé (permissions insuffisantes)
- **404 Not Found** : Ressource inexistante
- **409 Conflict** : Conflit (ex: email déjà utilisé)
- **422 Unprocessable Entity** : Validation sémantique échouée
- **429 Too Many Requests** : Rate limit dépassé

### Server Errors (5xx)

- **500 Internal Server Error** : Erreur serveur non gérée
- **502 Bad Gateway** : Erreur de proxy/gateway
- **503 Service Unavailable** : Service temporairement indisponible

### Exemples de Réponses

```python
# 200 OK - Succès
{
    "id": "uuid",
    "username": "john_doe",
    "bio": "Hello world"
}

# 400 Bad Request - Validation échouée
{
    "error": "Validation échouée",
    "details": {
        "birthdate": ["Ce champ est requis"],
        "email": ["Email invalide"]
    }
}

# 401 Unauthorized - Non authentifié
{
    "error": "Token d'authentification invalide ou expiré"
}

# 403 Forbidden - Pas d'accès
{
    "error": "Cette fonctionnalité nécessite un abonnement premium"
}

# 404 Not Found
{
    "error": "Utilisateur introuvable"
}

# 500 Internal Server Error
{
    "error": "Une erreur est survenue. Veuillez réessayer plus tard."
}
```

---

## Pagination

### PageNumberPagination (Défaut)

```python
# hivmeet_backend/settings.py

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Requête
GET /api/v1/discovery/?page=2&page_size=10

# Réponse
{
    "count": 150,  # Total d'éléments
    "next": "http://api.hivmeet.com/api/v1/discovery/?page=3",
    "previous": "http://api.hivmeet.com/api/v1/discovery/?page=1",
    "results": [
        {"id": "uuid1", ...},
        {"id": "uuid2", ...},
        // ... 10 éléments
    ]
}
```

### Cursor Pagination (Pour flux continus)

```python
# messaging/views.py

from rest_framework.pagination import CursorPagination

class MessageCursorPagination(CursorPagination):
    page_size = 50
    ordering = '-created_at'  # Plus récent en premier
    cursor_query_param = 'cursor'


class MessageViewSet(viewsets.ModelViewSet):
    pagination_class = MessageCursorPagination
    # ...

# Requête
GET /api/v1/messages/?conversation_id=abc&cursor=cD0yMDIz

# Réponse
{
    "next": "http://...?cursor=cD0yMDI0",
    "previous": "http://...?cursor=cD0yMDIy",
    "results": [...]
}
```

---

## Filtering

### Query Parameters

```python
# Filtrage simple
GET /api/v1/user-profiles/?gender=male&age_min=25&age_max=35

# Implémentation dans la vue
from rest_framework import viewsets

class UserProfileViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        queryset = UserProfile.objects.all()
        
        # Filtrer par gender
        gender = self.request.query_params.get('gender')
        if gender:
            queryset = queryset.filter(gender=gender)
        
        # Filtrer par age
        age_min = self.request.query_params.get('age_min')
        age_max = self.request.query_params.get('age_max')
        if age_min:
            queryset = queryset.filter(age__gte=age_min)
        if age_max:
            queryset = queryset.filter(age__lte=age_max)
        
        return queryset
```

### Django Filter Backend

```python
# Installer django-filter
# pip install django-filter

# hivmeet_backend/settings.py
INSTALLED_APPS += ['django_filters']

REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# profiles/views.py
from django_filters import rest_framework as filters

class UserProfileFilter(filters.FilterSet):
    age_min = filters.NumberFilter(field_name='age', lookup_expr='gte')
    age_max = filters.NumberFilter(field_name='age', lookup_expr='lte')
    gender = filters.CharFilter(field_name='gender')
    
    class Meta:
        model = UserProfile
        fields = ['age_min', 'age_max', 'gender']


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    filterset_class = UserProfileFilter
    search_fields = ['username', 'bio']
    ordering_fields = ['created_at', 'age']
    
# Requêtes possibles
GET /api/v1/user-profiles/?gender=male&age_min=25&ordering=-created_at
GET /api/v1/user-profiles/?search=developer
```

---

## Versioning

### URL Path Versioning (Utilisé dans HIVMeet)

```python
# hivmeet_backend/settings.py

REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'VERSION_PARAM': 'version',
}

# urls.py
from django.urls import path, include

urlpatterns = [
    path('api/v1/', include('api.v1.urls')),
    path('api/v2/', include('api.v2.urls')),  # Future version
]

# Dans les vues
class UserProfileViewSet(viewsets.ModelViewSet):
    def list(self, request):
        version = request.version  # 'v1' ou 'v2'
        
        if version == 'v1':
            serializer = UserProfileSerializerV1(...)
        elif version == 'v2':
            serializer = UserProfileSerializerV2(...)
        
        return Response(serializer.data)
```

---

## Documentation (Swagger/OpenAPI)

### Configuration drf-yasg

```python
# hivmeet_backend/urls.py

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="HIVMeet API",
        default_version='v1',
        description="API REST pour l'application HIVMeet",
        terms_of_service="https://hivmeet.com/terms/",
        contact=openapi.Contact(email="contact@hivmeet.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Documentation Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # JSON schema
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
]
```

### Documenter les Endpoints

```python
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class UserProfileViewSet(viewsets.ModelViewSet):
    
    @swagger_auto_schema(
        operation_description="Récupère le profil de l'utilisateur connecté",
        responses={
            200: UserProfileSerializer(),
            401: "Non authentifié",
        }
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Endpoint: GET /api/v1/user-profiles/me/
        
        Retourne le profil complet de l'utilisateur authentifié.
        """
        profile = request.user.profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_description="Like un utilisateur",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'is_super_like': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Super-like (premium)'
                ),
            }
        ),
        responses={
            201: "Like créé avec succès",
            403: "Fonctionnalité premium requise",
            404: "Utilisateur introuvable",
        }
    )
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        # ...
```

Accès : `http://localhost:8000/swagger/`

---

## Error Handling

### Format d'Erreur Standard

```python
# Toutes les réponses d'erreur suivent ce format
{
    "error": "Message d'erreur principal",
    "code": "error_code_slug",  # Optionnel
    "details": {}  # Détails validation (optionnel)
}
```

### Exemples par Type d'Erreur

```python
# 400 Bad Request - Validation
{
    "error": "Les données fournies sont invalides",
    "details": {
        "birthdate": ["Ce champ est requis"],
        "email": ["Saisissez une adresse e-mail valide"]
    }
}

# 401 Unauthorized
{
    "error": "Token d'authentification invalide ou expiré",
    "code": "invalid_token"
}

# 403 Forbidden
{
    "error": "Cette fonctionnalité nécessite un abonnement premium",
    "code": "premium_required"
}

# 404 Not Found
{
    "error": "Utilisateur introuvable",
    "code": "user_not_found"
}

# 429 Too Many Requests
{
    "error": "Trop de requêtes. Veuillez réessayer dans 60 secondes.",
    "code": "rate_limit_exceeded",
    "details": {"retry_after": 60}
}

# 500 Internal Server Error
{
    "error": "Une erreur est survenue. Veuillez réessayer plus tard.",
    "code": "internal_error"
}
```

### Implémentation

```python
# core/exceptions.py

from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        # Format uniforme
        error_data = {
            'error': response.data.get('detail', 'Erreur'),
        }
        
        # Ajouter validation errors si présents
        if isinstance(response.data, dict):
            non_field_errors = {k: v for k, v in response.data.items() if k != 'detail'}
            if non_field_errors:
                error_data['details'] = non_field_errors
        
        response.data = error_data
    
    return response

# hivmeet_backend/settings.py
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}
```

---

## Content Negotiation

### Accept Header

```python
# Client spécifie le format souhaité
GET /api/v1/user-profiles/me/
Headers:
    Accept: application/json  # Défaut

# HIVMeet supporte seulement JSON
# Pas de XML, CSV, etc. (pour l'instant)
```

### Response Headers

```python
# Toutes les réponses incluent
Content-Type: application/json
Cache-Control: no-cache, no-store, must-revalidate
X-Content-Type-Options: nosniff
```

---

## Request/Response Examples

### Authentication

```http
POST /api/v1/auth/firebase-exchange/
Content-Type: application/json

{
    "firebase_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6I..."
}

HTTP/1.1 200 OK
Content-Type: application/json

{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": {
        "id": "uuid",
        "email": "user@example.com",
        "username": "john_doe"
    }
}
```

### Profile Update

```http
PATCH /api/v1/user-profiles/me/
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{
    "bio": "Updated bio",
    "preferences": {
        "age_range": [25, 35],
        "max_distance": 50
    }
}

HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": "uuid",
    "username": "john_doe",
    "bio": "Updated bio",
    "birthdate": "1990-01-01",
    "gender": "male",
    "preferences": {
        "age_range": [25, 35],
        "max_distance": 50
    },
    // ... other fields
}
```

### Discovery

```http
GET /api/v1/discovery/?page=1&page_size=10
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...

HTTP/1.1 200 OK
Content-Type: application/json

{
    "count": 45,
    "next": "http://api.hivmeet.com/api/v1/discovery/?page=2",
    "previous": null,
    "results": [
        {
            "id": "uuid1",
            "username": "jane_doe",
            "age": 28,
            "bio": "Hello!",
            "photos": [
                {"id": "photo1", "url": "https://...", "is_main": true}
            ],
            "location": {"city": "Paris", "country": "France"},
            "compatibility_score": 85
        },
        // ... 9 more profiles
    ]
}
```

---

## API Design Checklist

Avant de créer un nouvel endpoint :

- [ ] URL suit la convention `/api/v1/{resource}/{action}/`
- [ ] Méthode HTTP appropriée (GET/POST/PUT/PATCH/DELETE)
- [ ] Status code correct (200/201/204/400/401/403/404/500)
- [ ] Authentification requise (sauf endpoints publics)
- [ ] Permissions vérifiées
- [ ] Validation des entrées avec serializer
- [ ] Pagination activée (pour listes)
- [ ] Format d'erreur uniforme
- [ ] Documenté avec Swagger
- [ ] Conforme à `docs/API_DOCUMENTATION.md`
- [ ] Tests API écrits
- [ ] Logging ajouté pour actions critiques

---

**Import in CLAUDE.md**: `@.claude/rules/api-guidelines.md`
