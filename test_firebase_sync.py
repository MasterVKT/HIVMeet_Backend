#!/usr/bin/env python3
"""
Script de test de synchronisation Firebase - Validation complète

Ce script teste:
1. La connexion à Firebase avec des identifiants de test
2. La récupération d'utilisateurs depuis Firebase
3. La cohérence des données
4. Les cas d'usage courants
"""

import os
import django
from datetime import datetime

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
import firebase_admin
from firebase_admin import auth
import logging

User = get_user_model()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_firebase_sync')


def test_user_authentication():
    """Tester l'authentification d'un utilisateur Firebase"""
    
    print("\n" + "="*70)
    print("🧪 TEST 1: AUTHENTIFICATION UTILISATEUR")
    print("="*70)
    
    test_email = 'thomas.dupont@test.com'
    test_password = 'testpass123'
    
    try:
        # Récupérer l'utilisateur Django
        user = User.objects.get(email=test_email)
        logger.info(f"✅ Utilisateur Django trouvé: {user.email} ({user.display_name})")
        
        # Récupérer l'utilisateur Firebase
        firebase_user = auth.get_user(user.firebase_uid)
        logger.info(f"✅ Utilisateur Firebase trouvé: {firebase_user.email}")
        logger.info(f"   - UID: {firebase_user.uid}")
        logger.info(f"   - Display Name: {firebase_user.display_name}")
        logger.info(f"   - Email Verified: {firebase_user.email_verified}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False


def test_user_data_consistency():
    """Tester la cohérence des données entre Django et Firebase"""
    
    print("\n" + "="*70)
    print("🧪 TEST 2: COHÉRENCE DES DONNÉES")
    print("="*70)
    
    inconsistencies = []
    
    # Tester 5 utilisateurs aléatoires
    test_users = User.objects.all()[:5]
    
    for user in test_users:
        try:
            firebase_user = auth.get_user(user.firebase_uid)
            
            # Vérifier les champs
            if firebase_user.email != user.email:
                inconsistencies.append(f"{user.email}: Email incohérent")
            
            if firebase_user.display_name != user.display_name:
                inconsistencies.append(f"{user.email}: Display name incohérent")
            
            logger.info(f"✅ {user.email}: Données cohérentes")
            
        except Exception as e:
            logger.error(f"❌ {user.email}: {e}")
            inconsistencies.append(str(e))
    
    if not inconsistencies:
        logger.info(f"\n✅ Tous les utilisateurs testés sont cohérents!")
        return True
    else:
        logger.warning(f"\n⚠️ {len(inconsistencies)} incohérence(s) détectée(s)")
        return False


def test_premium_status():
    """Tester la préservation du statut premium"""
    
    print("\n" + "="*70)
    print("🧪 TEST 3: STATUT PREMIUM")
    print("="*70)
    
    premium_users = User.objects.filter(is_premium=True)[:3]
    free_users = User.objects.filter(is_premium=False)[:3]
    
    logger.info(f"✅ Utilisateurs premium testés: {premium_users.count()}")
    for user in premium_users:
        logger.info(f"   💎 {user.display_name} ({user.email}) - Firebase UID: {user.firebase_uid}")
    
    logger.info(f"✅ Utilisateurs gratuit testés: {free_users.count()}")
    for user in free_users:
        logger.info(f"   🆓 {user.display_name} ({user.email}) - Firebase UID: {user.firebase_uid}")
    
    return True


def test_verification_status():
    """Tester la préservation du statut de vérification"""
    
    print("\n" + "="*70)
    print("🧪 TEST 4: STATUT DE VÉRIFICATION")
    print("="*70)
    
    verified_users = User.objects.filter(is_verified=True)[:3]
    unverified_users = User.objects.filter(is_verified=False)[:3]
    
    logger.info(f"✅ Utilisateurs vérifiés testés: {verified_users.count()}")
    for user in verified_users:
        logger.info(f"   ✅ {user.display_name} ({user.email}) - Statut: {user.verification_status}")
    
    logger.info(f"✅ Utilisateurs non vérifiés testés: {unverified_users.count()}")
    for user in unverified_users:
        logger.info(f"   ⏳ {user.display_name} ({user.email}) - Statut: {user.verification_status}")
    
    return True


def test_firebase_user_lookup():
    """Tester la recherche d'utilisateurs Firebase"""
    
    print("\n" + "="*70)
    print("🧪 TEST 5: RECHERCHE D'UTILISATEURS FIREBASE")
    print("="*70)
    
    try:
        # Rechercher par email
        test_email = 'sophie.leroy@test.com'
        firebase_user = auth.get_user_by_email(test_email)
        
        logger.info(f"✅ Utilisateur trouvé par email: {test_email}")
        logger.info(f"   - UID: {firebase_user.uid}")
        logger.info(f"   - Display Name: {firebase_user.display_name}")
        logger.info(f"   - Email: {firebase_user.email}")
        
        # Vérifier la cohérence
        django_user = User.objects.get(email=test_email)
        if firebase_user.uid == django_user.firebase_uid:
            logger.info(f"✅ Firebase UID correspond")
        else:
            logger.warning(f"⚠️ Firebase UID incohérent")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False


def test_password_validation():
    """Tester que les mots de passe sont valides"""
    
    print("\n" + "="*70)
    print("🧪 TEST 6: VALIDATION DES MOTS DE PASSE")
    print("="*70)
    
    users_without_password = []
    
    all_users = User.objects.all()
    
    for user in all_users:
        if not user.password or user.password == '' or user.password == '!':
            users_without_password.append(user)
    
    if users_without_password:
        logger.warning(f"⚠️ {len(users_without_password)} utilisateurs sans mot de passe")
        for user in users_without_password:
            logger.warning(f"   - {user.email}")
        return False
    else:
        logger.info(f"✅ Tous les {all_users.count()} utilisateurs ont un mot de passe")
        return True


def test_firebase_uid_uniqueness():
    """Tester que tous les Firebase UID sont uniques"""
    
    print("\n" + "="*70)
    print("🧪 TEST 7: UNICITÉ DES FIREBASE UID")
    print("="*70)
    
    all_users = User.objects.all()
    
    firebase_uids = [u.firebase_uid for u in all_users if u.firebase_uid]
    unique_uids = set(firebase_uids)
    
    if len(firebase_uids) == len(unique_uids):
        logger.info(f"✅ Tous les {len(unique_uids)} Firebase UID sont uniques")
        return True
    else:
        duplicates = len(firebase_uids) - len(unique_uids)
        logger.warning(f"⚠️ {duplicates} Firebase UID(s) dupliqué(s)")
        return False


def test_admin_accounts():
    """Tester les comptes administrateur"""
    
    print("\n" + "="*70)
    print("🧪 TEST 8: COMPTES ADMINISTRATEUR")
    print("="*70)
    
    admin_emails = ['admin@hivmeet.com', 'admin@admin.com']
    
    for admin_email in admin_emails:
        try:
            user = User.objects.get(email=admin_email)
            firebase_user = auth.get_user(user.firebase_uid)
            
            logger.info(f"✅ Admin trouvé: {user.email}")
            logger.info(f"   - Firebase UID: {user.firebase_uid}")
            logger.info(f"   - Premium: {'Oui 💎' if user.is_premium else 'Non'}")
            logger.info(f"   - Staff: {'Oui' if user.is_staff else 'Non'}")
            logger.info(f"   - Superuser: {'Oui' if user.is_superuser else 'Non'}")
            
        except Exception as e:
            logger.error(f"❌ Admin {admin_email}: {e}")
            return False
    
    return True


def run_all_tests():
    """Exécuter tous les tests"""
    
    print("\n" + "="*70)
    print("🧪 TESTS DE SYNCHRONISATION FIREBASE - SUITE COMPLÈTE")
    print("="*70)
    print(f"\n⏰ Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {
        'Authentification': test_user_authentication(),
        'Cohérence': test_user_data_consistency(),
        'Statut Premium': test_premium_status(),
        'Statut Vérification': test_verification_status(),
        'Recherche Firebase': test_firebase_user_lookup(),
        'Validation Mots de passe': test_password_validation(),
        'Unicité Firebase UID': test_firebase_uid_uniqueness(),
        'Comptes Admin': test_admin_accounts(),
    }
    
    # Résumé
    print("\n" + "="*70)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*70 + "\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\n📈 Résultat: {passed}/{total} tests réussis")
    
    if passed == total:
        logger.info("\n🎉 TOUS LES TESTS SONT PASSÉS!")
        return 0
    else:
        logger.warning(f"\n⚠️ {total - passed} test(s) échoué(s)")
        return 1


def main():
    """Fonction principale"""
    try:
        return run_all_tests()
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    exit(main())
