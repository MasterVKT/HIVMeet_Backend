#!/usr/bin/env python
"""
Script de test pour l'intégration MyCoolPay.
"""
import os
import sys
import django
import traceback
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

def test_mycoolpay_settings():
    """Test des paramètres MyCoolPay."""
    print("💳 TEST CONFIGURATION MYCOOLPAY")
    print("-" * 35)
    
    try:
        from django.conf import settings
        
        # Vérifier les variables d'environnement
        api_key = getattr(settings, 'MYCOOLPAY_API_KEY', '')
        api_secret = getattr(settings, 'MYCOOLPAY_API_SECRET', '')
        base_url = getattr(settings, 'MYCOOLPAY_BASE_URL', '')
        webhook_secret = getattr(settings, 'MYCOOLPAY_WEBHOOK_SECRET', '')
        
        print(f"✅ API Key: {'***' + api_key[-4:] if api_key else 'NON CONFIGURÉ'}")
        print(f"✅ API Secret: {'***' + api_secret[-4:] if api_secret else 'NON CONFIGURÉ'}")
        print(f"✅ Base URL: {base_url or 'NON CONFIGURÉ'}")
        print(f"✅ Webhook Secret: {'***' + webhook_secret[-4:] if webhook_secret else 'NON CONFIGURÉ'}")
        
        if not all([api_key, api_secret, base_url, webhook_secret]):
            print("⚠️ Certains paramètres MyCoolPay ne sont pas configurés")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Test configuration MyCoolPay failed: {e}")
        traceback.print_exc()
        return False

def test_subscription_models():
    """Test des modèles d'abonnement."""
    print("\n📋 TEST MODÈLES ABONNEMENT")
    print("-" * 30)
    
    try:
        django.setup()
        
        from subscriptions.models import SubscriptionPlan, Subscription, Transaction
        from subscriptions.services import MyCoolPayService, SubscriptionService
        
        print("✅ SubscriptionPlan model imported")
        print("✅ Subscription model imported")
        print("✅ Transaction model imported")
        print("✅ MyCoolPayService imported")
        print("✅ SubscriptionService imported")
        
        # Vérifier les méthodes principales
        mycoolpay_service = MyCoolPayService()
        if hasattr(mycoolpay_service, 'create_subscription'):
            print("✅ MyCoolPayService.create_subscription method exists")
        else:
            print("❌ MyCoolPayService.create_subscription method missing")
            return False
            
        if hasattr(mycoolpay_service, 'handle_webhook'):
            print("✅ MyCoolPayService.handle_webhook method exists")
        else:
            print("❌ MyCoolPayService.handle_webhook method missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Test modèles abonnement failed: {e}")
        traceback.print_exc()
        return False

def test_subscription_plans():
    """Test de création de plans d'abonnement."""
    print("\n💎 TEST PLANS ABONNEMENT")
    print("-" * 25)
    
    try:
        from subscriptions.models import SubscriptionPlan
        
        # Vérifier les plans existants
        plans_count = SubscriptionPlan.objects.count()
        print(f"✅ Plans existants: {plans_count}")
        
        if plans_count == 0:
            print("⚠️ Aucun plan d'abonnement configuré")
            
            # Créer un plan de test
            test_plan = SubscriptionPlan.objects.create(
                plan_id='hivmeet_monthly_test',
                name='HIVMeet Premium Test',
                name_en='HIVMeet Premium Test',
                name_fr='HIVMeet Premium Test',
                description='Plan de test premium',
                description_en='Premium test plan',
                description_fr='Plan de test premium',
                price=9.99,
                currency='EUR',
                billing_interval='month',
                unlimited_likes=True,
                can_see_likers=True,
                can_rewind=True,
                monthly_boosts_count=1,
                daily_super_likes_count=5,
                media_messaging_enabled=True,
                audio_video_calls_enabled=True,
                is_active=True
            )
            
            print(f"✅ Plan de test créé: {test_plan.name}")
        else:
            for plan in SubscriptionPlan.objects.all()[:3]:
                print(f"✅ Plan: {plan.name} - {plan.price} {plan.currency}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test plans abonnement failed: {e}")
        traceback.print_exc()
        return False

def test_premium_features():
    """Test des fonctionnalités premium."""
    print("\n🌟 TEST FONCTIONNALITÉS PREMIUM")
    print("-" * 35)
    
    try:
        from authentication.models import User
        from subscriptions.services import PremiumFeatureService
        
        # Créer un utilisateur de test
        test_user = User(
            email='premium_test@example.com',
            display_name='Premium Test User',
            birth_date='1990-01-01',
            is_premium=True
        )
        
        # Test des propriétés premium
        if hasattr(test_user, 'premium_features'):
            features = test_user.premium_features
            print(f"✅ Premium features: {features}")
        else:
            print("❌ User.premium_features property missing")
            return False
            
        if hasattr(test_user, 'can_send_super_like'):
            can_super_like = test_user.can_send_super_like
            print(f"✅ Can send super like: {can_super_like}")
        else:
            print("❌ User.can_send_super_like property missing")
            return False
            
        if hasattr(test_user, 'can_use_boost'):
            can_boost = test_user.can_use_boost
            print(f"✅ Can use boost: {can_boost}")
        else:
            print("❌ User.can_use_boost property missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Test fonctionnalités premium failed: {e}")
        traceback.print_exc()
        return False

def test_webhook_handler():
    """Test du gestionnaire de webhooks."""
    print("\n🪝 TEST GESTIONNAIRE WEBHOOKS")
    print("-" * 35)
    
    try:
        from subscriptions.views import WebhookView
        from subscriptions.services import MyCoolPayService
        
        print("✅ WebhookView imported")
        
        # Test de la structure du webhook
        webhook_view = WebhookView()
        if hasattr(webhook_view, 'post'):
            print("✅ WebhookView.post method exists")
        else:
            print("❌ WebhookView.post method missing")
            return False
            
        # Test du service MyCoolPay
        service = MyCoolPayService()
        if hasattr(service, 'verify_webhook_signature'):
            print("✅ MyCoolPayService.verify_webhook_signature exists")
        else:
            print("❌ MyCoolPayService.verify_webhook_signature missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Test webhook handler failed: {e}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("💳 TEST INTÉGRATION MYCOOLPAY")
    print("=" * 40)
    
    # Tests
    config_ok = test_mycoolpay_settings()
    models_ok = test_subscription_models()
    plans_ok = test_subscription_plans()
    features_ok = test_premium_features()
    webhook_ok = test_webhook_handler()
    
    # Résultats
    print("\n" + "=" * 40)
    print("📊 RÉSULTATS MYCOOLPAY:")
    print(f"⚙️ Configuration: {'✅ OK' if config_ok else '❌ ERREUR'}")
    print(f"📋 Modèles: {'✅ OK' if models_ok else '❌ ERREUR'}")
    print(f"💎 Plans: {'✅ OK' if plans_ok else '❌ ERREUR'}")
    print(f"🌟 Fonctionnalités: {'✅ OK' if features_ok else '❌ ERREUR'}")
    print(f"🪝 Webhooks: {'✅ OK' if webhook_ok else '❌ ERREUR'}")
    
    overall = config_ok and models_ok and plans_ok and features_ok and webhook_ok
    print(f"\n🎯 GLOBAL: {'✅ SUCCÈS' if overall else '❌ ÉCHEC'}")
    
    print(f"\n⏰ Tests complétés à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}") 