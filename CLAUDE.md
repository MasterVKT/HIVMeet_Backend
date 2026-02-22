# HIVMeet Backend - AI Agent Rules

**Project**: HIVMeet Backend API  
**Type**: Backend (Django REST Framework)  
**Purpose**: API REST sécurisée pour application de rencontre dédiée aux personnes vivant avec le VIH/SIDA  
**Stack**: Django 4.2 + DRF + PostgreSQL + Firebase Auth + Redis + Celery  
**Version**: 1.0  
**Last Updated**: 2026-02-22

---

## 🎯 Core Philosophy

HIVMeet est une application de rencontre sensible nécessitant la **plus haute sécurité**, la **protection maximale des données personnelles** et une **conformité stricte aux spécifications d'API** pour l'intégration avec le frontend Flutter.

---

## 🔴 Critical Rules (NEVER VIOLATE)

### 1. **Variables d'Environnement Obligatoires**

**Règle**: Tous les secrets, credentials et configurations sensibles DOIVENT être dans des variables d'environnement.

**JAMAIS hardcoder** :
- Clés API (Firebase, SendGrid, AWS, etc.)
- Credentials de base de données
- SECRET_KEY Django
- Tokens ou clés de chiffrement
- URLs de services externes (production)

**Toujours utiliser** :
```python
# ✅ CORRECT - Utiliser python-decouple
from decouple import config

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
DATABASE_URL = config('DATABASE_URL')
FIREBASE_CREDENTIALS = config('FIREBASE_CREDENTIALS_PATH')

# ❌ INTERDIT - Hardcoder
SECRET_KEY = 'django-insecure-hardcoded-key'
DEBUG = True
DATABASE_URL = 'postgresql://user:pass@localhost/db'
```

**Fichier de référence** : `env.example` contient tous les variables requises.

---

### 2. **Validation des Entrées Utilisateur**

**Règle**: TOUTES les données utilisateur doivent être validées côté backend avec des serializers DRF stricts.

**Jamais faire confiance au frontend** - Valider :
- Types de données
- Longueurs (min/max)
- Formats (email, dates, téléphone)
- Valeurs autorisées (choix, enums)
- Données sensibles (âge >= 18, statut VIH valide)

**Toujours utiliser** :
```python
# ✅ CORRECT - Serializer avec validation stricte
from rest_framework import serializers

class UserProfileSerializer(serializers.ModelSerializer):
    birthdate = serializers.DateField()
    gender = serializers.ChoiceField(choices=['male', 'female', 'other'])
    hiv_status = serializers.ChoiceField(choices=['positive', 'negative', 'unknown'])
    
    class Meta:
        model = UserProfile
        fields = ['birthdate', 'gender', 'hiv_status']
    
    def validate_birthdate(self, value):
        age = (date.today() - value).days // 365
        if age < 18:
            raise serializers.ValidationError("L'utilisateur doit avoir au moins 18 ans")
        return value
    
    def validate_hiv_status(self, value):
        # Validation spécifique au domaine
        if not value:
            raise serializers.ValidationError("Le statut VIH est requis")
        return value

# ❌ INTERDIT - Accès direct sans validation
def update_profile(request):
    profile = request.user.profile
    profile.birthdate = request.data.get('birthdate')  # Dangereux !
    profile.save()
```

**Protection RGPD** : Valider que les données sensibles (statut VIH) ne sont jamais exposées sans autorisation.

---

### 3. **Authentification Firebase Obligatoire**

**Règle**: Tous les endpoints protégés DOIVENT utiliser l'authentification Firebase via middleware custom.

**Architecture d'auth** :
- Frontend Flutter → Firebase Auth → Token ID Firebase
- Backend Django → Vérifie token Firebase → Récupère/crée User Django
- Utiliser middleware `FirebaseAuthenticationMiddleware`

**Toujours utiliser** :
```python
# ✅ CORRECT - Vue protégée avec Firebase Auth
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_profile(request):
    """
    L'utilisateur est authentifié via FirebaseAuthenticationMiddleware.
    request.user contient l'instance User Django liée au Firebase UID.
    """
    profile = request.user.profile
    serializer = UserProfileSerializer(profile)
    return Response(serializer.data)

# ❌ INTERDIT - Endpoint protégé sans authentification
@api_view(['GET'])
def get_my_profile(request):  # Pas de permission_classes
    user_id = request.GET.get('user_id')  # Dangereux !
    profile = UserProfile.objects.get(user_id=user_id)
    return Response(...)
```

**Exception** : Seuls les endpoints publics (`/auth/register`, `/auth/login`, `/health`) n'ont pas besoin d'auth.

