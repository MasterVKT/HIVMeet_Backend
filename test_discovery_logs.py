"""
Test des nouveaux logs de diagnostic pour la découverte.
Ce script simule l'appel au service de recommandations pour vérifier les logs.
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
from matching.services import RecommendationService
import logging

# Configure logging to see INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s %(name)s: %(message)s'
)

User = get_user_model()

def test_discovery_logs():
    """Test que les nouveaux logs fonctionnent correctement."""
    
    print("\n" + "="*80)
    print("TEST: Verification des logs de diagnostic")
    print("="*80 + "\n")
    
    # Get a test user - Marie from the logs
    try:
        user = User.objects.get(id='0e5ac2cb-07d8-4160-9f36-90393356f8c0')
        print(f"[OK] Utilisateur de test: {user.email} (Marie)")
    except User.DoesNotExist:
        print("[INFO] Marie non trouvee, utilisation d'un autre utilisateur")
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("[ERREUR] Aucun utilisateur disponible")
            return False
        print(f"[OK] Utilisateur alternatif: {user.email}")
    
    print("\n" + "-"*80)
    print("Appel du service de recommandations avec logs detailles:")
    print("-"*80 + "\n")
    
    # Call the recommendation service (logs will be generated)
    profiles = RecommendationService.get_recommendations(
        user=user,
        limit=10,
        offset=0
    )
    
    print("\n" + "-"*80)
    print(f"\n[RESULTAT] {len(profiles)} profils retournes")
    print("\n" + "="*80)
    print("[SUCCES] Les logs ont ete generes ci-dessus")
    print("="*80 + "\n")
    
    return True


if __name__ == '__main__':
    try:
        success = test_discovery_logs()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERREUR] Exception durant le test: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
