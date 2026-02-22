#!/usr/bin/env python
import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from django.db.models import F
from django.db.models.functions import ExtractYear

print("\n" + "="*80)
print("🔍 ANALYSE DES ÂGES")
print("="*80 + "\n")

# Âge de Julie
female = Profile.objects.filter(user__email='julie.moreau@test.com').first()
if female:
    age = date.today().year - female.user.birth_date.year
    print(f"Julie.moreau@test.com:")
    print(f"  - Birth date: {female.user.birth_date}")
    print(f"  - Age actuel: {age}")
    print(f"  - Cherche mâles entre: {female.age_min_preference}-{female.age_max_preference}")

print(f"\nÂges des profils mâles:")
males = Profile.objects.filter(gender='male').annotate(
    age = date.today().year - F('user__birth_date__year')
)
ages = []
for m in males:
    age = date.today().year - m.user.birth_date.year
    ages.append(age)
    if age < 20 or age > 30:
        print(f"  ❌ {m.user.email}: {age} ans (HORS PLAGE)")
    else:
        print(f"  ✅ {m.user.email}: {age} ans (IN RANGE)")

print(f"\nRésumé des mâles:")
print(f"  - Total: {len(ages)}")
print(f"  - Min age: {min(ages) if ages else 'N/A'}")
print(f"  - Max age: {max(ages) if ages else 'N/A'}")
in_range = sum(1 for a in ages if 20 <= a <= 30)
print(f"  - Entre 20-30: {in_range}")

print("\n" + "="*80 + "\n")
