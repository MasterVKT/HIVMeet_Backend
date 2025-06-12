"""
Validation des tâches de notification HIVMeet
"""
import os
import django

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

def validate_messaging_tasks():
    """Valide que les tâches de messagerie sont fonctionnelles."""
    print("Validation des tâches de messagerie...")
    
    try:
        from messaging.tasks import send_message_notification, send_call_notification
        
        # Vérifier les signatures des fonctions
        import inspect
        
        # send_message_notification
        sig = inspect.signature(send_message_notification)
        expected_params = ['recipient_id', 'sender_id', 'message_preview', 'match_id']
        actual_params = list(sig.parameters.keys())
        
        assert actual_params == expected_params, f"Paramètres incorrects pour send_message_notification: {actual_params}"
        print("  ✓ send_message_notification: signature correcte")
        
        # send_call_notification  
        sig = inspect.signature(send_call_notification)
        expected_params = ['callee_id', 'caller_id', 'call_type', 'match_id']
        actual_params = list(sig.parameters.keys())
        
        assert actual_params == expected_params, f"Paramètres incorrects pour send_call_notification: {actual_params}"
        print("  ✓ send_call_notification: signature correcte")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Erreur: {e}")
        return False

def validate_matching_tasks():
    """Valide que les tâches de matching sont fonctionnelles."""
    print("Validation des tâches de matching...")
    
    try:
        from matching.tasks import send_match_notification, send_like_notification
        
        import inspect
        
        # send_match_notification
        sig = inspect.signature(send_match_notification)
        expected_params = ['user_id', 'matched_user_id']
        actual_params = list(sig.parameters.keys())
        
        assert actual_params == expected_params, f"Paramètres incorrects pour send_match_notification: {actual_params}"
        print("  ✓ send_match_notification: signature correcte")
        
        # send_like_notification
        sig = inspect.signature(send_like_notification)
        expected_params = ['user_id', 'liker_id', 'is_super_like']
        actual_params = list(sig.parameters.keys())
        
        assert actual_params == expected_params, f"Paramètres incorrects pour send_like_notification: {actual_params}"
        print("  ✓ send_like_notification: signature correcte")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Erreur: {e}")
        return False

def validate_dependencies():
    """Valide que toutes les dépendances sont disponibles."""
    print("Validation des dépendances...")
    
    dependencies = [
        ('firebase_admin', 'Firebase Admin SDK'),
        ('celery', 'Celery'),
        ('redis', 'Redis'),
        ('django', 'Django')
    ]
    
    success = True
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"  ✓ {name}: disponible")
        except ImportError:
            print(f"  ✗ {name}: manquant")
            success = False
    
    return success

def main():
    """Fonction principale de validation."""
    print("=== VALIDATION DES TACHES DE NOTIFICATION ===\n")
    
    results = []
    
    results.append(validate_dependencies())
    results.append(validate_messaging_tasks())
    results.append(validate_matching_tasks())
    
    print(f"\n=== RÉSULTATS ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests réussis: {passed}/{total}")
    
    if passed == total:
        print("✓ Toutes les validations sont réussies!")
        print("✓ Les tâches de notification sont prêtes à être utilisées.")
    else:
        print("✗ Certaines validations ont échoué.")
        print("✗ Veuillez corriger les erreurs ci-dessus.")

if __name__ == '__main__':
    main()
