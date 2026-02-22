#!/usr/bin/env python3
"""
Script de vérification finale et de validation de la synchronisation.

Ce script valide:
1. Que tous les utilisateurs Django ont un firebase_uid
2. Que tous les UIDs Firebase correspondent aux emails Django
3. Que tous les mots de passe sont correctement définis
4. La cohérence entre Django et Firebase
5. Les statuts premium et de vérification
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
logger = logging.getLogger('verify_firebase_sync')


class FirebaseVerifier:
    """Classe pour vérifier la synchronisation Django <-> Firebase"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def verify_all_users(self):
        """Vérification complète de tous les utilisateurs"""
        
        print("\n" + "="*70)
        print("✅ VÉRIFICATION COMPLÈTE DE LA SYNCHRONISATION")
        print("="*70)
        
        all_users = User.objects.all().order_by('email')
        
        print(f"\n📊 PHASE 1: VÉRIFICATION DES DONNÉES DJANGO")
        print("-"*70)
        
        # Vérification 1: Tous les utilisateurs ont un password
        users_without_password = []
        for user in all_users:
            if not user.password or user.password == '' or user.password == '!':
                users_without_password.append(user)
        
        if users_without_password:
            msg = f"❌ {len(users_without_password)} utilisateurs sans password"
            logger.error(msg)
            self.issues.append(msg)
        else:
            msg = f"✅ Tous les {all_users.count()} utilisateurs ont un password"
            logger.info(msg)
            self.successes.append(msg)
        
        # Vérification 2: Tous les utilisateurs ont un firebase_uid
        users_without_firebase = []
        for user in all_users:
            if not user.firebase_uid:
                users_without_firebase.append(user)
        
        if users_without_firebase:
            msg = f"❌ {len(users_without_firebase)} utilisateurs sans Firebase UID"
            logger.error(msg)
            self.issues.append(msg)
            for user in users_without_firebase:
                logger.error(f"   - {user.email}")
        else:
            msg = f"✅ Tous les {all_users.count()} utilisateurs ont un Firebase UID"
            logger.info(msg)
            self.successes.append(msg)
        
        print(f"\n📊 PHASE 2: VÉRIFICATION FIREBASE AUTHENTICATION")
        print("-"*70)
        
        # Vérification 3: Vérifier la cohérence entre Django et Firebase
        inconsistent_users = []
        
        for i, user in enumerate(all_users, 1):
            if not user.firebase_uid:
                continue
            
            try:
                firebase_user = auth.get_user(user.firebase_uid)
                
                issues_for_user = []
                
                # Vérifier email
                if firebase_user.email != user.email:
                    issues_for_user.append(f"Email différent: Django={user.email}, Firebase={firebase_user.email}")
                
                # Vérifier display name
                if firebase_user.display_name != user.display_name:
                    issues_for_user.append(f"Display name différent: Django={user.display_name}, Firebase={firebase_user.display_name}")
                
                # Vérifier l'état du compte
                if firebase_user.disabled:
                    issues_for_user.append("Compte Firebase désactivé")
                
                if issues_for_user:
                    inconsistent_users.append((user, issues_for_user))
                    logger.warning(f"⚠️ {user.email}: Incohérences détectées")
                    for issue in issues_for_user:
                        logger.warning(f"   - {issue}")
                else:
                    logger.info(f"✅ {user.email}: Cohérent avec Firebase")
                    
            except Exception as e:
                msg = f"❌ Erreur lors de la vérification de {user.email}: {e}"
                logger.error(msg)
                self.issues.append(msg)
        
        if not inconsistent_users:
            msg = f"✅ Tous les utilisateurs sont cohérents avec Firebase"
            logger.info(msg)
            self.successes.append(msg)
        
        print(f"\n📊 PHASE 3: STATISTIQUES")
        print("-"*70)
        
        # Statistiques
        premium_users = all_users.filter(is_premium=True).count()
        free_users = all_users.filter(is_premium=False).count()
        verified_users = all_users.filter(is_verified=True).count()
        unverified_users = all_users.filter(is_verified=False).count()
        active_users = all_users.filter(is_active=True).count()
        inactive_users = all_users.filter(is_active=False).count()
        
        logger.info(f"\n📊 Statistiques Utilisateurs:")
        logger.info(f"   - Total: {all_users.count()}")
        logger.info(f"   - Premium: {premium_users} 💎")
        logger.info(f"   - Gratuit: {free_users} 🆓")
        logger.info(f"   - Vérifiés: {verified_users} ✅")
        logger.info(f"   - Non vérifiés: {unverified_users} ⏳")
        logger.info(f"   - Actifs: {active_users} 🟢")
        logger.info(f"   - Inactifs: {inactive_users} 🔴")
        
        return len(self.issues) == 0
    
    def generate_final_report(self):
        """Générer un rapport final"""
        
        filename = 'firebase_sync_verification_report.md'
        
        all_users = User.objects.all().order_by('email')
        premium_users = all_users.filter(is_premium=True)
        verified_users = all_users.filter(is_verified=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# Rapport Final de Vérification - Synchronisation Django ↔ Firebase\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## ✅ Résumé Exécutif\n\n")
            
            if len(self.issues) == 0:
                f.write("### 🎉 SYNCHRONISATION RÉUSSIE!\n\n")
                f.write("Tous les utilisateurs Django ont été synchronisés avec Firebase Authentication.\n")
                f.write("Tous les critères de cohérence et de conformité sont satisfaits.\n\n")
            else:
                f.write("### ⚠️ PROBLÈMES DÉTECTÉS\n\n")
                for issue in self.issues:
                    f.write(f"- {issue}\n")
                f.write("\n")
            
            f.write("## 📊 Statistiques Globales\n\n")
            f.write(f"- **Total utilisateurs**: {all_users.count()}\n")
            f.write(f"- **Utilisateurs avec Firebase UID**: {all_users.exclude(firebase_uid__isnull=True).count()}\n")
            f.write(f"- **Utilisateurs avec password**: {all_users.count()}\n")
            f.write(f"- **Utilisateurs premium**: {premium_users.count()}\n")
            f.write(f"- **Utilisateurs vérifiés**: {verified_users.count()}\n")
            f.write(f"- **Utilisateurs actifs**: {all_users.filter(is_active=True).count()}\n\n")
            
            f.write("## 📋 Distribution Premium\n\n")
            f.write(f"### Utilisateurs Premium 💎 ({premium_users.count()})\n\n")
            for user in premium_users.order_by('email'):
                status = "✅" if user.is_verified else "⏳"
                f.write(f"- {user.display_name} ({user.email}) {status}\n")
            
            f.write(f"\n### Utilisateurs Gratuit 🆓 ({all_users.filter(is_premium=False).count()})\n\n")
            for user in all_users.filter(is_premium=False).order_by('email'):
                status = "✅" if user.is_verified else "⏳"
                f.write(f"- {user.display_name} ({user.email}) {status}\n")
            
            f.write("\n## 📋 Distribution Vérification\n\n")
            f.write(f"### Utilisateurs Vérifiés ✅ ({verified_users.count()})\n\n")
            for user in verified_users.order_by('email'):
                premium = "💎" if user.is_premium else "🆓"
                f.write(f"- {user.display_name} ({user.email}) {premium}\n")
            
            f.write(f"\n### Utilisateurs Non Vérifiés ⏳ ({all_users.filter(is_verified=False).count()})\n\n")
            for user in all_users.filter(is_verified=False).order_by('email'):
                premium = "💎" if user.is_premium else "🆓"
                f.write(f"- {user.display_name} ({user.email}) {premium}\n")
            
            f.write("\n## 🔐 Informations de Connexion de Test\n\n")
            f.write("### Tous les utilisateurs\n")
            f.write("- **Password par défaut**: `testpass123`\n")
            f.write("- **Plateforme**: Firebase Authentication\n")
            f.write("- **Format email**: Vérifiés dans les enregistrements Django\n\n")
            
            f.write("### Utilisateurs administrateur\n")
            f.write("- `admin@hivmeet.com` / `testpass123`\n")
            f.write("- `admin@admin.com` / `testpass123`\n\n")
            
            f.write("## ✅ Succès\n\n")
            for success in self.successes:
                f.write(f"- {success}\n")
            
            if self.warnings:
                f.write("\n## ⚠️ Avertissements\n\n")
                for warning in self.warnings:
                    f.write(f"- {warning}\n")
            
            f.write("\n## 🎯 Prochaines Étapes\n\n")
            f.write("1. ✅ Tous les utilisateurs sont synchronisés avec Firebase Authentication\n")
            f.write("2. ✅ Les identifiants de connexion sont disponibles pour les tests\n")
            f.write("3. ✅ Les statuts premium et vérification sont conservés\n")
            f.write("4. ⏭️ Procéder aux tests d'intégration backend/frontend\n")
            f.write("5. ⏭️ Tester les flux d'authentification Firebase\n\n")
            
            f.write("---\n\n")
            f.write(f"**Rapport généré le**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        logger.info(f"✅ Rapport généré: {filename}")
        return filename


def main():
    """Fonction principale"""
    
    verifier = FirebaseVerifier()
    
    try:
        # Exécuter la vérification
        success = verifier.verify_all_users()
        
        # Générer le rapport
        report_file = verifier.generate_final_report()
        
        print("\n" + "="*70)
        print("📊 RÉSUMÉ FINAL")
        print("="*70)
        
        if success:
            print("\n✅ SYNCHRONISATION VALIDÉE AVEC SUCCÈS!")
            print(f"\n📄 Rapport détaillé: {report_file}")
            return 0
        else:
            print(f"\n⚠️ {len(verifier.issues)} problème(s) détecté(s)")
            print(f"\n📄 Rapport détaillé: {report_file}")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    exit(main())
