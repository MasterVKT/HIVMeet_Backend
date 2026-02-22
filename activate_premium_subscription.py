#!/usr/bin/env python
"""
Script pour activer une souscription premium pour un utilisateur de test.
Résout l'erreur 400 "no_active_subscription" lors de l'utilisation du Super Like.
"""
import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from subscriptions.models import Subscription, SubscriptionPlan
from profiles.models import Profile
import uuid

User = get_user_model()


def find_test_user():
    """Identifier l'utilisateur de test utilisé récemment."""
    print("\n" + "="*80)
    print("IDENTIFICATION DE L'UTILISATEUR DE TEST")
    print("="*80)
    
    # Chercher les utilisateurs premium sans souscription active
    users_premium_no_sub = User.objects.filter(
        is_premium=True
    ).exclude(
        subscription__isnull=False
    )
    
    print(f"\nUtilisateurs premium SANS souscription active: {users_premium_no_sub.count()}")
    
    for user in users_premium_no_sub:
        print(f"\n   Email: {user.email}")
        print(f"   Display name: {user.display_name}")
        print(f"   is_premium: {user.is_premium}")
        print(f"   is_verified: {user.is_verified}")
        print(f"   Dernière activité: {user.last_active if hasattr(user, 'last_active') else 'N/A'}")
    
    # Chercher aussi les utilisateurs de test récents
    test_emails = [
        'marie@test.com', 'julie@test.com', 'pierre@test.com',
        'marie_integration@test.com', 'test@test.com', 'user@test.com'
    ]
    
    print(f"\n\nUtilisateurs de test connus:")
    test_users = []
    for email in test_emails:
        try:
            user = User.objects.get(email=email)
            test_users.append(user)
            has_sub = hasattr(user, 'subscription') and user.subscription is not None
            print(f"\n   Email: {user.email}")
            print(f"   is_premium: {user.is_premium}")
            print(f"   is_verified: {user.is_verified}")
            print(f"   A une souscription: {has_sub}")
            if has_sub:
                print(f"      Status: {user.subscription.status}")
                print(f"      Plan: {user.subscription.plan.name}")
        except User.DoesNotExist:
            pass
    
    return users_premium_no_sub, test_users


def create_or_update_subscription_plan():
    """Créer ou récupérer un plan de souscription premium."""
    print("\n" + "="*80)
    print("VERIFICATION DU PLAN PREMIUM")
    print("="*80)
    
    # Chercher un plan premium existant
    premium_plan = SubscriptionPlan.objects.filter(
        is_active=True
    ).first()
    
    if premium_plan:
        print(f"\nPlan premium trouve: {premium_plan.name}")
        print(f"   Prix: {premium_plan.price} {premium_plan.currency}")
        print(f"   Intervalle: {premium_plan.billing_interval}")
        print(f"   Super likes quotidiens: {premium_plan.daily_super_likes_count}")
        print(f"   Boosts mensuels: {premium_plan.monthly_boosts_count}")
    else:
        print("\nAucun plan premium trouvé. Création d'un plan de test...")
        premium_plan = SubscriptionPlan.objects.create(
            plan_id=f'premium_monthly_{uuid.uuid4().hex[:8]}',
            name='Premium Monthly (Test)',
            name_en='Premium Monthly (Test)',
            name_fr='Premium Mensuel (Test)',
            description='Plan premium mensuel pour tests',
            description_en='Monthly premium plan for testing',
            description_fr='Plan premium mensuel pour tests',
            price=9.99,
            currency='USD',
            billing_interval='month',
            is_active=True,
            # Fonctionnalités premium
            unlimited_likes=True,
            can_see_likers=True,
            can_rewind=True,
            daily_super_likes_count=5,
            monthly_boosts_count=1,
            media_messaging_enabled=True,
            audio_video_calls_enabled=True
        )
        print(f"Plan créé: {premium_plan.name}")
    
    return premium_plan


def activate_subscription_for_user(user, plan):
    """Créer ou activer une souscription pour l'utilisateur."""
    print("\n" + "="*80)
    print(f"ACTIVATION SOUSCRIPTION POUR {user.email}")
    print("="*80)
    
    # Vérifier si une souscription existe déjà
    try:
        subscription = user.subscription
        print(f"\nSouscription existante trouvée:")
        print(f"   Status actuel: {subscription.status}")
        print(f"   Plan: {subscription.plan.name}")
        print(f"   Periode: {subscription.current_period_start} -> {subscription.current_period_end}")
        
        # Mettre à jour la souscription
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.plan = plan
        subscription.current_period_start = timezone.now()
        # Calculer la fin de période selon l'intervalle
        if plan.billing_interval == 'month':
            subscription.current_period_end = timezone.now() + timedelta(days=30)
        else:
            subscription.current_period_end = timezone.now() + timedelta(days=365)
        subscription.auto_renew = True
        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        
        # Réinitialiser les compteurs
        subscription.super_likes_remaining = plan.daily_super_likes_count * 30  # Pour le mois
        subscription.boosts_remaining = plan.monthly_boosts_count
        subscription.last_super_likes_reset = timezone.now()
        subscription.last_boosts_reset = timezone.now()
        
        subscription.save()
        
        print(f"\nOK Souscription mise a jour:")
        print(f"   Status: {subscription.status}")
        print(f"   Super likes restants: {subscription.super_likes_remaining}")
        print(f"   Boosts restants: {subscription.boosts_remaining}")
        
    except Subscription.DoesNotExist:
        print(f"\nAucune souscription existante. Création...")
        
        subscription = Subscription.objects.create(
            subscription_id=f'sub_{user.id}_{uuid.uuid4().hex[:8]}',
            user=user,
            plan=plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30 if plan.billing_interval == 'month' else 365),
            auto_renew=True,
            cancel_at_period_end=False,
            # Compteurs
            super_likes_remaining=plan.daily_super_likes_count * 30,
            boosts_remaining=plan.monthly_boosts_count,
            last_super_likes_reset=timezone.now(),
            last_boosts_reset=timezone.now()
        )
        
        print(f"\nOK Souscription creee:")
        print(f"   ID: {subscription.subscription_id}")
        print(f"   Status: {subscription.status}")
        print(f"   Super likes: {subscription.super_likes_remaining}/{plan.daily_super_likes_count * 30}")
        print(f"   Boosts: {subscription.boosts_remaining}/{plan.monthly_boosts_count}")
    
    # Vérifier et mettre à jour le flag is_premium de l'utilisateur
    if not user.is_premium:
        user.is_premium = True
        user.save()
        print(f"\nOK Flag is_premium active pour {user.email}")
    
    return subscription


