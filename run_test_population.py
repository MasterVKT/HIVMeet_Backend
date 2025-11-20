#!/usr/bin/env python3
"""
Script principal de peuplement de la base de données de test pour HIVMeet.

Ce script exécute en séquence:
1. Peuplement des utilisateurs de test
2. Création des interactions (likes, matches, messages)
3. Génération de statistiques et rapport final
"""

import os
import sys
import subprocess
import time
from datetime import datetime

def run_script(script_name, description):
    """
    Exécute un script Python et affiche le résultat.
    """
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes de timeout
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print(f"⚠️  Avertissements: {result.stderr}")
        
        if result.returncode == 0:
            print(f"✅ {description} terminé avec succès")
            return True
        else:
            print(f"❌ Erreur lors de {description}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout lors de {description}")
        return False
    except Exception as e:
        print(f"❌ Erreur lors de {description}: {e}")
        return False

def check_dependencies():
    """
    Vérifie que toutes les dépendances sont installées.
    """
    print("🔍 Vérification des dépendances...")
    
    required_packages = [
        'django',
        'requests',
        'python-dateutil'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Packages manquants: {', '.join(missing_packages)}")
        print("💡 Installez-les avec: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ Toutes les dépendances sont installées")
    return True

def check_django_setup():
    """
    Vérifie que Django est correctement configuré.
    """
    print("🔍 Vérification de la configuration Django...")
    
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
        import django
        django.setup()
        
        from django.conf import settings
        from django.db import connection
        
        # Tester la connexion à la base de données
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        print("✅ Configuration Django OK")
        return True
        
    except Exception as e:
        print(f"❌ Erreur de configuration Django: {e}")
        return False

def create_backup():
    """
    Crée une sauvegarde de la base de données actuelle.
    """
    print("💾 Création d'une sauvegarde...")
    
    try:
        from django.core.management import call_command
        from django.conf import settings
        
        backup_filename = f"backup_before_population_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        call_command('dumpdata', 
                    '--exclude', 'contenttypes',
                    '--exclude', 'auth.Permission',
                    '--exclude', 'sessions',
                    '--indent', '2',
                    '--output', backup_filename)
        
        print(f"✅ Sauvegarde créée: {backup_filename}")
        return True
        
    except Exception as e:
        print(f"⚠️  Impossible de créer la sauvegarde: {e}")
        return False

def generate_final_report():
    """
    Génère un rapport final avec toutes les informations importantes.
    """
    print("\n" + "="*60)
    print("📋 RAPPORT FINAL - PEUPLEMENT DE TEST HIVMEET")
    print("="*60)
    
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
        import django
        django.setup()
        
        from django.contrib.auth import get_user_model
        from profiles.models import Profile, ProfilePhoto
        from matching.models import Match, Like
        from messaging.models import Message
        
        User = get_user_model()
        
        # Statistiques générales
        total_users = User.objects.filter(is_active=True).exclude(role='admin').count()
        verified_users = User.objects.filter(is_verified=True).count()
        premium_users = User.objects.filter(is_premium=True).count()
        total_profiles = Profile.objects.count()
        total_photos = ProfilePhoto.objects.count()
        total_likes = Like.objects.count()
        total_matches = Match.objects.count()
        total_messages = Message.objects.count()
        
        print(f"\n📊 STATISTIQUES GÉNÉRALES:")
        print(f"   👥 Utilisateurs totaux: {total_users}")
        print(f"   ✅ Utilisateurs vérifiés: {verified_users}")
        print(f"   💎 Utilisateurs premium: {premium_users}")
        print(f"   📝 Profils créés: {total_profiles}")
        print(f"   📸 Photos de profil: {total_photos}")
        print(f"   💕 Likes créés: {total_likes}")
        print(f"   💘 Matches créés: {total_matches}")
        print(f"   💬 Messages créés: {total_messages}")
        
        # Répartition par genre
        profiles = Profile.objects.all()
        gender_stats = {}
        for profile in profiles:
            gender = profile.gender
            gender_stats[gender] = gender_stats.get(gender, 0) + 1
        
        print(f"\n👫 RÉPARTITION PAR GENRE:")
        for gender, count in gender_stats.items():
            percentage = (count / total_users) * 100 if total_users > 0 else 0
            print(f"   - {gender}: {count} ({percentage:.1f}%)")
        
        # Répartition par ville
        city_stats = {}
        for profile in profiles:
            city = profile.city
            if city:
                city_stats[city] = city_stats.get(city, 0) + 1
        
        print(f"\n🏙️  RÉPARTITION PAR VILLE:")
        for city, count in sorted(city_stats.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_users) * 100 if total_users > 0 else 0
            print(f"   - {city}: {count} ({percentage:.1f}%)")
        
        # Informations de connexion
        print(f"\n🔑 INFORMATIONS DE CONNEXION:")
        print(f"   👨‍💼 Admin: admin@hivmeet.com / adminpass123")
        print(f"   🔐 Mot de passe utilisateurs: testpass123")
        
        # Liste des utilisateurs de test
        print(f"\n👥 UTILISATEURS DE TEST:")
        users = User.objects.filter(is_active=True).exclude(role='admin').order_by('display_name')
        for user in users:
            status = "✅" if user.is_verified else "⏳"
            premium = "💎" if user.is_premium else "🆓"
            print(f"   {status} {premium} {user.display_name} ({user.email})")
        
        print(f"\n💡 CONSEILS POUR LES TESTS:")
        print(f"   - Testez le matching avec différents filtres d'âge et de distance")
        print(f"   - Vérifiez les conversations dans les matches créés")
        print(f"   - Testez les fonctionnalités premium (photos multiples, etc.)")
        print(f"   - Vérifiez les blocages et la modération")
        print(f"   - Testez la vérification des comptes")
        print(f"   - Vérifiez les notifications et l'activité récente")
        
        print(f"\n🎯 SCÉNARIOS DE TEST RECOMMANDÉS:")
        print(f"   1. Connexion avec un utilisateur vérifié premium")
        print(f"   2. Connexion avec un utilisateur non vérifié")
        print(f"   3. Test du matching avec filtres")
        print(f"   4. Test des likes et super likes")
        print(f"   5. Test des conversations dans les matches")
        print(f"   6. Test des blocages")
        print(f"   7. Test de la modération admin")
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération du rapport: {e}")

def main():
    """
    Fonction principale orchestrant le peuplement complet.
    """
    print("🚀 PEUPLEMENT COMPLET DE LA BASE DE DONNÉES HIVMEET")
    print("="*60)
    print(f"⏰ Début: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Vérifications préliminaires
    if not check_dependencies():
        print("❌ Arrêt: dépendances manquantes")
        return
    
    if not check_django_setup():
        print("❌ Arrêt: configuration Django incorrecte")
        return
    
    # Créer une sauvegarde
    create_backup()
    
    # Exécuter les scripts dans l'ordre
    scripts_to_run = [
        ("populate_test_users.py", "Peuplement des utilisateurs de test"),
        ("populate_test_interactions.py", "Création des interactions de test")
    ]
    
    success_count = 0
    for script, description in scripts_to_run:
        if run_script(script, description):
            success_count += 1
        else:
            print(f"❌ Échec de {description}")
            break
    
    # Générer le rapport final
    if success_count == len(scripts_to_run):
        generate_final_report()
        print(f"\n🎉 PEUPLEMENT TERMINÉ AVEC SUCCÈS!")
    else:
        print(f"\n⚠️  PEUPLEMENT PARTIEL - {success_count}/{len(scripts_to_run)} étapes réussies")
    
    print(f"⏰ Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 