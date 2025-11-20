#!/usr/bin/env python3
"""
Script de génération d'interactions de test pour HIVMeet.

Ce script crée des matches, messages, likes et autres interactions
entre les utilisateurs de test pour simuler une utilisation réelle.
"""

import os
import sys
import django
import random
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from authentication.models import User
from profiles.models import Profile
from matching.models import Match, Like
from messaging.models import Message

User = get_user_model()

# Messages de test variés
TEST_MESSAGES = [
    "Salut ! Comment ça va ?",
    "J'ai aimé ton profil, on pourrait discuter ?",
    "Salut ! J'ai vu qu'on avait des centres d'intérêt en commun.",
    "Bonjour ! Comment s'est passée ta journée ?",
    "Salut ! J'aimerais apprendre à te connaître.",
    "Hey ! Ton profil m'a beaucoup plu.",
    "Salut ! On a l'air d'avoir des choses en commun.",
    "Bonjour ! Comment vas-tu ?",
    "Salut ! J'ai remarqué ton profil, il est intéressant.",
    "Hey ! Ça te dirait de discuter un peu ?",
    "Salut ! J'aime bien ton approche de la vie.",
    "Bonjour ! Comment s'est passée ta semaine ?",
    "Salut ! On pourrait échanger sur nos passions ?",
    "Hey ! Ton profil m'a fait sourire.",
    "Salut ! J'aimerais en savoir plus sur toi.",
    "Bonjour ! Comment vas-tu aujourd'hui ?",
    "Salut ! On a l'air d'avoir des valeurs communes.",
    "Hey ! J'ai apprécié ta bio.",
    "Salut ! Ça te dirait de partager tes expériences ?",
    "Bonjour ! Comment s'est passée ta journée ?"
]

def create_test_likes():
    """
    Crée des likes entre utilisateurs compatibles.
    """
    print("💕 Création des likes de test...")
    
    users = list(User.objects.filter(is_active=True).exclude(role='admin'))
    created_likes = 0
    
    for user in users:
        if not user.is_verified:
            continue
            
        # Trouver des utilisateurs compatibles
        user_profile = user.profile
        compatible_users = []
        
        for other_user in users:
            if other_user == user or not other_user.is_verified:
                continue
                
            other_profile = other_user.profile
            
            # Vérifier la compatibilité
            if (other_user.age >= user_profile.age_min_preference and 
                other_user.age <= user_profile.age_max_preference and
                other_profile.gender in user_profile.genders_sought and
                user_profile.gender in other_profile.genders_sought):
                
                compatible_users.append(other_user)
        
        # Créer 1-3 likes par utilisateur (si des utilisateurs compatibles existent)
        if compatible_users:
            num_likes = random.randint(1, min(3, len(compatible_users)))
            selected_users = random.sample(compatible_users, num_likes)
        else:
            continue
        
        for liked_user in selected_users:
            try:
                like, created = Like.objects.get_or_create(
                    from_user=user,
                    to_user=liked_user,
                    defaults={
                        'like_type': random.choice(['regular', 'super']),
                        'created_at': timezone.now() - timedelta(days=random.randint(1, 30))
                    }
                )
                if created:
                    created_likes += 1
            except Exception as e:
                print(f"Erreur lors de la création du like: {e}")
    
    print(f"✅ {created_likes} likes créés")

def create_test_matches():
    """
    Crée des matches basés sur les likes mutuels.
    """
    print("💘 Création des matches de test...")
    
    # Trouver les likes mutuels
    likes = Like.objects.all()
    created_matches = 0
    
    for like in likes:
        # Vérifier s'il y a un like réciproque
        reciprocal_like = Like.objects.filter(
            from_user=like.to_user,
            to_user=like.from_user
        ).first()
        
        if reciprocal_like:
            # Créer un match
            try:
                match, created = Match.objects.get_or_create(
                    user1=like.from_user,
                    user2=like.to_user,
                    defaults={
                        'status': 'active',
                        'created_at': min(like.created_at, reciprocal_like.created_at),
                        'last_message_at': timezone.now() - timedelta(days=random.randint(1, 7))
                    }
                )
                if created:
                    created_matches += 1
            except Exception as e:
                print(f"Erreur lors de la création du match: {e}")
    
    print(f"✅ {created_matches} matches créés")

