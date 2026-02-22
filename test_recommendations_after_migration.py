"""
Test rapide du service de découverte après migration.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from matching.services import RecommendationService
from matching.models import InteractionHistory
from profiles.models import Profile

User = get_user_model()

# Test avec Marie
marie = User.objects.get(email='marie.claire@test.com')

print(f"\n👤 Utilisateur: {marie.display_name} ({marie.email})")
print(f"="*80)

# Vérifier InteractionHistory
history = InteractionHistory.objects.filter(user=marie, is_revoked=False)
print(f"\n📊 InteractionHistory:")
print(f"   Total interactions actives: {history.count()}")

# Compter les profils disponibles
all_profiles = Profile.objects.filter(
    user__is_active=True,
    user__email_verified=True,
    is_hidden=False,
    allow_profile_in_discovery=True
).exclude(user=marie).count()

print(f"\n📊 Profils totaux: {all_profiles}")

# Tester les recommandations
print(f"\n🎯 Test des recommandations...")
recommendations = RecommendationService.get_recommendations(marie, limit=20)

print(f"\n✅ Profils recommandés: {len(recommendations)}")

if recommendations:
    print(f"\n📋 Liste des profils:")
    for i, profile in enumerate(recommendations, 1):
        print(f"   {i}. {profile.user.display_name} ({profile.user.age} ans) - {profile.gender}")
else:
    print(f"\n❌ AUCUN PROFIL RECOMMANDÉ")
    print(f"\n🔍 Analyse des filtres du profil de Marie:")
    profile = marie.profile
    print(f"   - Distance max: {profile.distance_max_km} km")
    print(f"   - Localisation: lat={profile.latitude}, lon={profile.longitude}")
    print(f"   - Âge: {profile.age_min_preference}-{profile.age_max_preference} ans")
    print(f"   - Genres recherchés: {profile.genders_sought}")
    print(f"   - Types de relation: {profile.relationship_types_sought}")
    print(f"   - Seulement vérifiés: {profile.verified_only}")
    print(f"   - Seulement en ligne: {profile.online_only}")

print(f"\n" + "="*80)
