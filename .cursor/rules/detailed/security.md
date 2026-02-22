# Sécurité & Permissions - HIVMeet Backend

**Import with**: `@.claude/rules/security.md`

---

## CORS Configuration

Configuration CORS pour autoriser le frontend Flutter à communiquer avec l'API :

```python
# hivmeet_backend/settings.py

# CORS Headers
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=Csv()
)

# Pour le développement local (Flutter)
CORS_ALLOW_CREDENTIALS = True

# Headers autorisés
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Méthodes HTTP autorisées
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Production: Spécifier exactement les origines
# CORS_ALLOWED_ORIGINS = [
#     'https://hivmeet.app',
#     'https://www.hivmeet.app',
# ]
```

---

## CSRF Protection

Django CSRF activé par défaut mais adapté pour API REST :

```python
# hivmeet_backend/settings.py

# CSRF pour les formulaires web (admin Django)
CSRF_COOKIE_SECURE = not DEBUG  # True en production (HTTPS)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# DRF utilise l'authentification par token → CSRF désactivé pour API
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # SessionAuthentication désactivée pour éviter CSRF sur API
    ],
}

# Exempter les endpoints API du CSRF
from django.views.decorators.csrf import csrf_exempt

# Les vues DRF sont automatiquement exemptées
```

---

## XSS Protection

Protection contre les injections de scripts malveillants :

```python
# hivmeet_backend/settings.py

# Sécurité navigateur
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
```

**Dans les serializers** : DRF échappe automatiquement les chaînes HTML.

**Validation supplémentaire** :

```python
import bleach
from rest_framework import serializers

class UserProfileSerializer(serializers.ModelSerializer):
    bio = serializers.CharField(max_length=500)
    
    def validate_bio(self, value):
        """
        Nettoyer la bio de tout HTML malveillant.
        """
        # Supprimer tous les tags HTML
        clean_bio = bleach.clean(value, tags=[], strip=True)
        
        # Ou autoriser certains tags seulement
        # clean_bio = bleach.clean(value, tags=['b', 'i', 'u'], strip=True)
        
        return clean_bio
```

---

## Rate Limiting

Limiter les requêtes pour éviter les abus (brute force, spam) :

```python
# hivmeet_backend/settings.py

# Installer django-ratelimit
# pip install django-ratelimit

# Configuration globale
RATELIMIT_ENABLE = not DEBUG  # Désactivé en dev
RATELIMIT_VIEW = 'core.views.ratelimit_exceeded'

# Dans les vues
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST')
@api_view(['POST'])
def login(request):
    """
    Maximum 5 tentatives de connexion par minute par IP.
    """
    # ...


@ratelimit(key='user', rate='100/h', method='POST')
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    """
    Maximum 100 messages par heure par utilisateur.
    """
    # ...


@ratelimit(key='ip', rate='10/m', method='POST')
@api_view(['POST'])
def register(request):
    """
    Maximum 10 inscriptions par minute par IP.
    """
    # ...
```

**Handler pour limite dépassée** :

```python
# core/views.py

from rest_framework.response import Response
from rest_framework import status

def ratelimit_exceeded(request, exception):
    """
    Vue appelée quand rate limit est dépassé.
    """
    return Response(
        {
            'error': 'Trop de requêtes. Veuillez réessayer plus tard.',
            'code': 'rate_limit_exceeded'
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS
    )
```

---

## Permissions Personnalisées

### IsOwnerOrReadOnly

Permettre la modification seulement au propriétaire :

```python
# core/permissions.py

from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission: lecture pour tous, modification seulement pour le propriétaire.
    """
    
    def has_object_permission(self, request, view, obj):
        # Lecture autorisée pour tous (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Écriture seulement si propriétaire
        return obj.user == request.user


# Utilisation dans une vue
from rest_framework import viewsets
from core.permissions import IsOwnerOrReadOnly

class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        return UserProfile.objects.all()
```

### IsPremiumUser

Restreindre certaines fonctionnalités aux utilisateurs premium :

