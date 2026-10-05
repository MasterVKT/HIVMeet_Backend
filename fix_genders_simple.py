"""
Script pour corriger les genres des profils - Version simple avec sortie fichier.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile

# Prénoms masculins
MALE_NAMES = {'alex', 'test', 'target', 'admin', 'xp', 'seeker'}
# Prénoms féminins
FEMALE_NAMES = {'emma'}

def main():
    output = []
    output.append('=' * 60)
    output.append('CORRECTION DES GENRES')
    output.append('=' * 60)
    
    profiles = Profile.objects.select_related('user').all()
    to_fix = profiles.exclude(gender='male').exclude(gender='female')
    
    output.append(f'Profils a traiter: {to_fix.count()}')
    output.append('')
    
    corrected = 0
    for p in to_fix:
        first_name = (p.user.display_name or '').split()[0].lower() if p.user.display_name else ''
        old = p.gender
        
        if first_name in MALE_NAMES:
            p.gender = 'male'
            corrected += 1
            output.append(f'OK: {p.user.display_name} -> male')
        elif first_name in FEMALE_NAMES:
            p.gender = 'female'
            corrected += 1
            output.append(f'OK: {p.user.display_name} -> female')
        else:
            # Autres -> male par défaut
            p.gender = 'male'
            corrected += 1
            output.append(f'DEFAULT: {p.user.display_name} ({first_name}) -> male')
        
        p.save(update_fields=['gender'])
    
    output.append('')
    output.append(f'Corriges: {corrected}')
    
    # Stats finales
    from collections import Counter
    gender_counts = Counter(p.gender for p in profiles)
    output.append('')
    output.append('STATS FINALES:')
    for g, c in gender_counts.items():
        output.append(f'  {g}: {c}')
    
    non_mf = profiles.exclude(gender='male').exclude(gender='female').count()
    output.append(f'Non male/female restants: {non_mf}')
    
    # Écrire dans fichier
    with open('gender_fix_result.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print('\n'.join(output))

if __name__ == '__main__':
    main()
