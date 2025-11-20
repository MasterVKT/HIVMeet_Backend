#!/usr/bin/env python
"""
Script de test de base pour vérifier la configuration Django.
"""
import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

def test_django_imports():
    """Test des imports Django de base."""
    print("🔧 TEST IMPORTS DJANGO")
    print("-" * 30)
    
    try:
        import django
        print(f"✅ Django version: {django.get_version()}")
        
        django.setup()
        print("✅ Django setup successful")
        
        return True
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

def test_settings():
    """Test des settings Django."""
    print("\n⚙️ TEST SETTINGS")
    print("-" * 20)
    
    try:
        from django.conf import settings
        
        print(f"✅ Debug mode: {settings.DEBUG}")
        print(f"✅ Secret key: {'***' + settings.SECRET_KEY[-4:]}")
        print(f"✅ Database: {settings.DATABASES['default']['ENGINE']}")
        
        if hasattr(settings, 'FIREBASE_CREDENTIALS_PATH'):
            print(f"✅ Firebase credentials: {settings.FIREBASE_CREDENTIALS_PATH}")
        else:
            print("❌ Firebase credentials path not configured")
            
        return True
    except Exception as e:
        print(f"❌ Settings test failed: {e}")
        return False

def test_models():
    """Test des modèles Django."""
    print("\n📊 TEST MODÈLES")
    print("-" * 20)
    
    try:
        from django.contrib.auth import get_user_model
        from authentication.models import User
        from profiles.models import Profile
        from matching.models import Like, Match
        from messaging.models import Message
        from subscriptions.models import SubscriptionPlan
        
        print("✅ User model imported")
        print("✅ Profile model imported")
        print("✅ Matching models imported")
        print("✅ Messaging models imported") 
        print("✅ Subscription models imported")
        
        User = get_user_model()
        print(f"✅ User model: {User.__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        return False

def test_requirements():
    """Test des dépendances."""
    print("\n📦 TEST DÉPENDANCES")
    print("-" * 25)
    
    required_packages = [
        'django',
        'djangorestframework',
        'psycopg2',
        'redis',
        'celery',
        'firebase_admin',
        'python_decouple'
    ]
    
    success = True
    for package in required_packages:
        try:
            # Conversion des noms de packages
            import_name = package
            if package == 'python_decouple':
                import_name = 'decouple'
            elif package == 'psycopg2':
                import_name = 'psycopg2'
                
            __import__(import_name)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NON INSTALLÉ")
            success = False
    
    return success

if __name__ == '__main__':
    print("🚀 TEST CONFIGURATION HIVMEET BACKEND")
    print("=" * 45)
    
    # Tests
    django_ok = test_django_imports()
    settings_ok = test_settings()
    models_ok = test_models()
    deps_ok = test_requirements()
    
    # Résultats
    print("\n" + "=" * 45)
    print("📊 RÉSULTATS:")
    print(f"🔧 Django: {'✅ OK' if django_ok else '❌ ERREUR'}")
    print(f"⚙️ Settings: {'✅ OK' if settings_ok else '❌ ERREUR'}")
    print(f"📊 Modèles: {'✅ OK' if models_ok else '❌ ERREUR'}")
    print(f"📦 Dépendances: {'✅ OK' if deps_ok else '❌ ERREUR'}")
    
    overall = django_ok and settings_ok and models_ok and deps_ok
    print(f"\n🎯 GLOBAL: {'✅ SUCCÈS' if overall else '❌ ÉCHEC'}")
    
    if overall:
        print("\n🎉 Configuration prête pour la suite du développement!")
    else:
        print("\n⚠️ Problèmes détectés - à corriger avant de continuer") 