def create_test_messages():
    """
    Crée des messages dans les matches existants.
    """
    print("💬 Création des messages de test...")
    
    matches = Match.objects.filter(status='active')
    created_messages = 0
    
    for match in matches:
        users = [match.user1, match.user2]
        if len(users) != 2:
            continue
            
        # Créer 3-8 messages par conversation
        num_messages = random.randint(3, 8)
        
        for i in range(num_messages):
            sender = random.choice(users)
            content = random.choice(TEST_MESSAGES)
            
            # Créer des messages avec des timestamps progressifs
            message_time = match.created_at + timedelta(
                days=random.randint(1, 7),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            try:
                message = Message.objects.create(
                    match=match,
                    sender=sender,
                    content=content,
                    message_type='text',
                    created_at=message_time,
                    status='sent'
                )
                created_messages += 1
                
                # Mettre à jour le dernier message du match
                if message.created_at > match.last_message_at:
                    match.last_message_at = message.created_at
                    match.save()
                    
            except Exception as e:
                print(f"Erreur lors de la création du message: {e}")
    
    print(f"✅ {created_messages} messages créés")

def create_test_blocks():
    """
    Crée quelques blocages entre utilisateurs.
    """
    print("🚫 Création des blocages de test...")
    
    users = list(User.objects.filter(is_active=True).exclude(role='admin'))
    created_blocks = 0
    
    # Créer 2-5 blocages
    num_blocks = random.randint(2, 5)
    
    for _ in range(num_blocks):
        user1, user2 = random.sample(users, 2)
        
        try:
            user1.blocked_users.add(user2)
            created_blocks += 1
            print(f"   - {user1.display_name} a bloqué {user2.display_name}")
        except Exception as e:
            print(f"Erreur lors de la création du blocage: {e}")
    
    print(f"✅ {created_blocks} blocages créés")

def update_user_activity():
    """
    Met à jour les timestamps d'activité des utilisateurs.
    """
    print("⏰ Mise à jour des timestamps d'activité...")
    
    users = User.objects.filter(is_active=True)
    
    for user in users:
        # Définir une activité récente aléatoire
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        
        user.last_active = timezone.now() - timedelta(days=days_ago, hours=hours_ago)
        user.save()
    
    print(f"✅ Activité mise à jour pour {users.count()} utilisateurs")

def create_test_data_summary():
    """
    Affiche un résumé des données de test créées.
    """
    print("\n📊 RÉSUMÉ DES DONNÉES DE TEST")
    print("=" * 50)
    
    total_users = User.objects.filter(is_active=True).exclude(role='admin').count()
    verified_users = User.objects.filter(is_verified=True).count()
    premium_users = User.objects.filter(is_premium=True).count()
    total_likes = Like.objects.count()
    total_matches = Match.objects.count()
    total_messages = Message.objects.count()
    total_blocks = sum([user.blocked_users.count() for user in User.objects.all()])
    
    print(f"👥 Utilisateurs: {total_users}")
    print(f"✅ Vérifiés: {verified_users}")
    print(f"💎 Premium: {premium_users}")
    print(f"💕 Likes: {total_likes}")
    print(f"💘 Matches: {total_matches}")
    print(f"💬 Messages: {total_messages}")
    print(f"🚫 Blocages: {total_blocks}")
    
    # Statistiques par genre
    profiles = Profile.objects.all()
    gender_stats = {}
    for profile in profiles:
        gender = profile.gender
        gender_stats[gender] = gender_stats.get(gender, 0) + 1
    
    print(f"\n👫 Répartition par genre:")
    for gender, count in gender_stats.items():
        print(f"   - {gender}: {count}")
    
    # Statistiques par ville
    city_stats = {}
    for profile in profiles:
        city = profile.city
        if city:
            city_stats[city] = city_stats.get(city, 0) + 1
    
    print(f"\n🏙️  Répartition par ville:")
    for city, count in sorted(city_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {city}: {count}")

def main():
    """
    Fonction principale pour créer les interactions de test.
    """
    print("🚀 Début de la création des interactions de test...")
    
    # Vérifier qu'il y a des utilisateurs
    if User.objects.count() == 0:
        print("❌ Aucun utilisateur trouvé. Veuillez d'abord exécuter populate_test_users.py")
        return
    
    # Créer les interactions
    create_test_likes()
    create_test_matches()
    create_test_messages()
    create_test_blocks()
    update_user_activity()
    
    # Afficher le résumé
    create_test_data_summary()
    
    print("\n🎉 Création des interactions terminée!")
    print("\n💡 Conseils pour les tests:")
    print("   - Testez le matching avec différents filtres")
    print("   - Vérifiez les conversations dans les matches")
    print("   - Testez les fonctionnalités premium")
    print("   - Vérifiez les blocages et la modération")

if __name__ == "__main__":
    main() 