#!/usr/bin/env python3
"""
Script de test pour vérifier le peuplement de la base de données HIVMeet.

Ce script vérifie que tous les utilisateurs et interactions ont été créés correctement.
"""

import os
import sys
import django
from datetime import datetime

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile, ProfilePhoto
from matching.models import Match, Like
from messaging.models import Message

User = get_user_model()

def test_users_creation():
    """
    Teste la création des utilisateurs.
    """
    print("🔍 Test de création des utilisateurs...")
    
    users = User.objects.filter(is_active=True).exclude(role='admin')
    test_users = users.filter(email__endswith='@test.com')
    
    print(f"   - Utilisateurs totaux: {users.count()}")
    print(f"   - Utilisateurs de test: {test_users.count()}")
    
    if test_users.count() >= 15:
        print("   ✅ Nombre d'utilisateurs de test OK")
    else:
        print("   ❌ Nombre d'utilisateurs de test insuffisant")
        return False
    
    # Vérifier les statuts
    verified = test_users.filter(is_verified=True).count()
    premium = test_users.filter(is_premium=True).count()
    
    print(f"   - Utilisateurs vérifiés: {verified}")
    print(f"   - Utilisateurs premium: {premium}")
    
    if verified >= 10 and premium >= 7:
        print("   ✅ Répartition des statuts OK")
    else:
        print("   ❌ Répartition des statuts incorrecte")
        return False
    
    return True

def test_profiles_creation():
    """
    Teste la création des profils.
    """
    print("🔍 Test de création des profils...")
    
    profiles = Profile.objects.all()
    test_profiles = profiles.filter(user__email__endswith='@test.com')
    
    print(f"   - Profils totaux: {profiles.count()}")
    print(f"   - Profils de test: {test_profiles.count()}")
    
    if test_profiles.count() >= 15:
        print("   ✅ Nombre de profils de test OK")
    else:
        print("   ❌ Nombre de profils de test insuffisant")
        return False
    
    # Vérifier les données des profils
    profiles_with_bio = test_profiles.exclude(bio='').count()
    profiles_with_location = test_profiles.exclude(city='').count()
    
    print(f"   - Profils avec bio: {profiles_with_bio}")
    print(f"   - Profils avec ville: {profiles_with_location}")
    
    if profiles_with_bio >= 15 and profiles_with_location >= 15:
        print("   ✅ Données des profils OK")
    else:
        print("   ❌ Données des profils incomplètes")
        return False
    
    return True

def test_photos_creation():
    """
    Teste la création des photos de profil.
    """
    print("🔍 Test de création des photos...")
    
    photos = ProfilePhoto.objects.all()
    test_photos = photos.filter(profile__user__email__endswith='@test.com')
    main_photos = test_photos.filter(is_main=True)
    
    print(f"   - Photos totales: {photos.count()}")
    print(f"   - Photos de test: {test_photos.count()}")
    print(f"   - Photos principales: {main_photos.count()}")
    
    if main_photos.count() >= 15:
        print("   ✅ Photos principales OK")
    else:
        print("   ❌ Photos principales manquantes")
        return False
    
    # Vérifier les photos premium
    premium_users = User.objects.filter(is_premium=True, email__endswith='@test.com')
    premium_photos = test_photos.filter(profile__user__in=premium_users)
    
    print(f"   - Photos premium: {premium_photos.count()}")
    
    if premium_photos.count() >= 20:  # Au moins 1 photo principale + 1-3 photos supplémentaires
        print("   ✅ Photos premium OK")
    else:
        print("   ❌ Photos premium insuffisantes")
        return False
    
    return True

def test_interactions_creation():
    """
    Teste la création des interactions.
    """
    print("🔍 Test de création des interactions...")
    
    likes = Like.objects.all()
    matches = Match.objects.all()
    messages = Message.objects.all()
    
    print(f"   - Likes totaux: {likes.count()}")
    print(f"   - Matches totaux: {matches.count()}")
    print(f"   - Messages totaux: {messages.count()}")
    
    if likes.count() >= 20:
        print("   ✅ Likes créés OK")
    else:
        print("   ❌ Likes insuffisants")
        return False
    
    if matches.count() >= 10:
        print("   ✅ Matches créés OK")
    else:
        print("   ❌ Matches insuffisants")
        return False
    
    if messages.count() >= 30:
        print("   ✅ Messages créés OK")
    else:
        print("   ❌ Messages insuffisants")
        return False
    
    return True

def test_admin_user():
    """
    Teste la création de l'utilisateur administrateur.
    """
    print("🔍 Test de l'utilisateur administrateur...")
    
    admin_user = User.objects.filter(email='admin@hivmeet.com').first()
    
    if admin_user:
        print("   ✅ Utilisateur admin créé")
        
        if admin_user.is_staff and admin_user.is_superuser:
            print("   ✅ Permissions admin OK")
        else:
            print("   ❌ Permissions admin manquantes")
            return False
    else:
        print("   ❌ Utilisateur admin manquant")
        return False
    
    return True

