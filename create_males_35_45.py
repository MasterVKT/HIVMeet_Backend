#!/usr/bin/env python
import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile

User = get_user_model()

MALE_FIXTURES = [
    {"email": "male35@test.com", "birth_date": date(1991, 6, 15)},
    {"email": "male37@test.com", "birth_date": date(1989, 3, 22)},
    {"email": "male40@test.com", "birth_date": date(1986, 11, 9)},
    {"email": "male42@test.com", "birth_date": date(1984, 8, 2)},
    {"email": "male45@test.com", "birth_date": date(1981, 1, 30)},
]

created = 0
for fixture in MALE_FIXTURES:
    email = fixture["email"]
    birth_date = fixture["birth_date"]
    if User.objects.filter(email=email).exists():
        print(f"➡️  Existant: {email}")
        continue
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        birth_date=birth_date,
        email_verified=True,
        is_active=True,
    )
    profile = user.profile
    profile.gender = 'male'
    profile.genders_sought = ['female']
    profile.allow_profile_in_discovery = True
    profile.is_hidden = False
    profile.save()
    created += 1
    print(f"✅ Créé: {email} (age ~{date.today().year - birth_date.year})")

print(f"\nRésumé: {created} profils créés ou déjà présents")
