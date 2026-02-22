# HIVMeet Backend - Google Gemini Style Guide

**Project**: HIVMeet Backend API  
**Type**: Backend (Django REST Framework)  
**Stack**: Django 4.2 + DRF + PostgreSQL + Firebase Auth + Redis + Celery  

---

## 🎯 Philosophie du Projet

HIVMeet est une application de rencontre sensible pour personnes vivant avec le VIH/SIDA. Exige **sécurité maximale**, **protection des données** et **conformité stricte aux spécifications d'API** pour l'intégration Flutter frontend.

---

## 🔴 8 Règles Critiques (JAMAIS VIOLER)

### 1. Variables d'Environnement Obligatoires
**JAMAIS** hardcoder secrets/credentials. Toujours utiliser `python-decouple`:
```python
# ✅ CORRECT
from decouple import config
SECRET_KEY = config('SECRET_KEY')
DATABASE_URL = config('DATABASE_URL')

# ❌ INTERDIT
SECRET_KEY = 'django-insecure-hardcoded-key'
```

### 2. Validation des Entrées Utilisateur
**TOUTES** les données utilisateur validées avec serializers DRF stricts:
```python
# ✅ CORRECT - Validation stricte
class UserProfileSerializer(serializers.ModelSerializer):
    def validate_birthdate(self, value):
        age = (date.today() - value).days // 365
        if age < 18:
            raise serializers.ValidationError(_("18 ans minimum requis"))
        return value

# ❌ INTERDIT - Accès direct sans validation
profile.birthdate = request.data.get('birthdate')  # Dangereux!
```

### 3. Authentification Firebase Obligatoire
Tous endpoints protégés utilisent `FirebaseAuthenticationMiddleware`:
```python
# ✅ CORRECT
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_profile(request):
    profile = request.user.profile
    return Response(UserProfileSerializer(profile).data)

# ❌ INTERDIT - Pas de permission_classes
@api_view(['GET'])
def get_my_profile(request):  # Pas protégé!
```

### 4. Migrations Django Systématiques
CHAQUE modification de modèle = migration avant commit:
```bash
python manage.py makemigrations
python manage.py migrate
git add app/models.py app/migrations/
git commit -m "feat: ajout champ X"
```

### 5. Respect du Contrat d'API
Endpoints DOIVENT suivre `docs/API_DOCUMENTATION.md` exactement:
- URL exacte: `/api/v1/user-profiles/me/`
- Format JSON identique à la spec
- Codes HTTP corrects (200/201/204/400/401/403/404/500)

### 6. Logging avec Contexte Utilisateur
Logger actions critiques avec contexte (sans données sensibles):
```python
logger.info(f"Like créé - From: {request.user.id} To: {target_user.id} - IP: {request.META.get('REMOTE_ADDR')}")

# ❌ JAMAIS logger: mots de passe, tokens complets, données médicales
```

### 7. Transactions pour Opérations Critiques
Utiliser `@transaction.atomic` pour opérations multi-modèles:
```python
@transaction.atomic
def activate_premium(user, subscription_type, payment_id):
    subscription = Subscription.objects.create(...)
    profile.is_premium = True
    profile.save()
    Payment.objects.create(...)
```

### 8. Internationalisation FR/EN
Messages utilisateur internationalisés avec `gettext_lazy`:
```python
from django.utils.translation import gettext_lazy as _

raise serializers.ValidationError(_("Vous devez avoir 18 ans"))
return Response({'message': _("Like envoyé avec succès")})
```

---

## 📚 Règles Détaillées (Référence)

Pour règles détaillées, consulter:
- `.gemini/rules/architecture.md` - Structure apps, services, patterns
- `.gemini/rules/security.md` - CORS, permissions, rate limiting
- `.gemini/rules/api-guidelines.md` - Conventions API, pagination, erreurs

---

## 🔄 Workflow de Développement

**Avant de coder**:
- [ ] Lire spécification dans `docs/API_DOCUMENTATION.md`
- [ ] Vérifier modèles existants
- [ ] Consulter règles détaillées pertinentes

**Pendant le développement**:
- [ ] Respecter les 8 règles critiques
- [ ] Écrire tests
- [ ] Valider avec contrat d'API
- [ ] Logger actions critiques

**Avant commit**:
- [ ] Générer migrations (`makemigrations` + `migrate`)
- [ ] Exécuter tests (`pytest`)
- [ ] Vérifier linting (`flake8`, `black`)
- [ ] Tester avec Postman/curl

---

## 🚨 Erreurs Communes à Éviter

1. **Oublier sync Firebase ↔ Django**: User créé Firebase pas dans Django
2. **Exposer données sensibles**: Statut VIH, email dans réponses publiques
3. **Race conditions**: Utiliser `get_or_create` avec `@transaction.atomic`
4. **Ignorer edge cases**: Profil sans photo, premium expiré, etc.

---

## 📞 Intégrations

- **Frontend Flutter**: JSON REST, Bearer JWT, `docs/API_DOCUMENTATION.md`
- **Firebase**: Auth, Storage, Cloud Messaging
- **Services**: SendGrid/SES (emails), Stripe/PayPal (paiements)

---

## ✅ Checklist Avant Commit

- [ ] Pas de secrets hardcodés
- [ ] Serializers avec validations strictes
- [ ] Endpoints protégés avec `IsAuthenticated`
- [ ] Migrations générées et appliquées
- [ ] Format conforme à `API_DOCUMENTATION.md`
- [ ] Logs avec contexte (sans données sensibles)
- [ ] Transactions atomiques pour opérations critiques
- [ ] Messages internationalisés (`gettext_lazy`)

---

**Documentation**: `docs/API_DOCUMENTATION.md`, `docs/backend-specs.md`, `docs/backend-dev-plan.md`  
**Version**: 1.0 | **Last Updated**: 2026-02-22
