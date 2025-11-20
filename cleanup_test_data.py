#!/usr/bin/env python3
"""
Script de nettoyage des données de test pour HIVMeet.

Ce script supprime toutes les données de test créées par les scripts de peuplement.
"""

import os
import sys
import django
from datetime import datetime

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile, ProfilePhoto
from matching.models import Match, Like
from messaging.models import Message
from django.core.files.storage import default_storage
from django.db import transaction

User = get_user_model()

def cleanup_test_users():
    """
    Supprime tous les utilisateurs de test.
    """
    print("🗑️  Suppression des utilisateurs de test...")
    
    test_users = User.objects.filter(email__endswith='@test.com')
    admin_user = User.objects.filter(email='admin@hivmeet.com')
    
    print(f"   - Utilisateurs de test trouvés: {test_users.count()}")
    print(f"   - Utilisateur admin trouvé: {admin_user.count()}")
    
    # Supprimer les utilisateurs de test
    deleted_users = test_users.delete()
    print(f"   - Utilisateurs de test supprimés: {deleted_users[0]}")
    
    # Supprimer l'utilisateur admin
    deleted_admin = admin_user.delete()
    print(f"   - Utilisateur admin supprimé: {deleted_admin[0]}")
    
    return True

def cleanup_test_profiles():
    """
    Supprime tous les profils de test.
    """
    print("🗑️  Suppression des profils de test...")
    
    test_profiles = Profile.objects.filter(user__email__endswith='@test.com')
    admin_profiles = Profile.objects.filter(user__email='admin@hivmeet.com')
    
    print(f"   - Profils de test trouvés: {test_profiles.count()}")
    print(f"   - Profils admin trouvés: {admin_profiles.count()}")
    
    # Supprimer les profils de test
    deleted_profiles = test_profiles.delete()
    print(f"   - Profils de test supprimés: {deleted_profiles[0]}")
    
    # Supprimer les profils admin
    deleted_admin_profiles = admin_profiles.delete()
    print(f"   - Profils admin supprimés: {deleted_admin_profiles[0]}")
    
    return True

def cleanup_test_photos():
    """
    Supprime toutes les photos de test et les fichiers associés.
    """
    print("🗑️  Suppression des photos de test...")
    
    test_photos = ProfilePhoto.objects.filter(profile__user__email__endswith='@test.com')
    admin_photos = ProfilePhoto.objects.filter(profile__user__email='admin@hivmeet.com')
    
    print(f"   - Photos de test trouvées: {test_photos.count()}")
    print(f"   - Photos admin trouvées: {admin_photos.count()}")
    
    # Supprimer les fichiers de photos
    deleted_files = 0
    for photo in test_photos:
        try:
            if photo.photo_url and default_storage.exists(photo.photo_url):
                default_storage.delete(photo.photo_url)
                deleted_files += 1
            if photo.thumbnail_url and default_storage.exists(photo.thumbnail_url):
                default_storage.delete(photo.thumbnail_url)
                deleted_files += 1
        except Exception as e:
            print(f"   ⚠️  Erreur lors de la suppression du fichier {photo.photo_url}: {e}")
    
    for photo in admin_photos:
        try:
            if photo.photo_url and default_storage.exists(photo.photo_url):
                default_storage.delete(photo.photo_url)
                deleted_files += 1
            if photo.thumbnail_url and default_storage.exists(photo.thumbnail_url):
                default_storage.delete(photo.thumbnail_url)
                deleted_files += 1
        except Exception as e:
            print(f"   ⚠️  Erreur lors de la suppression du fichier {photo.photo_url}: {e}")
    
    print(f"   - Fichiers de photos supprimés: {deleted_files}")
    
    # Supprimer les enregistrements de photos
    deleted_photos = test_photos.delete()
    deleted_admin_photos = admin_photos.delete()
    
    print(f"   - Enregistrements de photos supprimés: {deleted_photos[0]}")
    print(f"   - Enregistrements de photos admin supprimés: {deleted_admin_photos[0]}")
    
    return True

def cleanup_test_interactions():
    """
    Supprime toutes les interactions de test.
    """
    print("🗑️  Suppression des interactions de test...")
    
    # Supprimer les likes
    likes = Like.objects.all()
    deleted_likes = likes.delete()
    print(f"   - Likes supprimés: {deleted_likes[0]}")
    
    # Supprimer les messages
    messages = Message.objects.all()
    deleted_messages = messages.delete()
    print(f"   - Messages supprimés: {deleted_messages[0]}")
    
    # Supprimer les matches
    matches = Match.objects.all()
    deleted_matches = matches.delete()
    print(f"   - Matches supprimés: {deleted_matches[0]}")
    
    return True

def cleanup_test_blocks():
    """
    Supprime tous les blocages de test.
    """
    print("🗑️  Suppression des blocages de test...")
    
    # Réinitialiser les blocages pour tous les utilisateurs
    users = User.objects.all()
    cleared_blocks = 0
    
    for user in users:
        if user.blocked_users.count() > 0:
            user.blocked_users.clear()
            cleared_blocks += 1
    
    print(f"   - Blocages supprimés pour {cleared_blocks} utilisateurs")
    
    return True

