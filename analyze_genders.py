"""
Script pour analyser et corriger les genres des profils.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile
from collections import Counter

def analyze_genders():
    profiles = Profile.objects.select_related('user').all()
    total = profiles.count()
    
    print('=' * 60)
    print('STATISTIQUES DES GENRES ACTUELS')
    print('=' * 60)
    print(f'Total des profils: {total}')
    print()
    
    gender_counts = Counter(p.gender for p in profiles)
    for gender, count in gender_counts.most_common():
        print(f'  {gender}: {count}')
    
    print()
    print('=' * 60)
    print('PROFILS A CORRIGER (non male/female)')
    print('=' * 60)
    
    to_fix = profiles.exclude(gender='male').exclude(gender='female')
    print(f'Nombre de profils a corriger: {to_fix.count()}')
    print()
    
    for p in to_fix:
        first_name = p.user.display_name.split()[0] if p.user.display_name else 'Unknown'
        print(f'  - {p.user.display_name} ({first_name}) - Genre actuel: {p.gender}')

if __name__ == '__main__':
    analyze_genders()
