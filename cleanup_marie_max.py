#!/usr/bin/env python
"""
Script de nettoyage des interactions entre Marie (40 ans) et Max Weber.

Supprime tous les liens (likes, dislikes, match, messages, calls, etc.)
entre ces deux utilisateurs pour permettre de recommencer les tests
de matching/messaging depuis le debut.

Usage: python cleanup_marie_max.py
"""
import os
import sys
import django

# Configurer Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

# Ajouter le repertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from authentication.models import User
from matching.models import Like, Dislike, Match, InteractionHistory, ProfileView, DailyLikeLimit
from messaging.models import Message, Call, TypingIndicator


def find_users():
    """Trouver Marie (40 ans) et Max Weber."""
    # Chercher Marie: display_name='Marie', age=40, email=marie.claire@test.com
    marie = User.objects.filter(
        display_name='Marie',
        email='marie.claire@test.com'
    ).first()

    if not marie:
        # Fallback: chercher par display_name seulement
        marie = User.objects.filter(
            display_name__icontains='Marie',
            birth_date__year=1986  # 40 ans en 2026
        ).first()

    if not marie:
        marie = User.objects.filter(
            display_name__icontains='Marie',
        ).first()

    # Chercher Max Weber: display_name='Max', email=max.weber@test.com
    max_weber = User.objects.filter(
        display_name='Max',
        email='max.weber@test.com'
    ).first()

    if not max_weber:
        # Fallback: chercher par email
        max_weber = User.objects.filter(
            email='max.weber@test.com'
        ).first()

    if not max_weber:
        print("User 'Max Weber' not found")
        print("\nAvailable users:")
        for u in User.objects.all().order_by('display_name'):
            age = u.age if u.birth_date else '?'
            print(f"  - {u.display_name} (email: {u.email}, age: {age})")

    return marie, max_weber


@transaction.atomic
def cleanup(marie, max_weber):
    """Supprimer toutes les interactions entre Marie et Max Weber."""
    print(f"\nTargets found:")
    print(f"  - {marie.display_name} (ID: {marie.id}, email: {marie.email}, age: {marie.age})")
    print(f"  - {max_weber.display_name} (ID: {max_weber.id}, email: {max_weber.email}, age: {max_weber.age})")

    total_deleted = 0

    # 1. Supprimer les Likes
    likes_qs = Like.objects.filter(
        (Q(from_user=marie) & Q(to_user=max_weber)) |
        (Q(from_user=max_weber) & Q(to_user=marie))
    )
    count = likes_qs.count()
    if count:
        likes_qs.delete()
        print(f"[OK] {count} Like(s) deleted")
        total_deleted += count
    else:
        print("[--] No Likes found")

    # 2. Supprimer les Dislikes
    dislikes_qs = Dislike.objects.filter(
        (Q(from_user=marie) & Q(to_user=max_weber)) |
        (Q(from_user=max_weber) & Q(to_user=marie))
    )
    count = dislikes_qs.count()
    if count:
        dislikes_qs.delete()
        print(f"[OK] {count} Dislike(s) deleted")
        total_deleted += count
    else:
        print("[--] No Dislikes found")

    # 3. Trouver et supprimer le Match (et ses dependants)
    match = Match.objects.filter(
        (Q(user1=marie) & Q(user2=max_weber)) |
        (Q(user1=max_weber) & Q(user2=marie))
    ).first()

    if match:
        # 3a. Supprimer les messages du match
        msg_count = Message.objects.filter(match=match).count()
        if msg_count:
            Message.objects.filter(match=match).delete()
            print(f"[OK] {msg_count} Message(s) deleted")
            total_deleted += msg_count

        # 3b. Supprimer les appels du match
        call_count = Call.objects.filter(match=match).count()
        if call_count:
            Call.objects.filter(match=match).delete()
            print(f"[OK] {call_count} Call(s) deleted")
            total_deleted += call_count

        # 3c. Supprimer les indicateurs de frappe du match
        typing_count = TypingIndicator.objects.filter(match=match).count()
        if typing_count:
            TypingIndicator.objects.filter(match=match).delete()
            print(f"[OK] {typing_count} TypingIndicator(s) deleted")
            total_deleted += typing_count

        # 3d. Supprimer le match lui-meme
        match.delete()
        print(f"[OK] Match deleted (ID: {match.id})")
        total_deleted += 1
    else:
        print("[--] No Match found")

    # 4. Supprimer l'historique d'interactions
    history_qs = InteractionHistory.objects.filter(
        (Q(user=marie) & Q(target_user=max_weber)) |
        (Q(user=max_weber) & Q(target_user=marie))
    )
    count = history_qs.count()
    if count:
        history_qs.delete()
        print(f"[OK] {count} InteractionHistory deleted")
        total_deleted += count
    else:
        print("[--] No InteractionHistory found")

    # 5. Supprimer les ProfileView entre eux
    views_qs = ProfileView.objects.filter(
        (Q(viewer=marie) & Q(viewed=max_weber)) |
        (Q(viewer=max_weber) & Q(viewed=marie))
    )
    count = views_qs.count()
    if count:
        views_qs.delete()
        print(f"[OK] {count} ProfileView(s) deleted")
        total_deleted += count
    else:
        print("[--] No ProfileView found")

    # 6. Reinitialiser les compteurs daily_like_limits du jour
    today = timezone.now().date()
    for user in [marie, max_weber]:
        limit, created = DailyLikeLimit.objects.get_or_create(
            user=user,
            date=today,
            defaults={'likes_count': 0, 'super_likes_count': 0, 'rewinds_count': 0}
        )
        if not created and (limit.likes_count > 0 or limit.super_likes_count > 0):
            limit.likes_count = 0
            limit.super_likes_count = 0
            limit.save(update_fields=['likes_count', 'super_likes_count'])
            print(f"[OK] DailyLikeLimit reset for {user.display_name}")
            total_deleted += 1

    print(f"\n[STATS] Total: {total_deleted} entries deleted/reset")
    print("[DONE] Cleanup completed successfully!")
    print("\nYou can now restart the matching/messaging tests from scratch.")


if __name__ == '__main__':
    marie, max_weber = find_users()

    if marie and max_weber:
        cleanup(marie, max_weber)
    else:
        print("\n[ERROR] Could not find both users. Check the names.")
        print("   If names are different, modify the find_users() function.")