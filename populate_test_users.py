#!/usr/bin/env python3
"""
Script de peuplement de la base de données avec des utilisateurs de test pour HIVMeet.

Ce script crée des utilisateurs de test avec des profils variés pour permettre
des tests complets de l'application sous tous les angles.
"""

import os
import sys
import django
import random
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.contrib.auth import get_user_model
from django.db import transaction

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from authentication.models import User
from profiles.models import Profile, ProfilePhoto

User = get_user_model()

# Données de test pour les utilisateurs
TEST_USERS_DATA = [
    # Utilisateurs masculins
    {
        'email': 'thomas.dupont@test.com',
        'display_name': 'Thomas',
        'birth_date': datetime(1990, 5, 15),
        'gender': 'male',
        'bio': 'Passionné de musique et de voyages. Je cherche une relation sérieuse basée sur la confiance et le respect.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Musique', 'Voyages', 'Cuisine'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 25,
        'age_max_preference': 35,
        'distance_max_km': 30,
        'genders_sought': ['female'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    {
        'email': 'marc.bernard@test.com',
        'display_name': 'Marc',
        'birth_date': datetime(1985, 8, 22),
        'gender': 'male',
        'bio': 'Sportif et amateur de bonne cuisine. J\'aime les conversations profondes et les rires partagés.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Sport', 'Cuisine', 'Lecture'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 30,
        'age_max_preference': 45,
        'distance_max_km': 50,
        'genders_sought': ['female', 'non_binary'],
        'is_verified': True,
        'is_premium': False,
        'verification_status': 'verified'
    },
    {
        'email': 'pierre.martin@test.com',
        'display_name': 'Pierre',
        'birth_date': datetime(1995, 3, 10),
        'gender': 'male',
        'bio': 'Étudiant en informatique, passionné de jeux vidéo et de nouvelles technologies.',
        'city': 'Marseille',
        'country': 'France',
        'interests': ['Jeux vidéo', 'Technologie', 'Cinéma'],
        'relationship_types_sought': ['casual', 'short_term'],
        'age_min_preference': 20,
        'age_max_preference': 28,
        'distance_max_km': 25,
        'genders_sought': ['female'],
        'is_verified': False,
        'is_premium': False,
        'verification_status': 'pending'
    },
    {
        'email': 'alex.chen@test.com',
        'display_name': 'Alex',
        'birth_date': datetime(1988, 12, 5),
        'gender': 'trans_male',
        'bio': 'Artiste et militant LGBTQ+. Je cherche des connexions authentiques et respectueuses.',
        'city': 'Toulouse',
        'country': 'France',
        'interests': ['Art', 'Militantisme', 'Musique'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 40,
        'genders_sought': ['male', 'female', 'non_binary'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    {
        'email': 'samuel.rodriguez@test.com',
        'display_name': 'Samuel',
        'birth_date': datetime(1982, 7, 18),
        'gender': 'male',
        'bio': 'Médecin spécialisé, j\'aime la randonnée et la photographie. Recherche une relation stable.',
        'city': 'Bordeaux',
        'country': 'France',
        'interests': ['Randonnée', 'Photographie', 'Médecine'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 35,
        'age_max_preference': 50,
        'distance_max_km': 60,
        'genders_sought': ['female'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    
    # Utilisateurs féminins
    {
        'email': 'sophie.leroy@test.com',
        'display_name': 'Sophie',
        'birth_date': datetime(1992, 4, 12),
        'gender': 'female',
        'bio': 'Professeure de yoga, passionnée de bien-être et de développement personnel.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Yoga', 'Bien-être', 'Lecture'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 28,
        'age_max_preference': 38,
        'distance_max_km': 35,
        'genders_sought': ['male'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    {
        'email': 'marie.claire@test.com',
        'display_name': 'Marie',
        'birth_date': datetime(1987, 9, 25),
        'gender': 'female',
        'bio': 'Architecte d\'intérieur, j\'aime l\'art, la décoration et les voyages culturels.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Art', 'Architecture', 'Voyages'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 30,
        'age_max_preference': 42,
        'distance_max_km': 45,
        'genders_sought': ['male'],
        'is_verified': True,
        'is_premium': False,
        'verification_status': 'verified'
    },
    {
        'email': 'julie.moreau@test.com',
        'display_name': 'Julie',
        'birth_date': datetime(1996, 1, 8),
        'gender': 'female',
        'bio': 'Étudiante en psychologie, passionnée de danse et de théâtre.',
        'city': 'Marseille',
        'country': 'France',
        'interests': ['Danse', 'Théâtre', 'Psychologie'],
        'relationship_types_sought': ['casual', 'short_term'],
        'age_min_preference': 22,
        'age_max_preference': 30,
        'distance_max_km': 20,
        'genders_sought': ['male'],
        'is_verified': False,
        'is_premium': False,
        'verification_status': 'not_started'
    },
    {
        'email': 'emma.taylor@test.com',
        'display_name': 'Emma',
        'birth_date': datetime(1990, 11, 15),
        'gender': 'trans_female',
        'bio': 'Ingénieure en informatique, passionnée de jeux vidéo et de science-fiction.',
        'city': 'Toulouse',
        'country': 'France',
        'interests': ['Jeux vidéo', 'Science-fiction', 'Technologie'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 25,
        'age_max_preference': 35,
        'distance_max_km': 30,
        'genders_sought': ['male', 'female'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    {
        'email': 'camille.dubois@test.com',
        'display_name': 'Camille',
        'birth_date': datetime(1985, 6, 30),
        'gender': 'female',
        'bio': 'Avocate spécialisée en droit des affaires. J\'aime la lecture, le tennis et les bonnes tables.',
        'city': 'Bordeaux',
        'country': 'France',
        'interests': ['Tennis', 'Lecture', 'Gastronomie'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 35,
        'age_max_preference': 48,
        'distance_max_km': 55,
        'genders_sought': ['male'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    
    # Utilisateurs non-binaires
    {
        'email': 'riley.smith@test.com',
        'display_name': 'Riley',
        'birth_date': datetime(1993, 2, 14),
        'gender': 'non_binary',
        'bio': 'Artiste peintre et militant pour les droits LGBTQ+. Je cherche des connexions authentiques.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Art', 'Militantisme', 'Musique'],
        'relationship_types_sought': ['friendship', 'long_term'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 40,
        'genders_sought': ['male', 'female', 'non_binary'],
        'is_verified': True,
        'is_premium': False,
        'verification_status': 'verified'
    },
    {
        'email': 'jordan.lee@test.com',
        'display_name': 'Jordan',
        'birth_date': datetime(1989, 10, 3),
        'gender': 'non_binary',
        'bio': 'Psychologue clinicien, passionné de psychologie positive et de méditation.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Psychologie', 'Méditation', 'Lecture'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 28,
        'age_max_preference': 45,
        'distance_max_km': 50,
        'genders_sought': ['male', 'female', 'non_binary'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    
    # Utilisateurs avec différents statuts de vérification
    {
        'email': 'paul.durand@test.com',
        'display_name': 'Paul',
        'birth_date': datetime(1991, 3, 20),
        'gender': 'male',
        'bio': 'Chef cuisinier, passionné de gastronomie et de vins.',
        'city': 'Nice',
        'country': 'France',
        'interests': ['Gastronomie', 'Vins', 'Cuisine'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 25,
        'age_max_preference': 35,
        'distance_max_km': 30,
        'genders_sought': ['female'],
        'is_verified': False,
        'is_premium': False,
        'verification_status': 'rejected'
    },
    {
        'email': 'lisa.garcia@test.com',
        'display_name': 'Lisa',
        'birth_date': datetime(1988, 7, 12),
        'gender': 'female',
        'bio': 'Designer graphique, créative et passionnée d\'art contemporain.',
        'city': 'Strasbourg',
        'country': 'France',
        'interests': ['Design', 'Art', 'Créativité'],
        'relationship_types_sought': ['casual', 'short_term'],
        'age_min_preference': 26,
        'age_max_preference': 36,
        'distance_max_km': 25,
        'genders_sought': ['male'],
        'is_verified': False,
        'is_premium': False,
        'verification_status': 'expired'
    },
    
    # Utilisateurs avec des préférences variées
    {
        'email': 'antoine.lefevre@test.com',
        'display_name': 'Antoine',
        'birth_date': datetime(1986, 12, 8),
        'gender': 'male',
        'bio': 'Photographe professionnel, passionné de voyages et de cultures du monde.',
        'city': 'Montpellier',
        'country': 'France',
        'interests': ['Photographie', 'Voyages', 'Cultures'],
        'relationship_types_sought': ['friendship', 'long_term'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 100,
        'genders_sought': ['female', 'non_binary'],
        'is_verified': True,
        'is_premium': True,
        'verification_status': 'verified'
    },
    {
        'email': 'nina.kovac@test.com',
        'display_name': 'Nina',
        'birth_date': datetime(1994, 5, 25),
        'gender': 'female',
        'bio': 'Traductrice freelance, passionnée de langues et de littérature.',
        'city': 'Nantes',
        'country': 'France',
        'interests': ['Langues', 'Littérature', 'Voyages'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 24,
        'age_max_preference': 34,
        'distance_max_km': 40,
        'genders_sought': ['male'],
        'is_verified': True,
        'is_premium': False,
        'verification_status': 'verified'
    }
]

def download_random_photo(gender, index):
    """
    Télécharge une photo aléatoire depuis Unsplash basée sur le genre.
    """
    try:
        # Catégories de photos basées sur le genre
        categories = {
            'male': ['portrait-man', 'business-man', 'fashion-man'],
            'female': ['portrait-woman', 'fashion-woman', 'business-woman'],
            'trans_male': ['portrait-man', 'fashion-man'],
            'trans_female': ['portrait-woman', 'fashion-woman'],
            'non_binary': ['portrait', 'fashion', 'artistic-portrait'],
            'other': ['portrait', 'fashion'],
            'prefer_not_to_say': ['portrait', 'fashion']
        }
        
        category = random.choice(categories.get(gender, ['portrait']))
        
        # URL Unsplash pour une photo aléatoire
        url = f"https://source.unsplash.com/400x600/?{category}"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
        else:
            # Fallback vers une image par défaut
            return None
    except Exception as e:
        print(f"Erreur lors du téléchargement de la photo: {e}")
        return None

def create_test_user(user_data):
    """
    Crée un utilisateur de test avec son profil.
    """
    try:
        with transaction.atomic():
            # Créer l'utilisateur
            user = User.objects.create(
                email=user_data['email'],
                display_name=user_data['display_name'],
                birth_date=user_data['birth_date'],
                is_verified=user_data['is_verified'],
                verification_status=user_data['verification_status'],
                is_premium=user_data['is_premium'],
                email_verified=True,
                is_active=True
            )
            
            # Définir un mot de passe par défaut
            user.set_password('testpass123')
            user.save()
            
            # Créer le profil
            profile = Profile.objects.create(
                user=user,
                bio=user_data['bio'],
                gender=user_data['gender'],
                city=user_data['city'],
                country=user_data['country'],
                interests=user_data['interests'],
                relationship_types_sought=user_data['relationship_types_sought'],
                age_min_preference=user_data['age_min_preference'],
                age_max_preference=user_data['age_max_preference'],
                distance_max_km=user_data['distance_max_km'],
                genders_sought=user_data['genders_sought'],
                is_hidden=False,
                show_online_status=True,
                allow_profile_in_discovery=True
            )
            
            # Ajouter des coordonnées géographiques aléatoires en France
            profile.latitude = random.uniform(42.0, 51.0)
            profile.longitude = random.uniform(-5.0, 9.0)
            profile.save()
            
            # Télécharger et ajouter des photos
            photo_content = download_random_photo(user_data['gender'], len(User.objects.all()))
            if photo_content:
                # Sauvegarder la photo principale
                photo_filename = f"profile_photos/{user.id}_main.jpg"
                saved_path = default_storage.save(photo_filename, ContentFile(photo_content))
                
                ProfilePhoto.objects.create(
                    profile=profile,
                    photo_url=saved_path,
                    thumbnail_url=saved_path,
                    is_main=True,
                    order=0,
                    is_approved=True
                )
                
                # Ajouter 1-3 photos supplémentaires pour les utilisateurs premium
                if user_data['is_premium']:
                    for i in range(1, random.randint(2, 4)):
                        additional_photo = download_random_photo(user_data['gender'], i)
                        if additional_photo:
                            additional_filename = f"profile_photos/{user.id}_additional_{i}.jpg"
                            additional_saved_path = default_storage.save(additional_filename, ContentFile(additional_photo))
                            
                            ProfilePhoto.objects.create(
                                profile=profile,
                                photo_url=additional_saved_path,
                                thumbnail_url=additional_saved_path,
                                is_main=False,
                                order=i,
                                is_approved=True
                            )
            
            # Définir la date premium si applicable
            if user_data['is_premium']:
                user.premium_until = timezone.now() + timedelta(days=random.randint(30, 365))
                user.save()
            
            print(f"✅ Utilisateur créé: {user.display_name} ({user.email})")
            return user
            
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'utilisateur {user_data['email']}: {e}")
        return None

def create_admin_user():
    """
    Crée un utilisateur administrateur pour les tests.
    """
    try:
        admin_user = User.objects.create(
            email='admin@hivmeet.com',
            display_name='Admin HIVMeet',
            birth_date=datetime(1980, 1, 1),
            is_staff=True,
            is_superuser=True,
            is_verified=True,
            verification_status='verified',
            is_premium=True,
            email_verified=True,
            is_active=True,
            role='admin'
        )
        admin_user.set_password('adminpass123')
        admin_user.save()
        
        # Créer le profil admin
        Profile.objects.create(
            user=admin_user,
            bio='Administrateur de la plateforme HIVMeet',
            gender='prefer_not_to_say',
            city='Paris',
            country='France',
            interests=['Administration', 'Modération', 'Support'],
            relationship_types_sought=[],
            age_min_preference=18,
            age_max_preference=99,
            distance_max_km=100,
            genders_sought=[],
            is_hidden=True,
            show_online_status=False,
            allow_profile_in_discovery=False
        )
        
        print("✅ Utilisateur administrateur créé: admin@hivmeet.com")
        return admin_user
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'admin: {e}")
        return None

def main():
    """
    Fonction principale pour peupler la base de données.
    """
    print("🚀 Début du peuplement de la base de données avec des utilisateurs de test...")
    
    # Vérifier si des utilisateurs existent déjà
    if User.objects.count() > 0:
        print("⚠️  Des utilisateurs existent déjà dans la base de données.")
        print("🔄 Continuation automatique pour ajouter de nouveaux utilisateurs...")
    
    # Créer l'utilisateur administrateur
    admin_user = create_admin_user()
    
    # Créer les utilisateurs de test
    created_users = []
    for i, user_data in enumerate(TEST_USERS_DATA, 1):
        print(f"\n📝 Création de l'utilisateur {i}/{len(TEST_USERS_DATA)}: {user_data['display_name']}")
        user = create_test_user(user_data)
        if user:
            created_users.append(user)
    
    # Afficher un résumé
    print(f"\n🎉 Peuplement terminé!")
    print(f"📊 Statistiques:")
    print(f"   - Utilisateurs créés: {len(created_users)}")
    print(f"   - Utilisateurs vérifiés: {User.objects.filter(is_verified=True).count()}")
    print(f"   - Utilisateurs premium: {User.objects.filter(is_premium=True).count()}")
    print(f"   - Utilisateurs avec photos: {ProfilePhoto.objects.filter(is_main=True).count()}")
    
    print(f"\n🔑 Informations de connexion:")
    print(f"   - Admin: admin@hivmeet.com / adminpass123")
    print(f"   - Utilisateurs de test: testpass123 (pour tous les utilisateurs)")
    
    print(f"\n📋 Utilisateurs créés:")
    for user in created_users:
        status = "✅ Vérifié" if user.is_verified else "⏳ En attente"
        premium = "💎 Premium" if user.is_premium else "🆓 Gratuit"
        print(f"   - {user.display_name} ({user.email}) - {status} - {premium}")

if __name__ == "__main__":
    main() 