"""
Script to clean test account data from the database.

This script removes all interactions, matches, and related data for a specific test user
to allow starting fresh tests without legacy data contamination.

Usage:
    python clean_test_account_data.py [--user-id USER_ID] [--dry-run]

Example:
    python clean_test_account_data.py --user-id 0e5ac2cb-07d8-4160-9f36-90393356f8c0 --dry-run
"""

import os
import sys
import argparse
import logging

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from matching.models import InteractionHistory, Match, Like, Dislike, ProfileView, Boost

logger = logging.getLogger('hivmeet.matching')
User = get_user_model()


def clean_test_account_data(user_id: str, dry_run: bool = False) -> dict:
    """
    Clean all interaction data for a test user.
    
    Args:
        user_id: The UUID of the test user
        dry_run: If True, only print what would be deleted
        
    Returns:
        dict: Statistics of what was deleted
    """
    logger.info(f"🔍 {'[DRY RUN] ' if dry_run else ''}Cleaning test account data for user: {user_id}")
    
    try:
        test_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"❌ User {user_id} not found")
        return {'error': 'User not found'}
    
    stats = {
        'user_id': str(test_user.id),
        'user_email': test_user.email,
        'interactions_sent_deleted': 0,
        'interactions_received_deleted': 0,
        'matches_deleted': 0,
        'likes_sent_deleted': 0,
        'likes_received_deleted': 0,
        'dislikes_deleted': 0,
        'profile_views_sent_deleted': 0,
        'profile_views_received_deleted': 0,
        'boosts_deleted': 0,
    }
    
    if dry_run:
        logger.info(f"📋 DRY RUN - Would delete the following data for {test_user.email}:")
    else:
        logger.info(f"🗑️  Deleting data for {test_user.email}:")
    
    with transaction.atomic():
        # 1. Count and delete interactions SENT by this user
        interactions_sent = InteractionHistory.objects.filter(user=test_user)
        stats['interactions_sent_deleted'] = interactions_sent.count()
        if dry_run:
            logger.info(f"   - Interactions sent: {stats['interactions_sent_deleted']}")
        else:
            interactions_sent.delete()
            logger.info(f"   ✅ Deleted {stats['interactions_sent_deleted']} interactions sent")
        
        # 2. Count and delete interactions RECEIVED by this user
        interactions_received = InteractionHistory.objects.filter(target_user=test_user)
        stats['interactions_received_deleted'] = interactions_received.count()
        if dry_run:
            logger.info(f"   - Interactions received: {stats['interactions_received_deleted']}")
        else:
            interactions_received.delete()
            logger.info(f"   ✅ Deleted {stats['interactions_received_deleted']} interactions received")
        
        # 3. Count and delete matches involving this user
        matches = Match.objects.filter(user1=test_user) | Match.objects.filter(user2=test_user)
        stats['matches_deleted'] = matches.count()
        if dry_run:
            logger.info(f"   - Matches: {stats['matches_deleted']}")
        else:
            matches.delete()
            logger.info(f"   ✅ Deleted {stats['matches_deleted']} matches")
        
        # 4. Count and delete likes sent by this user
        likes_sent = Like.objects.filter(from_user=test_user)
        stats['likes_sent_deleted'] = likes_sent.count()
        if dry_run:
            logger.info(f"   - Likes sent: {stats['likes_sent_deleted']}")
        else:
            likes_sent.delete()
            logger.info(f"   ✅ Deleted {stats['likes_sent_deleted']} likes sent")
        
        # 5. Count and delete likes received by this user
        likes_received = Like.objects.filter(to_user=test_user)
        stats['likes_received_deleted'] = likes_received.count()
        if dry_run:
            logger.info(f"   - Likes received: {stats['likes_received_deleted']}")
        else:
            likes_received.delete()
            logger.info(f"   ✅ Deleted {stats['likes_received_deleted']} likes received")
        
        # 6. Count and delete dislikes involving this user
        dislikes = Dislike.objects.filter(from_user=test_user) | Dislike.objects.filter(to_user=test_user)
        stats['dislikes_deleted'] = dislikes.count()
        if dry_run:
            logger.info(f"   - Dislikes: {stats['dislikes_deleted']}")
        else:
            dislikes.delete()
            logger.info(f"   ✅ Deleted {stats['dislikes_deleted']} dislikes")
        
        # 7. Count and delete profile views sent by this user
        views_sent = ProfileView.objects.filter(viewer=test_user)
        stats['profile_views_sent_deleted'] = views_sent.count()
        if dry_run:
            logger.info(f"   - Profile views sent: {stats['profile_views_sent_deleted']}")
        else:
            views_sent.delete()
            logger.info(f"   ✅ Deleted {stats['profile_views_sent_deleted']} profile views sent")
        
        # 8. Count and delete profile views received by this user
        views_received = ProfileView.objects.filter(viewed=test_user)
        stats['profile_views_received_deleted'] = views_received.count()
        if dry_run:
            logger.info(f"   - Profile views received: {stats['profile_views_received_deleted']}")
        else:
            views_received.delete()
            logger.info(f"   ✅ Deleted {stats['profile_views_received_deleted']} profile views received")
        
        # 9. Count and delete boosts for this user
        boosts = Boost.objects.filter(user=test_user)
        stats['boosts_deleted'] = boosts.count()
        if dry_run:
            logger.info(f"   - Boosts: {stats['boosts_deleted']}")
        else:
            boosts.delete()
            logger.info(f"   ✅ Deleted {stats['boosts_deleted']} boosts")
    
    if dry_run:
        logger.info(f"📋 DRY RUN COMPLETE - No data was actually deleted")
    else:
        logger.info(f"✅ All data cleaned for user {test_user.email}")
    
    return stats


