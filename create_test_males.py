#!/usr/bin/env python
"""
Script pour créer des profils masculins de test via Django shell
"""
from django.contrib.auth import get_user_model
from users.models import UserProfile

User = get_user_model()

# Profils masculins à créer
male_profiles_data = [
    {
        'display_name': 'Julien',
        'gender': 'male',
        'genders_sought': ['female'],  # Added
        'bio': 'Ingénieur informatique passionné par la tech et le sport.',
        'age': 35,
        'interests': ['technology', 'sports', 'travel'],
        'relationship_types_sought': ['long_term', 'friendship'],
    },
    {
        'display_name': 'Marc',
        'gender': 'male',
        'genders_sought': ['female'],  # Added
        'bio': 'Professeur d\'histoire. Aime lire, les musées et les randos.',
        'age': 42,
        'interests': ['reading', 'history', 'hiking'],
        'relationship_types_sought': ['long_term', 'friendship'],
    },
    {
        'display_name': 'Antoine',
        'gender': 'male',
        'genders_sought': ['female'],  # Added
        'bio': 'Cuisinier passionné. Cherche quelqu\'un pour partager bons repas.',
        'age': 38,
        'interests': ['cooking', 'food', 'travel'],
        'relationship_types_sought': ['long_term', 'friendship'],
    },
    {
        'display_name': 'Nicolas',
        'gender': 'male',
        'genders_sought': ['female'],  # Added
        'bio': 'Musicien amateur. Joue de la guitare et adore les concerts.',
        'age': 33,
        'interests': ['music', 'concerts', 'arts'],
        'relationship_types_sought': ['long_term', 'friendship'],
    },
    {
        'display_name': 'David',
        'gender': 'male',
        'genders_sought': ['female'],  # Added
        'bio': 'Développeur full-stack. Féru de cinéma et de vidéos jeux.',
        'age': 31,
        'interests': ['programming', 'cinema', 'gaming'],
        'relationship_types_sought': ['long_term', 'friendship'],
    },
]

print("\n🔄 Création des profils masculins de test...\n")

count = 0

for data in male_profiles_data:
    email = f"{data['display_name'].lower()}@test.com"
    
    try:
        # Vérifier si l'utilisateur existe déjà
        user = User.objects.filter(email=email).first()
        
        if not user:
            # Créer l'utilisateur
            user = User.objects.create_user(
                email=email,
                password='testpass123',
                full_name=data['display_name'],
                is_active=True,
            )
            print(f"✅ Utilisateur créé: {email}")
        else:
            print(f"ℹ️  Utilisateur existe déjà: {email}")
        
        # Créer ou mettre à jour le profil
        profile, created = UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'display_name': data['display_name'],
                'gender': data['gender'],
                'genders_sought': data.get('genders_sought', ['female']),  # Added
                'bio': data['bio'],
                'age': data['age'],
                'interests': data['interests'],
                'relationship_types_sought': data['relationship_types_sought'],
                'is_active': True,
                'email_verified': True,
                'allow_in_discovery': True,
                'location': 'Paris',
                'is_verified': False,
            }
        )
        
        if created:
            print(f"✅ Profil créé: {data['display_name']} ({data['gender']}, {data['age']})")
        else:
            print(f"🔄 Profil mis à jour: {data['display_name']}")
        
        count += 1
        
    except Exception as e:
        print(f"❌ Erreur pour {data['display_name']}: {e}")

print(f"\n✅ {count} profils masculins de test créés/mis à jour!")
print("🔄 Vous pouvez maintenant relancer l'app Flutter")
