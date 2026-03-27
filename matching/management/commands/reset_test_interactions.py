"""
Management command to reset interactions for test users.
Usage: python manage.py reset_test_interactions [--all] [--email EMAIL] [--dry-run]
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
django.setup()

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from matching.models import InteractionHistory, Like, Dislike, Match
from matching.services import RecommendationService

User = get_user_model()


class Command(BaseCommand):
    help = 'Réinitialise les interactions des utilisateurs de test'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Réinitialiser uniquement l\'utilisateur avec cet email',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Réinitialiser TOUTES les interactions (DANGEREUX!)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Afficher les actions sans les exécuter',
        )
        parser.add_argument(
            '--keep-matches',
            action='store_true',
            help='Conserver les matches existants (supprime seulement les likes/dislikes)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Réinitialisation des interactions ===\n'))
        
        dry_run = options['dry_run']
        user_email = options.get('email')
        reset_all = options.get('all', False)
        keep_matches = options.get('keep_matches', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Mode DRY-RUN: Aucune modification ne sera effectuée\n'))
        
        if reset_all:
            self._reset_all(dry_run, keep_matches)
        elif user_email:
            self._reset_user_by_email(user_email, dry_run, keep_matches)
        else:
            self._reset_test_users(dry_run, keep_matches)
    
    def _reset_user_by_email(self, email, dry_run=False, keep_matches=False):
        """Réinitialise les interactions pour un utilisateur par email."""
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f'Utilisateur avec email {email} non trouvé')
        
        self._reset_user(user, dry_run, keep_matches)
    
    def _reset_test_users(self, dry_run=False, keep_matches=False):
        """Réinitialise les interactions pour les utilisateurs de test."""
        # Identifier les utilisateurs de test (email contient 'test' ou 'Test')
        test_users = User.objects.filter(
            email__icontains='test'
        )
        
        if not test_users.exists():
            self.stdout.write('ℹ️  Aucun utilisateur de test trouvé')
            return
        
        self.stdout.write(f'📋 {test_users.count()} utilisateurs de test trouvés\n')
        
        # Lister les utilisateurs
        for user in test_users:
            self.stdout.write(f'   - {user.email} (ID: {user.id})')
        
        if not dry_run:
            confirm = input('\n⚠️  Confirmer la réinitialisation pour ces utilisateurs? (oui/non): ')
            if confirm.lower() != 'oui':
                self.stdout.write('❌ Opération annulée')
                return
        
        # Réinitialiser chaque utilisateur
        for user in test_users:
            self._reset_user(user, dry_run, keep_matches)
    
    def _reset_all(self, dry_run=False, keep_matches=False):
        """Réinitialise TOUTES les interactions (DANGEREUX!)."""
        self.stdout.write(self.style.ERROR('\n⚠️  ATTENTION: Cette action va supprimer TOUTES les interactions!\n'))
        
        # Compter avant suppression
        total_likes = InteractionHistory.objects.filter(
            interaction_type__in=[InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE]
        ).count()
        
        total_dislikes = InteractionHistory.objects.filter(
            interaction_type=InteractionHistory.DISLIKE
        ).count()
        
        total_matches = Match.objects.count() if not keep_matches else 0
        
        self.stdout.write(f'   - Likes/Super Likes à supprimer: {total_likes}')
        self.stdout.write(f'   - Dislikes à supprimer: {total_dislikes}')
        if not keep_matches:
            self.stdout.write(f'   - Matches à supprimer: {total_matches}')
        else:
            self.stdout.write(f'   - Matches conservés (--keep-matches)')
        
        if not dry_run:
            confirm = input('\nÊtes-vous sûr? Tapez "OUI" pour confirmer: ')
            if confirm != 'OUI':
                self.stdout.write('❌ Opération annulée')
                return
            
            # Confirmer une deuxième fois
            confirm2 = input('Dernière confirmation - taper "OUI" à nouveau: ')
            if confirm2 != 'OUI':
                self.stdout.write('❌ Opération annulée')
                return
        
        self.stdout.write('\n🗑️  Suppression en cours...\n')
        
        if not dry_run:
            # Supprimer les interactions
            if not keep_matches:
                deleted_interactions = InteractionHistory.objects.all().delete()[0]
            else:
                # Supprimer seulement les likes et dislikes, pas les matches
                deleted_interactions = InteractionHistory.objects.all().delete()[0]
            
            self.stdout.write(f'   - Interactions supprimées: {deleted_interactions}')
            
            if not keep_matches:
                deleted_matches = Match.objects.all().delete()[0]
                self.stdout.write(f'   - Matches supprimés: {deleted_matches}')
            
            # Supprimer aussi les tables legacy
            deleted_likes = Like.objects.all().delete()[0]
            deleted_dislikes = Dislike.objects.all().delete()[0]
            
            self.stdout.write(f'   - Likes (legacy) supprimés: {deleted_likes}')
            self.stdout.write(f'   - Dislikes (legacy) supprimés: {deleted_dislikes}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Opération terminée'))
    
    def _reset_user(self, user, dry_run=False, keep_matches=False):
        """Réinitialise les interactions pour un utilisateur."""
        self.stdout.write(f'\n👤 Utilisateur: {user.email} (ID: {user.id})')
        
        # Compter avant
        likes_count = InteractionHistory.objects.filter(
            user=user,
            interaction_type__in=[InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE]
        ).count()
        
        passes_count = InteractionHistory.objects.filter(
            user=user,
            interaction_type=InteractionHistory.DISLIKE
        ).count()
        
        matches_as_user = Match.objects.filter(user1=user).count()
        matches_as_other = Match.objects.filter(user2=user).count()
        
        self.stdout.write(f'   - Likes: {likes_count}')
        self.stdout.write(f'   - Passes: {passes_count}')
        self.stdout.write(f'   - Matches: {matches_as_user + matches_as_other}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('   [DRY-RUN] Aucune action effectuée'))
            return
        
        # Supprimer les interactions
        deleted = InteractionHistory.objects.filter(user=user).delete()[0]
        self.stdout.write(f'   ✅ Interactions supprimées: {deleted}')
        
        # Supprimer les tables legacy
        deleted_likes = Like.objects.filter(from_user=user).delete()[0]
        deleted_dislikes = Dislike.objects.filter(from_user=user).delete()[0]
        self.stdout.write(f'   ✅ Legacy likes supprimés: {deleted_likes}')
        self.stdout.write(f'   ✅ Legacy dislikes supprimés: {deleted_dislikes}')
        
        # Supprimer les matches si demandé
        if not keep_matches:
            # Matches où l'utilisateur est user1
            matches_1 = Match.objects.filter(user1=user)
            # Matches où l'utilisateur est user2
            matches_2 = Match.objects.filter(user2=user)
            
            deleted_matches = matches_1.count() + matches_2.count()
            matches_1.delete()
            matches_2.delete()
            
            self.stdout.write(f'   ✅ Matches supprimés: {deleted_matches}')
        
        # Vérifier après suppression
        remaining = InteractionHistory.objects.filter(user=user).count()
        if remaining == 0:
            self.stdout.write(self.style.SUCCESS('   ✅ Réinitialisation complète réussie'))
        else:
            self.stdout.write(self.style.WARNING(f'   ⚠️  {remaining} interactions restantes'))
