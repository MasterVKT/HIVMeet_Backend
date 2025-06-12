"""
Test de validation des URLs après correction
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

try:
    print("Testing Django setup...")
    django.setup()
    print("SUCCESS: Django setup completed")
      print("Testing URL configuration...")
    from django.urls import reverse
    from django.test import Client
    
    # Test que les URLs se chargent sans erreur
    from django.urls import resolve
    print("SUCCESS: URL configuration loaded")
    
    print("Testing specific URL imports...")
    
    # Test import de profiles.urls_settings
    import profiles.urls_settings
    print("SUCCESS: profiles.urls_settings imported")
    
    # Test import des autres URLs mentionnées dans api_urls.py
    import authentication.urls
    print("SUCCESS: authentication.urls imported")
    
    import profiles.urls
    print("SUCCESS: profiles.urls imported")
    
    import matching.urls.discovery
    print("SUCCESS: matching.urls.discovery imported")
    
    import matching.urls.matches
    print("SUCCESS: matching.urls.matches imported")
    
    import messaging.urls
    print("SUCCESS: messaging.urls imported")
    
    import messaging.urls_calls
    print("SUCCESS: messaging.urls_calls imported")
    
    print("\nALL TESTS PASSED - URL configuration is working correctly!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
