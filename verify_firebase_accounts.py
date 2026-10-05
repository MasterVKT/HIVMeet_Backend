"""
Verification des comptes Firebase pour les utilisateurs Django.
"""
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

import firebase_admin
from firebase_admin import auth as firebase_auth
from django.contrib.auth import get_user_model

User = get_user_model()

# Initialiser Firebase si pas deja fait
try:
    app = firebase_admin.get_app()
except ValueError:
    from hivmeet_backend.settings import FIREBASE_CREDENTIALS_PATH
    from decouple import config
    import json
    # Try loading credentials from path, or from env variable as JSON
    if FIREBASE_CREDENTIALS_PATH:
        cred = firebase_admin.credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    else:
        firebase_creds_json = config('FIREBASE_CREDENTIALS_JSON', default='')
        if firebase_creds_json:
            import json
            cred_dict = json.loads(firebase_creds_json)
            cred = firebase_admin.credentials.Certificate(cred_dict)
        else:
            print("ERREUR: Impossible de charger les credentials Firebase")
            sys.exit(1)
    app = firebase_admin.initialize_app(cred)

print("=" * 80)
print("VERIFICATION DES COMPTES FIREBASE")
print("=" * 80)

# 1. Utilisateurs avec Firebase UID
users_with_fb = User.objects.exclude(firebase_uid__isnull=True).exclude(firebase_uid__exact='')
print(f"\n1. Utilisateurs avec Firebase UID dans Django: {users_with_fb.count()}")

success = 0
failed = 0
for u in users_with_fb:
    try:
        fb_user = firebase_auth.get_user(u.firebase_uid)
        email_match = "OUI" if fb_user.email and fb_user.email.lower() == u.email.lower() else "NON"
        print(f"  OK | {u.display_name[:20]:20} | Django: {u.email[:30]:30} | Firebase: {str(fb_user.email or 'N/A')[:30]:30} | EmailMatch: {email_match} | Verified: {fb_user.email_verified}")
        success += 1
    except firebase_admin.auth.UserNotFoundError:
        print(f"  ERR | {u.display_name[:20]:20} | Email: {u.email:30} | Firebase UID: {u.firebase_uid} | COMPTE INTROUVABLE DANS FIREBASE!")
        failed += 1
    except Exception as e:
        print(f"  ERR | {u.display_name[:20]:20} | Email: {u.email:30} | Firebsae UID: {u.firebase_uid} | Erreur: {str(e)[:100]}")
        failed += 1

print(f"\n  => Firebase OK: {success} | Firebase INVALID: {failed}")

# 2. Lister TOUS les utilisateurs Firebase
print("\n\n2. LISTE DE TOUS LES UTILISATEURS FIREBASE AUTH")
print("-" * 80)
try:
    fb_users_list = list(firebase_auth.list_users().iterate_all())
    print(f"Total utilisateurs dans Firebase Auth: {len(fb_users_list)}")
    for fb_user in fb_users_list:
        # Verifier si cet UID existe dans Django
        django_user = User.objects.filter(firebase_uid=fb_user.uid).first()
        django_status = f"Django OK: {django_user.display_name}" if django_user else "PAS DANS DJANGO!"
        print(f"  UID: {fb_user.uid[:30]:30} | Email: {str(fb_user.email or 'N/A')[:30]:30} | Verified: {fb_user.email_verified} | {django_status}")
except Exception as e:
    print(f"Erreur listing Firebase: {e}")

print("\n" + "=" * 80)
print("RECOMMANDATIONS POUR LES TESTS")
print("=" * 80)
print("\nPour vous connecter avec un compte existant, utilisez les identifiants Firebase:")
print("Exemple - Marie (Premium): marie.claire@test.com")
print("Exemple - Sophie (Premium): sophie.leroy@test.com")
print("Exemple - Julie (Freemium): julie.moreau@test.com")
print("Exemple - Marc (Freemium): marc.bernard@test.com")
print("\nLes mots de passe sont ceux definis lors de la creation des comptes Firebase.")
print("Consultez votre console Firebase Authentication pour les mots de passe.")