#!/usr/bin/env python
"""
Script de tests complets HIVMeet Backend - Validation finale.
"""
import os
import sys
import subprocess
import django
import traceback
from datetime import datetime
import requests
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

def run_command(command, description="", timeout=30):
    """Exécute une commande avec timeout."""
    print(f"🔧 {description}")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        print(f"✅ {description} - SUCCÈS")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ÉCHEC")
        print(f"Erreur: {e.stderr}")
        return False, e.stderr
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT")
        return False, "Timeout"

def test_django_setup():
    """Test de configuration Django."""
    print("\n🔧 TEST CONFIGURATION DJANGO")
    print("-" * 35)
    
    try:
        django.setup()
        print("✅ Django setup successful")
        
        from django.conf import settings
        print(f"✅ Debug mode: {settings.DEBUG}")
        print(f"✅ Database: {settings.DATABASES['default']['ENGINE']}")
        
        return True
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

def test_database_migration():
    """Test des migrations de base de données."""
    print("\n🗃️ TEST MIGRATIONS BASE DE DONNÉES")
    print("-" * 40)
    
    success, output = run_command(
        "python manage.py migrate --check", 
        "Vérification migrations",
        timeout=60
    )
    
    if not success:
        print("⚠️ Migrations manquantes, exécution...")
        success, output = run_command(
            "python manage.py migrate", 
            "Exécution migrations",
            timeout=120
        )
    
    return success

def test_static_files():
    """Test de collecte des fichiers statiques."""
    print("\n📁 TEST FICHIERS STATIQUES")
    print("-" * 30)
    
    success, output = run_command(
        "python manage.py collectstatic --noinput", 
        "Collecte fichiers statiques",
        timeout=60
    )
    
    return success

def test_models_creation():
    """Test de création d'objets dans tous les modèles."""
    print("\n📊 TEST CRÉATION MODÈLES")
    print("-" * 30)
    
    try:
        from django.contrib.auth import get_user_model
        from profiles.models import Profile
        from matching.models import Like, Match
        from messaging.models import Message
        from subscriptions.models import SubscriptionPlan
        from resources.models import Category, Resource
        
        User = get_user_model()
        
        # Test création utilisateur
        test_user, created = User.objects.get_or_create(
            email='test@hivmeet.com',
            defaults={
                'display_name': 'Test User',
                'birth_date': '1990-01-01'
            }
        )
        print("✅ User model - création OK")
        
        # Test profil (créé automatiquement via signal)
        if hasattr(test_user, 'profile'):
            print("✅ Profile model - création automatique OK")
        else:
            print("❌ Profile model - signal non fonctionnel")
            return False
        
        # Test plan d'abonnement
        plan, created = SubscriptionPlan.objects.get_or_create(
            plan_id='test_plan',
            defaults={
                'name': 'Test Plan',
                'name_en': 'Test Plan',
                'name_fr': 'Plan Test',
                'description': 'Plan de test',
                'description_en': 'Test plan',
                'description_fr': 'Plan de test',
                'price': 9.99,
                'currency': 'EUR',
                'billing_interval': 'month'
            }
        )
        print("✅ SubscriptionPlan model - création OK")
        
        # Test catégorie ressource
        category, created = Category.objects.get_or_create(
            slug='test-category',
            defaults={
                'name': 'Test Category',
                'name_en': 'Test Category',
                'name_fr': 'Catégorie Test'
            }
        )
        print("✅ Category model - création OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Test modèles failed: {e}")
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test des endpoints API principaux."""
    print("\n🌐 TEST ENDPOINTS API")
    print("-" * 25)
    
    # Démarrer le serveur de test en arrière-plan
    print("🚀 Démarrage serveur de test...")
    
    try:
        # Test si le serveur est déjà en cours
        response = requests.get('http://localhost:8000/api/v1/', timeout=5)
        server_running = True
        print("✅ Serveur déjà en cours")
    except:
        server_running = False
        print("ℹ️ Démarrage du serveur nécessaire")
    
    if not server_running:
        # Ici on pourrait démarrer le serveur, mais pour simplifier on suppose qu'il doit être démarré manuellement
        print("⚠️ Veuillez démarrer le serveur: python manage.py runserver")
        return False
    
    # Test endpoints de base
    endpoints_to_test = [
        ('/', 'Root API'),
        ('/swagger/', 'Swagger Documentation'),
        ('/admin/', 'Admin Interface'),
    ]
    
    success_count = 0
    for endpoint, description in endpoints_to_test:
        try:
            response = requests.get(f'http://localhost:8000{endpoint}', timeout=10)
            if response.status_code in [200, 301, 302]:
                print(f"✅ {description} - {response.status_code}")
                success_count += 1
            else:
                print(f"❌ {description} - {response.status_code}")
        except Exception as e:
            print(f"❌ {description} - Erreur: {e}")
    
    return success_count == len(endpoints_to_test)

def test_premium_features():
    """Test des fonctionnalités premium."""
    print("\n🌟 TEST FONCTIONNALITÉS PREMIUM")
    print("-" * 35)
    
    try:
        from authentication.models import User
        from subscriptions.services import PremiumFeatureService
        
        # Créer un utilisateur premium de test
        premium_user = User(
            email='premium@test.com',
            display_name='Premium User',
            birth_date='1990-01-01',
            is_premium=True
        )
        
        # Test des propriétés premium
        tests = [
            ('premium_features', 'Premium features property'),
            ('can_send_super_like', 'Can send super like'),
            ('can_use_boost', 'Can use boost'),
            ('can_send_media_messages', 'Can send media messages'),
            ('can_make_calls', 'Can make calls'),
            ('can_see_who_liked', 'Can see who liked')
        ]
        
        success_count = 0
        for property_name, description in tests:
            if hasattr(premium_user, property_name):
                print(f"✅ {description}")
                success_count += 1
            else:
                print(f"❌ {description} - Propriété manquante")
        
        return success_count == len(tests)
        
    except Exception as e:
        print(f"❌ Test premium features failed: {e}")
        return False

def test_firebase_integration():
    """Test de l'intégration Firebase."""
    print("\n🔥 TEST INTÉGRATION FIREBASE")
    print("-" * 35)
    
    try:
        from hivmeet_backend.firebase_service import firebase_service
        
        # Test d'accès aux services
        auth_service = firebase_service.auth
        db_service = firebase_service.db
        bucket_service = firebase_service.bucket
        
        print("✅ Firebase Auth service accessible")
        print("✅ Firebase Firestore service accessible")
        print("✅ Firebase Storage service accessible")
        
        # Test de vérification de token invalide (doit lever une exception)
        try:
            firebase_service.verify_id_token("invalid_token")
            print("❌ Token verification should fail with invalid token")
            return False
        except ValueError:
            print("✅ Token verification works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Firebase integration test failed: {e}")
        return False

