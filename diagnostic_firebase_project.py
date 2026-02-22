#!/usr/bin/env python3
"""
Script de diagnostic Firebase - Vérifier quel projet Firebase est utilisé

Ce script vérifie:
1. Quel projet Firebase est configuré
2. Quel projet utilisateur est connecté dans la console
3. Si les utilisateurs créés sont dans le bon projet
4. Les configurations d'authentification
"""

import os
import django
from pathlib import Path
import json

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

import firebase_admin
from firebase_admin import credentials, auth
import logging

logger = logging.getLogger('firebase_diagnostic')
logging.basicConfig(level=logging.INFO)


def check_credentials():
    """Vérifier les credentials Firebase"""
    
    print("\n" + "="*70)
    print("🔍 DIAGNOSTIC FIREBASE - VÉRIFICATION DES CREDENTIALS")
    print("="*70)
    
    print("\n📋 CREDENTIALS CHARGÉES:")
    print("-" * 70)
    
    # Vérifier fichier credentials
    credentials_path = Path('credentials/hivmeet_firebase_credentials.json')
    
    if credentials_path.exists():
        print(f"✅ Fichier credentials trouvé: {credentials_path}")
        
        with open(credentials_path, 'r') as f:
            creds = json.load(f)
            
        print(f"\n   Project ID: {creds.get('project_id')}")
        print(f"   Client Email: {creds.get('client_email')}")
        print(f"   Client ID: {creds.get('client_id')}")
    else:
        print(f"❌ Fichier credentials manquant: {credentials_path}")
        return False
    
    return creds


def check_firebase_init(creds):
    """Vérifier que Firebase est initialisé avec les bonnes credentials"""
    
    print("\n📋 FIREBASE ADMIN SDK:")
    print("-" * 70)
    
    try:
        # Vérifier l'app Firebase initialisée
        if firebase_admin._apps:
            app = firebase_admin._apps[0]
            print(f"✅ Firebase Admin SDK initialisé")
            print(f"   Credential Project: {creds.get('project_id')}")
            
            # Obtenir le projet utilisé
            try:
                # Essayer de récupérer un utilisateur (même inexistant) pour valider la connexion
                auth.get_user('nonexistent-uid')
            except Exception as e:
                error_msg = str(e)
                # C'est normal que l'utilisateur n'existe pas
                if 'not found' in error_msg or 'INVALID_USER_ID' in error_msg:
                    print(f"✅ Connexion à Firebase Authentication validée")
                else:
                    print(f"⚠️ Erreur lors de la validation: {error_msg}")
            
            return True
        else:
            print(f"❌ Firebase Admin SDK non initialisé")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def list_firebase_users(creds):
    """Lister les utilisateurs Firebase"""
    
    print("\n📋 UTILISATEURS FIREBASE:")
    print("-" * 70)
    
    try:
        # Récupérer les utilisateurs
        page = auth.list_users(page_size=100)
        
        if not page.users:
            print(f"❌ AUCUN UTILISATEUR TROUVÉ DANS FIREBASE!")
            print(f"\n⚠️ Cela signifie:")
            print(f"   1. Le projet Firebase ({creds.get('project_id')}) n'a pas d'utilisateurs")
            print(f"   2. Les utilisateurs créés sont dans un AUTRE projet")
            print(f"   3. Les credentials ne correspondent PAS au bon projet")
            return []
        
        print(f"✅ {len(page.users)} utilisateurs trouvés dans Firebase")
        
        for user in page.users[:5]:
            print(f"\n   - {user.email}")
            print(f"     UID: {user.uid}")
            print(f"     Display Name: {user.display_name}")
        
        if len(page.users) > 5:
            print(f"\n   ... et {len(page.users) - 5} autres utilisateurs")
        
        return page.users
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des utilisateurs: {e}")
        return []


def compare_django_firebase():
    """Comparer les utilisateurs Django vs Firebase"""
    
    print("\n📋 COMPARAISON DJANGO vs FIREBASE:")
    print("-" * 70)
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    django_users = User.objects.all()
    
    print(f"✅ Utilisateurs Django: {django_users.count()}")
    
    # Essayer de trouver les UIDs créés dans Firebase
    try:
        found_in_firebase = []
        not_found_in_firebase = []
        
        for user in django_users[:10]:  # Vérifier les 10 premiers
            if user.firebase_uid:
                try:
                    firebase_user = auth.get_user(user.firebase_uid)
                    found_in_firebase.append(user)
                    print(f"\n   ✅ {user.email} trouvé dans Firebase")
                    print(f"      Firebase UID: {user.firebase_uid}")
                except Exception as e:
                    not_found_in_firebase.append(user)
                    print(f"\n   ❌ {user.email} NOT FOUND dans Firebase")
                    print(f"      Firebase UID (Django): {user.firebase_uid}")
                    print(f"      Erreur: {e}")
        
        if not_found_in_firebase:
            print(f"\n⚠️ {len(not_found_in_firebase)} utilisateurs Django NOT FOUND dans Firebase!")
            print(f"\n🔴 PROBLÈME IDENTIFIÉ:")
            print(f"   Les utilisateurs ont été créés dans un AUTRE projet Firebase!")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


def check_console_project():
    """Vérifier le projet visible dans la console"""
    
    print("\n📋 PROJET FIREBASE À VÉRIFIER:")
    print("-" * 70)
    
    creds_path = Path('credentials/hivmeet_firebase_credentials.json')
    if creds_path.exists():
        with open(creds_path, 'r') as f:
            creds = json.load(f)
        
        project_id = creds.get('project_id')
        
        print(f"\n🔍 Le projet Firebase configuré est: {project_id}")
        print(f"\n📋 POUR VÉRIFIER DANS LA CONSOLE:")
        print(f"   1. Allez sur: https://console.firebase.google.com/")
        print(f"   2. Vérifiez que vous êtes dans le projet: {project_id}")
        print(f"   3. Si NON, sélectionnez ce projet dans le menu déroulant")
        print(f"   4. Allez dans: Authentication > Users")
        print(f"   5. Vous devriez voir les 41 utilisateurs créés")
        
        print(f"\n❓ QUESTIONS À VOUS POSER:")
        print(f"   1. Êtes-vous connecté à Google avec le bon compte?")
        print(f"   2. Avez-vous accès au projet {project_id}?")
        print(f"   3. Êtes-vous dans le bon projet Firebase?")


def main():
    """Fonction principale"""
    
    print("\n" + "="*70)
    print("🔥 DIAGNOSTIC FIREBASE COMPLET")
    print("="*70)
    print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Vérifier les credentials
    creds = check_credentials()
    if not creds:
        print("\n❌ Impossible de continuer sans credentials")
        return False
    
    # 2. Vérifier Firebase init
    check_firebase_init(creds)
    
    # 3. Lister les utilisateurs Firebase
    firebase_users = list_firebase_users(creds)
    
    # 4. Comparer Django vs Firebase
    compare_django_firebase()
    
    # 5. Informations sur le projet
    check_console_project()
    
    print("\n" + "="*70)
    print("DIAGNOSTIC TERMINÉ")
    print("="*70)


if __name__ == '__main__':
    from datetime import datetime
    main()
