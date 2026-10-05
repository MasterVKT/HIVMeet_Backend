"""
Script pour corriger les genres des profils bas\u00e9s sur le pr\u00e9nom.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from profiles.models import Profile

# Mapping des pr\u00e9noms vers le genre (approximations bas\u00e9es sur les conventions)
# Pr\u00e9noms typiquement masculins
MALE_FIRST_NAMES = {
    'alex', 'alexandre', 'alexis', 'ali', 'aliou', 'ama', 'amine', 'amadou',
    'antoine', 'armand', 'arthur', 'aubin', 'augustin', 'baptiste', 'bastien',
    'benjamin', 'benoit', 'bernard', 'charles', 'chris', 'christian', 'christophe',
    'claude', 'clement', 'corentin', 'cyril', 'damien', 'daniel', 'david', 'denis',
    'desire', 'didier', 'dieudonne', 'dominique', 'emile', 'emmanuel', 'eric', 'etienne',
    'eugene', 'fabien', 'félix', 'francis', 'francois', 'frédéric', 'gabriel', 'gaston',
    'georges', 'gerald', 'germain', 'gilbert', 'gilles', 'gr\u00e9goire', 'guillaume',
    'guy', 'harold', 'henri', 'herve', 'honore', 'hubert', 'hugues', 'ivan', 'jacques',
    'jean', 'jean-paul', 'jerome', 'jocelyn', 'joel', 'johan', 'john', 'joseph', 'josue',
    'jules', 'julien', 'kevin', 'laurent', 'l\u00e9o', 'loic', 'louis', 'lucas', 'lucien',
    'marc', 'marcel', 'marius', 'martin', 'mathieu', 'matthew', 'michael', 'michel',
    'mohamed', 'mohammed', 'nicolas', 'noel', 'olivier', 'pascale', 'pascal', 'patrick',
    'paul', 'pierre', 'pierre-yves', 'quentin', 'raphael', 'raymond', 'regis', 'remi',
    'ren\u00e9', 'richard', 'robert', 'roger', 'roland', 's\u00e9bastien', 'serge', 's\u00e9raphin',
    'simon', 'stephane', 'sylvain', 'test', 'target', 'thomas', 'timoth\u00e9e', 'tom',
    'vincent', 'william', 'xp', 'yannick', 'yann', 'yves', 'admin',
}

# Pr\u00e9noms typiquement f\u00e9minins
FEMALE_FIRST_NAMES = {
    'agathe', 'alice', 'alie', 'alicia', 'allison', 'amandine', 'amy', 'andrea',
    'ang\u00e9lique', 'anna', 'anne', 'anne-marie', 'annick', 'audrey', 'aur\u00e9lie',
    'beatrice', 'bernadette', 'camille', 'carine', 'caroline', 'catherine', 'c\u00e9cile',
    'c\u00e9line', 'chantal', 'charlotte', 'chloe', 'christelle', 'christine', 'claire',
    'claudine', 'colette', 'corinne', 'daniella', 'danielle', 'delphine', 'denise',
    'diane', 'elodie', 'eline', 'emma', 'emmeline', 'estelle', 'etiennette', 'eva',
    'fabienne', 'florence', 'francoise', 'gabrielle', 'g\u00e9raldine', 'ginette',
    'h\u00e9l\u00e8ne', 'hermine', 'inge', 'isabelle', 'jacqueline', 'jade', 'jeanne',
    'jocelyne', 'josette', 'josiane', 'judith', 'julia', 'julie', 'juliette', 'laetitia',
    'laure', 'laurence', 'laurent', 'l\u00e9a', 'liliane', 'louise', 'lucie', 'lucille',
    'lydie', 'madeleine', 'magalie', 'm\u00e9lanie', 'micheline', 'mireille', 'monique',
    'nadia', 'nathalie', 'nicole', 'ninon', 'nora', 'odette', 'patricia', 'pauline',
    'priscillia', 'raphaelle', 'sandrine', 'sarah', 's\u00e9raphin', 'simone', 'solange',
    'sonia', 'st\u00e9phanie', 'suzanne', 'sylvie', 'th\u00e9r\u00e8se', 'vanessa', 'v\u00e9ronique',
    'victoria', 'violette', 'virginie', 'zoe',
}

# Pr\u00e9noms unisexes - \u00e0 traiter au cas par cas ou par d\u00e9faut masculine
UNISEX_NAMES = {
    'alex', 'alexis', 'jordan', 'riley', 'casey', 'dakota', 'jamie', 'morgan',
    'parker', 'reese', 'skyler', 'taylor', 'tommy', 'seeker',
}

def get_first_name(display_name):
    """Extrait le premier mot du display_name."""
    if not display_name:
        return ''
    return display_name.strip().split()[0].lower()

def infer_gender_from_first_name(first_name):
    """Inf\u00e8re le genre \u00e0 partir du pr\u00e9nom."""
    first_name_lower = first_name.lower()
    
    if first_name_lower in MALE_FIRST_NAMES:
        return 'male'
    elif first_name_lower in FEMALE_FIRST_NAMES:
        return 'female'
    elif first_name_lower in UNISEX_NAMES:
        # Par d\u00e9faut masculine pour les noms unisexes
        return 'male'
    else:
        # Si on ne peut pas d\u00e9duire, retourner None
        return None

def fix_profile_genders():
    print('=' * 60)
    print('CORRECTION DES GENRES DES PROFILS')
    print('=' * 60)
    
    profiles = Profile.objects.select_related('user').all()
    
    # Profils \u00e0 corriger (pas male ou female)
    to_fix = profiles.exclude(gender='male').exclude(gender='female')
    
    print(f'Nombre de profils \u00e0 traiter: {to_fix.count()}')
    print()
    
    corrected = []
    skipped = []
    
    for p in to_fix:
        first_name = get_first_name(p.user.display_name)
        old_gender = p.gender
        
        # Inf\u00e9rer le genre
        new_gender = infer_gender_from_first_name(first_name)
        
        if new_gender:
            p.gender = new_gender
            p.save(update_fields=['gender'])
            corrected.append({
                'name': p.user.display_name,
                'first_name': first_name,
                'old_gender': old_gender,
                'new_gender': new_gender,
            })
            print(f'  \u2713 {p.user.display_name} ({first_name}): {old_gender} -> {new_gender}')
        else:
            skipped.append({
                'name': p.user.display_name,
                'first_name': first_name,
                'gender': old_gender,
            })
            print(f'  ! {p.user.display_name} ({first_name}): {old_gender} -> SKIPPED (pr\u00e9nom non reconnu)')
    
    print()
    print('=' * 60)
    print('R\u00c9SUM\u00c9')
    print('=' * 60)
    print(f'Corrig\u00e9s: {len(corrected)}')
    print(f'Saut\u00e9s: {len(skipped)}')
    
    if skipped:
        print()
        print('Profils non trait\u00e9s (pr\u00e9noms non reconnus):')
        for s in skipped:
            print(f'  - {s["name"]} ({s["first_name"]}) - {s["gender"]}')
    
    # V\u00e9rification finale
    print()
    print('=' * 60)
    print('V\u00c9RIFICATION FINALE')
    print('=' * 60)
    
    from collections import Counter
    gender_counts = Counter(p.gender for p in profiles)
    total = profiles.count()
    
    print(f'Total des profils: {total}')
    for gender, count in gender_counts.most_common():
        pct = (count / total) * 100 if total > 0 else 0
        print(f'  {gender}: {count} ({pct:.1f}%)')
    
    # Verifier qu'il ne reste que male/female
    non_male_female = profiles.exclude(gender='male').exclude(gender='female').count()
    print()
    if non_male_female == 0:
        print('\u2705 Tous les profils sont maintenant male ou female!')
    else:
        print(f'\u26a0\ufe0f Il reste {non_male_female} profils non male/female')

if __name__ == '__main__':
    fix_profile_genders()