---

### 4. **Migrations Django Systématiques**

**Règle**: CHAQUE modification de modèle Django doit générer et appliquer une migration avant commit.

**Process obligatoire** :
```bash
# 1. Modifier le modèle
# 2. Générer la migration
python manage.py makemigrations

# 3. Vérifier la migration générée
cat <app>/migrations/XXXX_<description>.py

# 4. Appliquer la migration
python manage.py migrate

# 5. Commit ensemble (modèle + migration)
git add <app>/models.py <app>/migrations/
git commit -m "feat: ajout champ X au modèle Y"
```

**JAMAIS** :
- Modifier directement la base de données
- Supprimer ou éditer une migration déjà déployée
- Oublier de commit les migrations avec les modèles

**Migrations de données** :
```python
# ✅ CORRECT - Migration de données sécurisée
from django.db import migrations

def populate_default_preferences(apps, schema_editor):
    UserProfile = apps.get_model('profiles', 'UserProfile')
    for profile in UserProfile.objects.filter(preferences__isnull=True):
        profile.preferences = {
            'age_range': [18, 99],
            'max_distance': 50,
            'genders_sought': ['male', 'female']
        }
        profile.save()

class Migration(migrations.Migration):
    dependencies = [('profiles', '0012_previous_migration')]
    
    operations = [
        migrations.RunPython(populate_default_preferences),
    ]
```

---

### 5. **Respect du Contrat d'API**

**Règle**: Tous les endpoints DOIVENT suivre exactement les spécifications définies dans `docs/API_DOCUMENTATION.md`.

**Contrat strict** :
- **URL exacte** : `/api/v1/user-profiles/me/` (pas `/api/profiles/current/`)
- **Méthodes HTTP** : GET, POST, PUT, DELETE selon spécifications
- **Format de réponse** : Structure JSON identique à la documentation
- **Codes HTTP** : 200, 201, 204, 400, 401, 403, 404, 500 selon les cas

**Toujours vérifier** :
```python
# ✅ CORRECT - Respect du contrat API
# Endpoint: GET /api/v1/user-profiles/me/
# Réponse attendue dans API_DOCUMENTATION.md:
{
  "id": "uuid",
  "username": "string",
  "bio": "string",
  "birthdate": "YYYY-MM-DD",
  "gender": "string",
  "location": {"city": "string", "country": "string"},
  "photos": [{"id": "uuid", "url": "string", "is_main": bool}],
  "preferences": {...}
}

class UserProfileViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=['get'])
    def me(self, request):
        profile = request.user.profile
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)  # Format respecté

# ❌ INTERDIT - Format différent de la doc
return Response({
    'user_id': profile.id,  # Clé différente ('id' attendu)
    'name': profile.username,  # Clé différente ('username' attendu)
    'pictures': profile.photos.all()  # Clé différente ('photos' attendu)
})
```

**Process de vérification** :
1. Lire `docs/API_DOCUMENTATION.md` pour l'endpoint concerné
2. Implémenter exactement selon la spec
3. Tester avec Postman/curl en comparant la réponse à la doc
4. **Ne jamais modifier** le contrat sans coordination avec le frontend

---

### 6. **Logging avec Contexte Utilisateur**

**Règle**: Tous les logs d'erreur ou événements importants DOIVENT inclure un contexte utilisateur (sans exposer de données sensibles).

**Toujours logger** :
- Tentatives de connexion échouées
- Erreurs d'API (500, 400)
- Actions critiques (suppression de compte, changement de mot de passe)
- Erreurs de permissions (403)
- Erreurs Firebase Auth

**Format de log** :
```python
import logging

logger = logging.getLogger(__name__)

# ✅ CORRECT - Log avec contexte
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_user(request, user_id):
    try:
        target_user = User.objects.get(id=user_id)
        Like.objects.create(from_user=request.user, to_user=target_user)
        
        logger.info(
            f"Like créé - From: {request.user.id} ({request.user.email}) "
            f"To: {target_user.id} - IP: {request.META.get('REMOTE_ADDR')}"
        )
        
        return Response({'success': True}, status=201)
        
    except User.DoesNotExist:
        logger.warning(
            f"Tentative de like vers utilisateur inexistant - "
            f"User: {request.user.id} - Target: {user_id}"
        )
        return Response({'error': 'Utilisateur introuvable'}, status=404)
        
    except Exception as e:
        logger.error(
            f"Erreur lors du like - User: {request.user.id} - "
            f"Target: {user_id} - Error: {str(e)}",
            exc_info=True
        )
        return Response({'error': 'Erreur serveur'}, status=500)

# ❌ INTERDIT - Log sans contexte ou avec données sensibles
logger.error("Erreur dans like_user")  # Pas de contexte
logger.info(f"User password: {user.password}")  # Données sensibles exposées
```

