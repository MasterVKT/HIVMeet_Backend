#!/usr/bin/env python
"""
Script de test pour vérifier que la correction fonctionne correctement
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet.settings')
django.setup()

from profiles.models import Profile
from django.contrib.auth.models import User

# Vérifier les profils avec genders_sought manquants
print("\n" + "="*80)
print("🔍 Vérification post-migration:")
print("="*80)

missing = Profile.objects.filter(genders_sought__isnull=True)
print(f"\nProfils avec genders_sought=NULL: {missing.count()}")

for profile in missing:
    print(f"  - {profile.user.email} (gender={profile.gender})")

empty = Profile.objects.filter(genders_sought=[])
print(f"\nProfils avec genders_sought vide: {empty.count()}")

# Afficher les stats par genre
print("\n" + "="*80)
print("📊 Distribution des genders_sought par genre:")
print("="*80)

males = Profile.objects.filter(gender='male')
print(f"\nMâles ({males.count()}):")
print(f"  - Seeking females: {males.filter(genders_sought__contains=['female']).count()}")
print(f"  - NULL: {males.filter(genders_sought__isnull=True).count()}")

females = Profile.objects.filter(gender='female')
print(f"\nFemelles ({females.count()}):")
print(f"  - Seeking males: {females.filter(genders_sought__contains=['male']).count()}")
print(f"  - NULL: {females.filter(genders_sought__isnull=True).count()}")

# Vérifier la validité
all_profiles = Profile.objects.all()
print(f"\n✅ Total des profils: {all_profiles.count()}")
print(f"✅ Aucun NULL: {all_profiles.filter(genders_sought__isnull=False).count() == all_profiles.count()}")
