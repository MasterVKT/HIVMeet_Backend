"""
Script pour peupler la base de données avec des profils masculins
compatibles avec les filtres de Marie.

Cela permettra de tester la découverte avec des profils correspondants.
"""
import os
import sys
import django

# Forcer UTF-8 sur Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from profiles.models import Profile, ProfilePhoto
from datetime import date, timedelta
import random

User = get_user_model()

# Données pour créer des profils masculins
MALE_PROFILES = [
    {
        'first_name': 'Alexandre',
        'display_name': 'Alex',
        'email': 'alexandre.martin@test.com',
        'age': 35,
        'bio': "Passionné de musique et de voyages. Vivons positivement !",
        'interests': ['music', 'travel', 'cooking'],
    },
    {
        'first_name': 'Julien',
        'display_name': 'Jul',
        'email': 'julien.bernard@test.com',
        'age': 42,
        'bio': "Sportif et amateur de bon vin. Recherche relation sérieuse.",
        'interests': ['sports', 'wine', 'hiking'],
    },
    {
        'first_name': 'Nicolas',
        'display_name': 'Nico',
        'email': 'nicolas.dubois@test.com',
        'age': 38,
        'bio': "Entrepreneur et papa d'un enfant. J'aime la nature et les bons moments.",
        'interests': ['nature', 'business', 'family'],
    },
    {
        'first_name': 'Olivier',
        'display_name': 'Oli',
        'email': 'olivier.robert@test.com',
        'age': 45,
        'bio': "Médecin passionné par son métier. Recherche complicité et amitié.",
        'interests': ['medicine', 'reading', 'cinema'],
    },
    {
        'first_name': 'Fabien',
        'display_name': 'Fab',
        'email': 'fabien.durand@test.com',
        'age': 40,
        'bio': "Artiste et créatif. J'aime partager de bons moments autour d'un café.",
        'interests': ['art', 'coffee', 'photography'],
    },
    {
        'first_name': 'Benjamin',
        'display_name': 'Ben',
        'email': 'benjamin.moreau@test.com',
        'age': 36,
        'bio': "Ingénieur informatique et geek assumé. Fan de sci-fi !",
        'interests': ['technology', 'movies', 'gaming'],
    },
    {
        'first_name': 'Christophe',
        'display_name': 'Chris',
        'email': 'christophe.laurent@test.com',
        'age': 48,
        'bio': "Enseignant et militant associatif. Vivons ensemble, luttons ensemble.",
        'interests': ['education', 'activism', 'literature'],
    },
    {
        'first_name': 'Stéphane',
        'display_name': 'Steph',
        'email': 'stephane.simon@test.com',
        'age': 44,
        'bio': "Chef cuisinier et amoureux de gastronomie. La vie est un festin !",
        'interests': ['cooking', 'gastronomy', 'wine'],
    },
    {
        'first_name': 'Michaël',
        'display_name': 'Mika',
        'email': 'michael.michel@test.com',
        'age': 37,
        'bio': "Commercial et voyageur. J'aime découvrir de nouvelles cultures.",
        'interests': ['travel', 'culture', 'languages'],
    },
    {
        'first_name': 'François',
        'display_name': 'François',
        'email': 'francois.leroy@test.com',
        'age': 41,
        'bio': "Architecte et passionné d'urbanisme. Construisons ensemble !",
        'interests': ['architecture', 'design', 'urbanism'],
    },
]


def calculate_birth_date(age):
    """Calculer la date de naissance à partir de l'âge."""
    today = date.today()
    birth_year = today.year - age
    return date(birth_year, random.randint(1, 12), random.randint(1, 28))


