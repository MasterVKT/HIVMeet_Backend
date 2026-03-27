"""
Interaction service for managing user interactions (likes, dislikes, super likes).
Centralizes all interaction-related business logic.
"""
from django.db.models import Min, Count, Q
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from typing import Optional, Tuple, Set, List
import logging

from .models import InteractionHistory, Like, Dislike, Match

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


class InteractionService:
    """
    Service pour gérer les interactions de découverte.
    Centralise toute la logique liée aux likes, dislikes et super likes.
    """
    
    # Interaction types
    TYPE_LIKE = InteractionHistory.LIKE
    TYPE_SUPER_LIKE = InteractionHistory.SUPER_LIKE
    TYPE_DISLIKE = InteractionHistory.DISLIKE
    
    @staticmethod
    @transaction.atomic
    def create_or_update_interaction(user, target_user, interaction_type: str) -> Tuple[InteractionHistory, bool]:
        """
        Crée ou met à jour une interaction.
        
        Args:
            user: L'utilisateur qui effectue l'interaction
            target_user: L'utilisateur cible
            interaction_type: 'like', 'super_like', ou 'dislike'
            
        Returns:
            Tuple[Interaction, created]: L'interaction créée/mise à jour et un booléen indiquant si elle a été créée
        """
        logger.info(f"🔄 InteractionService.create_or_update_interaction - User: {user.id}, Target: {target_user.id}, Type: {interaction_type}")
        
        # Déléguer au modèle qui a déjà cette logique
        interaction, created = InteractionHistory.create_or_reactivate(
            user=user,
            target_user=target_user,
            interaction_type=interaction_type
        )
        
        logger.info(f"✅ Interaction {'créée' if created else 'mise à jour'}: {interaction.id}")
        
        return interaction, created
    
    @staticmethod
    def get_excluded_profile_ids(user) -> Set:
        """
        Retourne les IDs des profils avec lesquels l'utilisateur a déjà interagi
        (likes, dislikes, super likes) - en excluant les interactions révoquées.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            set: IDs des profils à exclure de la découverte
        """
        # Ne pas inclure les interactions révoquées
        return set(
            InteractionHistory.objects.filter(
                user=user,
                is_revoked=False
            ).values_list('target_user_id', flat=True).distinct()
        )
    
    @staticmethod
    def get_liked_profile_ids(user) -> Set:
        """
        Retourne les IDs des profils que l'utilisateur a likés (sans révocation).
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            set: IDs des profils likés
        """
        return set(
            InteractionHistory.objects.filter(
                user=user,
                interaction_type__in=[InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE],
                is_revoked=False
            ).values_list('target_user_id', flat=True).distinct()
        )
    
    @staticmethod
    def get_disliked_profile_ids(user) -> Set:
        """
        Retourne les IDs des profils que l'utilisateur a dislikés (sans révocation).
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            set: IDs des profils dislikés
        """
        return set(
            InteractionHistory.objects.filter(
                user=user,
                interaction_type=InteractionHistory.DISLIKE,
                is_revoked=False
            ).values_list('target_user_id', flat=True).distinct()
        )
    
    @staticmethod
    @transaction.atomic
    def clean_duplicate_interactions(user_id: int) -> int:
        """
        Supprime les interactions en double pour un utilisateur.
        Garde seulement la première interaction pour chaque profil cible.
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            int: Nombre d'interactions supprimées
        """
        logger.info(f"🧹 Nettoyage des doublons pour l'utilisateur {user_id}")
        
        # Trouver les ID des premières interactions pour chaque profil cible
        first_interactions = InteractionHistory.objects.filter(
            user_id=user_id
        ).values(
            'target_user_id', 'interaction_type'
        ).annotate(
            min_id=Min('id')
        ).values_list('min_id', flat=True)
        
        # Supprimer toutes les autres interactions
        deleted_count = InteractionHistory.objects.filter(
            user_id=user_id
        ).exclude(
            id__in=first_interactions
        ).delete()[0]
        
        logger.info(f"✅ {deleted_count} interactions en double supprimées")
        
        return deleted_count
    
    @staticmethod
    def clean_all_duplicate_interactions() -> dict:
        """
        Nettoie les doublons pour tous les utilisateurs.
        
        Returns:
            dict: Statistiques du nettoyage
        """
        logger.info("🧹 Nettoyage global des doublons d'interactions")
        
        users = InteractionHistory.objects.values_list('user_id', flat=True).distinct()
        total_deleted = 0
        users_processed = 0
        
        for user_id in users:
            deleted = InteractionService.clean_duplicate_interactions(user_id)
            total_deleted += deleted
            users_processed += 1
        
        result = {
            'users_processed': users_processed,
            'total_deleted': total_deleted
        }
        
        logger.info(f"✅ Nettoyage terminé: {users_processed} utilisateurs traités, {total_deleted} doublons supprimés")
        
        return result
    
    @staticmethod
    def has_interacted_with(user, target_user_id) -> bool:
        """
        Vérifie si l'utilisateur a déjà interagi avec un profil.
        
        Args:
            user: L'utilisateur connecté
            target_user_id: ID du profil cible
            
        Returns:
            bool: True si une interaction existe (non révoquée)
        """
        return InteractionHistory.objects.filter(
            user=user,
            target_user_id=target_user_id,
            is_revoked=False
        ).exists()
    
    @staticmethod
    def get_interaction_type(user, target_user_id) -> Optional[str]:
        """
        Retourne le type d'interaction avec un profil.
        
        Args:
            user: L'utilisateur connecté
            target_user_id: ID du profil cible
            
        Returns:
            str or None: Type d'interaction ('like', 'super_like', 'dislike')
        """
        interaction = InteractionHistory.objects.filter(
            user=user,
            target_user_id=target_user_id,
            is_revoked=False
        ).first()
        
        return interaction.interaction_type if interaction else None
    
    @staticmethod
    def revoke_interaction(user, interaction_id) -> Tuple[bool, Optional[str], Optional[InteractionHistory]]:
        """
        Révoque une interaction.
        
        Args:
            user: L'utilisateur connecté
            interaction_id: ID de l'interaction à révoquer
            
        Returns:
            Tuple[bool, str, Interaction]: (succès, message d'erreur, interaction)
        """
        try:
            interaction = InteractionHistory.objects.get(
                id=interaction_id,
                user=user
            )
        except InteractionHistory.DoesNotExist:
            return False, "Interaction non trouvée", None
        
        if interaction.is_revoked:
            return False, "Cette interaction a déjà été révoquée", interaction
        
        # Vérifier si c'est un like qui a résulté en un match actif
        if interaction.interaction_type in [InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE]:
            active_match = Match.objects.filter(
                Q(user1=user, user2=interaction.target_user) |
                Q(user1=interaction.target_user, user2=user),
                status=Match.ACTIVE
            ).exists()
            
            if active_match:
                return False, "Impossible de révoquer un like qui a résulté en un match actif", interaction
        
        # Révoquer l'interaction
        interaction.revoke()
        logger.info(f"✅ Interaction {interaction_id} révoquée avec succès")
        
        return True, None, interaction
    
    @staticmethod
    def get_user_likes(user, include_revoked: bool = False, limit: int = None, offset: int = 0) -> List[InteractionHistory]:
        """
        Retourne les likes d'un utilisateur.
        
        Args:
            user: L'utilisateur
            include_revoked: Inclure les likes révoqués
            limit: Nombre maximum de résultats
            offset: Décalage pour la pagination
            
        Returns:
            list: Liste des interactions de type like
        """
        queryset = InteractionHistory.get_user_likes(user, include_revoked=include_revoked)
        
        if offset:
            queryset = queryset[offset:]
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset)
    
    @staticmethod
    def get_user_passes(user, include_revoked: bool = False, limit: int = None, offset: int = 0) -> List[InteractionHistory]:
        """
        Retourne les passes/dilikes d'un utilisateur.
        
        Args:
            user: L'utilisateur
            include_revoked: Inclure les passes révoqués
            limit: Nombre maximum de résultats
            offset: Décalage pour la pagination
            
        Returns:
            list: Liste des interactions de type dislike
        """
        queryset = InteractionHistory.get_user_passes(user, include_revoked=include_revoked)
        
        if offset:
            queryset = queryset[offset:]
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset)
    
    @staticmethod
    def get_interaction_counts(user) -> dict:
        """
        Retourne les statistiques d'interactions pour un utilisateur.
        
        Args:
            user: L'utilisateur
            
        Returns:
            dict: Statistiques des interactions
        """
        likes_count = InteractionHistory.objects.filter(
            user=user,
            interaction_type=InteractionHistory.LIKE,
            is_revoked=False
        ).count()
        
        super_likes_count = InteractionHistory.objects.filter(
            user=user,
            interaction_type=InteractionHistory.SUPER_LIKE,
            is_revoked=False
        ).count()
        
        dislikes_count = InteractionHistory.objects.filter(
            user=user,
            interaction_type=InteractionHistory.DISLIKE,
            is_revoked=False
        ).count()
        
        return {
            'likes': likes_count,
            'super_likes': super_likes_count,
            'dislikes': dislikes_count,
            'total': likes_count + super_likes_count + dislikes_count
        }
    
    @staticmethod
    def verify_no_duplicates(user_id: int) -> Tuple[bool, List[dict]]:
        """
        Vérifie qu'il n'y a pas de doublons pour un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            Tuple[bool, list]: (est_valide, liste des problèmes)
        """
        issues = []
        
        # Grouper par profil cible et type d'interaction
        duplicates = InteractionHistory.objects.filter(
            user_id=user_id,
            is_revoked=False
        ).values(
            'target_user_id', 'interaction_type'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for dup in duplicates:
            issues.append({
                'target_user_id': dup['target_user_id'],
                'interaction_type': dup['interaction_type'],
                'count': dup['count']
            })
        
        return len(issues) == 0, issues
    
    @staticmethod
    def verify_all_users() -> dict:
        """
        Vérifie tous les utilisateurs pour des doublons.
        
        Returns:
            dict: Statistiques de la vérification
        """
        logger.info("🔍 Vérification de tous les utilisateurs pour des doublons")
        
        users = InteractionHistory.objects.values_list('user_id', flat=True).distinct()
        users_with_issues = []
        total_issues = 0
        
        for user_id in users:
            is_valid, issues = InteractionService.verify_no_duplicates(user_id)
            if not is_valid:
                users_with_issues.append({
                    'user_id': user_id,
                    'issues': issues
                })
                total_issues += len(issues)
        
        result = {
            'users_checked': len(users),
            'users_with_issues': len(users_with_issues),
            'total_issues': total_issues,
            'details': users_with_issues[:10]  # Limiter les détails aux 10 premiers
        }
        
        if result['users_with_issues'] == 0:
            logger.info("✅ Aucun doublon trouvé!")
        else:
            logger.warning(f"⚠️ {result['users_with_issues']} utilisateurs ont des doublons")
        
        return result
