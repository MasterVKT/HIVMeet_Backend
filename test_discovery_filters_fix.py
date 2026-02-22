#!/usr/bin/env python
"""
Script de test pour valider les corrections des filtres de découverte.

Tests:
1. Les profils révoqués réapparaissent dans la découverte
2. Le filtre relationship_type accepte les profils avec null/[] (tous types)
"""
import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile
from matching.models import InteractionHistory, Like, Dislike
from matching.services import RecommendationService
from django.utils import timezone

User = get_user_model()


def test_revoked_profiles_reappear():
    """
    Test 1: Vérifier que les profils révoqués réapparaissent dans la découverte
    """
    print("\n" + "="*80)
    print("TEST 1: Profils révoqués réapparaissent")
    print("="*80)
    
    # Créer ou récupérer un utilisateur de test
    test_user, _ = User.objects.get_or_create(
        email='test_revoke@test.com',
        defaults={
            'display_name': 'Test Revoke User',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 30)
        }
    )
    
    # Créer ou récupérer un profil cible
    target_user, _ = User.objects.get_or_create(
        email='target_revoke@test.com',
        defaults={
            'display_name': 'Target User',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 28),
            'email_verified': True,
            'is_active': True
        }
    )
    
    # S'assurer que le profil cible existe
    target_profile, _ = Profile.objects.get_or_create(
        user=target_user,
        defaults={
            'gender': 'female',
            'genders_sought': ['male'],
            'is_hidden': False,
            'allow_profile_in_discovery': True
        }
    )
    
    # S'assurer que le profil test existe
    test_profile, _ = Profile.objects.get_or_create(
        user=test_user,
        defaults={
            'gender': 'male',
            'genders_sought': ['female'],
            'age_min_preference': 20,
            'age_max_preference': 40
        }
    )
    
    # Nettoyer les interactions existantes
    InteractionHistory.objects.filter(user=test_user, target_user=target_user).delete()
    Like.objects.filter(from_user=test_user, to_user=target_user).delete()
    
    # Étape 1: Vérifier que le profil est visible initialement
    print("\n📊 Étape 1: État initial")
    recommendations_initial = RecommendationService.get_recommendations(test_user, limit=100)
    initial_ids = [p.user.id for p in recommendations_initial]
    print(f"   Nombre de profils: {len(recommendations_initial)}")
    print(f"   Target visible: {target_user.id in initial_ids}")
    
    # Étape 2: Créer un like (legacy)
    print("\n📊 Étape 2: Créer un like legacy")
    Like.objects.create(from_user=test_user, to_user=target_user)
    
    recommendations_after_like = RecommendationService.get_recommendations(test_user, limit=100)
    after_like_ids = [p.user.id for p in recommendations_after_like]
    print(f"   Nombre de profils: {len(recommendations_after_like)}")
    print(f"   Target visible: {target_user.id in after_like_ids}")
    print(f"   ✅ Expected: False (profil liké ne doit pas apparaître)")
    
    # Étape 3: Révoquer le like via InteractionHistory
    print("\n📊 Étape 3: Révoquer le like")
    InteractionHistory.objects.create(
        user=test_user,
        target_user=target_user,
        interaction_type='like',
        is_revoked=True
    )
    
    recommendations_after_revoke = RecommendationService.get_recommendations(test_user, limit=100)
    after_revoke_ids = [p.user.id for p in recommendations_after_revoke]
    print(f"   Nombre de profils: {len(recommendations_after_revoke)}")
    print(f"   Target visible: {target_user.id in after_revoke_ids}")
    
    # Vérification
    if target_user.id in after_revoke_ids:
        print(f"\n✅ TEST RÉUSSI: Le profil révoqué réapparaît dans la découverte")
        return True
    else:
        print(f"\n❌ TEST ÉCHOUÉ: Le profil révoqué ne réapparaît pas")
        return False


