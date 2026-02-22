#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de surveillance des erreurs au démarrage de l'application.
"""
import os
import sys
import django

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

print("="*60)
print("🔍 VÉRIFICATION DES IMPORTS ET CONFIGURATION")
print("="*60)

# Test 1: Django setup
try:
    django.setup()
    print("✅ Django setup: OK")
except Exception as e:
    print(f"❌ Django setup: ERREUR - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Imports des apps
print("\n📦 Test des imports des applications:")

apps_to_test = [
    ('authentication', 'authentication.models'),
    ('profiles', 'profiles.models'),
    ('matching', 'matching.models'),
    ('messaging', 'messaging.models'),
    ('resources', 'resources.models'),
    ('subscriptions', 'subscriptions.models'),
]

for app_name, module_path in apps_to_test:
    try:
        __import__(module_path)
        print(f"  ✅ {app_name}: OK")
    except Exception as e:
        print(f"  ❌ {app_name}: ERREUR - {e}")

# Test 3: Services
print("\n🔧 Test des services:")

services_to_test = [
    ('matching.services', 'RecommendationService'),
    ('matching.services', 'MatchingService'),
    ('resources.services', 'ResourceService'),
    ('resources.services', 'FeedService'),
]

for module_path, class_name in services_to_test:
    try:
        module = __import__(module_path, fromlist=[class_name])
        getattr(module, class_name)
        print(f"  ✅ {module_path}.{class_name}: OK")
    except Exception as e:
        print(f"  ❌ {module_path}.{class_name}: ERREUR - {e}")

# Test 4: URLs
print("\n🔗 Test de la configuration des URLs:")

try:
    from django.urls import get_resolver
    resolver = get_resolver()
    print(f"  ✅ Resolver chargé: {len(resolver.url_patterns)} patterns")
except Exception as e:
    print(f"  ❌ Resolver: ERREUR - {e}")

# Test 5: Middleware
print("\n⚙️  Test des middlewares:")

try:
    from django.conf import settings
    for middleware in settings.MIDDLEWARE:
        try:
            from django.utils.module_loading import import_string
            import_string(middleware)
            print(f"  ✅ {middleware.split('.')[-1]}: OK")
        except Exception as e:
            print(f"  ❌ {middleware}: ERREUR - {e}")
except Exception as e:
    print(f"  ❌ Middleware config: ERREUR - {e}")

# Test 6: Database
print("\n🗄️  Test de la connexion à la base de données:")

try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        print("  ✅ Connexion base de données: OK")
except Exception as e:
    print(f"  ❌ Base de données: ERREUR - {e}")

# Test 7: Firebase
print("\n🔥 Test de Firebase:")

try:
    from authentication.firebase_service import FirebaseService
    print("  ✅ FirebaseService: OK")
except Exception as e:
    print(f"  ❌ FirebaseService: ERREUR - {e}")

# Test 8: Celery
print("\n📊 Test de Celery:")

try:
    from hivmeet_backend.celery import app as celery_app
    print(f"  ✅ Celery app: {celery_app.main}")
except Exception as e:
    print(f"  ⚠️  Celery: {e} (peut être normal si désactivé)")

print("\n" + "="*60)
print("✅ VÉRIFICATION TERMINÉE")
print("="*60)
print("\nSi des erreurs apparaissent ci-dessus, elles doivent être corrigées.")
print("Si tout est OK, les erreurs peuvent provenir de:")
print("  1. Requêtes spécifiques du frontend")
print("  2. Données manquantes en base de données")
print("  3. Configuration environnement (.env)")
print("="*60)