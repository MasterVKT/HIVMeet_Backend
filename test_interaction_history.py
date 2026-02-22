"""
Script de test pour valider l'implémentation de l'historique des interactions.
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
from matching.models import InteractionHistory, Match
from matching.views_history import get_my_likes, get_my_passes, get_interaction_stats

User = get_user_model()


def test_interaction_history_model():
    """Test du modèle InteractionHistory."""
    print("\n" + "="*80)
    print("🧪 TEST 1: Modèle InteractionHistory")
    print("="*80)
    
    try:
        # Vérifier que le modèle existe et a les bons champs
        print("✅ Modèle InteractionHistory importé avec succès")
        
        # Vérifier les constantes
        assert hasattr(InteractionHistory, 'LIKE')
        assert hasattr(InteractionHistory, 'SUPER_LIKE')
        assert hasattr(InteractionHistory, 'DISLIKE')
        print("✅ Constantes d'interaction définies")
        
        # Vérifier les méthodes
        assert hasattr(InteractionHistory, 'get_user_likes')
        assert hasattr(InteractionHistory, 'get_user_passes')
        assert hasattr(InteractionHistory, 'create_or_reactivate')
        print("✅ Méthodes du modèle présentes")
        
        print("\n✅ Test du modèle réussi!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_my_likes_endpoint():
    """Test de l'endpoint GET /my-likes."""
    print("\n" + "="*80)
    print("🧪 TEST 2: Endpoint GET /my-likes")
    print("="*80)
    
    try:
        # Trouver un utilisateur
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("⚠️  Aucun utilisateur actif trouvé dans la base")
            return True  # Pas une erreur bloquante
        
        print(f"✅ Utilisateur trouvé: {user.email}")
        
        # Créer une requête factory
        factory = RequestFactory()
        request = factory.get('/api/v1/discovery/interactions/my-likes')
        force_authenticate(request, user=user)
        
        # Appeler la vue
        response = get_my_likes(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            print(f"📊 Nombre de likes: {data.get('count', 0)}")
            print("✅ Endpoint /my-likes fonctionne!")
            return True
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_my_passes_endpoint():
    """Test de l'endpoint GET /my-passes."""
    print("\n" + "="*80)
    print("🧪 TEST 3: Endpoint GET /my-passes")
    print("="*80)
    
    try:
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("⚠️  Aucun utilisateur actif trouvé")
            return True
        
        print(f"✅ Utilisateur: {user.email}")
        
        factory = RequestFactory()
        request = factory.get('/api/v1/discovery/interactions/my-passes')
        force_authenticate(request, user=user)
        
        response = get_my_passes(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            print(f"📊 Nombre de passes: {data.get('count', 0)}")
            print("✅ Endpoint /my-passes fonctionne!")
            return True
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_stats_endpoint():
    """Test de l'endpoint GET /stats."""
    print("\n" + "="*80)
    print("🧪 TEST 4: Endpoint GET /stats")
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
        
        response = get_interaction_stats(request)
        
        print(f"📥 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            print(f"\n📊 Statistiques:")
            print(f"   - Total likes: {data.get('total_likes', 0)}")
            print(f"   - Total super likes: {data.get('total_super_likes', 0)}")
            print(f"   - Total dislikes: {data.get('total_dislikes', 0)}")
            print(f"   - Total matches: {data.get('total_matches', 0)}")
            print(f"   - Ratio like/match: {data.get('like_to_match_ratio', 0)}")
            print(f"   - Interactions aujourd'hui: {data.get('total_interactions_today', 0)}")
            print(f"   - Limite quotidienne: {data.get('daily_limit', 0)}")
            print(f"   - Restant aujourd'hui: {data.get('remaining_today', 0)}")
            print("\n✅ Endpoint /stats fonctionne!")
            return True
        else:
            print(f"❌ Erreur: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_create_or_reactivate():
    """Test de la méthode create_or_reactivate."""
    print("\n" + "="*80)
    print("🧪 TEST 5: Méthode create_or_reactivate")
    print("="*80)
    
    try:
        # Trouver deux utilisateurs
        users = User.objects.filter(email_verified=True, is_active=True)[:2]
        if len(users) < 2:
            print("⚠️  Pas assez d'utilisateurs pour ce test")
            return True
        
        user1, user2 = users[0], users[1]
        print(f"✅ Utilisateurs: {user1.email} et {user2.email}")
        
        # Créer une interaction
        interaction, created = InteractionHistory.create_or_reactivate(
            user=user1,
            target_user=user2,
            interaction_type=InteractionHistory.LIKE
        )
        
        print(f"📝 Interaction créée: {created}")
        print(f"   - ID: {interaction.id}")
        print(f"   - Type: {interaction.interaction_type}")
        print(f"   - Révoquée: {interaction.is_revoked}")
        
        # Révoquer l'interaction
        interaction.revoke()
        print(f"🔄 Interaction révoquée")
        
        # Réactiver
        interaction2, created2 = InteractionHistory.create_or_reactivate(
            user=user1,
            target_user=user2,
            interaction_type=InteractionHistory.LIKE
        )
        
        print(f"🔄 Réactivation: created={created2}, ID={interaction2.id}")
        
        if interaction.id == interaction2.id and not created2:
            print("✅ Réactivation fonctionne correctement!")
            return True
        else:
            print("❌ Problème avec la réactivation")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Fonction principale pour exécuter tous les tests."""
    print("\n" + "🎯"*40)
    print("TESTS D'IMPLÉMENTATION DE L'HISTORIQUE DES INTERACTIONS")
    print("🎯"*40)
    
    results = []
    
    # Exécuter tous les tests
    results.append(("Test 1: Modèle InteractionHistory", test_interaction_history_model()))
    results.append(("Test 2: Endpoint /my-likes", test_get_my_likes_endpoint()))
    results.append(("Test 3: Endpoint /my-passes", test_get_my_passes_endpoint()))
    results.append(("Test 4: Endpoint /stats", test_get_stats_endpoint()))
    results.append(("Test 5: Méthode create_or_reactivate", test_create_or_reactivate()))
    
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
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) ont échoué")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
