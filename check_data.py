#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile

# Vérifier les genres
all_genders = Profile.objects.values('gender').distinct()
print("Genres dans la base:", [g['gender'] for g in all_genders])

# Vérifier le nombre de femmes
female_count = Profile.objects.filter(gender='female').count()
print(f"Nombre de femmes: {female_count}")

# Vérifier le nombre de mâles
male_count = Profile.objects.filter(gender='male').count()
print(f"Nombre de mâles: {male_count}")

# Afficher le genre des 5 premiers profils
print("\n5 premiers profils:")
for p in Profile.objects.all()[:5]:
    print(f"  - {p.user.email}: gender={p.gender}, genders_sought={p.genders_sought}")
