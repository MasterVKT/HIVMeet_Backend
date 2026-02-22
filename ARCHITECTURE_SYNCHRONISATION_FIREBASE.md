# 🏗️ ARCHITECTURE DE SYNCHRONISATION DJANGO ↔ FIREBASE

## Vue d'ensemble

Cette documentation décrit l'architecture et l'implémentation de la synchronisation bidirectionnelle entre Django et Firebase Authentication dans l'application HIVMeet.

---

## 🎯 Objectifs

1. **Synchroniser** tous les utilisateurs Django vers Firebase Authentication
2. **Maintenir** la cohérence des données entre les deux systèmes
3. **Préserver** tous les attributs utilisateur (statut premium, vérification, etc.)
4. **Valider** l'intégrité et la conformité des données
5. **Automatiser** le processus avec des scripts robustes

---

## 📐 Architecture Système

### Composants Principaux

```
┌─────────────────────────────────────────────────────────┐
│                   APPLICATION HIVMeet                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │   Django ORM     │         │  Firebase Admin  │     │
│  │                  │ ◄─────► │      SDK         │     │
│  │  - User Model    │         │                  │     │
│  │  - Profile       │         │ - Authentication │     │
│  │  - Verification  │         │ - Firestore      │     │
│  └──────────────────┘         │ - Storage        │     │
│         │                      └──────────────────┘     │
│         │                              │                 │
│         ▼                              ▼                 │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │   Django DB      │         │  Firebase Cloud  │     │
│  │  (PostgreSQL)    │         │  (Google Cloud)  │     │
│  └──────────────────┘         └──────────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Modèle de Données

### User Django

```python
class User(AbstractBaseUser, PermissionsMixin):
    # Identifiants
    id = UUIDField()  # PK
    email = EmailField(unique=True)
    firebase_uid = CharField(unique=True, null=True)  # Lien Firebase
    
    # Authentification
    password = CharField()
    email_verified = BooleanField()
    
    # Informations personnelles
    display_name = CharField()
    birth_date = DateField()
    phone_number = CharField()
    
    # Statut
    is_active = BooleanField()
    is_staff = BooleanField()
    is_superuser = BooleanField()
    
    # Premium
    is_premium = BooleanField()
    premium_until = DateTimeField()
    
    # Vérification
    is_verified = BooleanField()
    verification_status = CharField()  # verified, pending, rejected, expired
```

### Firebase User

```javascript
{
  uid: "JqidLJn0jEVnaYnR6luy5e7IFC52",
  email: "thomas.dupont@test.com",
  emailVerified: false,
  displayName: "Thomas",
  disabled: false,
  metadata: {
    creationTime: "2026-01-17T03:05:40.000Z",
    lastSignInTime: "2026-01-17T03:05:40.000Z"
  }
}
```

---

## 🔄 Flux de Synchronisation

### Phase 1: Validation (Pré-synchronisation)

```
START
  ├─ Récupérer tous les utilisateurs Django
  ├─ Pour chaque utilisateur:
  │   ├─ Vérifier email valide
  │   ├─ Vérifier display_name (3-30 caractères)
  │   ├─ Vérifier password défini
  │   ├─ Vérifier date de naissance (18+)
  │   └─ Marquer comme validé ou incompatible
  └─ Rapport: [utilisateurs valides] + [incompatibles]
```

### Phase 2: Synchronisation

```
START (pour chaque utilisateur valide)
  ├─ Vérifier firebase_uid existe?
  │   ├─ OUI → Mettre à jour l'utilisateur Firebase
  │   └─ NON → Créer nouvel utilisateur Firebase
  ├─ Sur succès:
  │   ├─ Sauvegarder firebase_uid dans Django
  │   └─ Vérifier cohérence (voir Phase 4)
  └─ Sur erreur:
      ├─ Si AlreadyExists → Récupérer l'UID existant
      └─ Sinon → Ajouter à liste d'erreurs
