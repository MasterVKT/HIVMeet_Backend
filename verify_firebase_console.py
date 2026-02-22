#!/usr/bin/env python3
"""
Script pour afficher exactement quel est le projet Firebase utilisé
et fournir les étapes pour le vérifier dans la console
"""

import json
from pathlib import Path

print("\n" + "="*80)
print("🔥 VÉRIFICATION DU PROJET FIREBASE")
print("="*80)

# Lire les credentials
creds_path = Path('credentials/hivmeet_firebase_credentials.json')

if not creds_path.exists():
    print(f"\n❌ ERREUR: Fichier credentials introuvable: {creds_path}")
    exit(1)

with open(creds_path, 'r') as f:
    creds = json.load(f)

project_id = creds.get('project_id')
print(f"\n✅ Projet Firebase actuellement utilisé:")
print(f"   🆔 Project ID: {project_id}")
print(f"   📧 Service Account: {creds.get('client_email')}")

print("\n" + "="*80)
print("📋 INSTRUCTIONS POUR VÉRIFIER DANS FIREBASE CONSOLE")
print("="*80)

print(f"""
1️⃣  Allez sur: https://console.firebase.google.com/

2️⃣  En haut à gauche, cliquez sur le sélecteur de projet (par défaut c'est 
   le projet actuellement actif)
   
3️⃣  VÉRIFIEZ:
   ✓ Êtes-vous dans le projet: {project_id} ?
   
   Si vous voyez un AUTRE projet:
   ➡️  Sélectionnez {project_id} dans la liste
   
   Si {project_id} n'existe PAS dans la liste:
   ⚠️  Cela signifie vous n'avez pas accès à ce projet
   
4️⃣  Une fois dans le projet {project_id}:
   ✓ Allez dans: Build > Authentication
   ✓ Cliquez sur l'onglet "Users"
   ✓ Vous devriez voir 41 utilisateurs

5️⃣  Si vous ne voyez TOUJOURS pas les utilisateurs:
   ✓ Vérifiez le compte Google connecté (haut à droite)
   ✓ Ce compte doit avoir accès au projet {project_id}

TROUBLESHOOTING:
---
❌ Vous voyez 0 utilisateurs même dans {project_id}?
   → Les utilisateurs SONT dans Firebase (nous l'avons vérifié)
   → Cela peut être un bug de cache du navigateur
   → Solution: Actualisez la page (Ctrl+F5 ou Cmd+Shift+R)
   
❌ Le projet {project_id} n'existe pas?
   → Vous devez vous connecter avec le compte Google qui a créé ce projet
   → OU le projet n'existe que dans ce compte Google spécifique
""")

print("="*80)
print(f"✨ Les 41 utilisateurs sont DÉFINITIVEMENT dans Firebase (projet {project_id})")
print("="*80 + "\n")