@transaction.atomic
def create_male_profile(data):
    """Créer un profil masculin pour Marie."""
    
    # Vérifier si l'utilisateur existe déjà
    if User.objects.filter(email=data['email']).exists():
        print(f"⏭️  {data['display_name']} existe déjà")
        return None
    
    # Créer l'utilisateur
    birth_date = calculate_birth_date(data['age'])
    
    user = User.objects.create(
        email=data['email'],
        display_name=data['display_name'],
        birth_date=birth_date,
        is_active=True,
        email_verified=True,
        is_verified=random.choice([True, False]),  # 50% vérifié
    )
    
    # Note: On ne définit pas de mot de passe pour gagner du temps
    # Ces comptes sont uniquement pour les tests de découverte
    
    # Récupérer le profil créé automatiquement par le signal
    profile = user.profile
    
    # Mettre à jour le profil
    # Coordonnées proches de Paris (dans un rayon de 25 km)
    # Marie est à lat=48.9133492, lon=2.4489635
    latitude = 48.9133492 + random.uniform(-0.2, 0.2)  # ~±22 km
    longitude = 2.4489635 + random.uniform(-0.2, 0.2)
    
    profile.bio = data['bio']
    profile.gender = 'male'
    profile.interests = data['interests']
    profile.bio = data['bio']
    profile.gender = 'male'
    profile.interests = data['interests']
    profile.age_min_preference = 30
    profile.age_max_preference = 50
    profile.genders_sought = ['female']  # Recherche des femmes
    profile.relationship_types_sought = ['long_term', 'friendship']
    profile.distance_max_km = 30
    profile.latitude = latitude
    profile.longitude = longitude
    profile.is_hidden = False
    profile.allow_profile_in_discovery = True
    profile.save()
    
    print(f"✅ {data['display_name']} créé ({data['age']} ans, lat={latitude:.4f}, lon={longitude:.4f})")
    return user


def main():
    """Fonction principale."""
    print("\n" + "="*80)
    print("  PEUPLEMENT DE PROFILS MASCULINS POUR MARIE")
    print("="*80 + "\n")
    
    print(f"📊 Création de {len(MALE_PROFILES)} profils masculins...")
    print(f"   - Âge: 35-48 ans")
    print(f"   - Genre: male")
    print(f"   - Recherche: female")
    print(f"   - Distance: ~25 km de Paris")
    print(f"   - Compatible avec Marie (39 ans, female)\n")
    
    created = 0
    skipped = 0
    
    for profile_data in MALE_PROFILES:
        user = create_male_profile(profile_data)
        if user:
            created += 1
        else:
            skipped += 1
    
    print(f"\n{'='*80}")
    print(f"  RÉSUMÉ")
    print(f"{'='*80}\n")
    
    print(f"✅ Profils créés: {created}")
    print(f"⏭️  Déjà existants: {skipped}")
    
    if created > 0:
        print(f"\n🎉 SUCCÈS!")
        print(f"\n📱 Vous pouvez maintenant tester la découverte avec Marie.")
        print(f"   Les profils créés devraient apparaître dans la page de découverte.\n")
        
        # Vérifier Marie
        try:
            marie = User.objects.get(email='marie.claire@test.com')
            print(f"👤 Marie:")
            print(f"   - Âge: {marie.age} ans")
            print(f"   - Préférences: {marie.profile.age_min_preference}-{marie.profile.age_max_preference} ans")
            print(f"   - Recherche: {marie.profile.genders_sought}")
            print(f"   - Distance max: {marie.profile.distance_max_km} km")
            
            # Tester les recommandations
            from matching.services import RecommendationService
            recommendations = RecommendationService.get_recommendations(marie, limit=20)
            
            print(f"\n🎯 Test de découverte:")
            print(f"   - Profils recommandés: {len(recommendations)}")
            
            if recommendations:
                print(f"\n   Exemples:")
                for profile in recommendations[:5]:
                    print(f"   - {profile.user.display_name} ({profile.user.age} ans)")
            else:
                print(f"\n   ⚠️  Aucun profil recommandé (vérifier les filtres)")
                
        except User.DoesNotExist:
            print(f"\n⚠️  Marie non trouvée (marie.claire@test.com)")
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    main()
