#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from django.db.models import Q

# Marie cherche: age_min_preference=30, age_max_preference=50, genders_sought=['male']
# Marie a: age=39

# Compter les profils mâles de 30-50 ans
males_in_range = Profile.objects.filter(
    gender='male',
    user__birth_date__year__range=[1976, 1996],  # 30-50 ans en 2026
    user__is_active=True,
    is_hidden=False,
    allow_profile_in_discovery=True
).count()

print(f"Profils mâles 30-50 ans, visibles: {males_in_range}")

# Ajouter le filtre d'interactions (historique dans matching.models)
from matching.models import InteractionHistory
excluded_ids = InteractionHistory.objects.filter(
    user_id='0e5ac2cb-07d8-4160-9f36-90393356f8c0',
    is_revoked=False
).values_list('target_user_id', flat=True)

available_males = males_in_range - len(excluded_ids)
print(f"Après exclusion interactions: {available_males}")