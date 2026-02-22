#!/usr/bin/env python3
"""
Script de correction et synchronisation des utilisateurs sans mot de passe.

Ce script:
1. Identifie tous les utilisateurs sans mot de passe défini
2. Défini le mot de passe par défaut pour ces utilisateurs
3. Les synchronise avec Firebase Authentication
4. Génère un rapport détaillé
"""

import os
import django
import time
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
logger = logging.getLogger('fix_firebase_sync')

DEFAULT_PASSWORD = 'testpass123'


def fix_missing_passwords():
    """
    Corriger les utilisateurs sans mot de passe défini.
    """
    print("\n" + "="*70)
    print("🔐 CORRECTION DES MOTS DE PASSE MANQUANTS")
    print("="*70)
    
    # Identifier les utilisateurs sans password
    users_without_password = []
    for user in User.objects.all():
        # Vérifier si le password est vide ou non valide
        if not user.password or user.password == '' or user.password == '!':
            users_without_password.append(user)
    
    logger.info(f"📋 Utilisateurs sans mot de passe: {len(users_without_password)}")
    
    if not users_without_password:
        logger.info("✅ Tous les utilisateurs ont un mot de passe!")
        return True
    
    fixed_count = 0
    
    for i, user in enumerate(users_without_password, 1):
        try:
            logger.info(f"\n[{i}/{len(users_without_password)}] Correction: {user.email}")
            
            # Définir le mot de passe
            user.set_password(DEFAULT_PASSWORD)
            user.save()
            
            logger.info(f"   ✅ Mot de passe défini: {DEFAULT_PASSWORD}")
            fixed_count += 1
            
        except Exception as e:
            logger.error(f"   ❌ Erreur: {e}")
    
    logger.info(f"\n✅ {fixed_count}/{len(users_without_password)} utilisateurs corrigés")
    return True


def sync_password_corrected_users():
    """
    Synchroniser les utilisateurs dont le mot de passe vient d'être corrigé.
    """
    print("\n" + "="*70)
    print("🔥 SYNCHRONISATION DES UTILISATEURS CORRIGÉS")
    print("="*70)
    
    synced_users = []
    failed_users = []
    
    # Identifier les utilisateurs sans firebase_uid
    users_to_sync = User.objects.filter(firebase_uid__isnull=True)
    
    logger.info(f"📋 Utilisateurs à synchroniser: {users_to_sync.count()}")
    
    for i, user in enumerate(users_to_sync, 1):
        try:
            logger.info(f"\n[{i}/{users_to_sync.count()}] Synchronisation: {user.email}")
            
            # Créer l'utilisateur Firebase
            firebase_user = auth.create_user(
                email=user.email,
                password=DEFAULT_PASSWORD,
                display_name=user.display_name,
            )
            
            # Mettre à jour le firebase_uid
            user.firebase_uid = firebase_user.uid
            user.save(update_fields=['firebase_uid'])
            
            logger.info(f"   ✅ Utilisateur Firebase créé: {firebase_user.uid}")
            synced_users.append(user)
            
            # Vérifier la cohérence
            firebase_user_check = auth.get_user(firebase_user.uid)
            if firebase_user_check.email == user.email:
                logger.info(f"   ✅ Cohérence vérifiée")
            
            time.sleep(0.5)
            
        except firebase_admin.exceptions.AlreadyExistsError as e:
            logger.warning(f"   ⚠️ Utilisateur déjà existant: {user.email}")
            
            try:
                firebase_user = auth.get_user_by_email(user.email)
                user.firebase_uid = firebase_user.uid
                user.save(update_fields=['firebase_uid'])
                logger.info(f"   ℹ️ UID Firebase lié: {firebase_user.uid}")
                synced_users.append(user)
            except Exception as e2:
                logger.error(f"   ❌ Impossible de récupérer l'utilisateur: {e2}")
                failed_users.append((user, str(e2)))
            
        except Exception as e:
            logger.error(f"   ❌ Erreur: {e}")
            failed_users.append((user, str(e)))
    
    print("\n" + "="*70)
    print("📊 RÉSUMÉ DE LA SYNCHRONISATION")
    print("="*70)
    
    logger.info(f"\n✅ Utilisateurs synchronisés: {len(synced_users)}")
    logger.info(f"❌ Utilisateurs non synchronisés: {len(failed_users)}")
    
    if failed_users:
        logger.warning("\n❌ UTILISATEURS NON SYNCHRONISÉS:")
        for user, error in failed_users:
            logger.warning(f"   - {user.email}: {error}")
    
    return len(failed_users) == 0