def generate_test_report(results):
    """Génère un rapport de test complet."""
    print("\n" + "=" * 60)
    print("📊 RAPPORT DE TESTS COMPLET")
    print("=" * 60)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"⏰ Date: {timestamp}")
    print(f"🎯 Réussite: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
    print("\n📋 DÉTAIL DES TESTS:")
    
    for test_name, success in results.items():
        status = "✅ SUCCÈS" if success else "❌ ÉCHEC"
        print(f"  {status} - {test_name}")
    
    if success_count == total_count:
        print(f"\n🎉 TOUS LES TESTS RÉUSSIS!")
        print("✅ Le backend HIVMeet est prêt pour la production!")
        
        print("\n📋 PROCHAINES ÉTAPES:")
        print("1. Configurer les vraies clés MyCoolPay dans .env")
        print("2. Configurer les certificates SSL pour HTTPS")
        print("3. Paramétrer les sauvegardes automatiques")
        print("4. Configurer le monitoring (Sentry)")
        print("5. Effectuer les tests de charge")
        
    else:
        print(f"\n⚠️ {total_count - success_count} test(s) en échec")
        print("Veuillez corriger les problèmes avant le déploiement en production")
    
    # Sauvegarder le rapport
    report_file = f"test_report_{timestamp.replace(':', '-').replace(' ', '_')}.txt"
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"Rapport de tests HIVMeet Backend\n")
            f.write(f"Généré le: {timestamp}\n\n")
            f.write(f"Résultats: {success_count}/{total_count}\n\n")
            for test_name, success in results.items():
                status = "SUCCÈS" if success else "ÉCHEC"
                f.write(f"{status} - {test_name}\n")
        
        print(f"\n💾 Rapport sauvegardé: {report_file}")
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder le rapport: {e}")

def main():
    """Fonction principale de test."""
    print("🚀 TESTS COMPLETS HIVMEET BACKEND")
    print("=" * 50)
    
    # Suite de tests
    tests = [
        ("Configuration Django", test_django_setup),
        ("Migrations Base de Données", test_database_migration),
        ("Fichiers Statiques", test_static_files),
        ("Création Modèles", test_models_creation),
        ("Fonctionnalités Premium", test_premium_features),
        ("Intégration Firebase", test_firebase_integration),
        ("Endpoints API", test_api_endpoints),
    ]
    
    results = {}
    
    # Exécution des tests
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"💥 Erreur inattendue dans {test_name}: {e}")
            traceback.print_exc()
            results[test_name] = False
        
        # Pause entre les tests
        time.sleep(1)
    
    # Génération du rapport final
    generate_test_report(results)
    
    # Code de sortie
    return 0 if all(results.values()) else 1

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrompus par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Erreur fatale: {e}")
        traceback.print_exc()
        sys.exit(1) 