**JAMAIS logger** :
- Mots de passe (même hashés)
- Tokens Firebase ou JWT complets
- Numéros de carte bancaire
- Données médicales détaillées

---

### 7. **Transactions pour Opérations Critiques**

**Règle**: Toute opération modifiant plusieurs modèles ou ayant des implications financières/matching DOIT utiliser des transactions atomiques.

**Opérations critiques** :
- Création/suppression de match
- Achat d'abonnement premium
- Suppression de compte utilisateur
- Migration de données

**Toujours utiliser** :
```python
from django.db import transaction

# ✅ CORRECT - Transaction atomique
@transaction.atomic
def activate_premium_subscription(user, subscription_type, payment_id):
    """
    Active un abonnement premium après paiement validé.
    Si une opération échoue, tout est rollback.
    """
    # 1. Créer la souscription
    subscription = Subscription.objects.create(
        user=user,
        type=subscription_type,
        status='active',
        payment_id=payment_id
    )
    
    # 2. Mettre à jour le profil utilisateur
    profile = user.profile
    profile.is_premium = True
    profile.premium_expiry = subscription.expiry_date
    profile.save()
    
    # 3. Enregistrer le paiement
    Payment.objects.create(
        user=user,
        subscription=subscription,
        amount=subscription.price,
        status='completed',
        transaction_id=payment_id
    )
    
    # 4. Logger l'événement
    logger.info(f"Premium activé - User: {user.id} - Sub: {subscription.id}")
    
    return subscription

# ❌ INTERDIT - Opérations critiques sans transaction
def activate_premium_subscription(user, subscription_type, payment_id):
    subscription = Subscription.objects.create(...)  # Peut réussir
    profile.is_premium = True
    profile.save()  # Peut échouer → Incohérence !
    Payment.objects.create(...)  # Ne s'exécute jamais si erreur avant
```

**Gestion d'erreurs** :
```python
@transaction.atomic
def delete_user_account(user_id):
    try:
        user = User.objects.get(id=user_id)
        
        # Supprimer en cascade
        user.profile.delete()
        user.likes_sent.all().delete()
        user.matches.all().delete()
        user.messages.all().delete()
        user.delete()
        
        logger.info(f"Compte supprimé - User: {user_id}")
        
    except Exception as e:
        logger.error(f"Erreur suppression compte {user_id}: {str(e)}")
        raise  # Rollback automatique
```

---

### 8. **Internationalisation (i18n) FR/EN**

**Règle**: Toutes les chaînes de caractères visibles par l'utilisateur (messages d'erreur, emails, notifications) DOIVENT être internationalisées.

**Utiliser Django i18n** :
```python
from django.utils.translation import gettext_lazy as _

# ✅ CORRECT - Messages internationalisés
class UserProfileSerializer(serializers.ModelSerializer):
    def validate_birthdate(self, value):
        age = (date.today() - value).days // 365
        if age < 18:
            raise serializers.ValidationError(
                _("Vous devez avoir au moins 18 ans pour utiliser HIVMeet.")
            )
        return value

# Dans les vues
@api_view(['POST'])
def like_user(request, user_id):
    try:
        # ...
        return Response({
            'success': True,
            'message': _("Like envoyé avec succès")
        })
    except Exception as e:
        return Response({
            'error': _("Une erreur est survenue. Veuillez réessayer.")
        }, status=500)

# ❌ INTERDIT - Messages en dur en français
raise serializers.ValidationError("Vous devez avoir 18 ans")  # Pas traduit
return Response({'message': "Like envoyé avec succès"})  # Pas traduit
```

**Fichiers de traduction** :
- Français : `locale/fr/LC_MESSAGES/django.po`
- Anglais : `locale/en/LC_MESSAGES/django.po`

**Commandes** :
```bash
# Générer les fichiers de traduction
python manage.py makemessages -l fr
python manage.py makemessages -l en

# Compiler les traductions
python manage.py compilemessages
```

---

## 📚 Detailed Rules (Import On-Demand)

Pour des règles détaillées sur des sujets spécifiques, importer les fichiers correspondants :

### Architecture & Patterns
```
@.claude/rules/architecture.md
```
- Structure des apps Django (authentication, profiles, matching, messaging, subscriptions)
- Patterns de services (MatchingService, NotificationService)
- Séparation des responsabilités (views → services → models)

