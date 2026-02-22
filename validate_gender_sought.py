#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from django.db.models import Q

print("\n" + "="*80)
print("🔍 TEST VALIDATION - Champ gender_sought Robustness")
print("="*80 + "\n")

# Compter les profils mâles sans genders_sought
males_without = Profile.objects.filter(
    Q(gender='male') & (Q(genders_sought__isnull=True) | Q(genders_sought=[]))
).count()

print(f"✅ Profils mâles sans genders_sought: {males_without}")
print(f"   Attendu: 0")
if males_without == 0:
    print(f"   ✅ VALIDÉ\n")
else:
    print(f"   ❌ ÉCHOUÉ\n")

# Compter les profils mâles avec genders_sought contenant 'female'
males_with = Profile.objects.filter(
    gender='male', 
    genders_sought__contains=['female']
).count()

print(f"✅ Profils mâles avec genders_sought contenant 'female': {males_with}")
print(f"   (Attendu: > 0 si des mâles existent)\n")

# Vérifier tous les profils
all_profiles = Profile.objects.all().count()
null_count = Profile.objects.filter(genders_sought__isnull=True).count()

print(f"📊 Statistics:")
print(f"   - Total profils: {all_profiles}")
print(f"   - Profils avec NULL: {null_count}")
print(f"   - Profils valides: {all_profiles - null_count}")

if null_count == 0:
    print(f"\n✅ TOUS LES TESTS VALIDÉS - Migration réussie!")
else:
    print(f"\n❌ ATTENTION: {null_count} profils ont encore NULL!")

print("\n" + "="*80 + "\n")