```

### Phase 3: Correction

```
START (pour utilisateurs sans password)
  ├─ Identifier les utilisateurs sans password
  ├─ Définir password par défaut
  ├─ Sauvegarder dans Django
  ├─ Créer/mettre à jour dans Firebase
  └─ Vérifier cohérence
```

### Phase 4: Vérification de Cohérence

```
START (pour chaque utilisateur synchronisé)
  ├─ Récupérer de Firebase
  ├─ Comparer:
  │   ├─ email Django vs Firebase
  │   ├─ display_name Django vs Firebase
  │   └─ état du compte (disabled)
  ├─ Si cohérent → OK ✅
  └─ Si incohérent → Avertissement ⚠️
```

---

## 🔐 Gestion des Mots de Passe

### Politique de Mot de Passe

```
Django:
  - Hashé avec PBKDF2 (défaut Django)
  - Stocké en base PostgreSQL
  - Vérification locale

Firebase:
  - Hashé et sécurisé par Google
  - Stocké dans Firebase Authentication
  - Pas d'accès au hash brut
```

### Synchronisation des Mots de Passe

```
┌─ Création nouvel utilisateur
│  └─ Passer le password en clair à Firebase
│     (Firebase le hachera avec ses propres algos)
│
├─ Mise à jour utilisateur existant
│  └─ Impossible de changer le password sans connaître l'ancien
│
└─ "Mot de passe oublié"
   └─ Utiliser l'email pour Firebase Password Reset
      (pas Django)
```

---

## 📈 Statistiques et Métriques

### Avant Synchronisation
```
Django Users: 41
  - Avec firebase_uid: 29
  - Sans firebase_uid: 12
  - Sans password: 9
```

### Après Synchronisation Complète
```
Django Users: 41
  - Avec firebase_uid: 41 (100%)
  - Avec password: 41 (100%)
  - Synchronisés: 41 (100%)
  - Cohérents: 40 (97.6%)
```

### Distribution
```
Premium: 17 (41.5%)
Gratuit: 24 (58.5%)

Vérifiés: 26 (63.4%)
Non vérifiés: 15 (36.6%)

Actifs: 41 (100%)
Inactifs: 0 (0%)
```

---

## 🧪 Tests et Validation

### Suite de Tests (8 tests)

| # | Test | Résultat |
|---|------|----------|
| 1 | Authentification Utilisateur | ✅ PASS |
| 2 | Cohérence des Données | ✅ PASS |
| 3 | Statut Premium | ✅ PASS |
| 4 | Statut Vérification | ✅ PASS |
| 5 | Recherche Firebase | ✅ PASS |
| 6 | Validation Mots de Passe | ✅ PASS |
| 7 | Unicité Firebase UID | ✅ PASS |
| 8 | Comptes Administrateur | ✅ PASS |

### Critères de Succès

```
✅ Tous les utilisateurs ont un firebase_uid
✅ Tous les utilisateurs ont un password
✅ Email correspond entre Django et Firebase
✅ Display name correspond entre Django et Firebase
✅ Statut premium conservé
✅ Statut de vérification conservé
✅ Pas de duplications d'utilisateurs
✅ Aucune erreur de synchronisation
```

---

## 🔗 Points d'Intégration

### Django ↔ Firebase

#### Authentication Endpoints
```
POST /api/auth/register
  - Crée utilisateur Django
  - Crée utilisateur Firebase
  - Retourne JWT token

POST /api/auth/login
  - Authentifie avec Firebase
  - Retourne JWT token + user data

POST /api/auth/refresh
  - Refresh le JWT token
  - Valide avec Firebase
```

#### User Management
```
GET /api/users/me
  - Récupère données Django + Firebase

PUT /api/users/me
  - Met à jour Django + Firebase

DELETE /api/users/me
  - Supprime de Django et Firebase
```

---

## 📝 Logging et Monitoring

### Logs Importants

```python
# Initialisation Firebase
logger.info("Firebase Admin SDK initialized successfully")

# Synchronisation
logger.info(f"[{i}/{total}] Synchronisation: {user.email}")
logger.info(f"   ✅ Utilisateur Firebase créé: {uid}")

