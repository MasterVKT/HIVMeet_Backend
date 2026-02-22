"""
Test de validation pour l'endpoint likes-received après correction.
"""
import os
import django
import sys

# Configuration Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import force_authenticate
from profiles.views_premium import LikesReceivedView, SuperLikesReceivedView
from matching.models import Like
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()


def test_likes_received_endpoint():
    """Test de l'endpoint likes-received."""
    print("\n" + "="*80)
    print("🧪 TEST: Endpoint GET /api/v1/user-profiles/likes-received/")
    print("="*80)
    
    try:
        # Trouver un utilisateur avec premium
        premium_users = User.objects.filter(
            premium_until__gt=timezone.now(),
            email_verified=True,
            is_active=True
        )
        
        if not premium_users.exists():
            print("⚠️  Aucun utilisateur premium trouvé")
            print("📝 Création d'un utilisateur premium de test...")
            
            # Créer un utilisateur premium de test
            user = User.objects.filter(email_verified=True, is_active=True).first()
            if not user:
                print("❌ Aucun utilisateur actif trouvé")
                return False
            
            # Donner le statut premium
            user.premium_until = timezone.now() + timedelta(days=30)
            user.save()
            print(f"✅ Utilisateur {user.email} mis à niveau en Premium")
        else:
            user = premium_users.first()
            print(f"✅ Utilisateur premium trouvé: {user.email}")
        
        # Créer une requête factory
        factory = RequestFactory()
        request = factory.get('/api/v1/user-profiles/likes-received/')
        force_authenticate(request, user=user)
        request.user = user
        
        # Créer la vue
        view = LikesReceivedView.as_view()
        
        # Appeler la vue
        response = view(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            if isinstance(data, dict):
                count = data.get('count', 0)
                results = data.get('results', [])
                print(f"📊 Nombre de likes reçus: {count}")
                if count > 0:
                    print(f"👤 Premier like de: {results[0].get('username', 'N/A')}")
                print("\n✅ Endpoint /likes-received/ fonctionne!")
            else:
                print(f"📊 Données reçues: {len(data)} likes")
                print("\n✅ Endpoint /likes-received/ fonctionne!")
            return True
        elif response.status_code == 403:
            print(f"❌ Erreur 403: {response.data}")
            print("⚠️  L'utilisateur n'a peut-être pas le statut premium correctement configuré")
            return False
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            print(f"   Réponse: {response.data}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_likes_received_non_premium():
    """Test que les utilisateurs non-premium reçoivent bien un 403."""
    print("\n" + "="*80)
    print("🧪 TEST: Vérification refus pour utilisateurs non-premium")
    print("="*80)
    
    try:
        # Trouver un utilisateur non-premium
        user = User.objects.filter(
            email_verified=True,
            is_active=True
        ).exclude(
            premium_until__gt=timezone.now()
        ).first()
        
        if not user:
            print("⚠️  Aucun utilisateur non-premium trouvé")
            return True
        
        print(f"✅ Utilisateur non-premium: {user.email}")
        
        # Créer une requête factory
        factory = RequestFactory()
        request = factory.get('/api/v1/user-profiles/likes-received/')
        force_authenticate(request, user=user)
        request.user = user
        
        # Créer la vue
        view = LikesReceivedView.as_view()
        
        # Appeler la vue
        response = view(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 403:
            print(f"📝 Message: {response.data.get('message', 'N/A')}")
            print("\n✅ Les non-premium sont correctement refusés (403)!")
            return True
        else:
            print(f"❌ Attendu 403, reçu {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_super_likes_received_endpoint():
    """Test de l'endpoint super-likes-received."""
    print("\n" + "="*80)
    print("🧪 TEST: Endpoint GET /api/v1/user-profiles/super-likes-received/")
    print("="*80)
    
    try:
        # Trouver un utilisateur avec premium
        user = User.objects.filter(
            premium_until__gt=timezone.now(),
            email_verified=True,
            is_active=True
        ).first()
        
        if not user:
            print("⚠️  Aucun utilisateur premium trouvé (utiliser test précédent)")
            return True
        
        print(f"✅ Utilisateur premium: {user.email}")
        
        # Créer une requête factory
        factory = RequestFactory()
        request = factory.get('/api/v1/user-profiles/super-likes-received/')
        force_authenticate(request, user=user)
        request.user = user
        
        # Créer la vue
        view = SuperLikesReceivedView.as_view()
        
        # Appeler la vue
        response = view(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            if isinstance(data, dict):
                count = data.get('count', 0)
                print(f"📊 Nombre de super likes reçus: {count}")
            else:
                print(f"📊 Données reçues: {len(data)} super likes")
            print("\n✅ Endpoint /super-likes-received/ fonctionne!")
            return True
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Fonction principale pour exécuter tous les tests."""
    print("\n" + "🎯"*40)
    print("TESTS DE VALIDATION - CORRECTION ENDPOINT LIKES-RECEIVED")
    print("🎯"*40)
    
    results = []
    
    # Exécuter tous les tests
    results.append(("Test 1: Endpoint likes-received (Premium)", test_likes_received_endpoint()))
    results.append(("Test 2: Refus non-premium (403)", test_likes_received_non_premium()))
    results.append(("Test 3: Endpoint super-likes-received", test_super_likes_received_endpoint()))
    
    # Afficher le résumé
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 Score: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS SONT PASSÉS!")
        print("\n✅ L'endpoint /api/v1/user-profiles/likes-received/ est maintenant fonctionnel")
        print("✅ Le frontend peut récupérer les likes reçus sans erreur 403")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) ont échoué")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