def test_relationship_type_null_accepted():
    """
    Test 2: Vérifier que les profils avec relationship_types_sought=[] sont acceptés
    """
    print("\n" + "="*80)
    print("TEST 2: Profils avec relationship_types [] acceptés")
    print("="*80)
    
    # Créer un utilisateur cherchant un type spécifique
    seeker_user, _ = User.objects.get_or_create(
        email='seeker@test.com',
        defaults={
            'display_name': 'Seeker',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 30),
            'is_active': True,
            'email_verified': True
        }
    )
    
    seeker_profile, _ = Profile.objects.get_or_create(
        user=seeker_user,
        defaults={
            'gender': 'male',
            'genders_sought': ['female'],
            'relationship_types_sought': ['long_term'],  # Cherche spécifiquement "long_term"
            'age_min_preference': 20,
            'age_max_preference': 40
        }
    )
    seeker_profile.relationship_types_sought = ['long_term']
    seeker_profile.save()
    
    # Créer des profils cibles avec différents relationship_types
    targets = []
    
    # Target 1: Avec le même type (correspondance exacte)
    target1, _ = User.objects.get_or_create(
        email='target_exact@test.com',
        defaults={
            'display_name': 'Target Exact Match',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 28),
            'is_active': True,
            'email_verified': True
        }
    )
    profile1, _ = Profile.objects.get_or_create(
        user=target1,
        defaults={
            'gender': 'female',
            'genders_sought': ['male'],
            'relationship_types_sought': ['long_term'],
            'is_hidden': False,
            'allow_profile_in_discovery': True
        }
    )
    profile1.relationship_types_sought = ['long_term']
    profile1.save()
    targets.append(('exact_match', target1))
    
    # Target 2: Avec [] (tous types)
    target2, _ = User.objects.get_or_create(
        email='target_all@test.com',
        defaults={
            'display_name': 'Target All Types',
            'birth_date': timezone.now().date().replace(year=timezone.now().year - 27),
            'is_active': True,
            'email_verified': True
        }
    )
    profile2, _ = Profile.objects.get_or_create(
        user=target2,
        defaults={
            'gender': 'female',
            'genders_sought': ['male'],
            'relationship_types_sought': [],  # Tous types
            'is_hidden': False,
            'allow_profile_in_discovery': True
        }
    )
    profile2.relationship_types_sought = []
    profile2.save()
    targets.append(('empty_array', target2))
    
    # Nettoyer les interactions
    for _, target in targets:
        InteractionHistory.objects.filter(user=seeker_user, target_user=target).delete()
    
    # Récupérer les recommandations
    print(f"\n📊 Seeker cherche: {seeker_profile.relationship_types_sought}")
    recommendations = RecommendationService.get_recommendations(seeker_user, limit=100)
    recommendation_ids = [p.user.id for p in recommendations]
    
    # Vérifier chaque target
    results = {}
    for target_type, target_user in targets:
        visible = target_user.id in recommendation_ids
        results[target_type] = visible
        print(f"\n   Target ({target_type}):")
        print(f"      relationship_types_sought: {Profile.objects.get(user=target_user).relationship_types_sought}")
        print(f"      Visible: {visible}")
    
    # Tous devraient être visibles
    all_visible = all(results.values())
    
    if all_visible:
        print(f"\n✅ TEST RÉUSSI: Tous les profils (exact, []) sont acceptés")
        return True
    else:
        print(f"\n❌ TEST ÉCHOUÉ: Certains profils ne sont pas acceptés")
        print(f"   Résultats: {results}")
        return False


def main():
    """Exécuter tous les tests"""
    print("\n🧪 VALIDATION DES CORRECTIONS DES FILTRES DE DÉCOUVERTE")
    print("="*80)
    
    results = []
    
    # Test 1
    try:
        result1 = test_revoked_profiles_reappear()
        results.append(("Profils révoqués réapparaissent", result1))
    except Exception as e:
        print(f"❌ Erreur lors du test 1: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Profils révoqués réapparaissent", False))
    
    # Test 2
    try:
        result2 = test_relationship_type_null_accepted()
        results.append(("Filtre relationship_type accepte []", result2))
    except Exception as e:
        print(f"❌ Erreur lors du test 2: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Filtre relationship_type accepte []", False))
    
    # Résumé
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)
    for test_name, result in results:
        status = "✅ RÉUSSI" if result else "❌ ÉCHOUÉ"
        print(f"   {status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    print("\n" + ("="*80))
    if all_passed:
        print("🎉 TOUS LES TESTS ONT RÉUSSI")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
    print("="*80 + "\n")
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
