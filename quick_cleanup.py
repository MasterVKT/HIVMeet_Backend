#!/usr/bin/env python3
"""
Script de nettoyage rapide pour supprimer les données de test existantes.
"""

import os
import django

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

def quick_cleanup():
    """
    Nettoyage rapide des données de test.
    """
    print("🧹 NETTOYAGE RAPIDE DES DONNÉES DE TEST")
    print("="*50)
    
    try:
        with transaction.atomic():
            # Supprimer les interactions
            likes_deleted = Like.objects.all().delete()[0]
            messages_deleted = Message.objects.all().delete()[0]
            matches_deleted = Match.objects.all().delete()[0]
            
            # Supprimer les photos
            photos_deleted = ProfilePhoto.objects.all().delete()[0]
            
            # Supprimer les profils
            profiles_deleted = Profile.objects.all().delete()[0]
            
            # Supprimer les utilisateurs de test
            test_users_deleted = User.objects.filter(email__endswith='@test.com').delete()[0]
            admin_deleted = User.objects.filter(email='admin@hivmeet.com').delete()[0]
            
            print(f"✅ Nettoyage terminé:")
            print(f"   - Likes supprimés: {likes_deleted}")
            print(f"   - Messages supprimés: {messages_deleted}")
            print(f"   - Matches supprimés: {matches_deleted}")
            print(f"   - Photos supprimées: {photos_deleted}")
            print(f"   - Profils supprimés: {profiles_deleted}")
            print(f"   - Utilisateurs de test supprimés: {test_users_deleted}")
            print(f"   - Admin supprimé: {admin_deleted}")
            
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage: {e}")

if __name__ == "__main__":
    quick_cleanup() 