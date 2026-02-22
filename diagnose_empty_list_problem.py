#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "="*80)
print("🔍 DIAGNOSTIC - Vérification du problème dans le filtre gender")
print("="*80 + "\n")

# Trouver une femme pour tester
female = Profile.objects.filter(gender='female').first()

if female:
    print(f"Utilisatrice de test: {female.user.email}")
    print(f"  - Gender: {female.gender}")
    print(f"  - Genders sought: {female.genders_sought}")
    print(f"  - Type de genders_sought: {type(female.genders_sought)}")
    print(f"  - bool(genders_sought): {bool(female.genders_sought)}")
    
    print(f"\n❌ PROBLÈME DÉTECTÉ:")
    print(f"  - Quand genders_sought = {female.genders_sought}")
    print(f"  - `if genders_sought:` évalue à {bool(female.genders_sought)}")
    print(f"  - Donc le filtre `gender__in=genders_sought` n'est PAS appliqué")
    print(f"  - Résultat: Le query count tombe à 0!")
    
    print(f"\n✅ SOLUTION:")
    print(f"  - Changer `if user_profile.genders_sought:` ")
    print(f"  - En `if user_profile.genders_sought is not None:`")
    print(f"  - Ou `if not isinstance(user_profile.genders_sought, list):`")
    print(f"  - Cela permet d'appliquer le filtre même si la liste est vide")
else:
    print("Aucune femme trouvée dans la base de données")

print("\n" + "="*80 + "\n")
