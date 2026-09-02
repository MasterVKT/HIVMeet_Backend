"""
Test edge cases for revocation workflow.
Specifically tests the scenario where discovery returns 0 profiles after revocation.
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
from django.db.models import Q

User = get_user_model()

def test_discovery_count_accuracy():
    """Test that discovery count is accurate after revocations."""
    
    print("\n" + "="*80)
    print("TEST: Precision du comptage des profils apres revocation")
    print("="*80 + "\n")
    
    # Get a test user
    user = User.objects.filter(email_verified=True, is_active=True).first()
    if not user:
        print("[ERREUR] Aucun utilisateur actif trouve")
        return False
    
    print(f"[OK] Utilisateur de test: {user.email} (ID: {user.id})")
    
    # Count total eligible profiles for this user
    print("\n--- Analyse des profils eligibles ---")
    
    user_profile = user.profile
    
    # Get all active interactions (non-revoked)
    active_interactions = InteractionHistory.objects.filter(
        user=user,
        is_revoked=False
    )
    print(f"Interactions actives (non revoquees): {active_interactions.count()}")
    for inter in active_interactions[:5]:
        print(f"  - {inter.target_user.display_name} ({inter.interaction_type})")
    
    # Get all revoked interactions
    revoked_interactions = InteractionHistory.objects.filter(
        user=user,
        is_revoked=True
    )
    print(f"\nInteractions revoquees: {revoked_interactions.count()}")
    for inter in revoked_interactions[:5]:
        print(f"  - {inter.target_user.display_name} ({inter.interaction_type})")
    
    # Get total eligible profiles (without interaction filter)
    total_profiles = Profile.objects.filter(
        user__is_active=True,
        user__email_verified=True,
        is_hidden=False,
        allow_profile_in_discovery=True
    ).exclude(user=user).count()
    
    print(f"\nTotal profils eligibles (sans filtre interaction): {total_profiles}")
    
    # Get profiles using the recommendation service
    profiles_from_service = RecommendationService.get_recommendations(user=user, limit=100)
    print(f"Profils retournes par RecommendationService: {len(profiles_from_service)}")
    
    # Calculate expected count
    interacted_ids = set(InteractionHistory.objects.filter(
        user=user,
        is_revoked=False
    ).values_list('target_user_id', flat=True))
    
    expected_available = total_profiles - len(interacted_ids)
    print(f"\nNombre attendu de profils disponibles: {expected_available}")
    print(f"  (Total eligibles: {total_profiles} - Interactions actives: {len(interacted_ids)})")
    
    # Test specific scenario: revoke one interaction and check if count increases
    print("\n--- Test de revocation ---")
    
    if active_interactions.exists():
        test_interaction = active_interactions.first()
        target_name = test_interaction.target_user.display_name
        target_id = test_interaction.target_user.id
        
        print(f"\n1. Profils disponibles AVANT revocation: {len(profiles_from_service)}")
        
        # Check if target is in discovery before revocation (should NOT be)
        target_in_before = any(p.user.id == target_id for p in profiles_from_service)
        print(f"   Profil '{target_name}' dans decouverte: {target_in_before}")
        
        # Revoke the interaction
        test_interaction.revoke()
        print(f"\n2. Revocation de l'interaction avec '{target_name}'")
        print(f"   Interaction ID: {test_interaction.id}")
        
        # Check discovery after revocation
        profiles_after_revoke = RecommendationService.get_recommendations(user=user, limit=100)
        print(f"\n3. Profils disponibles APRES revocation: {len(profiles_after_revoke)}")
        
        # Check if target is in discovery after revocation (should BE)
        target_in_after = any(p.user.id == target_id for p in profiles_after_revoke)
        print(f"   Profil '{target_name}' dans decouverte: {target_in_after}")
        
        if target_in_after and not target_in_before:
            print("\n[SUCCES] Le profil revoque est bien reapparu dans la decouverte!")
            
            # Cleanup: reactivate the interaction
            test_interaction.is_revoked = False
            test_interaction.revoked_at = None
            test_interaction.save()
            print(f"\n[Nettoyage] Interaction reactivee pour maintenir l'etat initial")
            
            return True
        else:
            print(f"\n[ERREUR] Probleme detecte:")
            print(f"  - Avant revocation: {target_in_before}")
            print(f"  - Apres revocation: {target_in_after}")
            return False
    else:
        print("\n[INFO] Aucune interaction active a tester. Creons-en une...")
        
        # Get a profile to interact with
        available_profiles = RecommendationService.get_recommendations(user=user, limit=1)
        if not available_profiles:
            print("[ERREUR] Aucun profil disponible pour creer une interaction de test")
            return False
        
        target = available_profiles[0].user
        
        # Create interaction
        interaction, created = InteractionHistory.create_or_reactivate(
            user=user,
            target_user=target,
            interaction_type=InteractionHistory.LIKE
        )
        
        print(f"[OK] Interaction creee avec {target.display_name}")
        
        # Verify it disappeared
        profiles_after_like = RecommendationService.get_recommendations(user=user, limit=100)
        target_in_discovery = any(p.user.id == target.id for p in profiles_after_like)
        
        if target_in_discovery:
            print("[ERREUR] Le profil n'a pas disparu apres le like!")
            interaction.revoke()
            return False
        
        print("[OK] Le profil a bien disparu apres le like")
        
        # Revoke and verify it reappeared
        interaction.revoke()
        
        profiles_after_revoke = RecommendationService.get_recommendations(user=user, limit=100)
        target_reappeared = any(p.user.id == target.id for p in profiles_after_revoke)
        
        if target_reappeared:
            print("[SUCCES] Le profil a bien reapparu apres la revocation!")
            return True
        else:
            print("[ERREUR] Le profil n'est pas reapparu apres la revocation!")
            
            # Debug info
            print("\n[DEBUG] Verification de l'etat de l'interaction:")
            interaction.refresh_from_db()
            print(f"  - is_revoked: {interaction.is_revoked}")
            print(f"  - revoked_at: {interaction.revoked_at}")
            
            return False
    
    return False


def test_filters_impact():
    """Test if user filters are preventing profiles from appearing."""
    
    print("\n" + "="*80)
    print("TEST: Impact des filtres utilisateur sur la decouverte")
    print("="*80 + "\n")
    
    # Get user mentioned in logs: olivier.robert@test.com (ID: 51cd2e63-5a3c-4a8e-aee2-9495950652fd)
    try:
        user = User.objects.get(id='51cd2e63-5a3c-4a8e-aee2-9495950652fd')
        print(f"[OK] Utilisateur des logs trouve: {user.email}")
    except User.DoesNotExist:
        print("[INFO] Utilisateur specifique des logs non trouve, utilisation d'un autre utilisateur")
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("[ERREUR] Aucun utilisateur disponible")
            return False
        print(f"[OK] Utilisateur alternatif: {user.email}")
    
    user_profile = user.profile
    
    print(f"\n--- Parametres du profil ---")
    print(f"Verifie uniquement: {user_profile.verified_only}")
    print(f"En ligne uniquement: {user_profile.online_only}")
    print(f"Age recherche: {user_profile.age_min_preference}-{user_profile.age_max_preference}")
    print(f"Genres recherches: {user_profile.genders_sought}")
    print(f"Distance max: {user_profile.distance_max_km} km")
    
    # Test discovery
    profiles = RecommendationService.get_recommendations(user=user, limit=20)
    print(f"\n[RESULTAT] Profils disponibles: {len(profiles)}")
    
    if len(profiles) == 0:
        print("\n[ATTENTION] Aucun profil disponible. Verifions pourquoi...")
        
        # Check if verified_only is too restrictive
        if user_profile.verified_only:
            verified_count = Profile.objects.filter(
                user__is_verified=True,
                user__is_active=True,
                user__email_verified=True
            ).exclude(user=user).count()
            print(f"  - Profils verifies disponibles: {verified_count}")
        
        # Check if online_only is too restrictive
        if user_profile.online_only:
            from django.utils import timezone
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(minutes=5)
            online_count = Profile.objects.filter(
                user__last_active__gte=cutoff,
                user__is_active=True,
                user__email_verified=True
            ).exclude(user=user).count()
            print(f"  - Profils en ligne (5 min): {online_count}")
        
        # Check interactions
        total_interactions = InteractionHistory.objects.filter(user=user).count()
        active_interactions = InteractionHistory.objects.filter(user=user, is_revoked=False).count()
        revoked_interactions = InteractionHistory.objects.filter(user=user, is_revoked=True).count()
        
        print(f"  - Total interactions: {total_interactions}")
        print(f"  - Interactions actives: {active_interactions}")
        print(f"  - Interactions revoquees: {revoked_interactions}")
        
        return False
    
    return True


if __name__ == '__main__':
    try:
        print("\n" + "="*80)
        print("SUITE DE TESTS: Cas limites de revocation")
        print("="*80)
        
        result1 = test_discovery_count_accuracy()
        result2 = test_filters_impact()
        
        print("\n" + "="*80)
        if result1 and result2:
            print("[SUCCES] Tous les tests sont passes!")
        else:
            print("[ECHEC] Certains tests ont echoue")
        print("="*80 + "\n")
        
        sys.exit(0 if (result1 and result2) else 1)
        
    except Exception as e:
        print(f"\n[ERREUR] Exception durant les tests: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
