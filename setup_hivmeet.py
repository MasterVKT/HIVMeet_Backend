#!/usr/bin/env python
"""
Script d'installation et configuration automatique HIVMeet Backend.
"""
import os
import sys
import subprocess
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

def run_command(command, description=""):
    """Exécute une commande et gère les erreurs."""
    print(f"🔧 {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - SUCCÈS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ÉCHEC")
        print(f"Erreur: {e.stderr}")
        return False

def check_database_connection():
    """Vérifie la connexion à la base de données."""
    print("\n📊 VÉRIFICATION BASE DE DONNÉES")
    print("-" * 35)
    
    try:
        django.setup()
        from django.db import connection
        
        # Test de connexion
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            
        print("✅ Connexion base de données OK")
        return True
        
    except Exception as e:
        print(f"❌ Connexion base de données ÉCHEC: {e}")
        print("💡 Vérifiez que PostgreSQL est démarré et configuré")
        return False

def create_superuser():
    """Crée un superutilisateur."""
    print("\n👤 CRÉATION SUPERUTILISATEUR")
    print("-" * 30)
    
    try:
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import User as DjangoUser
        
        User = get_user_model()
        
        # Vérifier si un superuser existe déjà
        if User.objects.filter(is_superuser=True).exists():
            print("✅ Superutilisateur déjà existant")
            return True
        
        # Créer le superuser
        email = "admin@hivmeet.com"
        password = "AdminHIV2024!"
        
        superuser = User.objects.create_user(
            email=email,
            password=password,
            display_name="Admin HIVMeet",
            birth_date="1980-01-01"
        )
        superuser.is_staff = True
        superuser.is_superuser = True
        superuser.email_verified = True
        superuser.save()
        
        print(f"✅ Superutilisateur créé:")
        print(f"   📧 Email: {email}")
        print(f"   🔑 Mot de passe: {password}")
        
        return True
        
    except Exception as e:
        print(f"❌ Création superutilisateur ÉCHEC: {e}")
        return False

def install_requirements():
    """Installe les dépendances manquantes."""
    print("\n📦 INSTALLATION DÉPENDANCES")
    print("-" * 30)
    
    missing_packages = []
    
    # Vérifier les packages requis
    required_packages = [
        'python-decouple',
        'django-redis',
        'firebase-admin',
        'celery',
        'flower'
    ]
    
    for package in required_packages:
        try:
            # Test d'import
            if package == 'python-decouple':
                import decouple
            elif package == 'django-redis':
                import django_redis
            elif package == 'firebase-admin':
                import firebase_admin
            elif package == 'celery':
                import celery
            elif package == 'flower':
                import flower
                
            print(f"✅ {package} - installé")
            
        except ImportError:
            print(f"❌ {package} - manquant")
            missing_packages.append(package)
    
    # Installer les packages manquants
    if missing_packages:
        print(f"\n🔧 Installation de {len(missing_packages)} packages...")
        for package in missing_packages:
            if run_command(f"pip install {package}", f"Installation {package}"):
                print(f"✅ {package} installé")
            else:
                print(f"❌ Échec installation {package}")
                return False
    
    return True

def setup_initial_data():
    """Configure les données initiales."""
    print("\n🌱 CONFIGURATION DONNÉES INITIALES")
    print("-" * 40)
    
    try:
        # Créer les plans d'abonnement par défaut
        from subscriptions.models import SubscriptionPlan
        
        if not SubscriptionPlan.objects.exists():
            # Plan Premium mensuel
            SubscriptionPlan.objects.create(
                plan_id='hivmeet_monthly',
                name='HIVMeet Premium',
                name_en='HIVMeet Premium',
                name_fr='HIVMeet Premium',
                description='Accès premium mensuel',
                description_en='Monthly premium access',
                description_fr='Accès premium mensuel',
                price=9.99,
                currency='EUR',
                billing_interval='month',
                unlimited_likes=True,
                can_see_likers=True,
                can_rewind=True,
                monthly_boosts_count=1,
                daily_super_likes_count=5,
                media_messaging_enabled=True,
                audio_video_calls_enabled=True,
                is_active=True,
                order=1
            )
            
            # Plan Premium annuel
            SubscriptionPlan.objects.create(
                plan_id='hivmeet_yearly',
                name='HIVMeet Premium Annuel',
                name_en='HIVMeet Premium Yearly',
                name_fr='HIVMeet Premium Annuel',
                description='Accès premium annuel avec réduction',
                description_en='Yearly premium access with discount',
                description_fr='Accès premium annuel avec réduction',
                price=99.99,
                currency='EUR',
                billing_interval='year',
                unlimited_likes=True,
                can_see_likers=True,
                can_rewind=True,
                monthly_boosts_count=2,
                daily_super_likes_count=10,
                media_messaging_enabled=True,
                audio_video_calls_enabled=True,
                is_active=True,
                order=2
            )
            
            print("✅ Plans d'abonnement créés")
        else:
            print("✅ Plans d'abonnement déjà existants")
        
        # Créer des catégories de ressources
        from resources.models import Category
        
        if not Category.objects.exists():
            categories = [
                {
                    'name': 'Santé et Bien-être',
                    'name_en': 'Health and Wellness',
                    'name_fr': 'Santé et Bien-être',
                    'slug': 'health-wellness'
                },
                {
                    'name': 'Support et Communauté',
                    'name_en': 'Support and Community',
                    'name_fr': 'Support et Communauté',
                    'slug': 'support-community'
                },
                {
                    'name': 'Information Médicale',
                    'name_en': 'Medical Information',
                    'name_fr': 'Information Médicale',
                    'slug': 'medical-info'
                }
            ]
            
            for cat_data in categories:
                Category.objects.create(**cat_data)
            
            print("✅ Catégories de ressources créées")
        else:
            print("✅ Catégories de ressources déjà existantes")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration données initiales ÉCHEC: {e}")
        return False