### Sécurité & Permissions
```
@.claude/rules/security.md
```
- Configuration CORS pour Flutter frontend
- Rate limiting (django-ratelimit)
- Protection CSRF et XSS
- Permissions customisées (IsOwnerOrReadOnly, IsPremiumUser)
- Audit trail des actions sensibles

### API & Serializers
```
@.claude/rules/api-guidelines.md
```
- Conventions de nommage d'endpoints
- Pagination (PageNumberPagination)
- Filtrage et recherche (django-filter)
- Versioning d'API (v1, v2)
- Documentation Swagger/OpenAPI (drf-yasg)

### Base de Données & Modèles
```
@.claude/rules/database.md
```
- Design des modèles (User, UserProfile, Like, Match, Message, Subscription)
- Relations (ForeignKey, ManyToMany)
- Indexation pour performance
- Gestion des migrations complexes
- Soft delete vs hard delete

### Firebase Integration
```
@.claude/rules/firebase.md
```
- Configuration Firebase Admin SDK
- Vérification des tokens ID
- Synchronisation Firebase UID ↔ Django User
- Gestion des notifications push (FCM)
- Firebase Storage pour photos

### Testing & Quality
```
@.claude/rules/testing.md
```
- Tests unitaires (pytest)
- Tests d'intégration (API)
- Fixtures et factories (factory_boy)
- Coverage minimum 80%
- Tests de régression

### Deployment & DevOps
```
@.claude/rules/deployment.md
```
- Configuration Docker/docker-compose
- Variables d'environnement par environnement
- CI/CD (GitHub Actions)
- Monitoring (Sentry, Prometheus)
- Backups et restauration

### Matching & Discovery Algorithm
```
@.claude/rules/matching-algorithm.md
```
- Logique de découverte de profils
- Calcul de compatibilité
- Filtres (âge, distance, préférences)
- Pondération des critères
- Éviter les doublons

### Premium Features
```
@.claude/rules/premium-features.md
```
- Gestion des abonnements
- Webhooks de paiement
- Déblocage de fonctionnalités
- Gestion de la date d'expiration
- Renouvellement automatique

### Messaging System
```
@.claude/rules/messaging.md
```
- Modèle de conversation
- Temps réel (WebSocket ou polling)
- Notifications push
- Chiffrement des messages
- Suppression/archivage

---

## 🚨 Common Mistakes to Avoid

### 1. Oublier la Synchronisation Firebase ↔ Django
**Problème** : User créé dans Firebase mais pas dans Django (ou inversement)

**Solution** :
```python
# ✅ CORRECT - Synchronisation automatique
from authentication.backends import FirebaseBackend

def firebase_exchange(request):
    firebase_token = request.data.get('firebase_token')
    
    # Vérifie le token et récupère/crée l'utilisateur Django
    firebase_backend = FirebaseBackend()
    user = firebase_backend.authenticate(request, token=firebase_token)
    
    if not user:
        return Response({'error': 'Token invalide'}, status=401)
    
    # Générer JWT Django
    jwt_token = generate_jwt(user)
    
    return Response({
        'token': jwt_token,
        'user': UserSerializer(user).data
    })
```

### 2. Exposer des Données Sensibles dans les Logs/Réponses
**Problème** : Statut VIH, email, téléphone exposés publiquement

**Solution** :
```python
# ✅ CORRECT - Serializer avec contrôle d'accès
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'bio', 'photos']
        # Ne PAS inclure: hiv_status, email, phone
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        # Ajouter hiv_status seulement si c'est le propriétaire
        if request and request.user == instance.user:
            data['hiv_status'] = instance.hiv_status
            data['email'] = instance.user.email
        
        return data
```

### 3. Ne Pas Gérer les Race Conditions
**Problème** : Deux utilisateurs likent simultanément → 2 matches créés

**Solution** :
```python
# ✅ CORRECT - Utiliser get_or_create avec transaction
from django.db import transaction

@transaction.atomic
def create_like_and_check_match(from_user, to_user):
    # Créer le like
    like, created = Like.objects.get_or_create(
        from_user=from_user,
        to_user=to_user
    )
    
    # Vérifier si match réciproque existe
    reverse_like = Like.objects.filter(
        from_user=to_user,
        to_user=from_user
    ).exists()
    
    if reverse_like:
        # Créer un seul match (idempotent)
        match, created = Match.objects.get_or_create(
            user1=min(from_user.id, to_user.id),
            user2=max(from_user.id, to_user.id)
        )
        return like, match
    
    return like, None
```

