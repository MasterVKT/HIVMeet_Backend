#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from django.db.models import Q

# Compter les profils mâles sans genders_sought valide
males_without = Profile.objects.filter(
    Q(gender='male') & Q(genders_sought__isnull=True)
).count()

print(f"Profils mâles sans genders_sought (NULL): {males_without}")
# Attendu: 0 (après migration)

# Compter les profils mâles avec genders_sought contenant 'female'
males_with_female = Profile.objects.filter(
    gender='male', 
    genders_sought__contains=['female']
).count()

print(f"Profils mâles avec genders_sought=['female']: {males_with_female}")
# Attendu: > 0 (valeurs corrigées)

# Vérifier l'intégrité globale
all_null = Profile.objects.filter(genders_sought__isnull=True).count()
print(f"\n✅ Intégrité globale - Profils avec NULL: {all_null}")
print(f"   Attendu: 0")

if males_without == 0 and all_null == 0:
    print("\n✅ VALIDATION RÉUSSIE")
else:
    print("\n❌ VALIDATION ÉCHOUÉE")