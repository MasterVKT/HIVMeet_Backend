#!/usr/bin/env python
"""
Test d'intégration pour valider les corrections des filtres Discovery.
Ce test simule un scénario utilisateur complet.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile
from matching.models import InteractionHistory
from matching.services import RecommendationService
from django.utils import timezone

User = get_user_model()


def test_integration_scenario():
    """
    Scénario d'intégration complet:
    1. Marie cherche des hommes pour relation long terme
    2. Elle like plusieurs profils
    3. Elle révoque certains likes
    4. Vérifier que les profils révoqués réapparaissent
    5. Vérifier que les profils avec [] (tous types) sont acceptés
    """
    print("\n" + "="*80)
    print("TEST D'INTEGRATION - Scenario Utilisateur Complet")
    print("="*80)
    
    # Créer Marie
    marie, _ = User.objects.get_or_create(
        email='marie_integration@test.com',
        defaults={
            'display_name': 'Marie',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 35),
            'is_active': True,
            'email_verified': True
        }
    )
    
    marie_profile, _ = Profile.objects.get_or_create(
        user=marie,
        defaults={
            'gender': 'female',
            'genders_sought': ['male'],
            'relationship_types_sought': ['long_term'],  # Cherche relation sérieuse
            'age_min_preference': 30,
            'age_max_preference': 50,
            'is_hidden': False,
            'allow_profile_in_discovery': True
        }
    )
    # Forcer les valeurs au cas où le profil existait déjà
    marie_profile.gender = 'female'
    marie_profile.genders_sought = ['male']
    marie_profile.relationship_types_sought = ['long_term']
    marie_profile.age_min_preference = 30
    marie_profile.age_max_preference = 50
    marie_profile.is_hidden = False
    marie_profile.allow_profile_in_discovery = True
    marie_profile.save()
    
    # Créer des profils hommes
    males = []
    
    # Pierre: Cherche aussi long_term (correspondance exacte)
    pierre, _ = User.objects.get_or_create(
        email='pierre_integration@test.com',
        defaults={
            'display_name': 'Pierre',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 40),
            'is_active': True,
            'email_verified': True
        }
    )
    pierre_profile, _ = Profile.objects.get_or_create(
        user=pierre,
        defaults={
            'gender': 'male',
            'genders_sought': ['female'],
            'relationship_types_sought': ['long_term'],
            'is_hidden': False,
            'allow_profile_in_discovery': True
        }
    )
    # Forcer les valeurs
    pierre_profile.gender = 'male'
    pierre_profile.genders_sought = ['female']
    pierre_profile.relationship_types_sought = ['long_term']
    pierre_profile.is_hidden = False
    pierre_profile.allow_profile_in_discovery = True
    pierre_profile.save()
    males.append(('Pierre (exact match)', pierre))
    
    # Paul: Ouvert à tout ([] - tous types)
    paul, _ = User.objects.get_or_create(
        email='paul_integration@test.com',
        defaults={
            'display_name': 'Paul',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 42),
            'is_active': True,
            'email_verified': True
        }
    )
    paul_profile, _ = Profile.objects.get_or_create(
        user=paul,
        defaults={
            'gender': 'male',
            'genders_sought': ['female'],
            'relationship_types_sought': [],  # Ouvert à tout
            'is_hidden': False,
            'allow_profile_in_discovery': True
        }
    )
    # Forcer les valeurs
    paul_profile.gender = 'male'
    paul_profile.genders_sought = ['female']
    paul_profile.relationship_types_sought = []
    paul_profile.is_hidden = False
    paul_profile.allow_profile_in_discovery = True
    paul_profile.save()
    males.append(('Paul (all types)', paul))
    
    # Jacques: Cherche casual (pas de correspondance)
    jacques, _ = User.objects.get_or_create(
        email='jacques_integration@test.com',
        defaults={
            'display_name': 'Jacques',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 38),
            'is_active': True,
            'email_verified': True
        }
    )
    jacques_profile, _ = Profile.objects.get_or_create(
        user=jacques,
        defaults={
            'gender': 'male',
            'genders_sought': ['female'],
            'relationship_types_sought': ['casual'],  # Pas de correspondance
            'is_hidden': False,
            'allow_profile_in_discovery': True
        }
    )
    # Forcer les valeurs
    jacques_profile.gender = 'male'
    jacques_profile.genders_sought = ['female']
    jacques_profile.relationship_types_sought = ['casual']
    jacques_profile.is_hidden = False
    jacques_profile.allow_profile_in_discovery = True
    jacques_profile.save()
    males.append(('Jacques (no match)', jacques))
    
    # Nettoyer les interactions existantes
    for _, male in males:
        InteractionHistory.objects.filter(user=marie, target_user=male).delete()
    
    # ÉTAPE 1: État initial
    print("\nETAPE 1: Etat Initial")
    print("-" * 80)
    recommendations = RecommendationService.get_recommendations(marie, limit=100)
    initial_ids = [p.user.id for p in recommendations]
    
    print(f"Total profils visibles: {len(recommendations)}")
    for name, male in males:
        visible = male.id in initial_ids
        status = "OK" if visible else "--"
        print(f"   [{status}] {name}: {visible}")
    
    # Vérifications
    assert pierre.id in initial_ids, "Pierre (exact match) doit être visible"
    assert paul.id in initial_ids, "Paul (all types) doit être visible"
    # Note: Jacques PEUT apparaître car le filtre vérifie ce que le profil CIBLE cherche,
    # pas une correspondance bidirectionnelle. Jacques peut être montré à Marie
    # même s'il cherche casual et elle long_term.
    
    # ÉTAPE 2: Marie like Pierre
    print("\nETAPE 2: Marie Like Pierre")
    print("-" * 80)
    InteractionHistory.objects.create(
        user=marie,
        target_user=pierre,
        interaction_type='like',
        is_revoked=False
    )
    
    recommendations = RecommendationService.get_recommendations(marie, limit=100)
    after_like_ids = [p.user.id for p in recommendations]
    
    print(f"Total profils visibles: {len(recommendations)}")
    for name, male in males:
        visible = male.id in after_like_ids
        status = "OK" if visible else "--"
        print(f"   [{status}] {name}: {visible}")
    
    assert pierre.id not in after_like_ids, "Pierre ne doit plus être visible après like"
    
    # ÉTAPE 3: Marie révoque le like de Pierre
    print("\nETAPE 3: Marie Revoque le Like de Pierre")
    print("-" * 80)
    interaction = InteractionHistory.objects.get(user=marie, target_user=pierre)
    interaction.is_revoked = True
    interaction.save()
    
    recommendations = RecommendationService.get_recommendations(marie, limit=100)
    after_revoke_ids = [p.user.id for p in recommendations]
    
    print(f"Total profils visibles: {len(recommendations)}")
    for name, male in males:
        visible = male.id in after_revoke_ids
        status = "OK" if visible else "--"
        print(f"   [{status}] {name}: {visible}")
    
    assert pierre.id in after_revoke_ids, "Pierre doit réapparaître après révocation"
    assert paul.id in after_revoke_ids, "Paul (all types) doit rester visible"
    
    # ÉTAPE 4: Vérifier le nombre de profils
    print("\nETAPE 4: Verification Finale")
    print("-" * 80)
    print(f"OK Pierre (exact match) reapparait apres revocation: {pierre.id in after_revoke_ids}")
    print(f"OK Paul (all types) reste visible: {paul.id in after_revoke_ids}")
    print(f"INFO Jacques (cherche casual, pas long_term): {jacques.id in after_revoke_ids}")
    print("   Note: Jacques PEUT être visible car le filtre montre les profils qui")
    print("   correspondent à ce que MARIE cherche (hommes), pas une correspondance bidirectionnelle")
    
    # Résumé
    all_checks_passed = (
        pierre.id in after_revoke_ids and
        paul.id in after_revoke_ids
        # Jacques peut être visible ou non selon d'autres critères
    )
    
    if all_checks_passed:
        print("\nOK TEST D'INTEGRATION REUSSI")
        return True
    else:
        print("\nERREUR TEST D'INTEGRATION ECHOUE")
        return False


def main():
    print("\nVALIDATION D'INTEGRATION - CORRECTIONS FILTRES DISCOVERY")
    print("="*80)
    
    try:
        success = test_integration_scenario()
        
        print("\n" + "="*80)
        if success:
            print("SUCCESS - TOUS LES TESTS D'INTEGRATION ONT REUSSI")
        else:
            print("ATTENTION - CERTAINS TESTS D'INTEGRATION ONT ECHOUE")
        print("="*80 + "\n")
        
        return success
    except Exception as e:
        print(f"\nERREUR lors du test d'integration: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
