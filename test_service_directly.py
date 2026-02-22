#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from matching.services import RecommendationService

print("\n" + "="*80)
print("🔍 TEST - RecommendationService avec une femme cherchant des hommes")
print("="*80 + "\n")

# Trouver une femme
female_profile = Profile.objects.filter(gender='female').first()

if female_profile:
    print(f"Utilisatrice: {female_profile.user.email}")
    print(f"  - Gender: {female_profile.gender}")
    print(f"  - Genders_sought: {female_profile.genders_sought}")
    
    print(f"\nAppel du service RecommendationService.get_recommendations()...")
    results = RecommendationService.get_recommendations(
        user=female_profile.user,
        limit=10,
        offset=0
    )
    
    print(f"\nRésultats: {len(results)} profils retournés")
    print(f"Attendu: > 0 (car {len([p for p in Profile.objects.filter(gender='male')])} profils mâles existent)")
    
    if results:
        print("\nProfils retournés:")
        for r in results[:3]:
            print(f"  - {r.user.email} (gender={r.gender})")
    else:
        print("\n❌ PROBLÈME: 0 profils retournés pour une femme cherchant des hommes!")
else:
    print("Aucune femme trouvée")

print("\n" + "="*80 + "\n")