```python
# subscriptions/permissions.py

from rest_framework import permissions
from datetime import date

class IsPremiumUser(permissions.BasePermission):
    """
    Permission: l'utilisateur doit avoir un abonnement premium actif.
    """
    
    message = "Cette fonctionnalité nécessite un abonnement premium."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        profile = request.user.profile
        
        # Vérifier si premium et non expiré
        return (
            profile.is_premium and
            profile.premium_expiry and
            profile.premium_expiry >= date.today()
        )


# Utilisation
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPremiumUser])
def get_likes_received(request):
    """
    Voir qui a liké votre profil (fonctionnalité premium).
    """
    # ...
```

### IsMatchedUser

Autoriser la messagerie seulement entre utilisateurs matchés :

```python
# messaging/permissions.py

from rest_framework import permissions

class IsMatchedUser(permissions.BasePermission):
    """
    Permission: les deux utilisateurs doivent être matchés.
    """
    
    message = "Vous devez être matchés pour envoyer un message."
    
    def has_object_permission(self, request, view, obj):
        # obj = Conversation
        from matching.models import Match
        
        participants = obj.participants.all()
        
        if request.user not in participants:
            return False
        
        # Vérifier si match existe entre les participants
        user1, user2 = participants[0], participants[1]
        
        return Match.objects.filter(
            user1=min(user1.id, user2.id),
            user2=max(user1.id, user2.id)
        ).exists()
```

---

## Audit Trail

Tracer les actions sensibles pour conformité et sécurité :

```python
# core/models.py

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AuditLog(models.Model):
    """
    Modèle pour tracer les actions sensibles.
    """
    ACTION_TYPES = [
        ('login', 'Connexion'),
        ('logout', 'Déconnexion'),
        ('password_change', 'Changement mot de passe'),
        ('profile_update', 'Mise à jour profil'),
        ('account_delete', 'Suppression compte'),
        ('premium_purchase', 'Achat premium'),
        ('message_sent', 'Message envoyé'),
        ('report_user', 'Signalement utilisateur'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255)
    details = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"


# Middleware pour capturer IP et User-Agent
# core/middleware.py

class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Ajouter IP et User-Agent au request
        request.audit_ip = self.get_client_ip(request)
        request.audit_user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        response = self.get_response(request)
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Utilisation dans les vues
from core.models import AuditLog

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    user = request.user
    
    # Logger l'action AVANT suppression
    AuditLog.objects.create(
        user=user,
        action='account_delete',
        ip_address=request.audit_ip,
        user_agent=request.audit_user_agent,
        details={'email': user.email, 'reason': request.data.get('reason')}
    )
    
    # Supprimer le compte
    user.delete()
    
    return Response({'message': 'Compte supprimé avec succès'}, status=204)
```

---

## Token Security (JWT)

### Configuration JWT sécurisée

```python
# hivmeet_backend/settings.py

from datetime import timedelta

SIMPLE_JWT = {
    # Durée de vie des tokens
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Court pour sécurité
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    
    # Algorithme de signature
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    
    # Rotation des refresh tokens
    'ROTATE_REFRESH_TOKENS': True,  # Nouveau refresh token à chaque refresh
    'BLACKLIST_AFTER_ROTATION': True,  # Blacklist l'ancien token
    
    # Claims JWT
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    
    # Autres options
    'UPDATE_LAST_LOGIN': True,
}

# Blacklist des tokens révoqués
INSTALLED_APPS += [
    'rest_framework_simplejwt.token_blacklist',
]
```

### Révocation de tokens (déconnexion)

```python
# authentication/views.py

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Déconnexion: blacklist le refresh token.
    """
    try:
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response(
                {'error': 'Refresh token requis'},
                status=400
            )
        
        # Blacklist le token
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response({'message': 'Déconnexion réussie'}, status=200)
        
    except Exception as e:
        return Response(
            {'error': 'Token invalide'},
            status=400
        )
```

---

## Encryption of Sensitive Data

Chiffrer les données sensibles au repos (statut VIH, localisation précise) :

