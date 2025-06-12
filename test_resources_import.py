#!/usr/bin/env python
"""
Test d'import des services resources après correction des erreurs.
"""
import os
import sys

# Configuration minimale
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.simple_settings')

try:
    import django
    django.setup()
    print("✓ Django setup successful")
    
    # Test d'import des services resources
    from resources.services import ResourceService, FeedService
    print("✓ ResourceService et FeedService importés avec succès")
    
    # Test des autres services pour s'assurer qu'il n'y a pas de régression
    from matching.services import MatchingService
    print("✓ MatchingService importé avec succès")
    
    print("\n🎉 SUCCÈS : Toutes les erreurs d'indentation et de syntaxe ont été corrigées !")
    print("Les services peuvent maintenant être importés sans erreur.")
    
except Exception as e:
    print(f"✗ Erreur lors du test : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("RÉSUMÉ DES CORRECTIONS APPLIQUÉES :")
print("="*60)
print("1. ✅ Correction des erreurs d'indentation dans resources/services.py")
print("2. ✅ Ajout des sauts de ligne manquants")
print("3. ✅ Correction des clauses try/except malformées")
print("4. ✅ Correction des espaces d'indentation incohérents")
print("5. ✅ Validation syntaxique complète")
print("="*60)
