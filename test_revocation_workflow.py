"""
Test script to verify revocation workflow.

This script tests:
1. User likes a profile -> profile disappears from discovery
2. User revokes the like
3. Profile reappears in discovery
"""
import os
import django
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from matching.models import InteractionHistory
from matching.services import RecommendationService
from profiles.models import Profile

User = get_user_model()

def test_revocation_workflow():
    """Test the complete revocation workflow."""
    
    print("\n" + "="*80)
    print("TEST: Revocation d'interactions et reapparition dans la decouverte")
    print("="*80 + "\n")
    
    # Get or create test users
    try:
        user1 = User.objects.filter(email_verified=True, is_active=True).first()
        if not user1:
            print("[ERREUR] Aucun utilisateur actif trouve")
            return False
        print(f"[OK] Utilisateur 1 trouve: {user1.email} (ID: {user1.id})")
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la recuperation de l'utilisateur: {str(e)}")
        return False
    
    # Get a target user from discovery before any interaction
    print("\nEtape 1: Recuperation des profils disponibles AVANT interaction")
    print("-" * 80)
    
    profiles_before = RecommendationService.get_recommendations(user=user1, limit=5)
    print(f"Nombre de profils disponibles: {len(profiles_before)}")
    
    if not profiles_before:
        print("[ERREUR] Aucun profil disponible pour les tests")
        return False
    
    target_profile = profiles_before[0]
    target_user = target_profile.user
    print(f"[OK] Profil cible selectionne: {target_user.display_name} (ID: {target_user.id})")
    
    # Step 2: Like the profile
    print("\nEtape 2: Like du profil cible")
    print("-" * 80)
    
    interaction, created = InteractionHistory.create_or_reactivate(
        user=user1,
        target_user=target_user,
        interaction_type=InteractionHistory.LIKE
    )
    
    if created:
        print(f"[OK] Nouvelle interaction creee: {interaction.id}")
    else:
        print(f"[OK] Interaction reactivee: {interaction.id}")
    
    print(f"   - Type: {interaction.interaction_type}")
    print(f"   - Is revoked: {interaction.is_revoked}")
    
    # Step 3: Check discovery (should NOT include the liked profile)
    print("\nEtape 3: Verification de la decouverte APRES like")
    print("-" * 80)
    
    profiles_after_like = RecommendationService.get_recommendations(user=user1, limit=10)
    print(f"Nombre de profils disponibles: {len(profiles_after_like)}")
    
    target_in_discovery = any(p.user.id == target_user.id for p in profiles_after_like)
    
    if target_in_discovery:
        print("[ERREUR] Le profil like apparait toujours dans la decouverte !")
        return False
    else:
        print("[OK] Le profil like a bien disparu de la decouverte")
    
    # Step 4: Revoke the interaction
    print("\nEtape 4: Revocation de l'interaction")
    print("-" * 80)
    
    interaction.revoke()
    interaction.refresh_from_db()
    
    print(f"[OK] Interaction revoquee: {interaction.id}")
    print(f"   - Is revoked: {interaction.is_revoked}")
    print(f"   - Revoked at: {interaction.revoked_at}")
    
    # Step 5: Check discovery (should include the profile again)
    print("\nEtape 5: Verification de la decouverte APRES revocation")
    print("-" * 80)
    
    profiles_after_revoke = RecommendationService.get_recommendations(user=user1, limit=10)
    print(f"Nombre de profils disponibles: {len(profiles_after_revoke)}")
    
    target_reappeared = any(p.user.id == target_user.id for p in profiles_after_revoke)
    
    if not target_reappeared:
        print("[ERREUR] Le profil revoque n'est PAS reapparu dans la decouverte !")
        print("\n[DEBUG] Profils actuellement dans la decouverte:")
        for p in profiles_after_revoke:
            print(f"   - {p.user.display_name} (ID: {p.user.id})")
        
        print("\n[DEBUG] Verification des interactions de l'utilisateur:")
        all_interactions = InteractionHistory.objects.filter(user=user1)
        print(f"Total interactions: {all_interactions.count()}")
        for inter in all_interactions:
            print(f"   - Cible: {inter.target_user.display_name} (ID: {inter.target_user.id})")
            print(f"     Type: {inter.interaction_type}, Is revoked: {inter.is_revoked}")
        
        return False
    else:
        print("[OK] Le profil revoque est bien reapparu dans la decouverte !")
    
    # Cleanup: Revoke all interactions for clean state
    print("\nNettoyage: Revocation de toutes les interactions de test")
    print("-" * 80)
    
    test_interactions = InteractionHistory.objects.filter(
        user=user1,
        target_user=target_user,
        is_revoked=False
    )
    
    for inter in test_interactions:
        inter.revoke()
        print(f"[OK] Interaction revoquee: {inter.id}")
    
    print("\n" + "="*80)
    print("[SUCCES] TEST REUSSI: Le workflow de revocation fonctionne correctement !")
    print("="*80 + "\n")
    
    return True


if __name__ == '__main__':
    try:
        success = test_revocation_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERREUR] ERREUR durant le test: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