```python
# core/encryption.py

from cryptography.fernet import Fernet
from django.conf import settings
import base64

class FieldEncryption:
    """
    Utilitaire pour chiffrer/déchiffrer des champs sensibles.
    """
    
    def __init__(self):
        # Clé de chiffrement depuis variable d'environnement
        key = settings.ENCRYPTION_KEY.encode()
        self.cipher = Fernet(key)
    
    def encrypt(self, value):
        """Chiffre une chaîne."""
        if not value:
            return None
        
        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_value):
        """Déchiffre une chaîne."""
        if not encrypted_value:
            return None
        
        decoded = base64.b64decode(encrypted_value.encode())
        decrypted = self.cipher.decrypt(decoded)
        return decrypted.decode()


# Utilisation dans un modèle
from django.db import models

class UserProfile(models.Model):
    # ...
    
    hiv_status_encrypted = models.TextField()  # Champ chiffré
    
    @property
    def hiv_status(self):
        """Déchiffre le statut VIH à la lecture."""
        encryptor = FieldEncryption()
        return encryptor.decrypt(self.hiv_status_encrypted)
    
    @hiv_status.setter
    def hiv_status(self, value):
        """Chiffre le statut VIH à l'écriture."""
        encryptor = FieldEncryption()
        self.hiv_status_encrypted = encryptor.encrypt(value)
```

**Configuration** :

```python
# hivmeet_backend/settings.py

# Générer une clé: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = config('ENCRYPTION_KEY')
```

---

## HTTPS Enforcement (Production)

Forcer HTTPS en production :

```python
# hivmeet_backend/settings.py

if not DEBUG:
    # Forcer HTTPS
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Proxy headers (si derrière Nginx/AWS ELB)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

---

## Input Sanitization Checklist

Avant d'accepter toute donnée utilisateur :

- [ ] **Type validation** : Vérifier le type (string, int, date, etc.)
- [ ] **Length validation** : Min/max length
- [ ] **Format validation** : Regex pour email, phone, URL
- [ ] **Whitelist validation** : Valeurs autorisées pour enums/choix
- [ ] **SQL Injection** : Utiliser ORM Django (protection automatique)
- [ ] **XSS** : Échapper HTML ou utiliser bleach.clean()
- [ ] **Path Traversal** : Valider les noms de fichiers uploadés
- [ ] **Command Injection** : Ne jamais passer input utilisateur à shell commands

**Exemple complet** :

```python
import re
import bleach
from rest_framework import serializers

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    bio = serializers.CharField(max_length=500, required=False)
    location_city = serializers.CharField(max_length=100, required=False)
    website = serializers.URLField(required=False, allow_blank=True)
    
    def validate_bio(self, value):
        # XSS: Supprimer HTML
        clean_bio = bleach.clean(value, tags=[], strip=True)
        
        # Length
        if len(clean_bio) > 500:
            raise serializers.ValidationError("Bio trop longue (max 500 caractères)")
        
        return clean_bio
    
    def validate_location_city(self, value):
        # Whitelist: seulement lettres, espaces, tirets
        if not re.match(r'^[a-zA-ZÀ-ÿ\s\-]+$', value):
            raise serializers.ValidationError("Ville invalide")
        
        return value
    
    def validate_website(self, value):
        # URLField valide déjà le format URL
        # Vérifier protocole autorisé
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("URL doit commencer par http:// ou https://")
        
        return value
```

---

## Security Checklist

Avant déploiement en production :

- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` unique et non exposée
- [ ] HTTPS activé (SECURE_SSL_REDIRECT = True)
- [ ] CORS configuré avec origines spécifiques (pas de wildcard)
- [ ] Rate limiting activé sur login/register/API
- [ ] JWT avec durée courte (15min access token)
- [ ] Refresh token blacklist activé
- [ ] Audit logging pour actions sensibles
- [ ] Permissions vérifiées sur tous les endpoints
- [ ] Données sensibles chiffrées (statut VIH)
- [ ] Validation stricte de toutes les entrées utilisateur
- [ ] Tests de sécurité (OWASP Top 10)
- [ ] Monitoring activé (Sentry pour erreurs)
- [ ] Backups automatiques de la base de données

---

**Import in CLAUDE.md**: `@.claude/rules/security.md`
