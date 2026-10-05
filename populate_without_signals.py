#!/usr/bin/env python3
"""
Script de peuplement sans signaux - désactive temporairement les signaux pour éviter les conflits.
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile, ProfilePhoto, Verification
from profiles.photo_storage import profile_photo_storage
from matching.models import Match, Like
from messaging.models import Message
from django.core.files.storage import default_storage
from django.db import transaction
from datetime import datetime
import requests
import random
import time
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

import firebase_admin
from firebase_admin import credentials, auth
from hivmeet_backend.settings import FIREBASE_CREDENTIALS_PATH

User = get_user_model()

# Données des utilisateurs de test
TEST_USERS_DATA = [
    {
        'email': 'thomas.dupont@test.com',
        'display_name': 'Thomas',
        'birth_date': datetime(1988, 5, 15),
        'gender': 'male',
        'bio': 'Passionné de musique et de voyages. Je cherche une relation sérieuse basée sur la confiance et le respect.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Musique', 'Voyages', 'Sport', 'Cinéma'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 25,
        'age_max_preference': 45,
        'distance_max_km': 50,
        'genders_sought': ['female', 'non_binary'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 12, 31)
    },
    {
        'email': 'marc.bernard@test.com',
        'display_name': 'Marc',
        'birth_date': datetime(1984, 8, 22),
        'gender': 'male',
        'bio': 'Professionnel dans le domaine de la santé. J\'aime la lecture et les promenades en nature.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Lecture', 'Nature', 'Santé', 'Photographie'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 30,
        'genders_sought': ['female'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'pierre.martin@test.com',
        'display_name': 'Pierre',
        'birth_date': datetime(1994, 3, 10),
        'gender': 'male',
        'bio': 'Étudiant en informatique. Passionné de jeux vidéo et de nouvelles technologies.',
        'city': 'Marseille',
        'country': 'France',
        'interests': ['Jeux vidéo', 'Informatique', 'Technologie', 'Sport'],
        'relationship_types_sought': ['casual', 'friendship'],
        'age_min_preference': 20,
        'age_max_preference': 35,
        'distance_max_km': 25,
        'genders_sought': ['female', 'male', 'non_binary'],
        'is_verified': False,
        'verification_status': 'pending',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'alex.chen@test.com',
        'display_name': 'Alex',
        'birth_date': datetime(1987, 11, 5),
        'gender': 'trans_male',
        'bio': 'Artiste et militant LGBTQ+. Je cherche des personnes ouvertes d\'esprit et bienveillantes.',
        'city': 'Toulouse',
        'country': 'France',
        'interests': ['Art', 'LGBTQ+', 'Militantisme', 'Musique'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 40,
        'genders_sought': ['female', 'male', 'non_binary'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 10, 15)
    },
    {
        'email': 'samuel.rodriguez@test.com',
        'display_name': 'Samuel',
        'birth_date': datetime(1981, 12, 18),
        'gender': 'male',
        'bio': 'Chef cuisinier passionné. J\'aime partager ma passion pour la gastronomie et découvrir de nouvelles saveurs.',
        'city': 'Bordeaux',
        'country': 'France',
        'interests': ['Cuisine', 'Gastronomie', 'Voyages', 'Culture'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 35,
        'age_max_preference': 55,
        'distance_max_km': 60,
        'genders_sought': ['female'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 11, 30)
    },
    {
        'email': 'sophie.leroy@test.com',
        'display_name': 'Sophie',
        'birth_date': datetime(1991, 7, 8),
        'gender': 'female',
        'bio': 'Architecte créative. J\'aime l\'art, l\'architecture et les voyages culturels.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Architecture', 'Art', 'Voyages', 'Design'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 28,
        'age_max_preference': 45,
        'distance_max_km': 35,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 9, 20)
    },
    {
        'email': 'marie.claire@test.com',
        'display_name': 'Marie',
        'birth_date': datetime(1986, 4, 12),
        'gender': 'female',
        'bio': 'Professeure de français. Passionnée de littérature et de poésie.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Littérature', 'Poésie', 'Enseignement', 'Lecture'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 25,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'julie.moreau@test.com',
        'display_name': 'Julie',
        'birth_date': datetime(1995, 9, 25),
        'gender': 'female',
        'bio': 'Étudiante en psychologie. J\'aime comprendre les gens et les aider.',
        'city': 'Marseille',
        'country': 'France',
        'interests': ['Psychologie', 'Aide aux autres', 'Sport', 'Musique'],
        'relationship_types_sought': ['casual', 'friendship'],
        'age_min_preference': 20,
        'age_max_preference': 30,
        'distance_max_km': 20,
        'genders_sought': ['male', 'female'],
        'is_verified': False,
        'verification_status': 'not_submitted',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'emma.taylor@test.com',
        'display_name': 'Emma',
        'birth_date': datetime(1989, 2, 14),
        'gender': 'trans_female',
        'bio': 'Infirmière dévouée. Je cherche quelqu\'un qui accepte et respecte mon identité.',
        'city': 'Toulouse',
        'country': 'France',
        'interests': ['Santé', 'Soins', 'LGBTQ+', 'Sport'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 30,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 8, 10)
    },
    {
        'email': 'camille.dubois@test.com',
        'display_name': 'Camille',
        'birth_date': datetime(1984, 6, 30),
        'gender': 'female',
        'bio': 'Avocate spécialisée en droit social. J\'aime la justice et l\'équité.',
        'city': 'Bordeaux',
        'country': 'France',
        'interests': ['Droit', 'Justice', 'Lecture', 'Voyages'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 35,
        'age_max_preference': 55,
        'distance_max_km': 40,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 12, 31)
    },
    {
        'email': 'riley.smith@test.com',
        'display_name': 'Riley',
        'birth_date': datetime(1992, 1, 20),
        'gender': 'non_binary',
        'bio': 'Développeur web et militant pour les droits numériques. Je crois en un internet libre et accessible.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Programmation', 'Droits numériques', 'Technologie', 'Militantisme'],
        'relationship_types_sought': ['friendship', 'long_term'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 30,
        'genders_sought': ['male', 'female', 'non_binary'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'jordan.lee@test.com',
        'display_name': 'Jordan',
        'birth_date': datetime(1988, 10, 8),
        'gender': 'non_binary',
        'bio': 'Artiste visuel et photographe. Je capture la beauté de la diversité humaine.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Photographie', 'Art', 'LGBTQ+', 'Voyages'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 28,
        'age_max_preference': 45,
        'distance_max_km': 35,
        'genders_sought': ['male', 'female', 'non_binary'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 7, 15)
    },
    {
        'email': 'paul.durand@test.com',
        'display_name': 'Paul',
        'birth_date': datetime(1990, 3, 15),
        'gender': 'male',
        'bio': 'Mécanicien passionné de motos. J\'aime la mécanique et les sensations fortes.',
        'city': 'Nice',
        'country': 'France',
        'interests': ['Mécanique', 'Motos', 'Sport', 'Technique'],
        'relationship_types_sought': ['casual', 'friendship'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 25,
        'genders_sought': ['female'],
        'is_verified': False,
        'verification_status': 'rejected',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'lisa.garcia@test.com',
        'display_name': 'Lisa',
        'birth_date': datetime(1987, 11, 22),
        'gender': 'female',
        'bio': 'Designer graphique créative. J\'aime créer des visuels qui racontent des histoires.',
        'city': 'Strasbourg',
        'country': 'France',
        'interests': ['Design', 'Art', 'Créativité', 'Culture'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 28,
        'age_max_preference': 45,
        'distance_max_km': 30,
        'genders_sought': ['male'],
        'is_verified': False,
        'verification_status': 'expired',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'antoine.lefevre@test.com',
        'display_name': 'Antoine',
        'birth_date': datetime(1985, 7, 4),
        'gender': 'male',
        'bio': 'Ingénieur en énergies renouvelables. Je travaille pour un avenir plus durable.',
        'city': 'Montpellier',
        'country': 'France',
        'interests': ['Environnement', 'Développement durable', 'Science', 'Nature'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 40,
        'genders_sought': ['female'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 6, 30)
    },
    {
        'email': 'nina.kovac@test.com',
        'display_name': 'Nina',
        'birth_date': datetime(1993, 5, 18),
        'gender': 'female',
        'bio': 'Danseuse professionnelle. La danse est ma passion et ma vie.',
        'city': 'Nantes',
        'country': 'France',
        'interests': ['Danse', 'Art', 'Performance', 'Musique'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 35,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'marcus.wilson@test.com',
        'display_name': 'Marcus',
        'birth_date': datetime(1982, 9, 12),
        'gender': 'male',
        'bio': 'Professeur d\'anglais américain. J\'aime partager ma culture et apprendre des autres.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Enseignement', 'Langues', 'Culture', 'Voyages'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 50,
        'genders_sought': ['female'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 4, 15)
    },
    {
        'email': 'sarah.connor@test.com',
        'display_name': 'Sarah',
        'birth_date': datetime(1989, 12, 3),
        'gender': 'female',
        'bio': 'Médecin généraliste. Je soigne les corps et les cœurs avec bienveillance.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Médecine', 'Santé', 'Lecture', 'Sport'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 28,
        'age_max_preference': 45,
        'distance_max_km': 30,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 11, 20)
    },
    {
        'email': 'kevin.zhang@test.com',
        'display_name': 'Kevin',
        'birth_date': datetime(1991, 4, 25),
        'gender': 'male',
        'bio': 'Développeur de jeux vidéo. Je crée des mondes virtuels et je cherche ma princesse dans le monde réel.',
        'city': 'Marseille',
        'country': 'France',
        'interests': ['Jeux vidéo', 'Programmation', 'Technologie', 'Science-fiction'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 25,
        'age_max_preference': 35,
        'distance_max_km': 25,
        'genders_sought': ['female'],
        'is_verified': False,
        'verification_status': 'pending',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'amelie.rousseau@test.com',
        'display_name': 'Amélie',
        'birth_date': datetime(1986, 8, 14),
        'gender': 'female',
        'bio': 'Vétérinaire passionnée d\'animaux. J\'aime soigner et protéger tous les êtres vivants.',
        'city': 'Toulouse',
        'country': 'France',
        'interests': ['Animaux', 'Vétérinaire', 'Nature', 'Sport'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 40,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'david.kim@test.com',
        'display_name': 'David',
        'birth_date': datetime(1988, 1, 30),
        'gender': 'male',
        'bio': 'Chef d\'entreprise dans le secteur technologique. Je cherche quelqu\'un qui partage mes valeurs.',
        'city': 'Paris',
        'country': 'France',
        'interests': ['Entrepreneuriat', 'Technologie', 'Business', 'Sport'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 25,
        'age_max_preference': 45,
        'distance_max_km': 60,
        'genders_sought': ['female'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 12, 31)
    },
    {
        'email': 'clara.martinez@test.com',
        'display_name': 'Clara',
        'birth_date': datetime(1994, 6, 22),
        'gender': 'female',
        'bio': 'Étudiante en médecine. Je travaille dur pour réaliser mes rêves et aider les autres.',
        'city': 'Bordeaux',
        'country': 'France',
        'interests': ['Médecine', 'Études', 'Sport', 'Musique'],
        'relationship_types_sought': ['casual', 'friendship'],
        'age_min_preference': 20,
        'age_max_preference': 30,
        'distance_max_km': 20,
        'genders_sought': ['male'],
        'is_verified': False,
        'verification_status': 'not_submitted',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'lucas.anderson@test.com',
        'display_name': 'Lucas',
        'birth_date': datetime(1983, 11, 8),
        'gender': 'male',
        'bio': 'Policier dévoué. Je protège et je sers avec honneur et intégrité.',
        'city': 'Nice',
        'country': 'France',
        'interests': ['Sécurité', 'Sport', 'Justice', 'Famille'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 25,
        'age_max_preference': 45,
        'distance_max_km': 35,
        'genders_sought': ['female'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 8, 25)
    },
    {
        'email': 'zoe.thompson@test.com',
        'display_name': 'Zoé',
        'birth_date': datetime(1990, 3, 17),
        'gender': 'female',
        'bio': 'Journaliste indépendante. Je raconte les histoires qui méritent d\'être entendues.',
        'city': 'Strasbourg',
        'country': 'France',
        'interests': ['Journalisme', 'Écriture', 'Voyages', 'Culture'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 28,
        'age_max_preference': 45,
        'distance_max_km': 30,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'max.weber@test.com',
        'display_name': 'Max',
        'birth_date': datetime(1987, 7, 29),
        'gender': 'male',
        'bio': 'Psychologue clinicien. J\'aide les gens à mieux se comprendre et à s\'épanouir.',
        'city': 'Montpellier',
        'country': 'France',
        'interests': ['Psychologie', 'Aide aux autres', 'Lecture', 'Sport'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 40,
        'genders_sought': ['female'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 9, 10)
    },
    {
        'email': 'elena.petrov@test.com',
        'display_name': 'Elena',
        'birth_date': datetime(1985, 12, 11),
        'gender': 'female',
        'bio': 'Scientifique en recherche médicale. Je travaille pour améliorer la santé de tous.',
        'city': 'Nantes',
        'country': 'France',
        'interests': ['Science', 'Recherche', 'Santé', 'Lecture'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 30,
        'age_max_preference': 50,
        'distance_max_km': 35,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': True,
        'premium_until': datetime(2025, 7, 5)
    },
    {
        'email': 'adrian.rodriguez@test.com',
        'display_name': 'Adrian',
        'birth_date': datetime(1992, 2, 28),
        'gender': 'male',
        'bio': 'Éducateur spécialisé. Je travaille avec des enfants en difficulté et j\'aime les aider à grandir.',
        'city': 'Lyon',
        'country': 'France',
        'interests': ['Éducation', 'Enfants', 'Aide aux autres', 'Sport'],
        'relationship_types_sought': ['long_term'],
        'age_min_preference': 25,
        'age_max_preference': 40,
        'distance_max_km': 25,
        'genders_sought': ['female'],
        'is_verified': False,
        'verification_status': 'pending',
        'is_premium': False,
        'premium_until': None
    },
    {
        'email': 'isabella.silva@test.com',
        'display_name': 'Isabella',
        'birth_date': datetime(1989, 10, 5),
        'gender': 'female',
        'bio': 'Archéologue passionnée. Je découvre les secrets du passé et je partage ma passion pour l\'histoire.',
        'city': 'Marseille',
        'country': 'France',
        'interests': ['Archéologie', 'Histoire', 'Voyages', 'Culture'],
        'relationship_types_sought': ['long_term', 'friendship'],
        'age_min_preference': 28,
        'age_max_preference': 45,
        'distance_max_km': 50,
        'genders_sought': ['male'],
        'is_verified': True,
        'verification_status': 'verified',
        'is_premium': False,
        'premium_until': None
    }
]

def download_random_photo(gender, index):
    """
    Télécharge une photo aléatoire depuis Pexels (plus fiable qu'Unsplash).
    """
    try:
        # Utiliser Pexels qui est plus stable
        # Catégories adaptées au genre
        if gender in ['male', 'trans_male']:
            search_terms = ['man', 'portrait', 'business', 'professional', 'guy']
        elif gender in ['female', 'trans_female']:
            search_terms = ['woman', 'portrait', 'fashion', 'professional', 'girl']
        else:
            search_terms = ['portrait', 'people', 'professional', 'person']
        
        search_term = random.choice(search_terms)
        
        # Utiliser Pexels via leur API publique (sans clé API)
        # Format: https://images.pexels.com/photos/[id]/pexels-photo-[id].jpeg
        # Nous allons utiliser des IDs d'images populaires de Pexels
        pexels_photo_ids = [
            # Photos masculines
            3184291, 3184292, 3184293, 3184294, 3184295,  # Hommes professionnels
            3184296, 3184297, 3184298, 3184299, 3184300,  # Portraits masculins
            # Photos féminines  
            3184301, 3184302, 3184303, 3184304, 3184305,  # Femmes professionnelles
            3184306, 3184307, 3184308, 3184309, 3184310,  # Portraits féminins
            # Photos neutres
            3184311, 3184312, 3184313, 3184314, 3184315,  # Portraits neutres
        ]
        
        photo_id = random.choice(pexels_photo_ids)
        url = f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?auto=compress&cs=tinysrgb&w=400&h=600&fit=crop"
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        # Créer un nom de fichier unique
        filename = f"profile_photos/{gender}_{index}_{int(time.time())}.jpg"
        
        # Sauvegarder l'image
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        
        file_content = ContentFile(response.content)
        saved_path = None
        
        print(f"   📸 Photo téléchargée: {saved_path}")
        return response.content
        
    except Exception as e:
        print(f"   ⚠️  Erreur téléchargement photo: {e}")
        # En cas d'échec, retourner un chemin fictif pour continuer
        return f"profile_photos/placeholder_{gender}_{index}.jpg"

def attach_private_test_photo(profile, image_data, *, is_main, order=0):
    """Use the phase-2 private-media boundary for seed photos."""
    stored = profile_photo_storage.upload_image(
        image_data=image_data,
        owner_id=str(profile.user_id),
    )
    return ProfilePhoto.objects.create(
        profile=profile,
        photo_url='',
        thumbnail_url='',
        storage_key=stored['storage_key'],
        thumbnail_storage_key=stored['thumbnail_storage_key'],
        storage_state=ProfilePhoto.PRIVATE,
        is_main=is_main,
        is_approved=True,
        order=order,
    )


def create_test_user(user_data):
    """
    Crée un utilisateur de test avec son profil et ses photos.
    """
    try:
        # Créer l'utilisateur
        user = User.objects.create(
            email=user_data['email'],
            display_name=user_data['display_name'],
            birth_date=user_data['birth_date'],
            is_verified=user_data['is_verified'],
            verification_status=user_data['verification_status'],
            is_premium=user_data['is_premium'],
            premium_until=user_data['premium_until'],
            email_verified=True,
            is_active=True,
            role='user'
        )
        
        # Définir le mot de passe
        user.set_password('testpass123')
        
        try:
            firebase_user = auth.create_user(
                email=user_data['email'],
                password='testpass123',
                display_name=user_data['display_name']
            )
            user.firebase_uid = firebase_user.uid
            print(f"   🔥 Utilisateur Firebase créé: UID {user.firebase_uid}")
        except Exception as e:
            print(f"   ⚠️ Erreur lors de la création Firebase: {e}")
            return None

        user.save()
        
        # Créer le profil manuellement (sans signal)
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
        
        # Ajouter des coordonnées géographiques aléatoires
        profile.latitude = 48.8566 + random.uniform(-0.1, 0.1)  # Paris ±0.1°
        profile.longitude = 2.3522 + random.uniform(-0.1, 0.1)
        profile.save()
        
        # Créer l'enregistrement de vérification manuellement
        Verification.objects.create(
            user=user,
            status=user_data['verification_status']
        )
        
        # Télécharger et ajouter une photo principale
        photo_data = download_random_photo(user_data['gender'], len(TEST_USERS_DATA))
        if photo_data:
            attach_private_test_photo(profile, photo_data, is_main=True)
        
        # Ajouter des photos supplémentaires pour les utilisateurs premium
        if user_data['is_premium']:
            num_extra_photos = random.randint(1, 3)
            for i in range(num_extra_photos):
                extra_photo_data = download_random_photo(user_data['gender'], f"{len(TEST_USERS_DATA)}_extra_{i}")
                if extra_photo_data:
                    attach_private_test_photo(profile, extra_photo_data, is_main=False, order=i)
        
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
        
        try:
            firebase_admin_user = auth.create_user(
                email='admin@hivmeet.com',
                password='adminpass123',
                display_name='Admin HIVMeet'
            )
            admin_user.firebase_uid = firebase_admin_user.uid
            print(f"   🔥 Admin Firebase créé: UID {admin_user.firebase_uid}")
        except Exception as e:
            print(f"   ⚠️ Erreur lors de la création Firebase admin: {e}")
            return None

        admin_user.save()
        
        # Créer le profil admin manuellement
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
        
        # Créer l'enregistrement de vérification admin
        Verification.objects.create(
            user=admin_user,
            status='verified'
        )
        
        print("✅ Utilisateur administrateur créé: admin@hivmeet.com")
        return admin_user
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'admin: {e}")
        return None

def force_cleanup():
    """
    Force la suppression de toutes les données existantes.
    """
    print("🧹 FORÇAGE DU NETTOYAGE COMPLET")
    print("="*50)
    
    try:
        with transaction.atomic():
            # Supprimer dans l'ordre pour éviter les contraintes
            Like.objects.all().delete()
            Message.objects.all().delete()
            Match.objects.all().delete()
            ProfilePhoto.objects.all().delete()
            Profile.objects.all().delete()
            Verification.objects.all().delete()
            User.objects.all().delete()
            
            print("✅ Nettoyage forcé terminé")
            
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage forcé: {e}")

def disable_signals():
    """
    Désactive temporairement les signaux pour éviter les conflits.
    """
    print("🔇 Désactivation des signaux...")
    
    # Désactiver les signaux en supprimant les receivers
    from profiles.signals import create_user_profile, cleanup_user_firebase
    
    # Supprimer les receivers
    post_save.disconnect(create_user_profile, sender=User)
    pre_delete.disconnect(cleanup_user_firebase, sender=User)
    
    print("✅ Signaux désactivés")

def enable_signals():
    """
    Réactive les signaux.
    """
    print("🔊 Réactivation des signaux...")
    
    # Réactiver les signaux
    from profiles.signals import create_user_profile, cleanup_user_firebase
    
    # Reconnecter les receivers
    post_save.connect(create_user_profile, sender=User)
    pre_delete.connect(cleanup_user_firebase, sender=User)
    
    print("✅ Signaux réactivés")

def main():
    """
    Fonction principale pour peupler la base de données.
    """
    print("🚀 PEUPLEMENT SANS SIGNAUX DE LA BASE DE DONNÉES")
    print("="*60)
    
    try:
        # Désactiver les signaux
        disable_signals()
        
        # Forcer le nettoyage
        force_cleanup()
        
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
            
    finally:
        # Réactiver les signaux
        enable_signals()

if __name__ == "__main__":
    main()
