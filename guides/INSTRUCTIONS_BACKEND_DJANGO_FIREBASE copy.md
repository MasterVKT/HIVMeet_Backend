# 🔧 Instructions Détaillées Backend Django - HIVMeet Firebase Exchange

## 🎯 Problème Identifié

**L'endpoint `/api/v1/auth/firebase-exchange/` retourne 404** et **les tokens Firebase sont rejetés avec 401**. Le backend Django doit être configuré pour :
1. Exposer l'endpoint d'échange de tokens
2. Valider les tokens Firebase Auth
3. Générer des tokens JWT Django
4. Créer/récupérer les utilisateurs

## 📋 Architecture de la Solution

### **Flux d'Authentification**
```
Flutter App → Token Firebase → Django Endpoint → Validation Firebase → User Django → JWT Django → API Calls
```

## 🛠️ Instructions d'Implémentation

### **1. Structure des Dossiers et Fichiers**

**Créer/modifier ces fichiers dans le projet Django :**
- `firebase_config.py` (nouveau fichier à la racine du projet)
- `views.py` (modification - ajouter la vue firebase_token_exchange)
- `urls.py` de l'application (modification - ajouter la route)
- `urls.py` principal (vérification/modification du routing)
- `.env` (modification - ajouter variables Firebase)
- `requirements.txt` (modification - ajouter firebase-admin)

### **2. Configuration Firebase Admin SDK (firebase_config.py)**

**Localisation :** À la racine du projet Django (même niveau que manage.py)

**Logique détaillée :**
1. **Importer les modules nécessaires :**
   - `firebase_admin` pour l'initialisation
   - `credentials` de firebase_admin pour l'authentification
   - `os` pour les variables d'environnement
   - `settings` de django.conf pour la configuration

2. **Fonction d'initialisation Firebase :**
   - Vérifier si Firebase Admin SDK n'est pas déjà initialisé (`firebase_admin._apps`)
   - Si pas initialisé :
     - **Option A (Production)** : Utiliser un fichier service account JSON
       - Récupérer le chemin du fichier via `settings.FIREBASE_SERVICE_ACCOUNT_KEY`
       - Vérifier que le fichier existe avec `os.path.exists()`
       - Créer les credentials avec `credentials.Certificate(service_account_path)`
     - **Option B (Développement)** : Utiliser les variables d'environnement
       - Construire un dictionnaire de configuration avec les clés :
         - `type`: "service_account"
         - `project_id`: récupéré de l'environnement ou hardcodé "hivmeet-f76f8"
         - `private_key_id`: récupéré via `os.getenv('FIREBASE_PRIVATE_KEY_ID')`
         - `private_key`: récupéré via `os.getenv('FIREBASE_PRIVATE_KEY')` avec remplacement `\\n` → `\n`
         - `client_email`: récupéré via `os.getenv('FIREBASE_CLIENT_EMAIL')`
         - `client_id`: récupéré via `os.getenv('FIREBASE_CLIENT_ID')`
         - `auth_uri`: "https://accounts.google.com/o/oauth2/auth"
         - `token_uri`: "https://oauth2.googleapis.com/token"
         - `auth_provider_x509_cert_url`: "https://www.googleapis.com/oauth2/v1/certs"
         - `client_x509_cert_url`: récupéré via `os.getenv('FIREBASE_CLIENT_X509_CERT_URL')`
       - Créer les credentials avec `credentials.Certificate(config_dict)`
     - Initialiser Firebase avec `firebase_admin.initialize_app(cred)`

3. **Appel de la fonction :**
   - Exécuter la fonction d'initialisation au niveau module (pas dans une fonction)

### **3. Vue Firebase Token Exchange (views.py)**

**Localisation :** Dans le fichier `views.py` de votre application Django

**Imports nécessaires :**
- `api_view, permission_classes` de rest_framework.decorators
- `AllowAny` de rest_framework.permissions
- `Response` de rest_framework.response
- `status` de rest_framework
- `RefreshToken` de rest_framework_simplejwt.tokens
- `auth` de firebase_admin
- `User` de django.contrib.auth.models
- `transaction` de django.db
- `logging` de Python standard

**Décorateurs de la fonction :**
- `@api_view(['POST'])` pour accepter uniquement les requêtes POST
- `@permission_classes([AllowAny])` pour permettre l'accès sans authentification préalable

**Nom de la fonction :** `firebase_token_exchange`

**Paramètre :** `request` (objet requête Django REST Framework)

**Logique détaillée de la fonction :**

1. **Récupération et validation des paramètres d'entrée :**
   - Extraire `firebase_token` de `request.data.get('firebase_token')`
   - Si `firebase_token` est None ou vide :
     - Retourner Response avec status 400
     - Message d'erreur : "firebase_token est requis"
     - Code d'erreur : "MISSING_TOKEN"

