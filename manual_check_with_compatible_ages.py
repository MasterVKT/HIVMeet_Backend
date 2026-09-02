#!/usr/bin/env python
import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "="*80)
print("✨ CRÉATION DE PROFILS DE TEST COMPATIBLES")
print("="*80 + "\n")

# Créer un mâle jeune
young_male_user = User.objects.create_user(
    email='test_young_male@test.com',
    password='testpass123',
    birth_date=date(2000, 5, 15),  # 24 ans
    email_verified=True
)

young_male_profile = young_male_user.profile
young_male_profile.gender = 'male'
young_male_profile.genders_sought = ['female']
young_male_profile.allow_profile_in_discovery = True
young_male_profile.save()

print(f"✅ Mâle créé: test_young_male@test.com")
print(f"   - Age: 24 ans")
print(f"   - genders_sought: ['female']")

# Créer une femme avec plage d'âge compatible
young_female_user = User.objects.create_user(
    email='test_young_female@test.com',
    password='testpass123',
    birth_date=date(1998, 3, 20),  # 26 ans
    email_verified=True
)

young_female_profile = young_female_user.profile
young_female_profile.gender = 'female'
young_female_profile.genders_sought = ['male']
young_female_profile.age_min_preference = 22  # Accepte mâles 22-28
young_female_profile.age_max_preference = 28
young_female_profile.allow_profile_in_discovery = True
young_female_profile.save()

print(f"\n✅ Femme créée: test_young_female@test.com")
print(f"   - Age: 26 ans")
print(f"   - Cherche: mâles 22-28 ans")
print(f"   - genders_sought: ['male']")

print("\n" + "-"*80)
print("🧪 TEST DU SERVICE\n")

from matching.services import RecommendationService

results = RecommendationService.get_recommendations(
    user=young_female_user,
    limit=10,
    offset=0
)

print(f"Résultats pour test_young_female@test.com: {len(results)} profils")

if len(results) > 0:
    print("✅ SUCCÈS - Profils retournés !")
    for r in results[:3]:
        age = date.today().year - r.user.birth_date.year
        print(f"   - {r.user.email} ({age} ans, gender={r.gender})")
else:
    print("❌ ÉCHOUÉ - Aucun profil retourné")

print("\n" + "="*80 + "\n")
