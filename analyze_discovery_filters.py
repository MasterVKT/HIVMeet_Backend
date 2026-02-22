"""
Analyse détaillée des filtres qui bloquent la découverte.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Q, F
from django.utils import timezone
from profiles.models import Profile
from matching.models import InteractionHistory
import math
from datetime import timedelta

User = get_user_model()

def analyze_filters(user):
    """Analyser en détail les filtres de découverte."""
    
    print(f"\n{'='*80}")
    print(f"  ANALYSE DÉTAILLÉE DES FILTRES - {user.display_name}")
    print(f"{'='*80}\n")
    
    profile = user.profile
    
    # Étape 1: Profils de base
    print("📊 ÉTAPE 1: Profils de base (actifs, vérifiés, visible)")
    base_profiles = Profile.objects.filter(
        user__is_active=True,
        user__email_verified=True,
        is_hidden=False,
        allow_profile_in_discovery=True
    ).exclude(user=user)
    
    print(f"   Total: {base_profiles.count()} profils")
    
    # Étape 2: Exclusions par interactions
    print(f"\n📊 ÉTAPE 2: Exclusion des profils déjà interagis")
    interacted_ids = InteractionHistory.objects.filter(
        user=user,
        is_revoked=False
    ).values_list('target_user_id', flat=True)
    
    profiles_after_interactions = base_profiles.exclude(user_id__in=interacted_ids)
    print(f"   Exclus: {len(interacted_ids)} profils")
    print(f"   Restants: {profiles_after_interactions.count()} profils")
    
    # Étape 3: Filtre d'âge (MUTUAL)
    print(f"\n📊 ÉTAPE 3: Filtre d'âge (MUTUAL)")
    user_age = user.age
    print(f"   Âge de {user.display_name}: {user_age} ans")
    print(f"   Préférences de {user.display_name}: {profile.age_min_preference}-{profile.age_max_preference} ans")
    
    if user_age:
        # Filtre 1: Les profils doivent accepter l'âge de l'utilisateur
        profiles_who_accept_user_age = profiles_after_interactions.filter(
            age_min_preference__lte=user_age,
            age_max_preference__gte=user_age
        )
        print(f"   Profils qui acceptent {user_age} ans: {profiles_who_accept_user_age.count()}")
        
        # Filtrer 2: L'utilisateur doit accepter l'âge des profils
        profiles_after_age = profiles_who_accept_user_age.annotate(
            user_age_calc=timezone.now().year - F('user__birth_date__year')
        ).filter(
            user_age_calc__gte=profile.age_min_preference,
            user_age_calc__lte=profile.age_max_preference
        )
        print(f"   Profils avec âge {profile.age_min_preference}-{profile.age_max_preference}: {profiles_after_age.count()}")
    else:
        profiles_after_age = profiles_after_interactions
        print(f"   ⚠️  Âge de l'utilisateur non défini")
    
    # Afficher quelques exemples de profils éliminés par l'âge
    if profiles_after_interactions.count() > profiles_after_age.count():
        print(f"\n   Exemples de profils éliminés par l'âge:")
        eliminated = profiles_after_interactions.exclude(
            id__in=profiles_after_age.values_list('id', flat=True)
        )[:5]
        
        for p in eliminated:
            target_age = p.user.age
            print(f"     - {p.user.display_name} ({target_age} ans)")
            print(f"       Préfère: {p.age_min_preference}-{p.age_max_preference} ans (vs {user_age})")
            print(f"       Marie préfère: {profile.age_min_preference}-{profile.age_max_preference} ans (vs {target_age})")
    
    # Étape 4: Filtre de genre (MUTUAL)
    print(f"\n📊 ÉTAPE 4: Filtre de genre (MUTUAL)")
    print(f"   Genre de {user.display_name}: {profile.gender}")
    print(f"   Genres recherchés par {user.display_name}: {profile.genders_sought}")
    
    # Filtre 1: L'utilisateur recherche ces genres
    if profile.genders_sought:
        profiles_gender_match = profiles_after_age.filter(gender__in=profile.genders_sought)
        print(f"   Profils avec genre recherché: {profiles_gender_match.count()}")
    else:
        profiles_gender_match = profiles_after_age
        print(f"   Pas de préférence de genre (tous acceptés)")
    
    # Filtre 2: Les profils doivent rechercher le genre de l'utilisateur
    if profile.gender and profile.gender != 'prefer_not_to_say':
        profiles_after_gender = profiles_gender_match.filter(
            Q(genders_sought__contains=[profile.gender]) |
            Q(genders_sought=[])  # Empty list = tous
        )
        print(f"   Profils qui recherchent '{profile.gender}': {profiles_after_gender.count()}")
    else:
        profiles_after_gender = profiles_gender_match
        print(f"   Genre non spécifié")
    
    # Afficher exemples éliminés
    if profiles_after_age.count() > profiles_after_gender.count():
        print(f"\n   Exemples de profils éliminés par le genre:")
        eliminated = profiles_after_age.exclude(
            id__in=profiles_after_gender.values_list('id', flat=True)
        )[:5]
        
        for p in eliminated:
            print(f"     - {p.user.display_name} (genre: {p.gender})")
            print(f"       Recherche: {p.genders_sought or 'tous'}")
            print(f"       Marie recherche: {profile.genders_sought}")
    
    # Étape 5: Type de relation
    print(f"\n📊 ÉTAPE 5: Filtre de type de relation")
    print(f"   Types recherchés par {user.display_name}: {profile.relationship_types_sought}")
    
    if profile.relationship_types_sought:
        relationship_filter = Q()
        for rel_type in profile.relationship_types_sought:
            relationship_filter |= Q(relationship_types_sought__contains=[rel_type])
        
        profiles_after_relationship = profiles_after_gender.filter(relationship_filter)
        print(f"   Profils avec types compatibles: {profiles_after_relationship.count()}")
        
        # Afficher exemples éliminés
        if profiles_after_gender.count() > profiles_after_relationship.count():
            print(f"\n   Exemples de profils éliminés par le type de relation:")
            eliminated = profiles_after_gender.exclude(
                id__in=profiles_after_relationship.values_list('id', flat=True)
            )[:5]
            
            for p in eliminated:
                print(f"     - {p.user.display_name}")
                print(f"       Recherche: {p.relationship_types_sought}")
                print(f"       Marie recherche: {profile.relationship_types_sought}")
    else:
        profiles_after_relationship = profiles_after_gender
        print(f"   Pas de préférence de type (tous acceptés)")
    
    # Étape 6: Distance
    print(f"\n📊 ÉTAPE 6: Filtre de distance")
    print(f"   Distance max de {user.display_name}: {profile.distance_max_km} km")
    print(f"   Localisation: lat={profile.latitude}, lon={profile.longitude}")
    
    if profile.latitude and profile.longitude:
        user_lat = float(profile.latitude)
        user_lon = float(profile.longitude)
        max_distance = profile.distance_max_km
        
        # Calculer rough bounding box
        lat_diff = max_distance / 111.0
        lon_diff = max_distance / (111.0 * math.cos(math.radians(user_lat)))
        
        bbox_filter = Q(
            latitude__gte=user_lat - lat_diff,
            latitude__lte=user_lat + lat_diff,
            longitude__gte=user_lon - lon_diff,
            longitude__lte=user_lon + lon_diff
        )
        
        profiles_after_distance = profiles_after_relationship.filter(bbox_filter)
        print(f"   Profils dans la zone (bounding box): {profiles_after_distance.count()}")
        
        # Afficher exemples éliminés
        if profiles_after_relationship.count() > profiles_after_distance.count():
            print(f"\n   Exemples de profils éliminés par la distance:")
            eliminated = profiles_after_relationship.exclude(
                id__in=profiles_after_distance.values_list('id', flat=True)
            )[:5]
            
            for p in eliminated:
                if p.latitude and p.longitude:
                    # Calculer distance approximative
                    dlat = float(p.latitude) - user_lat
                    dlon = float(p.longitude) - user_lon
                    distance = math.sqrt(dlat**2 + dlon**2) * 111  # Approximation
                    print(f"     - {p.user.display_name}")
                    print(f"       Position: lat={p.latitude}, lon={p.longitude}")
                    print(f"       Distance approximative: {distance:.1f} km")
                else:
                    print(f"     - {p.user.display_name} (pas de coordonnées)")
    else:
        profiles_after_distance = profiles_after_relationship
        print(f"   ⚠️  Localisation non définie")
    
    # Étape 7: Autres filtres
    print(f"\n📊 ÉTAPE 7: Autres filtres")
    print(f"   Seulement vérifiés: {profile.verified_only}")
    print(f"   Seulement en ligne: {profile.online_only}")
    
    final_profiles = profiles_after_distance
    
    if profile.verified_only:
        final_profiles = final_profiles.filter(user__is_verified=True)
        print(f"   Après filtre 'vérifiés': {final_profiles.count()}")
    
    if profile.online_only:
        cutoff_time = timezone.now() - timedelta(minutes=5)
        final_profiles = final_profiles.filter(user__last_active__gte=cutoff_time)
        print(f"   Après filtre 'en ligne': {final_profiles.count()}")
    
    # Résumé final
    print(f"\n{'='*80}")
    print(f"  RÉSUMÉ FINAL")
    print(f"{'='*80}\n")
    
    print(f"   Profils de départ: {base_profiles.count()}")
    print(f"   Après exclusions: {profiles_after_interactions.count()}")
    print(f"   Après âge: {profiles_after_age.count()}")
    print(f"   Après genre: {profiles_after_gender.count()}")
    print(f"   Après relation: {profiles_after_relationship.count()}")
    print(f"   Après distance: {profiles_after_distance.count()}")
    print(f"   FINAL: {final_profiles.count()}")
    
    if final_profiles.count() > 0:
        print(f"\n✅ Profils disponibles:")
        for p in final_profiles[:10]:
            print(f"   - {p.user.display_name} ({p.user.age} ans, {p.gender})")
    else:
        print(f"\n❌ AUCUN PROFIL DISPONIBLE APRÈS FILTRAGE")
        print(f"\n💡 RECOMMANDATIONS:")
        print(f"   1. Élargir la plage d'âge ({profile.age_min_preference}-{profile.age_max_preference})")
        print(f"   2. Augmenter la distance max ({profile.distance_max_km} km)")
        print(f"   3. Vérifier les préférences de genre et relation")


# Test avec Marie
marie = User.objects.get(email='marie.claire@test.com')
analyze_filters(marie)
