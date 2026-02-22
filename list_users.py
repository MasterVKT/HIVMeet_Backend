"""
Script to list available test users.
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "="*80)
print("📋 Liste des utilisateurs disponibles")
print("="*80 + "\n")

users = User.objects.all()[:10]

if not users:
    print("❌ Aucun utilisateur trouvé dans la base de données")
else:
    print(f"Total utilisateurs: {User.objects.count()}\n")
    
    for user in users:
        print(f"📧 Email: {user.email}")
        print(f"   ID: {user.id}")
        print(f"   Nom: {user.display_name}")
        print(f"   Actif: {user.is_active}")
        print(f"   Email vérifié: {user.email_verified}")
        print()

print("="*80 + "\n")