def test_data_consistency():
    """
    Teste la cohérence des données.
    """
    print("🔍 Test de cohérence des données...")
    
    # Vérifier que chaque utilisateur a un profil
    users_without_profile = User.objects.filter(
        email__endswith='@test.com',
        profile__isnull=True
    ).count()
    
    if users_without_profile == 0:
        print("   ✅ Tous les utilisateurs ont un profil")
    else:
        print(f"   ❌ {users_without_profile} utilisateurs sans profil")
        return False
    
    # Vérifier que chaque profil a une photo principale
    profiles_without_main_photo = Profile.objects.filter(
        user__email__endswith='@test.com',
        photos__is_main=True
    ).count()
    
    if profiles_without_main_photo >= 15:
        print("   ✅ Tous les profils ont une photo principale")
    else:
        print(f"   ❌ {15 - profiles_without_main_photo} profils sans photo principale")
        return False
    
    # Vérifier les timestamps
    recent_users = User.objects.filter(
        email__endswith='@test.com',
        last_active__gte=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    
    if recent_users > 0:
        print("   ✅ Activité récente détectée")
    else:
        print("   ⚠️  Aucune activité récente détectée")
    
    return True

def generate_test_report():
    """
    Génère un rapport de test complet.
    """
    print("\n" + "="*60)
    print("📋 RAPPORT DE TEST - PEUPLEMENT HIVMEET")
    print("="*60)
    
    # Statistiques détaillées
    users = User.objects.filter(email__endswith='@test.com')
    profiles = Profile.objects.filter(user__email__endswith='@test.com')
    photos = ProfilePhoto.objects.filter(profile__user__email__endswith='@test.com')
    likes = Like.objects.all()
    matches = Match.objects.all()
    messages = Message.objects.all()
    
    print(f"\n📊 STATISTIQUES DÉTAILLÉES:")
    print(f"   👥 Utilisateurs de test: {users.count()}")
    print(f"   📝 Profils créés: {profiles.count()}")
    print(f"   📸 Photos de profil: {photos.count()}")
    print(f"   💕 Likes créés: {likes.count()}")
    print(f"   💘 Matches créés: {matches.count()}")
    print(f"   💬 Messages créés: {messages.count()}")
    
    # Répartition par genre
    gender_stats = {}
    for profile in profiles:
        gender = profile.gender
        gender_stats[gender] = gender_stats.get(gender, 0) + 1
    
    print(f"\n👫 RÉPARTITION PAR GENRE:")
    for gender, count in gender_stats.items():
        print(f"   - {gender}: {count}")
    
    # Répartition par ville
    city_stats = {}
    for profile in profiles:
        city = profile.city
        if city:
            city_stats[city] = city_stats.get(city, 0) + 1
    
    print(f"\n🏙️  RÉPARTITION PAR VILLE:")
    for city, count in sorted(city_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {city}: {count}")
    
    # Statuts de vérification
    verified_count = users.filter(is_verified=True).count()
    premium_count = users.filter(is_premium=True).count()
    
    print(f"\n✅ STATUTS:")
    print(f"   - Vérifiés: {verified_count}/{users.count()}")
    print(f"   - Premium: {premium_count}/{users.count()}")
    
    # Qualité des données
    profiles_with_bio = profiles.exclude(bio='').count()
    profiles_with_interests = profiles.exclude(interests=[]).count()
    
    print(f"\n📝 QUALITÉ DES DONNÉES:")
    print(f"   - Profils avec bio: {profiles_with_bio}/{profiles.count()}")
    print(f"   - Profils avec intérêts: {profiles_with_interests}/{profiles.count()}")
    
    # Interactions
    active_matches = matches.filter(status='active').count()
    messages_per_match = messages.count() / matches.count() if matches.count() > 0 else 0
    
    print(f"\n💕 INTERACTIONS:")
    print(f"   - Matches actifs: {active_matches}/{matches.count()}")
    print(f"   - Messages par match: {messages_per_match:.1f}")

def main():
    """
    Fonction principale de test.
    """
    print("🧪 DÉBUT DES TESTS DE PEUPLEMENT HIVMEET")
    print("="*60)
    
    tests = [
        ("Création des utilisateurs", test_users_creation),
        ("Création des profils", test_profiles_creation),
        ("Création des photos", test_photos_creation),
        ("Création des interactions", test_interactions_creation),
        ("Utilisateur administrateur", test_admin_user),
        ("Cohérence des données", test_data_consistency)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"🧪 Test: {test_name}")
        print(f"{'='*40}")
        
        try:
            if test_func():
                print(f"✅ {test_name}: SUCCÈS")
                passed_tests += 1
            else:
                print(f"❌ {test_name}: ÉCHEC")
        except Exception as e:
            print(f"❌ {test_name}: ERREUR - {e}")
    
    # Rapport final
    print(f"\n{'='*60}")
    print("📋 RÉSULTATS FINAUX")
    print(f"{'='*60}")
    print(f"✅ Tests réussis: {passed_tests}/{total_tests}")
    print(f"📊 Taux de succès: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 TOUS LES TESTS SONT PASSÉS!")
        print("✅ Le peuplement de la base de données est réussi")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
        print("❌ Vérifiez les erreurs ci-dessus")
    
    # Générer le rapport détaillé
    generate_test_report()
    
    print(f"\n⏰ Test terminé: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 