def verify_premium_features(user):
    """Vérifier que toutes les fonctionnalités premium sont accessibles."""
    print("\n" + "="*80)
    print(f"VERIFICATION DES FONCTIONNALITES PREMIUM")
    print("="*80)
    
    from subscriptions.utils import check_feature_availability, get_user_subscription
    
    subscription = get_user_subscription(user)
    
    if not subscription:
        print("\nERREUR: Aucune souscription trouvee!")
        return False
    
    print(f"\nSouscription active: {subscription.subscription_id}")
    print(f"Status: {subscription.status}")
    print(f"Plan: {subscription.plan.name}")
    
    # Vérifier chaque fonctionnalité
    features = [
        'unlimited_likes',
        'see_likers',
        'rewind',
        'boost',
        'super_like',
        'media_messaging',
        'calls'
    ]
    
    print(f"\nVérification des fonctionnalités:")
    all_ok = True
    for feature in features:
        result = check_feature_availability(user, feature)
        status = "[OK]" if result['available'] else "[--]"
        reason = result.get('reason', 'N/A')
        print(f"   {status} {feature}: {result['available']} ({reason})")
        if not result['available'] and feature in ['super_like', 'boost']:
            all_ok = False
    
    return all_ok


def main():
    """Fonction principale."""
    print("\nACTIVATION SOUSCRIPTION PREMIUM POUR TESTS")
    print("="*80)
    
    # 1. Identifier les utilisateurs de test
    users_no_sub, test_users = find_test_user()
    
    # 2. Demander quel utilisateur activer
    print("\n" + "="*80)
    print("SELECTION DE L'UTILISATEUR")
    print("="*80)
    
    all_users = list(users_no_sub) + [u for u in test_users if u not in users_no_sub]
    
    if not all_users:
        print("\nAucun utilisateur de test trouve!")
        print("\nCreation d'un utilisateur de test par defaut...")
        
        user, created = User.objects.get_or_create(
            email='test_premium@test.com',
            defaults={
                'display_name': 'Test Premium User',
                'birth_date': timezone.now().date().replace(year=timezone.now().year - 30),
                'is_active': True,
                'email_verified': True,
                'is_premium': True,
                'is_verified': True
            }
        )
        
        if created:
            print(f"OK Utilisateur cree: {user.email}")
            # Créer un profil
            Profile.objects.get_or_create(
                user=user,
                defaults={
                    'gender': 'male',
                    'genders_sought': ['female'],
                    'is_hidden': False,
                    'allow_profile_in_discovery': True
                }
            )
        all_users = [user]
    
    print(f"\nUtilisateurs disponibles:")
    for i, user in enumerate(all_users, 1):
        has_sub = hasattr(user, 'subscription') and user.subscription is not None
        print(f"   {i}. {user.email} (premium: {user.is_premium}, subscription: {has_sub})")
    
    # Activer pour TOUS les utilisateurs premium sans souscription
    print(f"\n>> Activation pour tous les utilisateurs premium sans souscription...")
    
    # 3. Créer/récupérer le plan premium
    plan = create_or_update_subscription_plan()
    
    # 4. Activer la souscription pour chaque utilisateur
    results = []
    for user in all_users:
        try:
            subscription = activate_subscription_for_user(user, plan)
            is_ok = verify_premium_features(user)
            results.append((user, subscription, is_ok))
        except Exception as e:
            print(f"\nERREUR pour {user.email}: {e}")
            import traceback
            traceback.print_exc()
            results.append((user, None, False))
    
    # 5. Résumé
    print("\n" + "="*80)
    print("RESUME")
    print("="*80)
    
    for user, subscription, is_ok in results:
        status = "[OK]" if is_ok else "[ERREUR]"
        print(f"\n{status} {user.email}")
        if subscription:
            print(f"   Souscription: {subscription.subscription_id}")
            print(f"   Status: {subscription.status}")
            print(f"   Super likes: {subscription.super_likes_remaining}")
            print(f"   Boosts: {subscription.boosts_remaining}")
    
    print("\n" + "="*80)
    if all(is_ok for _, _, is_ok in results):
        print("SUCCESS - TOUS LES UTILISATEURS SONT PRETS POUR LES TESTS PREMIUM")
    else:
        print("ATTENTION - CERTAINS UTILISATEURS ONT DES PROBLEMES")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