def verify_cleaned_data(user_id: str) -> dict:
    """
    Verify that all data has been cleaned for a user.
    
    Args:
        user_id: The UUID of the test user
        
    Returns:
        dict: Verification results
    """
    logger.info(f"🔍 Verifying cleaned data for user: {user_id}")
    
    try:
        test_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {'error': 'User not found', 'clean': False}
    
    verification = {
        'user_id': str(test_user.id),
        'user_email': test_user.email,
        'clean': True,
        'remaining_data': {}
    }
    
    # Check remaining data
    remaining_interactions_sent = InteractionHistory.objects.filter(user=test_user).count()
    remaining_interactions_received = InteractionHistory.objects.filter(target_user=test_user).count()
    remaining_matches = (Match.objects.filter(user1=test_user) | Match.objects.filter(user2=test_user)).count()
    remaining_likes_sent = Like.objects.filter(from_user=test_user).count()
    remaining_likes_received = Like.objects.filter(to_user=test_user).count()
    remaining_dislikes = (Dislike.objects.filter(from_user=test_user) | Dislike.objects.filter(to_user=test_user)).count()
    
    verification['remaining_data']['interactions_sent'] = remaining_interactions_sent
    verification['remaining_data']['interactions_received'] = remaining_interactions_received
    verification['remaining_data']['matches'] = remaining_matches
    verification['remaining_data']['likes_sent'] = remaining_likes_sent
    verification['remaining_data']['likes_received'] = remaining_likes_received
    verification['remaining_data']['dislikes'] = remaining_dislikes
    
    # Check if data is clean
    total_remaining = (
        remaining_interactions_sent + 
        remaining_interactions_received + 
        remaining_matches + 
        remaining_likes_sent + 
        remaining_likes_received + 
        remaining_dislikes
    )
    
    if total_remaining > 0:
        verification['clean'] = False
        logger.warning(f"⚠️  Found {total_remaining} remaining records for user {test_user.email}")
    else:
        logger.info(f"✅ User {test_user.email} has no remaining interaction data")
    
    return verification


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Clean test account data')
    parser.add_argument('--user-id', type=str, default='0e5ac2cb-07d8-4160-9f36-90393356f8c0',
                        help='UUID of the test user to clean')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deleted without actually deleting')
    parser.add_argument('--verify', action='store_true',
                        help='Verify that data has been cleaned')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if args.verify:
        # Verify cleaned data
        result = verify_cleaned_data(args.user_id)
        print(f"\n{'='*60}")
        print(f"VERIFICATION RESULTS")
        print(f"{'='*60}")
        print(f"User: {result.get('user_email', 'N/A')}")
        print(f"User ID: {result.get('user_id', 'N/A')}")
        print(f"Clean: {'✅ YES' if result.get('clean') else '❌ NO'}")
        print(f"\nRemaining data:")
        for key, value in result.get('remaining_data', {}).items():
            print(f"  - {key}: {value}")
        print(f"{'='*60}\n")
    else:
        # Clean data
        result = clean_test_account_data(args.user_id, dry_run=args.dry_run)
        print(f"\n{'='*60}")
        print(f"CLEANUP RESULTS {'(DRY RUN)' if args.dry_run else ''}")
        print(f"{'='*60}")
        print(f"User: {result.get('user_email', 'N/A')}")
        print(f"User ID: {result.get('user_id', 'N/A')}")
        
        if 'error' in result:
            print(f"Error: {result['error']}")
        else:
            print(f"\nDeleted:")
            print(f"  - Interactions sent: {result.get('interactions_sent_deleted', 0)}")
            print(f"  - Interactions received: {result.get('interactions_received_deleted', 0)}")
            print(f"  - Matches: {result.get('matches_deleted', 0)}")
            print(f"  - Likes sent: {result.get('likes_sent_deleted', 0)}")
            print(f"  - Likes received: {result.get('likes_received_deleted', 0)}")
            print(f"  - Dislikes: {result.get('dislikes_deleted', 0)}")
            print(f"  - Profile views sent: {result.get('profile_views_sent_deleted', 0)}")
            print(f"  - Profile views received: {result.get('profile_views_received_deleted', 0)}")
            print(f"  - Boosts: {result.get('boosts_deleted', 0)}")
        print(f"{'='*60}\n")
        
        # Verify after cleanup (if not dry run)
        if not args.dry_run and 'error' not in result:
            verification = verify_cleaned_data(args.user_id)
            if not verification.get('clean'):
                print("⚠️  WARNING: Some data may not have been cleaned properly")
                for key, value in verification.get('remaining_data', {}).items():
                    if value > 0:
                        print(f"  - {key}: {value}")


if __name__ == '__main__':
    main()
