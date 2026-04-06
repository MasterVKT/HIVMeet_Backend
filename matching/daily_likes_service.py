"""
Daily Likes Service for HIVMeet.

Service centralisé pour gérer les limites de likes quotidiens,
les super likes, et le compteur de likes restants.

Basé sur les spécifications de BACKEND_DAILY_LIKES_CORRECTION.md
"""
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
import logging

from .models import Like, DailyLikeLimit, InteractionHistory
from subscriptions.models import Subscription

logger = logging.getLogger('hivmeet.matching')


class DailyLikesService:
    """
    Service pour gérer les limites de likes quotidiens.
    
    Limites selon les specs:
    - Utilisateurs gratuits: 10 likes/jour, 1 super like/jour
    - Utilisateurs premium: likes illimités, 5 super likes/jour
    """
    
    # Limites par défaut (spécifications: 10 likes gratuits)
    FREE_DAILY_LIKES_LIMIT = 10
    FREE_DAILY_SUPER_LIKES_LIMIT = 1
    PREMIUM_DAILY_SUPER_LIKES_LIMIT = 5
    
    # Valeur pour indiquer illimité (pas 999 qui cause des bugs)
    UNLIMITED = -1
    
    @staticmethod
    def is_premium_user(user) -> bool:
        """
        Vérifie si l'utilisateur a un abonnement premium actif.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            bool: True si premium, False sinon
        """
        # Méthode 1: Vérifier l'attribut is_premium sur le user model
        if hasattr(user, 'is_premium') and user.is_premium:
            return True
        
        # Méthode 2: Vérifier via Subscription model
        try:
            return Subscription.objects.filter(
                user=user,
                status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING],
                current_period_end__gt=timezone.now()
            ).exists()
        except Exception as e:
            logger.warning(f"[DailyLikesService] Error checking premium status: {e}")
            return False
    
    @staticmethod
    def get_user_daily_limit(user) -> int:
        """
        Retourne la limite quotidienne de likes pour un utilisateur.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Limite quotidienne (10 pour gratuits, -1 pour illimité premium)
        """
        if DailyLikesService.is_premium_user(user):
            return DailyLikesService.UNLIMITED  # Indique illimité
        
        return DailyLikesService.FREE_DAILY_LIKES_LIMIT
    
    @staticmethod
    def get_start_of_day() -> datetime:
        """
        Retourne le début de la journée en UTC (minuit).
        
        Returns:
            datetime: Début de la journée UTC
        """
        now = timezone.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def get_end_of_day() -> datetime:
        """
        Retourne la fin de la journée en UTC (minuit du lendemain).
        
        Returns:
            datetime: Fin de la journée UTC
        """
        now = timezone.now()
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def count_likes_today(user) -> int:
        """
        Compte les likes réguliers envoyés par l'utilisateur aujourd'hui.
        Utilise à la fois le modèle Like et InteractionHistory pour compatibilité.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de likes réguliers envoyés aujourd'hui
        """
        today_start = DailyLikesService.get_start_of_day()
        today_end = DailyLikesService.get_end_of_day()
        
        # Compter via le nouveau modèle InteractionHistory (non révoqués)
        interaction_count = InteractionHistory.objects.filter(
            user=user,
            interaction_type=InteractionHistory.LIKE,
            is_revoked=False,
            created_at__gte=today_start,
            created_at__lt=today_end
        ).count()
        
        # Compter via l'ancien modèle Like pour compatibilité
        like_count = Like.objects.filter(
            from_user=user,
            created_at__gte=today_start,
            created_at__lt=today_end
        ).exclude(like_type='super').count()
        
        # Retourner le maximum des deux pour éviter les incohérences
        return max(interaction_count, like_count)
    
    @staticmethod
    def count_super_likes_today(user) -> int:
        """
        Compte les super likes envoyés par l'utilisateur aujourd'hui.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de super likes envoyés aujourd'hui
        """
        today_start = DailyLikesService.get_start_of_day()
        today_end = DailyLikesService.get_end_of_day()
        
        # Compter via InteractionHistory
        interaction_count = InteractionHistory.objects.filter(
            user=user,
            interaction_type=InteractionHistory.SUPER_LIKE,
            is_revoked=False,
            created_at__gte=today_start,
            created_at__lt=today_end
        ).count()
        
        # Compter via l'ancien modèle Like
        super_like_count = Like.objects.filter(
            from_user=user,
            like_type='super',
            created_at__gte=today_start,
            created_at__lt=today_end
        ).count()
        
        return max(interaction_count, super_like_count)
    
    @staticmethod
    def get_likes_remaining(user) -> int:
        """
        Calcule les likes restants pour aujourd'hui.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de likes restants (0 à 10 pour gratuits, -1 pour illimité)
        """
        daily_limit = DailyLikesService.get_user_daily_limit(user)
        
        # Les utilisateurs premium ont des likes illimités
        if daily_limit == DailyLikesService.UNLIMITED:
            return DailyLikesService.UNLIMITED
        
        likes_sent = DailyLikesService.count_likes_today(user)
        remaining = daily_limit - likes_sent
        
        # S'assurer que la valeur est dans les limites valides [0, daily_limit]
        return max(0, min(remaining, daily_limit))
    
    @staticmethod
    def get_super_likes_remaining(user) -> int:
        """
        Calcule les super likes restants pour aujourd'hui.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            int: Nombre de super likes restants
        """
        if DailyLikesService.is_premium_user(user):
            limit = DailyLikesService.PREMIUM_DAILY_SUPER_LIKES_LIMIT
        else:
            limit = DailyLikesService.FREE_DAILY_SUPER_LIKES_LIMIT
        
        sent = DailyLikesService.count_super_likes_today(user)
        remaining = limit - sent
        
        return max(0, min(remaining, limit))
    
    @staticmethod
    def can_user_like(user) -> tuple:
        """
        Vérifie si l'utilisateur peut encore liker aujourd'hui.
        
        Returns:
            tuple: (peut_liker: bool, message_erreur: str)
        """
        if DailyLikesService.is_premium_user(user):
            return True, ""
        
        remaining = DailyLikesService.get_likes_remaining(user)
        
        if remaining <= 0:
            return False, _("Limite de likes quotidiens atteinte. Réessayez demain!")
        
        return True, ""
    
    @staticmethod
    def check_and_use_daily_like(user) -> tuple:
        """
        Vérifie si l'utilisateur peut liker et retourne les infos de limite.
        Cette méthode est utilisée AVANT de créer un like pour éviter l'erreur off-by-one.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            tuple: (success: bool, remaining: int, limit: int|None, error: str|None)
        """
        # Vérifier si premium
        if DailyLikesService.is_premium_user(user):
            return (True, DailyLikesService.UNLIMITED, None, None)
        
        # Obtenir les informations actuelles
        daily_info = DailyLikesService.get_status_summary(user)
        
        # Vérifier si la limite est atteinte
        if daily_info['remaining'] <= 0:
            reset_at = daily_info.get('reset_at')
            reset_str = reset_at.isoformat() if reset_at else None
            return (
                False,
                0,
                daily_info['limit'],
                f"Daily like limit reached. Limit: {daily_info['limit']}, Reset at: {reset_str}"
            )
        
        # Retourner les infos pour que le caller puisse décrémenter après le like
        return (
            True,
            daily_info['remaining'],  # Remaining AVANT le like (sera décrémenté après)
            daily_info['limit'],
            None
        )
    
    @staticmethod
    def get_daily_likes_info(user) -> dict:
        """
        Retourne les informations de likes quotidiens pour l'utilisateur.
        Méthode alias pour compatibilité avec les documents de correction.
        
        Returns:
            dict: {
                'remaining': int,  # Nombre de likes restants (-1 si premium/sans limite)
                'limit': int|None,  # Limite quotidienne (None si premium)
                'used_today': int,  # Likes utilisés aujourd'hui
                'reset_at': datetime,  # Heure de réinitialisation
                'is_premium': bool,
            }
        """
        is_premium = DailyLikesService.is_premium_user(user)
        
        if is_premium:
            return {
                'remaining': DailyLikesService.UNLIMITED,
                'limit': None,
                'used_today': 0,
                'reset_at': None,
                'is_premium': True,
            }
        
        # Configuration pour utilisateurs gratuits
        daily_limit = DailyLikesService.FREE_DAILY_LIKES_LIMIT
        
        # Récupérer les likes utilisés aujourd'hui (non révoqués)
        likes_used_today = DailyLikesService.count_likes_today(user)
        
        # Calculer les likes restants
        remaining = max(0, daily_limit - likes_used_today)
        
        # Calculer l'heure de réinitialisation (minuit)
        tomorrow = timezone.now().date() + timedelta(days=1)
        reset_at = timezone.make_aware(datetime.combine(tomorrow, datetime.min.time()))
        
        return {
            'remaining': remaining,
            'limit': daily_limit,
            'used_today': likes_used_today,
            'reset_at': reset_at,
            'is_premium': False,
        }
    
    @staticmethod
    def can_user_super_like(user) -> tuple:
        """
        Vérifie si l'utilisateur peut encore envoyer un super like aujourd'hui.
        
        Returns:
            tuple: (peut_super_liker: bool, message_erreur: str)
        """
        remaining = DailyLikesService.get_super_likes_remaining(user)
        
        if remaining <= 0:
            return False, _("Limite de super likes quotidiens atteinte. Réessayez demain!")
        
        return True, ""
    
    @staticmethod
    def get_next_reset_time() -> datetime:
        """
        Retourne l'heure du prochain reset du compteur (minuit UTC).
        
        Returns:
            datetime: Timestamp du prochain reset
        """
        now = timezone.now()
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def get_status_summary(user) -> dict:
        """
        Retourne un résumé complet du statut des limites quotidiennes.
        
        Returns:
            dict: Statut complet incluant likes restants, limites, et heure de reset
        """
        is_premium = DailyLikesService.is_premium_user(user)
        daily_limit = DailyLikesService.get_user_daily_limit(user)
        likes_remaining = DailyLikesService.get_likes_remaining(user)
        super_likes_remaining = DailyLikesService.get_super_likes_remaining(user)
        
        return {
            'daily_likes_remaining': likes_remaining,
            'daily_likes_limit': daily_limit if daily_limit != DailyLikesService.UNLIMITED else None,
            'super_likes_remaining': super_likes_remaining,
            'super_likes_limit': (
                DailyLikesService.PREMIUM_DAILY_SUPER_LIKES_LIMIT 
                if is_premium 
                else DailyLikesService.FREE_DAILY_SUPER_LIKES_LIMIT
            ),
            'is_premium': is_premium,
            'reset_at': DailyLikesService.get_next_reset_time().isoformat(),
            'likes_used_today': DailyLikesService.count_likes_today(user),
            'super_likes_used_today': DailyLikesService.count_super_likes_today(user),
        }
    
    @staticmethod
    def log_status(user, context: str = "") -> None:
        """
        Log le statut actuel pour le debug.
        
        Args:
            user: L'utilisateur
            context: Contexte additionnel pour le log
        """
        status = DailyLikesService.get_status_summary(user)
        logger.info(
            f"[DAILY_LIKES] {context} - User: {user.id} ({user.email}) - "
            f"is_premium={status['is_premium']}, "
            f"daily_likes_remaining={status['daily_likes_remaining']}, "
            f"likes_used_today={status['likes_used_today']}, "
            f"super_likes_remaining={status['super_likes_remaining']}, "
            f"daily_likes_limit={status['daily_likes_limit']}"
        )
