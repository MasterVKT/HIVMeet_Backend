#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "="*80)
print("🔍 DIAGNOSTIC DISCOVERY FILTER - Profils Mâles Éligibles")
print("="*80 + "\n")

# Étape 1: Tous les profils mâles
total_males = Profile.objects.filter(gender='male').count()
print(f"1️⃣  Tous les profils mâles: {total_males}")

# Étape 2: Mâles actifs
active_males = Profile.objects.filter(
    gender='male',
    user__is_active=True
).count()
print(f"2️⃣  Mâles avec user__is_active=True: {active_males}")

# Étape 3: Mâles avec email vérifié
email_verified_males = Profile.objects.filter(
    gender='male',
    user__is_active=True,
    user__email_verified=True
).count()
print(f"3️⃣  Mâles avec email_verified=True: {email_verified_males}")

# Étape 4: Mâles non cachés
not_hidden_males = Profile.objects.filter(
    gender='male',
    user__is_active=True,
    user__email_verified=True,
    is_hidden=False
).count()
print(f"4️⃣  Mâles avec is_hidden=False: {not_hidden_males}")

# Étape 5: Mâles avec allow_profile_in_discovery
discovery_allowed_males = Profile.objects.filter(
    gender='male',
    user__is_active=True,
    user__email_verified=True,
    is_hidden=False,
    allow_profile_in_discovery=True
).count()
print(f"5️⃣  Mâles avec allow_profile_in_discovery=True: {discovery_allowed_males}")

print("\n" + "-"*80)
print("📊 RÉSUMÉ PAR CRITÈRE:")
print("-"*80 + "\n")

# Analyser où les profils se perdent
males_breakdown = {
    'Tous': total_males,
    'User actif': active_males,
    'Email vérifié': email_verified_males,
    'Non caché': not_hidden_males,
    'Discovery enabled': discovery_allowed_males
}

for i, (criterion, count) in enumerate(males_breakdown.items(), 1):
    print(f"{i}. {criterion:25} : {count:3} profils")

if discovery_allowed_males == 0:
    print("\n❌ PROBLÈME DÉTECTÉ: 0 profils mâles éligibles!")
    print("\n🔧 Diagnostic détaillé:\n")
    
    # Vérifier chaque critère individuellement
    only_not_active = Profile.objects.filter(
        gender='male',
        user__is_active=False
    ).count()
    print(f"   - Mâles NON actifs: {only_not_active}")
    
    only_not_verified = Profile.objects.filter(
        gender='male',
        user__is_active=True,
        user__email_verified=False
    ).count()
    print(f"   - Mâles (actifs) NON email vérifiés: {only_not_verified}")
    
    only_hidden = Profile.objects.filter(
        gender='male',
        user__is_active=True,
        user__email_verified=True,
        is_hidden=True
    ).count()
    print(f"   - Mâles (actifs, vérifiés) CACHÉS: {only_hidden}")
    
    only_discovery_disabled = Profile.objects.filter(
        gender='male',
        user__is_active=True,
        user__email_verified=True,
        is_hidden=False,
        allow_profile_in_discovery=False
    ).count()
    print(f"   - Mâles (actifs, vérifiés, visibles) Discovery DISABLED: {only_discovery_disabled}")
else:
    print(f"\n✅ {discovery_allowed_males} profils mâles ÉLIGIBLES pour Discovery!")

print("\n" + "="*80 + "\n")

# Vérifier aussi les genders_sought
print("📋 VÉRIFICATION genders_sought:\n")
males_with_gender_sought = Profile.objects.filter(
    gender='male',
    genders_sought__isnull=False
).exclude(genders_sought=[]).count()
males_empty_gender_sought = Profile.objects.filter(
    gender='male',
    genders_sought=[]
).count()
males_null_gender_sought = Profile.objects.filter(
    gender='male',
    genders_sought__isnull=True
).count()

print(f"   - Mâles avec genders_sought défini: {males_with_gender_sought}")
print(f"   - Mâles avec genders_sought vide []: {males_empty_gender_sought}")
print(f"   - Mâles avec genders_sought NULL: {males_null_gender_sought}")

print("\n" + "="*80 + "\n")