2. **Validation du token Firebase :**
   - Logger l'information : "🔄 Tentative d'échange token Firebase..."
   - Dans un bloc try/except :
     - Appeler `auth.verify_id_token(firebase_token)` pour décoder le token
     - Si succès : Logger "✅ Token Firebase valide pour UID: {uid}"
     - Si exception : 
       - Logger "❌ Token Firebase invalide: {erreur}"
       - Retourner Response avec status 401
       - Message : "Token Firebase invalide ou expiré"
       - Code : "INVALID_FIREBASE_TOKEN"

3. **Extraction des informations utilisateur :**
   - Récupérer `firebase_uid` du token décodé (clé 'uid')
   - Récupérer `email` du token décodé (clé 'email')
   - Récupérer `name` du token décodé (clé 'name', défaut '')
   - Récupérer `email_verified` du token décodé (clé 'email_verified', défaut False)
   - Si email est None ou vide :
     - Retourner Response avec status 400
     - Message : "Email requis dans le token Firebase"
     - Code : "MISSING_EMAIL"

4. **Gestion de l'utilisateur Django :**
   - Dans un bloc `transaction.atomic()` :
     - Appeler `User.objects.get_or_create()` avec :
       - Critère de recherche : `email=email`
       - Valeurs par défaut si création :
         - `username=email`
         - `first_name=nom.split(' ')[0]` si nom existe, sinon ''
         - `last_name=' '.join(nom.split(' ')[1:])` si plusieurs mots dans nom, sinon ''
         - `is_active=True`
     - La méthode retourne `(user, created)` :
       - Si `created=True` : Logger "👤 Nouvel utilisateur créé: {email}"
       - Si `created=False` : Logger "👤 Utilisateur existant: {email}"

5. **Génération des tokens JWT Django :**
   - Créer un RefreshToken pour l'utilisateur : `refresh = RefreshToken.for_user(user)`
   - Extraire l'access token : `access_token = refresh.access_token`
   - Logger "🎯 Tokens JWT générés pour utilisateur ID: {user.id}"

6. **Réponse de succès :**
   - Retourner Response avec status 200 contenant :
     - `access`: access token converti en string
     - `refresh`: refresh token converti en string
     - `user`: dictionnaire avec :
       - `id`: ID de l'utilisateur Django
       - `email`: email de l'utilisateur
       - `first_name`: prénom
       - `last_name`: nom de famille
       - `firebase_uid`: UID Firebase original
       - `email_verified`: statut de vérification email

7. **Gestion des erreurs globales :**
   - Entourer toute la logique dans un try/except général
   - En cas d'exception non prévue :
     - Logger "💥 Erreur inattendue dans firebase_token_exchange: {erreur}"
     - Retourner Response avec status 500
     - Message : "Erreur interne du serveur"
     - Code : "INTERNAL_ERROR"

### **4. Configuration des URLs**

**A. URLs de l'application (yourapp/urls.py)**

**Localisation :** Dans le dossier de votre application Django

**Imports nécessaires :**
- `path` de django.urls
- `views` du module local (`. import views`)

**Structure de urlpatterns :**
- Créer ou modifier la liste `urlpatterns`
- Ajouter une entrée : `path('auth/firebase-exchange/', views.firebase_token_exchange, name='firebase-exchange')`
- L'URL relative sera : `auth/firebase-exchange/`
- La vue associée : `views.firebase_token_exchange`
- Le nom de la route : `firebase-exchange`

**B. URLs principal (myproject/urls.py)**

**Localisation :** À la racine du projet Django (même dossier que settings.py)

**Vérification nécessaire :**
- Confirmer la présence de `path('api/v1/', include('yourapp.urls'))` dans urlpatterns
- Remplacer 'yourapp' par le nom réel de votre application Django
- Si cette ligne n'existe pas, l'ajouter

**Résultat final :** L'URL complète sera accessible à `/api/v1/auth/firebase-exchange/`

### **5. Variables d'Environnement (.env)**

**Localisation :** Fichier `.env` à la racine du projet Django

**Variables à ajouter :**

1. **FIREBASE_PRIVATE_KEY_ID**
   - Valeur : L'ID de la clé privée de votre service account Firebase
   - Format : Chaîne alphanumériqueFormat exemple : "1a2b3c4d5e6f..."

2. **FIREBASE_PRIVATE_KEY**
   - Valeur : La clé privée complète du service account
   - Format : Commencer par "-----BEGIN PRIVATE KEY-----\n" et finir par "\n-----END PRIVATE KEY-----\n"
   - Important : Utiliser des échappements \n pour les retours à la ligne