def verify_all_users():
    """
    Vérifier que tous les utilisateurs ont un firebase_uid et un password.
    """
    print("\n" + "="*70)
    print("✅ VÉRIFICATION FINALE")
    print("="*70)
    
    all_users = User.objects.all()
    
    users_without_password = []
    users_without_firebase = []
    
    for user in all_users:
        if not user.password or user.password == '' or user.password == '!':
            users_without_password.append(user)
        
        if not user.firebase_uid:
            users_without_firebase.append(user)
    
    logger.info(f"📊 Total utilisateurs: {all_users.count()}")
    logger.info(f"✅ Utilisateurs avec password: {all_users.count() - len(users_without_password)}")
    logger.info(f"✅ Utilisateurs avec Firebase UID: {all_users.count() - len(users_without_firebase)}")
    
    if users_without_password:
        logger.warning(f"\n⚠️ {len(users_without_password)} utilisateurs sans mot de passe:")
        for user in users_without_password:
            logger.warning(f"   - {user.email}")
    
    if users_without_firebase:
        logger.warning(f"\n⚠️ {len(users_without_firebase)} utilisateurs sans Firebase UID:")
        for user in users_without_firebase:
            logger.warning(f"   - {user.email}")
    
    if not users_without_password and not users_without_firebase:
        logger.info("\n✅ TOUS LES UTILISATEURS SONT CORRECTEMENT CONFIGURÉS!")
        return True
    
    return False


def generate_detailed_report():
    """
    Générer un rapport détaillé de la synchronisation complète.
    """
    filename = 'firebase_sync_detailed_report.md'
    
    all_users = User.objects.all().order_by('email')
    
    users_with_password = all_users.exclude(password='') & all_users.exclude(password='!')
    users_with_firebase = all_users.exclude(firebase_uid__isnull=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Rapport Détaillé de Synchronisation Django ↔ Firebase\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 📊 Résumé Global\n\n")
        f.write(f"- **Total utilisateurs**: {all_users.count()}\n")
        f.write(f"- **Utilisateurs avec mot de passe**: {users_with_password.count()}\n")
        f.write(f"- **Utilisateurs avec Firebase UID**: {users_with_firebase.count()}\n")
        f.write(f"- **Utilisateurs premium**: {all_users.filter(is_premium=True).count()}\n")
        f.write(f"- **Utilisateurs vérifiés**: {all_users.filter(is_verified=True).count()}\n\n")
        
        f.write("## 📋 Liste Complète des Utilisateurs\n\n")
        
        for user in all_users:
            status_icons = []
            
            if user.password and user.password != '' and user.password != '!':
                status_icons.append('🔐')
            else:
                status_icons.append('❌')
            
            if user.firebase_uid:
                status_icons.append('🔥')
            else:
                status_icons.append('❌')
            
            if user.is_premium:
                status_icons.append('💎')
            else:
                status_icons.append('🆓')
            
            if user.is_verified:
                status_icons.append('✅')
            else:
                status_icons.append('⏳')
            
            status_line = ' '.join(status_icons)
            
            f.write(f"### {user.display_name} ({user.email})\n\n")
            f.write(f"**Status**: {status_line}\n\n")
            f.write(f"- Firebase UID: `{user.firebase_uid or 'N/A'}`\n")
            f.write(f"- Premium: {'Oui 💎' if user.is_premium else 'Non 🆓'}\n")
            f.write(f"- Vérifié: {'Oui ✅' if user.is_verified else 'Non ⏳'}\n")
            f.write(f"- Actif: {'Oui' if user.is_active else 'Non'}\n")
            f.write(f"- Email vérifié: {'Oui' if user.email_verified else 'Non'}\n\n")
        
        f.write("## Légende\n\n")
        f.write("- 🔐/❌: Mot de passe défini/Non défini\n")
        f.write("- 🔥/❌: Firebase UID synchronisé/Non synchronisé\n")
        f.write("- 💎/🆓: Premium/Gratuit\n")
        f.write("- ✅/⏳: Vérifié/En attente\n")
    
    logger.info(f"✅ Rapport généré: {filename}")
    return filename


def main():
    """Fonction principale"""
    try:
        # Phase 1: Corriger les mots de passe manquants
        fix_missing_passwords()
        
        # Phase 2: Synchroniser les utilisateurs corrigés
        sync_password_corrected_users()
        
        # Phase 3: Vérification finale
        verify_all_users()
        
        # Phase 4: Générer les rapports
        sync_report = generate_detailed_report()
        
        print("\n" + "="*70)
        print("✅ CORRECTION ET SYNCHRONISATION TERMINÉES!")
        print("="*70)
        print(f"\n📄 Rapport détaillé: {sync_report}")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    exit(main())
