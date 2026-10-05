"""
Script pour modifier le mot de passe de max.weber@test.com
"""
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
email = 'max.weber@test.com'
new_password = 'testpass123'

try:
    user = User.objects.get(email=email)
    user.set_password(new_password)
    user.save()
    print(f'OK: Mot de passe modifie avec succes pour {user.display_name} ({user.email})')
    print(f'    Premium: {user.is_premium}')
    print(f'    Firebase UID: {user.firebase_uid}')
except User.DoesNotExist:
    print(f'ERREUR: Utilisateur {email} introuvable')
except Exception as e:
    print(f'ERREUR: {e}')