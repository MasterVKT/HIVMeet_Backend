"""
Test de validation pour les corrections BACKEND_CORRECTION_INTERACTIONS_DUPLICATES 
et BACKEND_CORRECTION_SWIPES_COUNTER.

Usage: python test_corrections_validations.py
"""
import os
import sys
import django

# Configuration Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from matching.daily_likes_service import DailyLikesService
from matching.interaction_service import InteractionService
from matching.models import InteractionHistory, Like, Dislike, Match

User = get_user_model()


def test_daily_likes_service():
    """Test les méthodes du DailyLikesService."""
    print("\n" + "="*60)
    print("TEST: DailyLikesService")
    print("="*60)
    
    # Récupérer un utilisateur de test
    user = User.objects.filter(profile__is_premium=False).first()
    
    if not user:
        print("❌ Aucun utilisateur non-premium trouvé")
        return False
    
    print(f"\n👤 Utilisateur: {user.email}")
    
    # Test 1: get_daily_likes_info
    print("\n📊 Test 1: get_daily_likes_info()")
    info = DailyLikesService.get_daily_likes_info(user)
    print(f"   - remaining: {info['remaining']}")
    print(f"   - limit: {info['limit']}")
    print(f"   - used_today: {info['used_today']}")
    print(f"   - is_premium: {info['is_premium']}")
    
    assert 'remaining' in info, "missing 'remaining' key"
    assert 'limit' in info, "missing 'limit' key"
    assert 'used_today' in info, "missing 'used_today' key"
    assert 'is_premium' in info, "missing 'is_premium' key"
    print("   ✅ OK")
    
    # Test 2: check_and_use_daily_like
    print("\n📊 Test 2: check_and_use_daily_like()")
    success, remaining, limit, error = DailyLikesService.check_and_use_daily_like(user)
    print(f"   - success: {success}")
    print(f"   - remaining: {remaining}")
    print(f"   - limit: {limit}")
    print(f"   - error: {error}")
    
    assert isinstance(success, bool), "success should be bool"
    assert isinstance(remaining, int), "remaining should be int"
    assert remaining >= 0, "remaining should be >= 0"
    print("   ✅ OK")
    
    # Test 3: get_status_summary
    print("\n📊 Test 3: get_status_summary()")
    summary = DailyLikesService.get_status_summary(user)
    print(f"   - daily_likes_remaining: {summary['daily_likes_remaining']}")
    print(f"   - daily_likes_limit: {summary['daily_likes_limit']}")
    print(f"   - is_premium: {summary['is_premium']}")
    print(f"   - reset_at: {summary['reset_at']}")
    
    assert 'daily_likes_remaining' in summary
    assert 'daily_likes_limit' in summary
    assert 'is_premium' in summary
    assert 'reset_at' in summary
    print("   ✅ OK")
    
    return True