def generate_secret_key():
    """Génère une nouvelle clé secrète Django."""
    from django.core.management.utils import get_random_secret_key
    return get_random_secret_key()

def create_env_file():
    """Crée le fichier .env avec la configuration."""
    print("\n📝 CRÉATION FICHIER .ENV")
    print("-" * 25)
    
    env_content = f"""# HIVMeet Backend Configuration
# Généré automatiquement le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Django Configuration
SECRET_KEY={generate_secret_key()}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hivmeet_db

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=credentials/hivmeet_firebase_credentials.json
FIREBASE_STORAGE_BUCKET=hivmeet-f76f8.firebasestorage.app

# MyCoolPay Configuration (À configurer avec vos vraies clés)
MYCOOLPAY_API_KEY=your_api_key_here
MYCOOLPAY_API_SECRET=your_secret_here
MYCOOLPAY_BASE_URL=https://api.mycoolpay.com/v1
MYCOOLPAY_WEBHOOK_SECRET=your_webhook_secret_here

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=HIVMeet <noreply@hivmeet.com>

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Frontend Configuration
FRONTEND_URL=http://localhost:3000
"""
    
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("✅ Fichier .env créé")
        return True
    except Exception as e:
        print(f"❌ Erreur création .env: {e}")
        return False

def main():
    """Fonction principale d'installation."""
    print("🚀 INSTALLATION HIVMEET BACKEND")
    print("=" * 40)
    
    from datetime import datetime
    
    # Étapes d'installation
    steps = [
        ("🔧 Installation dépendances", install_requirements),
        ("📝 Création fichier .env", create_env_file),
        ("🗃️ Migration base de données", lambda: run_command("python manage.py migrate", "Migration BD")),
        ("📊 Vérification BD", check_database_connection),
        ("🌱 Données initiales", setup_initial_data),
        ("👤 Création superuser", create_superuser),
    ]
    
    results = []
    
    for description, func in steps:
        print(f"\n{description}")
        print("-" * len(description))
        
        try:
            result = func()
            results.append(result)
            
            if result:
                print(f"✅ {description} - SUCCÈS")
            else:
                print(f"❌ {description} - ÉCHEC")
                
        except Exception as e:
            print(f"❌ {description} - ERREUR: {e}")
            results.append(False)
    
    # Résumé final
    print("\n" + "=" * 40)
    print("📊 RÉSUMÉ INSTALLATION:")
    
    success_count = sum(results)
    total_count = len(results)
    
    for i, (desc, _) in enumerate(steps):
        status = "✅" if results[i] else "❌"
        print(f"{status} {desc}")
    
    print(f"\n🎯 SUCCÈS: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 INSTALLATION TERMINÉE AVEC SUCCÈS!")
        print("\n📋 PROCHAINES ÉTAPES:")
        print("1. Configurez les vraies clés MyCoolPay dans .env")
        print("2. Configurez Firebase credentials")
        print("3. Lancez le serveur: python manage.py runserver")
        print("4. Accédez à l'admin: http://localhost:8000/admin")
    else:
        print("\n⚠️ INSTALLATION INCOMPLÈTE")
        print("Veuillez corriger les erreurs et relancer le script")

if __name__ == '__main__':
    from datetime import datetime
    main() 