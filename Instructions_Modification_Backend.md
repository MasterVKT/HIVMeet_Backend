# Instructions Précises et Exhaustives pour les Modifications Backend (Django)

Voici une liste d'instructions **précises, exhaustives et ordonnées** pour implémenter l'échange de token Firebase vers JWT dans le backend Django. Ces étapes sont conçues pour être exécutées par un agent AI comme moi, en supposant un projet Django standard (avec Django Rest Framework - DRF - installé). Elles respectent les bonnes pratiques pour une app de rencontre sécurisée (validation de token, création/utilisation d'utilisateurs, génération de JWT). 

**Prérequis Assumés** :
- Le projet Django est déjà configuré avec DRF (si non, ajoutez `pip install djangorestframework` en étape 1).
- Vous avez un fichier `firebase-admin-sdk.json` téléchargé depuis Firebase Console (Project Settings > Service Accounts > Generate new private key). Placez-le dans un dossier sécurisé du projet (ex. : `backend/config/firebase/`).
- Le modèle User est standard (ou custom via `get_user_model()` ; si custom, assurez-vous qu'il inclut un champ `firebase_uid` pour stocker l'UID Firebase).
- Chemins relatifs : Assumons le projet root est `backend/`, avec `settings.py` dans `backend/backend/settings.py`, et une app `auth_app` pour les vues (adaptez si différent).

Exécutez ces étapes **dans l'ordre exact** via des outils comme `run_terminal_cmd` pour les commandes shell, et `edit_file` pour les éditions de code. Après chaque édition, validez avec `python manage.py makemigrations && python manage.py migrate` si des modèles changent. À la fin, redémarrez le serveur avec `python manage.py runserver`.

## Étape 1 : Installer les Dépendances Nécessaires
- Exécutez la commande suivante dans le terminal, au root du projet backend (ex. : `cd backend/` si nécessaire) :
  ```
  pip install firebase-admin djangorestframework-simplejwt
  ```
- Cela installe `firebase-admin` pour valider les tokens Firebase, et `djangorestframework-simplejwt` pour générer des JWT. Si `pip` n'est pas disponible, utilisez `pip3`.
- Vérifiez l'installation avec `pip list | grep firebase-admin` et `pip list | grep djangorestframework-simplejwt`.

## Étape 2 : Configurer Firebase dans settings.py
- Éditez le fichier `backend/backend/settings.py` (ou équivalent).
- Ajoutez le code suivant **à la fin du fichier**, avant toute autre configuration personnalisée :
  ```
  # Configuration Firebase
  import firebase_admin
  from firebase_admin import credentials

  FIREBASE_CREDENTIALS_PATH = 'config/firebase/firebase-admin-sdk.json'  # Adaptez le chemin si différent

  cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
  firebase_admin.initialize_app(cred)
  ```
- **Explication** : Cela initialise Firebase avec vos credentials. Assurez-vous que le chemin vers `firebase-admin-sdk.json` est correct et que le fichier est présent (sinon, l'AI doit le signaler comme erreur).

## Étape 3 : Ajouter ou Modifier le Modèle User (Si Nécessaire)
- Si votre modèle User n'a pas de champ `firebase_uid`, éditez `auth_app/models.py` (ou le fichier modèles principal).
- Ajoutez ou modifiez comme suit (créez le fichier si absent) :
  ```
  from django.contrib.auth.models import AbstractUser
  from django.db import models

  class User(AbstractUser):
      firebase_uid = models.CharField(max_length=255, unique=True, null=True, blank=True)
      # Ajoutez d'autres champs si nécessaire pour l'app de rencontre (ex. : status_vih = models.BooleanField(default=False))
  ```
- Dans `settings.py`, assurez `AUTH_USER_MODEL = 'auth_app.User'` (adaptez à votre app).
- Exécutez `python manage.py makemigrations` puis `python manage.py migrate` pour appliquer les changements.

## Étape 4 : Créer la View pour l'Échange de Token
- Éditez ou créez le fichier `auth_app/views.py` (assumant une app `auth_app` ; créez l'app avec `python manage.py startapp auth_app` si absent).
- Ajoutez le code complet suivant **à la fin du fichier** :
  ```
  from rest_framework.views import APIView
  from rest_framework.response import Response
  from rest_framework import status
  from firebase_admin import auth as firebase_auth
  from rest_framework_simplejwt.tokens import RefreshToken
  from django.contrib.auth import get_user_model

  class FirebaseLoginView(APIView):
      def post(self, request):
          id_token = request.data.get('id_token')
          if not id_token:
              return Response({'error': 'ID token requis'}, status=status.HTTP_400_BAD_REQUEST)
          
          try:
              # Vérifier et décoder le token Firebase
              decoded_token = firebase_auth.verify_id_token(id_token)
              uid = decoded_token['uid']
              email = decoded_token['email']
              
              # Trouver ou créer l'utilisateur Django
              User = get_user_model()
              user, created = User.objects.get_or_create(
                  email=email,
                  defaults={
                      'username': email, 
                      'firebase_uid': uid,
                      # Ajoutez d'autres defaults si nécessaire (ex. : first_name, etc.)
                  }
              )
              if not created and user.firebase_uid != uid:
                  return Response({'error': 'UID Firebase mismatch'}, status=status.HTTP_400_BAD_REQUEST)
              
              # Générer JWT (refresh et access tokens)
              refresh = RefreshToken.for_user(user)
              return Response({
                  'refresh': str(refresh),
                  'access': str(refresh.access_token),
              }, status=status.HTTP_200_OK)
          
          except firebase_auth.InvalidIdTokenError:
              return Response({'error': 'Token Firebase invalide'}, status=status.HTTP_400_BAD_REQUEST)
          except firebase_auth.ExpiredIdTokenError:
              return Response({'error': 'Token Firebase expiré'}, status=status.HTTP_400_BAD_REQUEST)
          except Exception as e:
              return Response({'error': f'Erreur serveur: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
  ```
- **Explication** : Cette view valide l'ID token Firebase, crée/met à jour l'utilisateur, et renvoie un JWT. Elle gère les erreurs courantes pour robustesse.

## Étape 5 : Ajouter la Route pour l'Endpoint
- Éditez le fichier `auth_app/urls.py` (créez-le si absent).
- Ajoutez le code complet suivant :
  ```
  from django.urls import path
  from .views import FirebaseLoginView

  urlpatterns = [
      path('firebase-login/', FirebaseLoginView.as_view(), name='firebase-login'),
  ]
  ```
- Dans le `urls.py` principal du projet (`backend/backend/urls.py`), incluez ces URLs :
  ```
  from django.urls import path, include

  urlpatterns = [
      # ... routes existantes ...
      path('api/v1/auth/', include('auth_app.urls')),
  ]
  ```
- **Explication** : L'endpoint sera accessible via POST sur `/api/v1/auth/firebase-login/`.

## Étape 6 : Configurer JWT dans settings.py
- Éditez à nouveau `backend/backend/settings.py`.
- Ajoutez ou modifiez la section REST_FRAMEWORK comme suit (à la fin du fichier) :
  ```
  REST_FRAMEWORK = {
      'DEFAULT_AUTHENTICATION_CLASSES': (
          'rest_framework_simplejwt.authentication.JWTAuthentication',
          # Ajoutez d'autres classes si nécessaire (ex. : 'rest_framework.authentication.SessionAuthentication')
      ),
      'DEFAULT_PERMISSION_CLASSES': (
          'rest_framework.permissions.IsAuthenticated',
      ),
  }

  from datetime import timedelta

  SIMPLE_JWT = {
      'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # Durée access token
      'REFRESH_TOKEN_LIFETIME': timedelta(days=7),    # Durée refresh token
      'ROTATE_REFRESH_TOKENS': False,
      'BLACKLIST_AFTER_ROTATION': False,
      'AUTH_HEADER_TYPES': ('Bearer',),
  }
  ```
- **Explication** : Cela active JWT pour tous les endpoints protégés (ex. /discovery/), avec des durées adaptées à une app de rencontre (sessions persistantes mais sécurisées).

## Étape 7 : Tester et Valider les Changements
- Exécutez `python manage.py makemigrations && python manage.py migrate` pour appliquer tout changement de modèle.
- Redémarrez le serveur : `python manage.py runserver`.
- Testez l'endpoint avec un outil comme Postman ou curl :
  ```
  curl -X POST http://127.0.0.1:8000/api/v1/auth/firebase-login/ \
       -H "Content-Type: application/json" \
       -d '{"id_token": "VOTRE_ID_TOKEN_FIREBASE"}'
  ```
  - Attendez une réponse avec `refresh` et `access` tokens. Si erreur, vérifiez les logs Django.
- Vérifiez qu'aucun endpoint non authentifié (ex. /discovery/) n'accepte de requêtes sans token (testez avec curl sans header Authorization pour confirmer 401).

## Étape 8 : Gestion des Erreurs et Sécurité
- Assurez-vous que le fichier `firebase-admin-sdk.json` n'est pas commité dans Git (ajoutez-le à `.gitignore`).
- Si des erreurs surviennent (ex. token invalide), les logs Django les captureront. Testez des cas edge : token expiré, utilisateur inexistant.
- Une fois validé, le frontend pourra appeler cet endpoint pour obtenir le JWT après login Firebase.