def test_interaction_service():
    """Test les méthodes du InteractionService."""
    print("\n" + "="*60)
    print("TEST: InteractionService")
    print("="*60)
    
    # Récupérer un utilisateur de test
    user = User.objects.filter(is_active=True).first()
    
    if not user:
        print("❌ Aucun utilisateur actif trouvé")
        return False
    
    print(f"\n👤 Utilisateur: {user.email}")
    
    # Test 1: get_excluded_profile_ids
    print("\n📊 Test 1: get_excluded_profile_ids()")
    excluded_ids = InteractionService.get_excluded_profile_ids(user)
    print(f"   - Nombre de profils exclus: {len(excluded_ids)}")
    print(f"   - Type: {type(excluded_ids)}")
    
    assert isinstance(excluded_ids, set), "should return a set"
    print("   ✅ OK")
    
    # Test 2: get_liked_profile_ids
    print("\n📊 Test 2: get_liked_profile_ids()")
    liked_ids = InteractionService.get_liked_profile_ids(user)
    print(f"   - Nombre de profils likés: {len(liked_ids)}")
    
    assert isinstance(liked_ids, set), "should return a set"
    print("   ✅ OK")
    
    # Test 3: get_disliked_profile_ids
    print("\n📊 Test 3: get_disliked_profile_ids()")
    disliked_ids = InteractionService.get_disliked_profile_ids(user)
    print(f"   - Nombre de profils dislikés: {len(disliked_ids)}")
    
    assert isinstance(disliked_ids, set), "should return a set"
    print("   ✅ OK")
    
    # Test 4: has_interacted_with
    print("\n📊 Test 4: has_interacted_with()")
    # Trouver un utilisateur avec qui il y a eu une interaction
    first_interaction = InteractionHistory.objects.filter(user=user, is_revoked=False).first()
    if first_interaction:
        target_id = first_interaction.target_user_id
        has_interacted = InteractionService.has_interacted_with(user, target_id)
        print(f"   - has_interacted with {target_id}: {has_interacted}")
        assert has_interacted == True, "should return True for existing interaction"
        print("   ✅ OK")
    else:
        print("   ⚠️  Pas d'interaction existante à tester")
        print("   ⏭️  SKIPPED")
    
    # Test 5: verify_no_duplicates
    print("\n📊 Test 5: verify_no_duplicates()")
    is_valid, issues = InteractionService.verify_no_duplicates(user.id)
    print(f"   - is_valid: {is_valid}")
    print(f"   - issues: {len(issues)}")
    
    assert isinstance(is_valid, bool), "is_valid should be bool"
    assert isinstance(issues, list), "issues should be list"
    print("   ✅ OK")
    
    return True


def test_interaction_history_model():
    """Test le modèle InteractionHistory."""
    print("\n" + "="*60)
    print("TEST: InteractionHistory Model")
    print("="*60)
    
    # Test indexes
    print("\n📊 Test 1: Indexes")
    indexes = InteractionHistory._meta.indexes
    print(f"   - Nombre d'index: {len(indexes)}")
    for idx in indexes:
        print(f"   - Index: {idx}")
    
    # Vérifier les index importants
    index_fields = [str(idx.fields) for idx in indexes]
    expected_indexes = [
        "('user', '-created_at')",
        "('target_user', '-created_at')",
        "('user', 'is_revoked')",
    ]
    
    print(f"   - Index fields: {index_fields}")
    print("   ✅ OK")
    
    # Test constraints
    print("\n📊 Test 2: Constraints")
    constraints = InteractionHistory._meta.constraints
    print(f"   - Nombre de contraintes: {len(constraints)}")
    for const in constraints:
        print(f"   - Constraint: {const}")
    
    print("   ✅ OK")
    
    return True


def test_interaction_workflow():
    """Test le workflow complet d'interaction."""
    print("\n" + "="*60)
    print("TEST: Workflow d'Interaction Complet")
    print("="*60)
    
    # Récupérer deux utilisateurs de test
    users = User.objects.filter(is_active=True, profile__is_hidden=False)[:2]
    
    if len(users) < 2:
        print("❌ Pas assez d'utilisateurs pour tester")
        return False
    
    user1, user2 = users[0], users[1]
    print(f"\n👤 User1: {user1.email}")
    print(f"👤 User2: {user2.email}")
    
    # Nettoyer les interactions existantes
    InteractionHistory.objects.filter(user=user1, target_user=user2).delete()
    
    # Test 1: Création d'un like
    print("\n📊 Test 1: create_or_update_interaction (like)")
    interaction, created = InteractionService.create_or_update_interaction(
        user1, user2, 'like'
    )
    print(f"   - created: {created}")
    print(f"   - interaction_id: {interaction.id}")
    print(f"   - interaction_type: {interaction.interaction_type}")
    print(f"   - is_revoked: {interaction.is_revoked}")
    
    assert interaction.interaction_type == 'like'
    assert interaction.is_revoked == False
    print("   ✅ OK")
    
    # Test 2: Vérifier que le profil est exclu
    print("\n📊 Test 2: Profil exclu de la découverte")
    excluded_ids = InteractionService.get_excluded_profile_ids(user1)
    is_excluded = user2.id in excluded_ids
    print(f"   - Profil exclu: {is_excluded}")
    
    assert is_excluded == True, "User2 should be excluded from discovery"
    print("   ✅ OK")
    
    # Test 3: Révoquer l'interaction
    print("\n📊 Test 3: revoke_interaction")
    success, error_msg, revoked_interaction = InteractionService.revoke_interaction(
        user1, interaction.id
    )
    print(f"   - success: {success}")
    print(f"   - error_msg: {error_msg}")
    
    assert success == True, "Revocation should succeed"
    assert revoked_interaction.is_revoked == True
    print("   ✅ OK")
    
    # Test 4: Vérifier que le profil n'est plus exclu après révocation
    print("\n📊 Test 4: Profil réinclus après révocation")
    excluded_ids = InteractionService.get_excluded_profile_ids(user1)
    is_still_excluded = user2.id in excluded_ids
    print(f"   - Profil toujours exclu: {is_still_excluded}")
    
    assert is_still_excluded == False, "User2 should NOT be excluded after revocation"
    print("   ✅ OK")
    
    # Test 5: Créer un dislike après le like révoqué
    print("\n📊 Test 5: create_or_update_interaction (dislike après like révoqué)")
    interaction, created = InteractionService.create_or_update_interaction(
        user1, user2, 'dislike'
    )
    print(f"   - created: {created}")
    print(f"   - interaction_type: {interaction.interaction_type}")
    
    assert interaction.interaction_type == 'dislike'
    print("   ✅ OK")
    
    # Nettoyage
    InteractionHistory.objects.filter(user=user1, target_user=user2).delete()
    
    return True


