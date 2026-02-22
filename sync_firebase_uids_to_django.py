#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour synchroniser les UIDs Firebase dans Django
si certains utilisateurs ne les ont pas
"""

import os
import sys
import django
from pathlib import Path

# Force UTF-8 encoding
if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

import firebase_admin
from firebase_admin import auth
from django.contrib.auth import get_user_model

User = get_user_model()

print("\n" + "="*80)
print("SYNCHRONISATION DES UIDS FIREBASE DANS DJANGO")
print("="*80)

# Récupérer tous les utilisateurs Firebase
try:
    page = auth.list_users(max_results=100)
    firebase_users = page.users
    
    print(f"\nTotal utilisateurs Firebase: {len(firebase_users)}")
    
    # Pour chaque utilisateur Firebase, vérifier s'il a un UID dans Django
    updated_count = 0
    already_has_count = 0
    
    for fb_user in firebase_users:
        email = fb_user.email
        uid = fb_user.uid
        
        # Chercher l'utilisateur Django
        django_user = User.objects.filter(email=email).first()
        
        if django_user:
            if not django_user.firebase_uid:
                # Mettre à jour
                django_user.firebase_uid = uid
                django_user.save()
                print(f"  OK Mise a jour: {email} -> UID: {uid}")
                updated_count += 1
            else:
                if django_user.firebase_uid == uid:
                    already_has_count += 1
                else:
                    # UID différent, mettre à jour
                    print(f"  OK Correction: {email}")
                    print(f"      ancien UID: {django_user.firebase_uid}")
                    print(f"      nouveau UID: {uid}")
                    django_user.firebase_uid = uid
                    django_user.save()
                    updated_count += 1
        else:
            print(f"  ATTENTION: {email} NOT FOUND dans Django!")
    
    print(f"\n" + "-"*80)
    print(f"Resume:")
    print(f"  - Utilisateurs mis a jour: {updated_count}")
    print(f"  - Utilisateurs deja avec UID: {already_has_count}")
    print(f"  - Total traites: {updated_count + already_has_count}/{len(firebase_users)}")
    
    # Verification finale
    print(f"\n" + "-"*80)
    print(f"Verification finale:")
    
    django_users_with_uid = User.objects.filter(firebase_uid__isnull=False).count()
    django_count = User.objects.count()
    
    print(f"  - Utilisateurs Django avec firebase_uid: {django_users_with_uid}/{django_count}")
    
    if django_users_with_uid == django_count:
        print(f"  OK PARFAIT: Tous les utilisateurs Django ont un firebase_uid!")
    else:
        print(f"  ATTENTION: {django_count - django_users_with_uid} utilisateurs sans firebase_uid")
    
except Exception as e:
    print(f"ERREUR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80 + "\n")
