"""
Analyse détaillée de TOUS les profils existants pour comprendre
pourquoi ils ne sont pas visibles dans la découverte.
"""
import os
import sys
import django

# Forcer UTF-8 sur Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Q
from profiles.models import Profile
from matching.models import InteractionHistory
from django.utils import timezone

User = get_user_model()


def analyze_profile_for_marie_compatibility(profile, marie_profile, marie_age):
    """Analyser pourquoi un profil n'est pas compatible avec Marie."""
    issues = []
    
    # 1. Vérifier l'âge - MUTUAL
    target_age = profile.user.age
    
    # Marie doit accepter l'âge du profil
    if target_age and (target_age < marie_profile.age_min_preference or target_age > marie_profile.age_max_preference):
        issues.append(f"❌ Âge {target_age} hors de la plage de Marie ({marie_profile.age_min_preference}-{marie_profile.age_max_preference})")
    
    # Le profil doit accepter l'âge de Marie
    if marie_age and (marie_age < profile.age_min_preference or marie_age > profile.age_max_preference):
        issues.append(f"❌ Préfère {profile.age_min_preference}-{profile.age_max_preference} ans (Marie a {marie_age} ans)")
    
    # 2. Vérifier le genre - MUTUAL
    # Marie recherche ce genre ?
    if marie_profile.genders_sought and profile.gender not in marie_profile.genders_sought:
        issues.append(f"❌ Genre '{profile.gender}' pas dans recherche de Marie {marie_profile.genders_sought}")
    
    # Le profil recherche le genre de Marie ?
    if profile.genders_sought and marie_profile.gender not in profile.genders_sought and profile.genders_sought != []:
        issues.append(f"❌ Recherche {profile.genders_sought}, pas '{marie_profile.gender}'")
    
    # 3. Vérifier les types de relation
    if marie_profile.relationship_types_sought and profile.relationship_types_sought:
        common = set(marie_profile.relationship_types_sought) & set(profile.relationship_types_sought)
        if not common:
            issues.append(f"❌ Aucun type de relation commun (Marie: {marie_profile.relationship_types_sought}, Profil: {profile.relationship_types_sought})")
    
    # 4. Vérifier la localisation
    if not profile.latitude or not profile.longitude:
        issues.append(f"⚠️  Pas de coordonnées GPS")
    
    # 5. Vérifier la visibilité
    if profile.is_hidden:
        issues.append(f"❌ Profil caché")
    
    if not profile.allow_profile_in_discovery:
        issues.append(f"❌ Découverte désactivée")
    
    if not profile.user.is_active:
        issues.append(f"❌ Utilisateur inactif")
    
    if not profile.user.email_verified:
        issues.append(f"❌ Email non vérifié")
    
    return issues


def main():
    """Fonction principale."""
    print("\n" + "="*80)
    print("  ANALYSE COMPLÈTE DE TOUS LES PROFILS EXISTANTS")
    print("="*80 + "\n")
    
    # Obtenir Marie
    marie = User.objects.get(email='marie.claire@test.com')
    marie_profile = marie.profile
    marie_age = marie.age
    
    print(f"👤 Profil de référence: Marie")
    print(f"   Âge: {marie_age} ans")
    print(f"   Genre: {marie_profile.gender}")
    print(f"   Recherche: {marie_profile.genders_sought}")
    print(f"   Préférences d'âge: {marie_profile.age_min_preference}-{marie_profile.age_max_preference} ans")
    print(f"   Types de relation: {marie_profile.relationship_types_sought}")
    print(f"   Distance max: {marie_profile.distance_max_km} km")
    print(f"   Localisation: lat={marie_profile.latitude}, lon={marie_profile.longitude}")
    
    # Obtenir les profils déjà interagis
    interacted_ids = InteractionHistory.objects.filter(
        user=marie,
        is_revoked=False
    ).values_list('target_user_id', flat=True)
    
    print(f"\n📊 Profils déjà interagis: {len(interacted_ids)}")
    
    # Obtenir TOUS les profils
    all_profiles = Profile.objects.select_related('user').exclude(user=marie).order_by('user__display_name')
    
    print(f"\n📊 Total de profils (hors Marie): {all_profiles.count()}")
    
    # Analyser chaque profil
    print(f"\n{'='*80}")
    print("  ANALYSE DÉTAILLÉE PAR PROFIL")
    print(f"{'='*80}\n")
    
    compatible_count = 0
    incompatible_by_reason = {
        'age_mutual': 0,
        'gender_mutual': 0,
        'relation': 0,
        'location': 0,
        'visibility': 0,
        'already_interacted': 0
    }
    
    for profile in all_profiles:
        print(f"\n{'─'*80}")
        print(f"👤 {profile.user.display_name} ({profile.user.email})")
        print(f"   Âge: {profile.user.age} ans | Genre: {profile.gender}")
        print(f"   Recherche: {profile.genders_sought}")
        print(f"   Préfère: {profile.age_min_preference}-{profile.age_max_preference} ans")
        print(f"   Relations: {profile.relationship_types_sought}")
        print(f"   GPS: lat={profile.latitude}, lon={profile.longitude}")
        print(f"   Actif: {profile.user.is_active} | Vérifié: {profile.user.email_verified}")
        print(f"   Caché: {profile.is_hidden} | Découverte: {profile.allow_profile_in_discovery}")
        
        # Vérifier si déjà interagi
        if profile.user.id in interacted_ids:
            print(f"   ⏭️  DÉJÀ INTERAGI (exclu de la découverte)")
            incompatible_by_reason['already_interacted'] += 1
            continue
        
        # Analyser la compatibilité
        issues = analyze_profile_for_marie_compatibility(profile, marie_profile, marie_age)
        
        if not issues:
            print(f"   ✅ COMPATIBLE avec Marie!")
            compatible_count += 1
        else:
            print(f"   ❌ INCOMPATIBLE:")
            for issue in issues:
                print(f"      {issue}")
                # Compter les raisons
                if "Âge" in issue or "Préfère" in issue:
                    incompatible_by_reason['age_mutual'] += 1
                elif "Genre" in issue or "Recherche" in issue:
                    incompatible_by_reason['gender_mutual'] += 1
                elif "relation" in issue:
                    incompatible_by_reason['relation'] += 1
                elif "coordonnées" in issue:
                    incompatible_by_reason['location'] += 1
                elif "caché" in issue or "Découverte" in issue or "inactif" in issue or "vérifié" in issue:
                    incompatible_by_reason['visibility'] += 1
    
    # Résumé final
    print(f"\n{'='*80}")
    print("  RÉSUMÉ FINAL")
    print(f"{'='*80}\n")
    
    print(f"📊 Profils totaux (hors Marie): {all_profiles.count()}")
    print(f"   ⏭️  Déjà interagis: {len(interacted_ids)}")
    print(f"   ✅ Compatibles: {compatible_count}")
    print(f"   ❌ Incompatibles: {all_profiles.count() - len(interacted_ids) - compatible_count}")
    
    print(f"\n📊 Raisons d'incompatibilité:")
    print(f"   Âge mutual: {incompatible_by_reason['age_mutual']} profils")
    print(f"   Genre mutual: {incompatible_by_reason['gender_mutual']} profils")
    print(f"   Type de relation: {incompatible_by_reason['relation']} profils")
    print(f"   Localisation: {incompatible_by_reason['location']} profils")
    print(f"   Visibilité/Statut: {incompatible_by_reason['visibility']} profils")
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    main()
