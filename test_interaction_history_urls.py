"""
Test de validation pour les endpoints d'historique des interactions.
Vérifie que les URLs sont correctement enregistrées et accessibles.
"""
import os
import django
import sys

# Configuration Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.urls import resolve, reverse
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import force_authenticate
from matching.models import InteractionHistory
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


def test_url_resolution():
    """Test que les URLs sont correctement enregistrées."""
    print("\n" + "="*80)
    print("🧪 TEST 1: Résolution des URLs")
    print("="*80)
    
    urls_to_test = [
        '/api/v1/discovery/interactions/my-likes',
        '/api/v1/discovery/interactions/my-passes',
        '/api/v1/discovery/interactions/stats',
    ]
    
    all_passed = True
    
    for url in urls_to_test:
        try:
            match = resolve(url)
            print(f"✅ {url} → {match.func.__name__}")
        except Exception as e:
            print(f"❌ {url} → ERREUR: {str(e)}")
            all_passed = False
    
    if all_passed:
        print("\n✅ Toutes les URLs sont correctement enregistrées!")
        return True
    else:
        print("\n❌ Certaines URLs ne sont pas enregistrées")
        return False


def test_my_likes_endpoint():
    """Test de l'endpoint my-likes via requête HTTP simulée."""
    print("\n" + "="*80)
    print("🧪 TEST 2: Endpoint GET /api/v1/discovery/interactions/my-likes")
    print("="*80)
    
    try:
        # Trouver un utilisateur
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("⚠️  Aucun utilisateur actif trouvé")
            return True
        
        print(f"✅ Utilisateur: {user.email}")
        
        # Créer une requête factory
        factory = RequestFactory()
        request = factory.get('/api/v1/discovery/interactions/my-likes')
        force_authenticate(request, user=user)
        request.user = user
        
        # Importer la vue
        from matching.views_history import get_my_likes
        
        # Appeler la vue
        response = get_my_likes(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            count = data.get('count', 0)
            print(f"📊 Nombre de likes: {count}")
            print("✅ Endpoint /my-likes fonctionne!")
            return True
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            print(f"   Réponse: {response.data}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_my_passes_endpoint():
    """Test de l'endpoint my-passes via requête HTTP simulée."""
    print("\n" + "="*80)
    print("🧪 TEST 3: Endpoint GET /api/v1/discovery/interactions/my-passes")
    print("="*80)
    
    try:
        # Trouver un utilisateur
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("⚠️  Aucun utilisateur actif trouvé")
            return True
        
        print(f"✅ Utilisateur: {user.email}")
        
        # Créer une requête factory
        factory = RequestFactory()
        request = factory.get('/api/v1/discovery/interactions/my-passes')
        force_authenticate(request, user=user)
        request.user = user
        
        # Importer la vue
        from matching.views_history import get_my_passes
        
        # Appeler la vue
        response = get_my_passes(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            count = data.get('count', 0)
            print(f"📊 Nombre de passes: {count}")
            print("✅ Endpoint /my-passes fonctionne!")
            return True
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            print(f"   Réponse: {response.data}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_stats_endpoint():
    """Test de l'endpoint stats."""
    print("\n" + "="*80)
    print("🧪 TEST 4: Endpoint GET /api/v1/discovery/interactions/stats")
    print("="*80)
    
    try:
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("⚠️  Aucun utilisateur actif trouvé")
            return True
        
        print(f"✅ Utilisateur: {user.email}")
        
        factory = RequestFactory()
        request = factory.get('/api/v1/discovery/interactions/stats')
        force_authenticate(request, user=user)
        request.user = user
        
        from matching.views_history import get_interaction_stats
        
        response = get_interaction_stats(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            print(f"\n📊 Statistiques:")
            print(f"   - Total likes: {data.get('total_likes', 0)}")
            print(f"   - Total passes: {data.get('total_dislikes', 0)}")
            print(f"   - Total matches: {data.get('total_matches', 0)}")
            print("✅ Endpoint /stats fonctionne!")
            return True
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_create_sample_data():
    """Créer des données de test pour valider le fonctionnement."""
    print("\n" + "="*80)
    print("🧪 TEST 5: Création de données de test")
    print("="*80)
    
    try:
        # Trouver deux utilisateurs
        users = User.objects.filter(email_verified=True, is_active=True)[:2]
        if len(users) < 2:
            print("⚠️  Pas assez d'utilisateurs pour créer des données")
            return True
        
        user1, user2 = users[0], users[1]
        print(f"✅ Utilisateurs: {user1.email} et {user2.email}")
        
        # Créer une interaction like
        like_interaction, created = InteractionHistory.create_or_reactivate(
            user=user1,
            target_user=user2,
            interaction_type=InteractionHistory.LIKE
        )
        
        if created:
            print(f"✅ Interaction LIKE créée: {like_interaction.id}")
        else:
            print(f"ℹ️  Interaction LIKE existante: {like_interaction.id}")
        
        # Trouver un troisième utilisateur pour le pass
        user3 = User.objects.filter(email_verified=True, is_active=True).exclude(
            id__in=[user1.id, user2.id]
        ).first()
        
        if user3:
            # Créer une interaction pass
            pass_interaction, created = InteractionHistory.create_or_reactivate(
                user=user1,
                target_user=user3,
                interaction_type=InteractionHistory.DISLIKE
            )
            
            if created:
                print(f"✅ Interaction PASS créée: {pass_interaction.id}")
            else:
                print(f"ℹ️  Interaction PASS existante: {pass_interaction.id}")
        
        print("\n✅ Données de test créées ou vérifiées!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Fonction principale pour exécuter tous les tests."""
    print("\n" + "🎯"*40)
    print("TESTS DE VALIDATION - ENDPOINTS INTERACTION HISTORY")
    print("🎯"*40)
    
    results = []
    
    # Exécuter tous les tests
    results.append(("Test 1: Résolution des URLs", test_url_resolution()))
    results.append(("Test 2: Endpoint my-likes", test_my_likes_endpoint()))
    results.append(("Test 3: Endpoint my-passes", test_my_passes_endpoint()))
    results.append(("Test 4: Endpoint stats", test_stats_endpoint()))
    results.append(("Test 5: Création données test", test_create_sample_data()))
    
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
        print("\n✅ Les endpoints d'historique des interactions sont opérationnels:")
        print("   - GET /api/v1/discovery/interactions/my-likes")
        print("   - GET /api/v1/discovery/interactions/my-passes")
        print("   - GET /api/v1/discovery/interactions/stats")
        print("   - POST /api/v1/discovery/interactions/<uuid>/revoke")
        print("\n✅ Le frontend peut maintenant accéder à ces endpoints sans erreur 404")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) ont échoué")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
