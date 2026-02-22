#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour lister TOUS les utilisateurs Firebase créés
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
print("LISTE COMPLETE DES UTILISATEURS FIREBASE")
print("="*80)

# Récupérer les 100 premiers utilisateurs Firebase
try:
    page = auth.list_users(max_results=100)
    users = page.users
    
    print(f"\nOK {len(users)} utilisateurs trouves dans Firebase:\n")
    
    # Afficher les utilisateurs
    for i, user in enumerate(users, 1):
        email = user.email or "N/A"
        uid = user.uid
        display_name = user.display_name or "N/A"
        
        # Chercher dans Django
        django_user = User.objects.filter(email=email).first()
        has_firebase_uid = "OK" if django_user and django_user.firebase_uid else "NO"
        
        print(f"{i:2d}. {email:40s} | UID: {uid:20s} | {has_firebase_uid}")
    
    print(f"\n" + "-"*80)
    print(f"Total: {len(users)} utilisateurs dans Firebase")
    
    # Comparer avec Django
    django_count = User.objects.count()
    print(f"Total: {django_count} utilisateurs dans Django")
    
    if len(users) == django_count:
        print(f"\nOK: Les nombres correspondent!")
    else:
        print(f"\nATTENTION: Les nombres ne correspondent pas")
        print(f"   Firebase: {len(users)} users")
        print(f"   Django: {django_count} users")
    
    # Vérifier les UIDs Firebase en Django
    print(f"\n" + "-"*80)
    print("Verification des UIDs Firebase en Django:")
    
    django_users_with_uid = User.objects.filter(firebase_uid__isnull=False).count()
    print(f"   Utilisateurs Django avec firebase_uid: {django_users_with_uid}/{django_count}")
    
    if django_users_with_uid == django_count:
        print(f"   OK Tous les utilisateurs Django ont un firebase_uid!")
    
except Exception as e:
    print(f"ERREUR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80 + "\n")