3. **FIREBASE_CLIENT_EMAIL**
   - Valeur : L'email du service account Firebase
   - Format : "firebase-adminsdk-xxxxx@hivmeet-f76f8.iam.gserviceaccount.com"

4. **FIREBASE_CLIENT_ID**
   - Valeur : L'ID client du service account
   - Format : Nombre à 21 chiffres

5. **FIREBASE_CLIENT_X509_CERT_URL**
   - Valeur : URL du certificat X509
   - Format : "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40hivmeet-f76f8.iam.gserviceaccount.com"

**Option alternative :** Utiliser un fichier JSON de service account et définir `FIREBASE_SERVICE_ACCOUNT_KEY` avec le chemin vers ce fichier.

### **6. Dépendances (requirements.txt)**

**Ajouter la ligne :**
```
firebase-admin>=6.0.0
```

**Installation :**
Exécuter `pip install firebase-admin` dans l'environnement virtuel Django

### **7. Configuration Django Settings**

**Vérifications dans settings.py :**

1. **INSTALLED_APPS :** Confirmer que votre application Django est listée
2. **Optionnel :** Ajouter `FIREBASE_SERVICE_ACCOUNT_KEY = '/path/to/service-account.json'` si vous utilisez un fichier JSON

### **8. Tests de Validation**

**A. Test d'existence de l'endpoint :**
- Commande : `python manage.py show_urls | grep firebase`
- Résultat attendu : `/api/v1/auth/firebase-exchange/` doit apparaître

**B. Test avec curl :**
```bash
curl -X POST http://localhost:8000/api/v1/auth/firebase-exchange/ \
  -H "Content-Type: application/json" \
  -d '{"firebase_token": "test"}'
```
- Résultat attendu : Status 400 ou 401 (pas 404)

**C. Test avec token réel :**
- Utiliser un vrai token Firebase depuis Flutter
- Résultat attendu : Status 200 avec tokens JWT en réponse

### **9. Logs et Debugging**

**Configuration des logs Django :**
- Assurez-vous que le logging est configuré pour voir les messages d'info et d'erreur
- Les logs à surveiller :
  - "🔄 Tentative d'échange token Firebase..."
  - "✅ Token Firebase valide pour UID: ..."
  - "👤 Utilisateur existant/créé: ..."
  - "🎯 Tokens JWT générés pour utilisateur ID: ..."

### **10. Ordre d'Implémentation Recommandé**

1. **Installer firebase-admin** (`pip install firebase-admin`)
2. **Créer firebase_config.py** avec la logique d'initialisation
3. **Ajouter variables d'environnement** dans .env
4. **Implémenter la vue firebase_token_exchange** dans views.py
5. **Configurer les URLs** (app et principal)
6. **Redémarrer le serveur Django**
7. **Tester avec curl** puis avec Flutter

## 🎯 Résultat Final Attendu

Après implémentation complète :
- ✅ L'endpoint `/api/v1/auth/firebase-exchange/` retourne 200 OK avec un token Firebase valide
- ✅ Les tokens JWT Django sont générés et fonctionnent avec l'API Discovery
- ✅ L'application Flutter peut s'authentifier et accéder aux données
- ✅ Plus d'erreurs 404 ou 401 dans les logs

## 📊 Logs de Succès Attendus

**Côté Django :**
```
🔄 Tentative d'échange token Firebase...
✅ Token Firebase valide pour UID: eUcVrZFynGNuVTN1FdrMURQjjSo1
👤 Utilisateur existant: vekout@yahoo.fr
🎯 Tokens JWT générés pour utilisateur ID: 1
POST /api/v1/auth/firebase-exchange/ 200 OK
GET /api/v1/discovery/?page=1&per_page=20 200 OK
```

**Côté Flutter :**
```
🔍 DEBUG: Utilisateur Firebase: vekout@yahoo.fr
🔑 Token Firebase récupéré: eyJhbGciOiJSUzI1NiIs...
🔄 Tentative échange token Firebase...
✅ Échange token réussi
✅ Token Django JWT utilisé
🚀 REQUEST: GET http://10.0.2.2:8000/api/v1/discovery/
✅ RESPONSE: 200 OK
```

Cette implémentation crée une authentification robuste et sécurisée entre Firebase Auth et Django JWT pour l'application HIVMeet.

---

## 📝 Notes Importantes

1. **Sécurité :** Les clés Firebase doivent être gardées secrètes et ne jamais être commitées dans le repository
2. **Environnement :** Utilisez des variables d'environnement différentes pour développement/production
3. **Monitoring :** Surveillez les logs pour détecter les tentatives d'authentification échouées
4. **Performance :** L'initialisation Firebase n'est faite qu'une seule fois au démarrage du serveur
5. **Gestion d'erreurs :** Toutes les erreurs sont loggées et retournent des codes d'erreur appropriés 