### 4. Ignorer les Cas Limites (Edge Cases)
**Exemples** :
- Profil sans photo (utilisateur supprime toutes ses photos)
- Utilisateur premium expiré (ne pas bloquer brutalement)
- Distance hors limites (utilisateur à l'étranger)
- Age limite (utilisateur devient mineur après création... impossible mais vérifier)

**Solution** : Ajouter des validations et des valeurs par défaut robustes.

---

## 🔄 Development Workflow

### 1. Avant de Coder
- [ ] Lire la spécification dans `docs/API_DOCUMENTATION.md`
- [ ] Vérifier les modèles existants dans `<app>/models.py`
- [ ] Consulter les règles détaillées pertinentes (`.claude/rules/`)

### 2. Pendant le Développement
- [ ] Respecter les 8 Critical Rules
- [ ] Écrire des tests pour la nouvelle fonctionnalité
- [ ] Valider avec le contrat d'API
- [ ] Logger les actions critiques

### 3. Avant de Commit
- [ ] Générer et appliquer les migrations (`makemigrations` + `migrate`)
- [ ] Exécuter les tests (`pytest`)
- [ ] Vérifier le linting (`flake8`, `black`)
- [ ] Tester manuellement avec Postman/curl

### 4. Après Merge
- [ ] Vérifier les logs en production
- [ ] Monitorer Sentry pour erreurs
- [ ] Valider avec le frontend Flutter

---

## 📞 Integration Points

### Frontend Flutter
- **Repository GitHub** : À définir (coordination avec équipe frontend)
- **Format d'API** : JSON REST (`Content-Type: application/json`)
- **Authentification** : Bearer token JWT dans `Authorization` header
- **Documentation partagée** : `docs/API_DOCUMENTATION.md`

### Services Externes
- **Firebase Auth** : Authentification utilisateurs
- **Firebase Storage** : Stockage photos de profil
- **Firebase Cloud Messaging** : Notifications push
- **SendGrid/AWS SES** : Envoi d'emails
- **Stripe/PayPal** : Paiements abonnements premium (à confirmer)

---

## 🎓 Learning Resources

### Django REST Framework
- [Official DRF Docs](https://www.django-rest-framework.org/)
- [DRF Serializers Best Practices](https://www.django-rest-framework.org/api-guide/serializers/)
- [Authentication & Permissions](https://www.django-rest-framework.org/api-guide/authentication/)

### Firebase Integration
- [Firebase Admin Python SDK](https://firebase.google.com/docs/admin/setup)
- [Verify ID Tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens)

### Dating App Specific
- Algorithms: Matching, discovery, recommendation systems
- Data modeling for social apps
- Real-time messaging architectures

---

## ✅ Rule Compliance Checklist

Avant chaque commit, vérifier :

- [ ] **Rule 1** : Aucun secret hardcodé (vérifier avec `grep -r "SECRET_KEY\|PASSWORD" --exclude-dir=venv`)
- [ ] **Rule 2** : Tous les serializers ont des validations strictes
- [ ] **Rule 3** : Tous les endpoints protégés ont `@permission_classes([IsAuthenticated])`
- [ ] **Rule 4** : Migrations générées et appliquées pour modifications de modèles
- [ ] **Rule 5** : Format de réponse conforme à `docs/API_DOCUMENTATION.md`
- [ ] **Rule 6** : Logs avec contexte utilisateur (sans données sensibles)
- [ ] **Rule 7** : Transactions atomiques pour opérations critiques
- [ ] **Rule 8** : Messages utilisateur internationalisés avec `gettext_lazy`

---

## 🆘 When You're Stuck

1. **Check existing code** : Chercher des patterns similaires dans le projet
   ```bash
   # Exemple : Comment sont implémentés les autres endpoints ?
   grep -r "api_view\|ViewSet" profiles/ matching/ messaging/
   ```

2. **Consult detailed rules** : Importer la règle détaillée pertinente
   ```
   @.claude/rules/api-guidelines.md
   @.claude/rules/security.md
   ```

3. **Review API documentation** : `docs/API_DOCUMENTATION.md` est la source de vérité

4. **Ask for clarification** : Si spécifications ambiguës, demander au développeur avant d'assumer

---

## 📝 Notes

- Ce fichier contient les règles **essentielles** uniquement (optimisé pour tokens)
- Pour des règles détaillées, utiliser les imports `@.claude/rules/<topic>.md`
- Ces règles sont synchronisées avec Cursor, GitHub Copilot et Google Gemini
- **Ne jamais modifier** ce fichier sans synchroniser les autres agents

---

**Last Review**: 2026-02-22  
**Next Review**: À chaque changement majeur d'architecture ou de spécifications
