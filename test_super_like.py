#!/usr/bin/env python
"""
Test rapide de la fonctionnalité Super Like pour un utilisateur premium.
"""
import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from subscriptions.utils import check_feature_availability, consume_premium_feature

User = get_user_model()


def test_super_like():
    """Tester la fonctionnalité Super Like."""
    print("\n" + "="*80)
    print("TEST SUPER LIKE")
    print("="*80)
    
    # Prendre un utilisateur premium
    user = User.objects.filter(is_premium=True, subscription__isnull=False).first()
    
    if not user:
        print("\nAucun utilisateur premium avec souscription trouve!")
        return False
    
    print(f"\nUtilisateur: {user.email}")
    print(f"is_premium: {user.is_premium}")
    
    # Vérifier disponibilité
    availability = check_feature_availability(user, 'super_like')
    print(f"\nSuper Like disponible: {availability['available']}")
    print(f"Raison: {availability['reason']}")
    
    if not availability['available']:
        print("\nERREUR: Super Like devrait être disponible!")
        return False
    
    # Consommer un Super Like
    result = consume_premium_feature(user, 'super_like')
    print(f"\nConsommation Super Like:")
    print(f"   Success: {result['success']}")
    print(f"   Remaining: {result['remaining']}")
    print(f"   Error: {result.get('error', 'None')}")
    
    if not result['success']:
        print(f"\nERREUR lors de la consommation: {result.get('error')}")
        return False
    
    # Recharger et vérifier
    user.refresh_from_db()
    subscription = user.subscription
    print(f"\nApres consommation:")
    print(f"   Super likes restants: {subscription.super_likes_remaining}")
    
    return result['success']


if __name__ == '__main__':
    success = test_super_like()
    print("\n" + "="*80)
    if success:
        print("SUCCESS - Le Super Like fonctionne correctement!")
    else:
        print("ERREUR - Probleme avec le Super Like")
    print("="*80 + "\n")
    sys.exit(0 if success else 1)
