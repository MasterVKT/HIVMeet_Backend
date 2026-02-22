"""
Script pour vérifier et corriger le statut Premium de l'utilisateur Marie.
"""
import os
import django
import sys

# Configuration Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


def check_and_fix_marie_premium():
    """Vérifier et donner le statut Premium à Marie."""
    print("\n" + "="*80)
    print("🔍 VÉRIFICATION DU STATUT PREMIUM - marie.claire@test.com")
    print("="*80)
    
    try:
        # Trouver Marie
        marie = User.objects.get(email='marie.claire@test.com')
        print(f"\n✅ Utilisateur trouvé: {marie.email}")
        print(f"   - ID: {marie.id}")
        print(f"   - Actif: {marie.is_active}")
        print(f"   - Email vérifié: {marie.email_verified}")
        
        # Vérifier le statut Premium
        print(f"\n📊 STATUT PREMIUM ACTUEL:")
        print(f"   - is_premium: {marie.is_premium}")
        print(f"   - premium_until: {marie.premium_until}")
        
        needs_fix = False
        
        if not marie.is_premium:
            print(f"   ❌ is_premium = False (doit être True)")
            needs_fix = True
        
        if not marie.premium_until or marie.premium_until <= timezone.now():
            print(f"   ❌ premium_until expiré ou absent")
            needs_fix = True
        elif marie.is_premium:
            print(f"   ✅ Premium actif jusqu'au: {marie.premium_until}")
            print(f"   ⏰ Reste: {(marie.premium_until - timezone.now()).days} jours")
        
        if needs_fix:
            # Donner le statut Premium
            print(f"\n🔧 CORRECTION EN COURS...")
            marie.is_premium = True
            marie.premium_until = timezone.now() + timedelta(days=365)
            marie.save()
            
            print(f"   ✅ Statut Premium activé!")
            print(f"   📅 is_premium: {marie.is_premium}")
            print(f"   📅 premium_until: {marie.premium_until}")
            print(f"   ⏰ Durée: 365 jours")
        
        return True
            
    except User.DoesNotExist:
        print(f"\n❌ Erreur: Utilisateur marie.claire@test.com introuvable")
        return False
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_other_test_users():
    """Vérifier et donner Premium à d'autres utilisateurs de test."""
    print("\n" + "="*80)
    print("🔍 VÉRIFICATION DES AUTRES UTILISATEURS DE TEST")
    print("="*80)
    
    test_emails = [
        'camille.dubois@test.com',
        'lucas.anderson@test.com',
        'zoe.thompson@test.com',
        'antoine.lefevre@test.com'
    ]
    
    updated_count = 0
    
    for email in test_emails:
        try:
            user = User.objects.get(email=email)
            
            # Vérifier si Premium
            if not user.is_premium or not user.premium_until or user.premium_until <= timezone.now():
                user.is_premium = True
                user.premium_until = timezone.now() + timedelta(days=365)
                user.save()
                print(f"✅ {email} → Premium activé (365 jours)")
                updated_count += 1
            else:
                print(f"ℹ️  {email} → Déjà Premium (expire: {user.premium_until.date()})")
        except User.DoesNotExist:
            print(f"⚠️  {email} → Utilisateur introuvable")
        except Exception as e:
            print(f"❌ {email} → Erreur: {str(e)}")
    
    if updated_count > 0:
        print(f"\n✅ {updated_count} utilisateur(s) mis à jour")
    
    return True


def test_likes_received_access():
    """Tester l'accès à likes-received après correction."""
    print("\n" + "="*80)
    print("🧪 TEST D'ACCÈS À LIKES-RECEIVED")
    print("="*80)
    
    try:
        marie = User.objects.get(email='marie.claire@test.com')
        
        # Vérifier via la fonction is_premium_user
        from subscriptions.utils import is_premium_user
        
        is_premium = is_premium_user(marie)
        print(f"\n📊 Vérification is_premium_user():")
        print(f"   - Résultat: {is_premium}")
        print(f"   - premium_until: {marie.premium_until}")
        print(f"   - Maintenant: {timezone.now()}")
        
        if is_premium:
            print(f"\n✅ Marie a bien le statut Premium!")
            print(f"✅ Elle devrait pouvoir accéder à /likes-received/")
        else:
            print(f"\n❌ is_premium_user() retourne False")
            print(f"⚠️  Problème de logique dans subscriptions.utils.is_premium_user()")
        
        # Tester l'endpoint
        from django.test import RequestFactory
        from rest_framework.test import force_authenticate
        from profiles.views_premium import LikesReceivedView
        
        factory = RequestFactory()
        request = factory.get('/api/v1/user-profiles/likes-received/')
        force_authenticate(request, user=marie)
        request.user = marie
        
        view = LikesReceivedView.as_view()
        response = view(request)
        
        print(f"\n📥 Test de l'endpoint:")
        print(f"   - Status code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ SUCCÈS - Endpoint accessible!")
            data = response.data
            if isinstance(data, dict):
                print(f"   - Nombre de likes: {data.get('count', 0)}")
        elif response.status_code == 403:
            print(f"   ❌ ÉCHEC - Toujours 403 Forbidden")
            print(f"   - Message: {response.data}")
        else:
            print(f"   ⚠️  Code inattendu: {response.status_code}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Fonction principale."""
    print("\n" + "="*80)
    print("CORRECTION DU STATUT PREMIUM POUR LES TESTS")
    print("="*80)
    
    results = []
    
    # Vérifier et corriger Marie
    results.append(("Correction Marie Premium", check_and_fix_marie_premium()))
    
    # Vérifier les autres utilisateurs
    results.append(("Correction autres utilisateurs", check_other_test_users()))
    
    # Tester l'accès
    results.append(("Test accès likes-received", test_likes_received_access()))
    
    # Résumé
    print("\n" + "="*80)
    print("📊 RÉSUMÉ")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ OK" if result else "❌ ÉCHEC"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 Score: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 TOUT EST CORRIGÉ!")
        print("\n✅ Actions effectuées:")
        print("   1. Statut Premium activé pour Marie (365 jours)")
        print("   2. Autres utilisateurs de test vérifiés")
        print("   3. Endpoint /likes-received/ testé avec succès")
        print("\n💡 Redémarrez le serveur Django pour appliquer les changements:")
        print("   Ctrl+C puis: python manage.py runserver 0.0.0.0:8000")
        return True
    else:
        print(f"\n⚠️  {total - passed} problème(s) détecté(s)")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
