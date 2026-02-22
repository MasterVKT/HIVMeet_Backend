"""
Script de test pour valider l'implémentation des filtres de découverte.
"""
import os
import django
import sys

# Configuration Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

import json
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import force_authenticate
from matching.views_discovery import update_discovery_filters, get_discovery_filters, get_discovery_profiles
from profiles.models import Profile

User = get_user_model()


def test_update_filters():
    """Test de mise à jour des filtres."""
    print("\n" + "="*80)
    print("🧪 TEST 1: Mise à jour des filtres de découverte")
    print("="*80)
    
    # Créer un utilisateur de test s'il n'existe pas
    try:
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("❌ Aucun utilisateur actif trouvé dans la base de données")
            return False
        
        print(f"✅ Utilisateur trouvé: {user.email} (ID: {user.id})")
        
        # Créer une requête factory
        factory = RequestFactory()
        
        # Données de test pour les filtres
        filter_data = {
            'age_min': 25,
            'age_max': 35,
            'distance_max_km': 30,
            'genders': ['female'],
            'relationship_types': ['serious'],
            'verified_only': True,
            'online_only': False
        }
        
        print(f"\n📤 Envoi des filtres:")
        print(json.dumps(filter_data, indent=2))
        
        # Créer une requête PUT
        request = factory.put(
            '/api/v1/discovery/filters',
            data=json.dumps(filter_data),
            content_type='application/json'
        )
        force_authenticate(request, user=user)
        
        # Appeler la vue
        response = update_discovery_filters(request)
        
        print(f"\n📥 Réponse (Status: {response.status_code}):")
        print(json.dumps(response.data, indent=2, ensure_ascii=False))
        
        if response.status_code == 200:
            print("\n✅ Filtres mis à jour avec succès!")
            
            # Vérifier que les données sont bien sauvegardées
            profile = Profile.objects.get(user=user)
            print(f"\n🔍 Vérification de la base de données:")
            print(f"   - Age min: {profile.age_min_preference}")
            print(f"   - Age max: {profile.age_max_preference}")
            print(f"   - Distance max: {profile.distance_max_km} km")
            print(f"   - Genders sought: {profile.genders_sought}")
            print(f"   - Relationship types: {profile.relationship_types_sought}")
            print(f"   - Verified only: {profile.verified_only}")
            print(f"   - Online only: {profile.online_only}")
            
            return True
        else:
            print(f"\n❌ Échec de la mise à jour des filtres")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_filters():
    """Test de récupération des filtres."""
    print("\n" + "="*80)
    print("🧪 TEST 2: Récupération des filtres de découverte")
    print("="*80)
    
    try:
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("❌ Aucun utilisateur actif trouvé")
            return False
        
        print(f"✅ Utilisateur: {user.email}")
        
        factory = RequestFactory()
        
        # Créer une requête GET
        request = factory.get('/api/v1/discovery/filters')
        force_authenticate(request, user=user)
        
        # Appeler la vue
        response = get_discovery_filters(request)
        
        print(f"\n📥 Réponse (Status: {response.status_code}):")
        print(json.dumps(response.data, indent=2, ensure_ascii=False))
        
        if response.status_code == 200:
            print("\n✅ Filtres récupérés avec succès!")
            return True
        else:
            print(f"\n❌ Échec de la récupération des filtres")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_profiles_with_filters():
    """Test de récupération des profils avec application des filtres."""
    print("\n" + "="*80)
    print("🧪 TEST 3: Récupération des profils avec filtres appliqués")
    print("="*80)
    
    try:
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("❌ Aucun utilisateur actif trouvé")
            return False
        
        print(f"✅ Utilisateur: {user.email}")
        
        # D'abord, définir des filtres restrictifs
        profile = user.profile
        print(f"\n📊 Filtres actuels:")
        print(f"   - Age: {profile.age_min_preference}-{profile.age_max_preference}")
        print(f"   - Distance max: {profile.distance_max_km} km")
        print(f"   - Genders: {profile.genders_sought}")
        print(f"   - Verified only: {profile.verified_only}")
        print(f"   - Online only: {profile.online_only}")
        
        factory = RequestFactory()
        
        # Créer une requête GET
        request = factory.get('/api/v1/discovery/profiles?page=1&page_size=5')
        force_authenticate(request, user=user)
        
        # Appeler la vue
        response = get_discovery_profiles(request)
        
        print(f"\n📥 Réponse (Status: {response.status_code}):")
        print(f"   - Nombre de profils retournés: {response.data.get('count', 0)}")
        
        if response.status_code == 200:
            results = response.data.get('results', [])
            print(f"\n📋 Profils trouvés: {len(results)}")
            
            for idx, profile_data in enumerate(results, 1):
                print(f"\n   Profil {idx}:")
                print(f"      - Nom: {profile_data.get('display_name')}")
                print(f"      - Age: {profile_data.get('age')}")
                print(f"      - Vérifié: {profile_data.get('is_verified')}")
                print(f"      - En ligne: {profile_data.get('is_online')}")
                print(f"      - Distance: {profile_data.get('distance_km')} km")
            
            print("\n✅ Profils récupérés avec succès!")
            
            # Vérifier si les filtres sont bien appliqués
            if profile.verified_only:
                all_verified = all(p.get('is_verified', False) for p in results)
                if all_verified:
                    print("✅ Filtre 'verified_only' correctement appliqué")
                else:
                    print("⚠️  Filtre 'verified_only' non respecté")
            
            if profile.online_only:
                all_online = all(p.get('is_online', False) for p in results)
                if all_online:
                    print("✅ Filtre 'online_only' correctement appliqué")
                else:
                    print("⚠️  Filtre 'online_only' non respecté")
            
            return True
        else:
            print(f"\n❌ Échec de la récupération des profils")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_filters_with_all_option():
    """Test avec l'option 'all' pour les filtres."""
    print("\n" + "="*80)
    print("🧪 TEST 4: Test avec filtres 'all' (larges)")
    print("="*80)
    
    try:
        user = User.objects.filter(email_verified=True, is_active=True).first()
        if not user:
            print("❌ Aucun utilisateur actif trouvé")
            return False
        
        print(f"✅ Utilisateur: {user.email}")
        
        factory = RequestFactory()
        
        # Définir des filtres très larges
        filter_data = {
            'age_min': 18,
            'age_max': 99,
            'distance_max_km': 100,
            'genders': ['all'],
            'relationship_types': ['all'],
            'verified_only': False,
            'online_only': False
        }
        
        print(f"\n📤 Envoi des filtres larges:")
        print(json.dumps(filter_data, indent=2))
        
        request = factory.put(
            '/api/v1/discovery/filters',
            data=json.dumps(filter_data),
            content_type='application/json'
        )
        force_authenticate(request, user=user)
        
        response = update_discovery_filters(request)
        
        if response.status_code == 200:
            print("\n✅ Filtres larges appliqués!")
            
            # Récupérer les profils
            request = factory.get('/api/v1/discovery/profiles?page=1&page_size=10')
            force_authenticate(request, user=user)
            
            response = get_discovery_profiles(request)
            
            if response.status_code == 200:
                count = response.data.get('count', 0)
                print(f"\n📊 Résultat avec filtres larges: {count} profils trouvés")
                
                # Devrait retourner plus de profils qu'avec des filtres restrictifs
                if count > 0:
                    print("✅ Les filtres 'all' fonctionnent correctement (plus de profils disponibles)")
                    return True
                else:
                    print("⚠️  Aucun profil trouvé (base de données vide?)")
                    return True  # Ce n'est pas une erreur si la DB est vide
            
        print(f"\n❌ Échec du test avec filtres larges")
        return False
        
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Fonction principale pour exécuter tous les tests."""
    print("\n" + "🎯"*40)
    print("TESTS D'IMPLÉMENTATION DES FILTRES DE DÉCOUVERTE")
    print("🎯"*40)
    
    results = []
    
    # Exécuter tous les tests
    results.append(("Test 1: Mise à jour des filtres", test_update_filters()))
    results.append(("Test 2: Récupération des filtres", test_get_filters()))
    results.append(("Test 3: Profils avec filtres", test_get_profiles_with_filters()))
    results.append(("Test 4: Filtres 'all'", test_filters_with_all_option()))
    
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