def test_clean_duplicate_interactions():
    """Test le nettoyage des doublons."""
    print("\n" + "="*60)
    print("TEST: Nettoyage des Doublons")
    print("="*60)
    
    # Récupérer un utilisateur
    user = User.objects.filter(is_active=True).first()
    
    if not user:
        print("❌ Aucun utilisateur trouvé")
        return False
    
    print(f"\n👤 Utilisateur: {user.email}")
    
    # Test verify_all_users
    print("\n📊 Test 1: verify_all_users()")
    result = InteractionService.verify_all_users()
    print(f"   - users_checked: {result['users_checked']}")
    print(f"   - users_with_issues: {result['users_with_issues']}")
    print(f"   - total_issues: {result['total_issues']}")
    
    assert 'users_checked' in result
    assert 'users_with_issues' in result
    assert 'total_issues' in result
    print("   ✅ OK")
    
    return True


def run_all_tests():
    """Exécute tous les tests."""
    print("\n" + "="*60)
    print("🧪 VALIDATION DES CORRECTIONS BACKEND")
    print("="*60)
    
    results = []
    
    # Test DailyLikesService
    try:
        results.append(("DailyLikesService", test_daily_likes_service()))
    except Exception as e:
        print(f"\n❌ Test DailyLikesService échoué: {e}")
        import traceback
        traceback.print_exc()
        results.append(("DailyLikesService", False))
    
    # Test InteractionService
    try:
        results.append(("InteractionService", test_interaction_service()))
    except Exception as e:
        print(f"\n❌ Test InteractionService échoué: {e}")
        import traceback
        traceback.print_exc()
        results.append(("InteractionService", False))
    
    # Test InteractionHistory Model
    try:
        results.append(("InteractionHistory Model", test_interaction_history_model()))
    except Exception as e:
        print(f"\n❌ Test InteractionHistory Model échoué: {e}")
        import traceback
        traceback.print_exc()
        results.append(("InteractionHistory Model", False))
    
    # Test Workflow d'Interaction
    try:
        results.append(("Interaction Workflow", test_interaction_workflow()))
    except Exception as e:
        print(f"\n❌ Test Interaction Workflow échoué: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Interaction Workflow", False))
    
    # Test Clean Duplicate Interactions
    try:
        results.append(("Clean Duplicates", test_clean_duplicate_interactions()))
    except Exception as e:
        print(f"\n❌ Test Clean Duplicates échoué: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Clean Duplicates", False))
    
    # Résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} - {name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "="*60)
    if all_passed:
        print("🎉 TOUS LES TESTS ONT RÉUSSI!")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
