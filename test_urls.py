"""
Test des imports d'URLs
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

def test_url_imports():
    """Test tous les imports d'URLs"""
    
    tests = [
        ('authentication.urls', 'Authentication URLs'),
        ('profiles.urls', 'Profiles URLs'),
        ('messaging.urls', 'Messaging URLs'),
        ('messaging.urls_calls', 'Messaging Calls URLs'),
        ('matching.urls.discovery', 'Matching Discovery URLs'),
        ('matching.urls.matches', 'Matching Matches URLs'),
    ]
    
    print("Test des imports d'URLs...")
    print("=" * 40)
    
    success_count = 0
    for module_name, description in tests:
        try:
            __import__(module_name)
            print(f"SUCCES: {description}")
            success_count += 1
        except ImportError as e:
            print(f"ERREUR: {description} - {e}")
        except Exception as e:
            print(f"ERREUR: {description} - {type(e).__name__}: {e}")
    
    print("=" * 40)
    print(f"Resultats: {success_count}/{len(tests)} modules charges avec succes")
    
    return success_count == len(tests)

if __name__ == '__main__':
    test_url_imports()
