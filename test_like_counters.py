"""
Test script pour vérifier les compteurs de likes.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from matching.services import MatchingService
from matching.models import DailyLikeLimit

User = get_user_model()

def test_like_counters():
    """Test les compteurs de likes pour différents types d'utilisateurs."""
    
    print("\n" + "="*60)
    print("TEST DES COMPTEURS DE LIKES")
    print("="*60 + "\n")
    
    # Récupérer quelques utilisateurs
    users = User.objects.all()[:3]
    
    if not users:
        print("❌ Aucun utilisateur trouvé dans la base de données")
        return
    
    for user in users:
        print(f"\n👤 Utilisateur: {user.display_name} ({user.email})")
        print(f"   ID: {user.id}")
        print(f"   Is Premium: {getattr(user, 'is_premium', False)}")
        print(f"   Is Verified: {getattr(user, 'is_verified', False)}")
        
        # Récupérer les limites
        limits = MatchingService.get_daily_like_limit(user)
        super_likes = MatchingService.get_super_likes_remaining(user)
        
        print(f"\n   📊 Compteurs:")
        print(f"      Likes restants: {limits['remaining_likes']}")
        print(f"      Total likes: {limits['total_likes']}")
        print(f"      Likes utilisés: {limits['likes_used']}")
        print(f"      Super likes restants: {super_likes}")
        
        # Vérifier la cohérence
        if limits['remaining_likes'] == 999:
            if not getattr(user, 'is_premium', False):
                print(f"\n   ⚠️  PROBLÈME: Le compteur affiche 999 mais l'utilisateur n'est pas premium!")
            else:
                print(f"\n   ✅ OK: Utilisateur premium avec likes illimités")
        else:
            expected_remaining = limits['total_likes'] - limits['likes_used']
            if limits['remaining_likes'] == expected_remaining:
                print(f"\n   ✅ OK: Le compteur est cohérent")
            else:
                print(f"\n   ❌ ERREUR: Le compteur ne correspond pas!")
                print(f"      Attendu: {expected_remaining}, Reçu: {limits['remaining_likes']}")
        
        print("\n" + "-"*60)
    
    print("\n" + "="*60)
    print("FIN DES TESTS")
    print("="*60 + "\n")

if __name__ == '__main__':
    test_like_counters()
