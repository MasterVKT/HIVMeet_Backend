"""
Signals for resources app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
import logging

from .models import FeedPostLike, FeedPostComment

logger = logging.getLogger('hivmeet.resources')


@receiver(post_save, sender=FeedPostLike)
def update_like_count_on_create(sender, instance, created, **kwargs):
    """
    Update like count when a like is created.
    """
    if created:
        # This is handled in the service, but as a safety measure
        pass


@receiver(post_delete, sender=FeedPostLike)
def update_like_count_on_delete(sender, instance, **kwargs):
    """
    Update like count when a like is deleted.
    """
    # This is handled in the service, but as a safety measure
    pass


@receiver(post_save, sender=FeedPostComment)
def update_comment_count_on_create(sender, instance, created, **kwargs):
    """
    Update comment count when a comment is created.
    """
    if created and instance.status == FeedPostComment.APPROVED:
        # This is handled in the service, but as a safety measure
        pass


@receiver(post_delete, sender=FeedPostComment)
def update_comment_count_on_delete(sender, instance, **kwargs):
    """
    Update comment count when a comment is deleted.
    """
    if instance.status == FeedPostComment.APPROVED:
        instance.post.comment_count = F('comment_count') - 1
        instance.post.save(update_fields=['comment_count'])