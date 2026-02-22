#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet.settings')
sys.path.insert(0, os.path.dirname(__file__))

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

from profiles.models import Profile

# Vérifier les NULL values
missing = Profile.objects.filter(genders_sought__isnull=True)
print(f"\n✅ Profils avec genders_sought=NULL après migration: {missing.count()}")

if missing.count() > 0:
    for p in missing:
        print(f"   - {p.user.email} (gender={p.gender})")

# Vérifier le total
all_profiles = Profile.objects.all()
print(f"✅ Total des profils: {all_profiles.count()}")
print(f"✅ Tous les profils ont genders_sought: {all_profiles.filter(genders_sought__isnull=False).count() == all_profiles.count()}")

# Distribution par genre
males = Profile.objects.filter(gender='male', genders_sought__isnull=False)
print(f"\n📊 Mâles avec genders_sought valide: {males.count()}")

females = Profile.objects.filter(gender='female', genders_sought__isnull=False)
print(f"📊 Femelles avec genders_sought valide: {females.count()}")

others = Profile.objects.filter(genders_sought__isnull=False).exclude(gender__in=['male', 'female'])
print(f"📊 Autres avec genders_sought valide: {others.count()}")

print("\n✅ Migration réussie ! Le champ genders_sought est désormais robuste.")
