"""
Management command to clean duplicate interactions in the database.
Usage: python manage.py clean_interaction_duplicates [--user-id USER_ID] [--verify-only]
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
django.setup()

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Min, Count
from matching.models import InteractionHistory
from matching.interaction_service import InteractionService
from matching.services import RecommendationService


class Command(BaseCommand):
    help = 'Nettoie les doublons d\'interactions dans la base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Nettoyer uniquement les doublons pour un utilisateur spécifique',
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Vérifier seulement, sans supprimer les doublons',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Nettoyer les doublons pour tous les utilisateurs',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Nettoyage des doublons d\'interactions ===\n'))
        
        verify_only = options['verify_only']
        user_id = options.get('user_id')
        clean_all = options.get('all', False)
        
        if verify_only:
            self._verify_all()
        elif user_id:
            self._clean_user(user_id, verify_only)
        elif clean_all:
            self._clean_all()
        else:
            self.stdout.write(self.style.WARNING(
                '⚠️  Veuillez spécifier une option:\n'
                '   --user-id USER_ID pour nettoyer un utilisateur\n'
                '   --all pour nettoyer tous les utilisateurs\n'
                '   --verify-only pour vérifier sans nettoyer'
            ))
    
    def _verify_all(self):
        """Vérifie tous les utilisateurs pour des doublons."""
        self.stdout.write('🔍 Vérification de tous les utilisateurs...\n')
        
        result = InteractionService.verify_all_users()
        
        self.stdout.write(f'\n📊 Résultats de la vérification:')
        self.stdout.write(f'   - Utilisateurs vérifiés: {result["users_checked"]}')
        self.stdout.write(f'   - Utilisateurs avec problèmes: {result["users_with_issues"]}')
        self.stdout.write(f'   - Problèmes totaux: {result["total_issues"]}')
        
        if result['users_with_issues'] > 0:
            self.stdout.write(self.style.WARNING('\n⚠️  Détails des problèmes:'))
            for user_data in result['details']:
                self.stdout.write(f'   - Utilisateur {user_data["user_id"]}:')
                for issue in user_data['issues']:
                    self.stdout.write(f'      * {issue["interaction_type"]} x {issue["count"]} sur le profil {issue["target_user_id"]}')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Aucun doublon trouvé!'))
    
    def _clean_user(self, user_id, verify_only=False):
        """Nettoie les doublons pour un utilisateur spécifique."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f'Utilisateur avec ID {user_id} non trouvé')
        
        self.stdout.write(f'👤 Utilisateur: {user.email} (ID: {user_id})\n')
        
        if verify_only:
            # Vérifier seulement
            is_valid, issues = InteractionService.verify_no_duplicates(user_id)
            
            if is_valid:
                self.stdout.write(self.style.SUCCESS('✅ Aucun doublon trouvé pour cet utilisateur'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  {len(issues)} doublons trouvés:'))
                for issue in issues:
                    self.stdout.write(f'   - {issue["interaction_type"]} x {issue["count"]} sur le profil {issue["target_user_id"]}')
        else:
            # Nettoyer
            deleted = InteractionService.clean_duplicate_interactions(user_id)
            
            if deleted > 0:
                self.stdout.write(self.style.SUCCESS(f'✅ {deleted} doublons supprimés'))
            else:
                self.stdout.write('ℹ️  Aucun doublon à supprimer')
    
    def _clean_all(self):
        """Nettoie les doublons pour tous les utilisateurs."""
        self.stdout.write('🧹 Nettoyage global...\n')
        
        # D'abord vérifier
        self.stdout.write('1️⃣  Vérification initiale:')
        verification = InteractionService.verify_all_users()
        self.stdout.write(f'   - Utilisateurs avec problèmes: {verification["users_with_issues"]}')
        
        if verification['users_with_issues'] == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ Aucun doublon à nettoyer!'))
            return
        
        # Confirmer avant de continuer
        confirm = input(f'\n⚠️  Cela va supprimer {verification["total_issues"]} doublons pour {verification["users_with_issues"]} utilisateurs.\nContinuer? (oui/non): ')
        
        if confirm.lower() != 'oui':
            self.stdout.write('❌ Opération annulée')
            return
        
        # Exécuter le nettoyage
        self.stdout.write('\n2️⃣  Exécution du nettoyage:')
        result = InteractionService.clean_all_duplicate_interactions()
        
        self.stdout.write(f'   - Utilisateurs traités: {result["users_processed"]}')
        self.stdout.write(f'   - Doublons supprimés: {result["total_deleted"]}')
        
        # Vérifier après
        self.stdout.write('\n3️⃣  Vérification finale:')
        final_check = InteractionService.verify_all_users()
        
        if final_check['users_with_issues'] == 0:
            self.stdout.write(self.style.SUCCESS('✅ Tous les doublons ont été supprimés avec succès!'))
        else:
            self.stdout.write(self.style.ERROR(
                f'\n⚠️  {final_check["users_with_issues"]} problèmes restants. '
                'Certains doublons n\'ont pas pu être supprimés (contraintes d\'intégrité).'
            ))
