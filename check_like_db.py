"""Check if the like interaction was created in the database."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.db import connection
from matching.models import InteractionHistory, Like
from authentication.models import User

# Check recent interactions
print("=== Recent InteractionHistory records ===")
for ih in InteractionHistory.objects.order_by('-created_at')[:5]:
    print(f"  ID: {ih.id}, User: {ih.user_id}, Target: {ih.target_user_id}, "
          f"Type: {ih.interaction_type}, Created: {ih.created_at}")

# Check ALICE's likes
alice = User.objects.get(email='alice.hivmeet@test.local')
print(f"\n=== ALICE's likes (sent) ===")
for like in Like.objects.filter(from_user=alice).order_by('-created_at')[:5]:
    print(f"  ID: {like.id}, To: {like.to_user.email}, Created: {like.created_at}")

# Check if BOB has been liked by ALICE
bob = User.objects.get(email='bob.hivmeet@test.local')
liked = Like.objects.filter(from_user=alice, to_user=bob).exists()
print(f"\n=== ALICE liked BOB? {liked} ===")

# Check interaction history for ALICE → BOB
interactions = InteractionHistory.objects.filter(user=alice, target_user=bob)
print(f"=== InteractionHistory ALICE→BOB: {interactions.count()} records ===")
for ih in interactions:
    print(f"  Type: {ih.interaction_type}, Created: {ih.created_at}")

# Check ALICE's daily likes count
from matching.models import DailyLikeLimit
try:
    limit = DailyLikeLimit.objects.get(user=alice)
    print(f"\n=== DailyLikeLimit for ALICE ===")
    print(f"  Date: {limit.date}, Likes used: {limit.likes_count}, "
          f"Super likes used: {limit.super_likes_count}")
except DailyLikeLimit.DoesNotExist:
    print("\nNo DailyLikeLimit record for ALICE yet")