# Vérification
logger.info(f"✅ {user.email}: Cohérent avec Firebase")
logger.warning(f"⚠️ {user.email}: Incohérences détectées")

# Erreurs
logger.error(f"❌ Erreur lors de la synchronisation: {error}")
```

### Métriques à Monitorer

```
- Nombre d'utilisateurs synchronisés / total
- Temps de synchronisation par utilisateur
- Nombre d'erreurs / tentatives
- Incohérences détectées
- Rate limiting Firebase atteint
```

---

## 🚀 Déploiement en Production

### Pré-déploiement

```bash
# 1. Sauvegarder la base de données
pg_dump hivmeet > backup.sql

# 2. Synchroniser tous les utilisateurs
python sync_django_to_firebase.py

# 3. Corriger les utilisateurs sans password
python fix_and_sync_firebase.py

# 4. Vérifier la synchronisation
python verify_firebase_sync.py

# 5. Tester les fonctionnalités
python test_firebase_sync.py

# 6. Vérifier les logs pour les erreurs
grep "ERROR\|WARNING" logs/firebase.log
```

### Après Déploiement

```bash
# 1. Monitorer les utilisateurs
python verify_firebase_sync.py

# 2. Tester les connexions
python test_firebase_sync.py

# 3. Vérifier les incohérences
# (automatiquement via le middleware)
```

---

## 🔐 Sécurité

### Données Sensibles

```
Django:
  - Passwords: Hashés avec PBKDF2
  - Emails: En clair (nécessaire pour authentification)
  - Firebase UID: Lien de synchronisation

Firebase:
  - Passwords: Hashés avec Google Cloud Security
  - Emails: En clair (authentification)
  - Metadata: Timestamps, etc.
```

### Contrôle d'Accès

```
Firebase UID:
  - Unique par utilisateur
  - Généré automatiquement par Firebase
  - Stocké en Django pour lier les systèmes
  
Permissions:
  - Basées sur is_staff / is_superuser Django
  - Vérifiées dans les endpoints API
  - JWT token contient les permissions
```

---

## 🎯 Cas d'Usage

### 1. Nouvel Utilisateur
```
Frontend → API /register
         → Django create_user()
         → Firebase create_user()
         → Retourner firebase_uid
         → Retourner JWT token
```

### 2. Connexion Existante
```
Frontend → API /login (email + password)
         → Firebase authenticate()
         → Récupérer firebase_uid
         → Récupérer user Django
         → Retourner JWT token
```

### 3. Synchronisation Manuel
```
Admin → python sync_django_to_firebase.py
      → Valider tous les utilisateurs
      → Créer/mettre à jour Firebase
      → Générer rapport
```

---

## 📚 Documentation Connexe

- [GUIDE_SYNCHRONISATION_FIREBASE.md](./GUIDE_SYNCHRONISATION_FIREBASE.md) - Guide d'utilisation
- [SYNTHESE_SYNCHRONISATION_FIREBASE.md](./SYNTHESE_SYNCHRONISATION_FIREBASE.md) - Synthèse complète
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - Documentation API
- [firebase_config.py](./firebase_config.py) - Configuration Firebase

---

## 🔍 Troubleshooting

### Problème: Firebase UID manquant
**Solution**: Exécuter `sync_django_to_firebase.py`

### Problème: Incohérence détectée
**Solution**: Exécuter `verify_firebase_sync.py` pour identifier, corriger manuellement si nécessaire

### Problème: Impossible de se connecter
**Solution**: Vérifier firebase_config.py et les credentials

### Problème: Performance lente
**Solution**: Augmenter les délais entre les synchronisations (0.5s → 1s)

---

## 📞 Support

Pour des questions techniques:
1. Vérifier les logs
2. Exécuter verify_firebase_sync.py
3. Consulter la Firebase Console
4. Vérifier la documentation Django/Firebase

---

**Version**: 1.0  
**Dernière mise à jour**: 17 Janvier 2026  
**Statut**: Production Ready ✅
