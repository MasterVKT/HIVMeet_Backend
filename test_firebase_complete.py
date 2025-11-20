#!/usr/bin/env python
"""
Script de test complet pour l'intégration Firebase HIVMeet.
"""
import os
import sys
import django
import traceback
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

def main():
    print("🔥 TEST INTÉGRATION FIREBASE HIVMEET")
    print("=" * 50)
    
    # Setup Django
    try:
        django.setup()
        print("✅ Django setup successful")
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        traceback.print_exc()
        return False
    
    # Test Firebase service import
    try:
        from hivmeet_backend.firebase_service import firebase_service
        print("✅ Firebase service imported successfully")
    except Exception as e:
        print(f"❌ Firebase service import failed: {e}")
        traceback.print_exc()
        return False
    
    # Test Firebase credentials
    try:
        from django.conf import settings
        import os
        
        creds_path = settings.FIREBASE_CREDENTIALS_PATH
        print(f"📁 Credentials path: {creds_path}")
        
        if os.path.exists(creds_path):
            print("✅ Credentials file exists")
        else:
            print("❌ Credentials file not found")
            return False
            
    except Exception as e:
        print(f"❌ Credentials check failed: {e}")
        traceback.print_exc()
        return False
    
    # Test Firebase initialization
    try:
        # This will trigger the initialization
        auth_service = firebase_service.auth
        db_service = firebase_service.db
        bucket_service = firebase_service.bucket
        
        print("✅ Firebase Auth service initialized")
        print("✅ Firebase Firestore service initialized")
        print("✅ Firebase Storage service initialized")
        
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        traceback.print_exc()
        return False
    
    # Test Firebase Auth operations (without actually creating users)
    try:
        # Test token verification (will fail with invalid token, but service should work)
        try:
            firebase_service.verify_id_token("invalid_token")
        except ValueError as expected:
            print("✅ Token verification service working (expected ValueError)")
        except Exception as e:
            print(f"❌ Unexpected error in token verification: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Firebase Auth test failed: {e}")
        traceback.print_exc()
        return False
    
    # Test Firestore connection
    try:
        # Test simple Firestore operation
        test_collection = db_service.collection('test')
        print("✅ Firestore collection access working")
        
    except Exception as e:
        print(f"❌ Firestore test failed: {e}")
        traceback.print_exc()
        return False
    
    # Test Storage bucket access
    try:
        bucket_name = bucket_service.name
        print(f"✅ Storage bucket access working: {bucket_name}")
        
    except Exception as e:
        print(f"❌ Storage bucket test failed: {e}")
        traceback.print_exc()
        return False
    
    # Test User model with Firebase integration
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check if User model has Firebase fields
        if hasattr(User, 'firebase_uid'):
            print("✅ User model has firebase_uid field")
        else:
            print("❌ User model missing firebase_uid field")
            return False
            
    except Exception as e:
        print(f"❌ User model test failed: {e}")
        traceback.print_exc()
        return False
    
    print("\n🎉 TOUS LES TESTS FIREBASE RÉUSSIS!")
    print(f"⏰ Tests complétés à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return True

def test_firebase_auth_flow():
    """Test complet du flux d'authentification Firebase."""
    print("\n🔐 TEST FLUX AUTHENTIFICATION FIREBASE")
    print("-" * 40)
    
    try:
        from authentication.views import register_view
        from authentication.serializers import UserRegistrationSerializer
        print("✅ Authentication views and serializers imported")
        
        # Test serializer validation
        test_data = {
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'display_name': 'Test User',
            'birth_date': '1990-01-01'
        }
        
        serializer = UserRegistrationSerializer(data=test_data)
        if serializer.is_valid():
            print("✅ User registration serializer validation working")
        else:
            print(f"❌ Serializer validation failed: {serializer.errors}")
            return False
            
    except Exception as e:
        print(f"❌ Authentication flow test failed: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_firebase_middleware():
    """Test du middleware Firebase."""
    print("\n🔧 TEST MIDDLEWARE FIREBASE")
    print("-" * 30)
    
    try:
        from authentication.middleware import FirebaseAuthenticationMiddleware
        print("✅ Firebase middleware imported successfully")
        
        # Test middleware class exists and has required methods
        middleware = FirebaseAuthenticationMiddleware(lambda x: x)
        if hasattr(middleware, '__call__') and hasattr(middleware, '_get_user'):
            print("✅ Firebase middleware structure correct")
        else:
            print("❌ Firebase middleware missing required methods")
            return False
            
    except Exception as e:
        print(f"❌ Firebase middleware test failed: {e}")
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    try:
        # Test principal Firebase
        firebase_success = main()
        
        # Test flux d'authentification
        auth_success = test_firebase_auth_flow()
        
        # Test middleware
        middleware_success = test_firebase_middleware()
        
        # Résultats finaux
        print("\n" + "=" * 50)
        print("📊 RÉSULTATS FINAUX:")
        print(f"🔥 Firebase Core: {'✅ SUCCÈS' if firebase_success else '❌ ÉCHEC'}")
        print(f"🔐 Authentification: {'✅ SUCCÈS' if auth_success else '❌ ÉCHEC'}")
        print(f"🔧 Middleware: {'✅ SUCCÈS' if middleware_success else '❌ ÉCHEC'}")
        
        overall_success = firebase_success and auth_success and middleware_success
        print(f"\n🎯 STATUT GLOBAL: {'✅ TOUS LES TESTS RÉUSSIS' if overall_success else '❌ CERTAINS TESTS ONT ÉCHOUÉ'}")
        
        sys.exit(0 if overall_success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrompus par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Erreur fatale: {e}")
        traceback.print_exc()
        sys.exit(1) 