def cleanup_orphaned_data():
    """
    Supprime les données orphelines.
    """
    print("🗑️  Suppression des données orphelines...")
    
    # Supprimer les profils sans utilisateur
    orphaned_profiles = Profile.objects.filter(user__isnull=True)
    deleted_orphaned_profiles = orphaned_profiles.delete()
    print(f"   - Profils orphelins supprimés: {deleted_orphaned_profiles[0]}")
    
    # Supprimer les photos sans profil
    orphaned_photos = ProfilePhoto.objects.filter(profile__isnull=True)
    deleted_orphaned_photos = orphaned_photos.delete()
    print(f"   - Photos orphelines supprimées: {deleted_orphaned_photos[0]}")
    
    # Supprimer les messages sans match
    orphaned_messages = Message.objects.filter(match__isnull=True)
    deleted_orphaned_messages = orphaned_messages.delete()
    print(f"   - Messages orphelins supprimés: {deleted_orphaned_messages[0]}")
    
    return True

def create_cleanup_report():
    """
    Génère un rapport de nettoyage.
    """
    print("\n" + "="*60)
    print("📋 RAPPORT DE NETTOYAGE - HIVMEET")
    print("="*60)
    
    # Vérifier qu'il ne reste plus de données de test
    remaining_users = User.objects.filter(email__endswith='@test.com').count()
    remaining_admin = User.objects.filter(email='admin@hivmeet.com').count()
    remaining_profiles = Profile.objects.filter(user__email__endswith='@test.com').count()
    remaining_photos = ProfilePhoto.objects.filter(profile__user__email__endswith='@test.com').count()
    remaining_likes = Like.objects.count()
    remaining_matches = Match.objects.count()
    remaining_messages = Message.objects.count()
    
    print(f"\n📊 DONNÉES RESTANTES:")
    print(f"   👥 Utilisateurs de test: {remaining_users}")
    print(f"   👨‍💼 Utilisateur admin: {remaining_admin}")
    print(f"   📝 Profils de test: {remaining_profiles}")
    print(f"   📸 Photos de test: {remaining_photos}")
    print(f"   💕 Likes: {remaining_likes}")
    print(f"   💘 Matches: {remaining_matches}")
    print(f"   💬 Messages: {remaining_messages}")
    
    if (remaining_users == 0 and remaining_admin == 0 and 
        remaining_profiles == 0 and remaining_photos == 0 and
        remaining_likes == 0 and remaining_matches == 0 and 
        remaining_messages == 0):
        print("\n✅ NETTOYAGE RÉUSSI!")
        print("   Toutes les données de test ont été supprimées")
    else:
        print("\n⚠️  NETTOYAGE PARTIEL")
        print("   Certaines données de test restent présentes")
    
    # Statistiques générales
    total_users = User.objects.count()
    total_profiles = Profile.objects.count()
    total_photos = ProfilePhoto.objects.count()
    
    print(f"\n📈 STATISTIQUES GÉNÉRALES:")
    print(f"   👥 Utilisateurs totaux: {total_users}")
    print(f"   📝 Profils totaux: {total_profiles}")
    print(f"   📸 Photos totales: {total_photos}")

def main():
    """
    Fonction principale de nettoyage.
    """
    print("🧹 DÉBUT DU NETTOYAGE DES DONNÉES DE TEST HIVMEET")
    print("="*60)
    print(f"⏰ Début: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Demander confirmation
    print("\n⚠️  ATTENTION: Ce script va supprimer toutes les données de test!")
    response = input("Êtes-vous sûr de vouloir continuer? (y/N): ")
    
    if response.lower() != 'y':
        print("❌ Nettoyage annulé.")
        return
    
    try:
        with transaction.atomic():
            # Exécuter les nettoyages dans l'ordre
            cleanup_functions = [
                ("Interactions de test", cleanup_test_interactions),
                ("Photos de test", cleanup_test_photos),
                ("Profils de test", cleanup_test_profiles),
                ("Utilisateurs de test", cleanup_test_users),
                ("Blocages de test", cleanup_test_blocks),
                ("Données orphelines", cleanup_orphaned_data)
            ]
            
            for cleanup_name, cleanup_func in cleanup_functions:
                print(f"\n{'='*40}")
                print(f"🧹 Nettoyage: {cleanup_name}")
                print(f"{'='*40}")
                
                try:
                    cleanup_func()
                    print(f"✅ {cleanup_name}: SUCCÈS")
                except Exception as e:
                    print(f"❌ {cleanup_name}: ERREUR - {e}")
            
            # Générer le rapport final
            create_cleanup_report()
            
            print(f"\n🎉 NETTOYAGE TERMINÉ!")
            print(f"⏰ Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage: {e}")
        print("⚠️  Certaines données peuvent ne pas avoir été supprimées")

if __name__ == "__main__":
    main() 