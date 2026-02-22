"""
Script de diagnostic pour analyser le problème de découverte vide.
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from matching.models import Like, Dislike, InteractionHistory, Match
from profiles.models import Profile
from matching.services import RecommendationService

User = get_user_model()


def print_section(title):
    """Afficher un titre de section."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def analyze_user_interactions(user):
    """Analyser les interactions d'un utilisateur."""
    print(f"👤 Utilisateur: {user.email} ({user.display_name})")
    print(f"   ID: {user.id}")
    print(f"   Premium: {user.is_premium}")
    print(f"   Vérifié: {user.is_verified}")
    
    print("\n📊 DONNÉES DANS LES TABLES:")
    
    # Compter les likes dans la table Like
    likes_table = Like.objects.filter(from_user=user)
    print(f"\n   Table Like (modèle legacy):")
    print(f"   - Total: {likes_table.count()} likes")
    if likes_table.exists():
        print(f"   - Exemples:")
        for like in likes_table[:5]:
            print(f"     • {like.to_user.display_name} (créé: {like.created_at})")
    
    # Compter les dislikes dans la table Dislike
    dislikes_table = Dislike.objects.filter(from_user=user)
    active_dislikes = dislikes_table.filter(expires_at__gt=timezone.now())
    print(f"\n   Table Dislike (modèle legacy):")
    print(f"   - Total: {dislikes_table.count()} dislikes")
    print(f"   - Actifs (non expirés): {active_dislikes.count()}")
    if active_dislikes.exists():
        print(f"   - Exemples d'actifs:")
        for dislike in active_dislikes[:5]:
            print(f"     • {dislike.to_user.display_name} (expire: {dislike.expires_at})")
    
    # Compter les interactions dans InteractionHistory
    interactions = InteractionHistory.objects.filter(user=user)
    active_interactions = interactions.filter(is_revoked=False)
    
    print(f"\n   Table InteractionHistory (nouveau système):")
    print(f"   - Total: {interactions.count()} interactions")
    print(f"   - Actives: {active_interactions.count()}")
    print(f"   - Révoquées: {interactions.filter(is_revoked=True).count()}")
    
    if active_interactions.exists():
        print(f"\n   Détail par type (actives seulement):")
        for itype in [InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE, InteractionHistory.DISLIKE]:
            count = active_interactions.filter(interaction_type=itype).count()
            print(f"   - {itype}: {count}")
    
    # Vérifier les matches
    matches = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        status=Match.ACTIVE
    )
    print(f"\n   Matches:")
    print(f"   - Total: {matches.count()}")
    
    return {
        'legacy_likes': likes_table.count(),
        'legacy_dislikes': active_dislikes.count(),
        'history_total': interactions.count(),
        'history_active': active_interactions.count(),
        'matches': matches.count()
    }


def test_recommendation_service(user):
    """Tester le service de recommandation."""
    print_section("TEST DU SERVICE DE RECOMMANDATION")
    
    print(f"🔍 Test pour: {user.email}")
    
    # Compter le total de profils disponibles
    all_profiles = Profile.objects.filter(
        user__is_active=True,
        user__email_verified=True,
        is_hidden=False,
        allow_profile_in_discovery=True
    ).exclude(user=user).count()
    
    print(f"\n📊 Profils totaux dans la base:")
    print(f"   - Profils actifs et vérifiés: {all_profiles}")
    
    # Tester les recommandations
    print(f"\n🎯 Appel de RecommendationService.get_recommendations()...")
    recommendations = RecommendationService.get_recommendations(user, limit=20)
    
    print(f"\n✅ Résultat:")
    print(f"   - Profils recommandés: {len(recommendations)}")
    
    if recommendations:
        print(f"\n   Exemples de profils recommandés:")
        for i, profile in enumerate(recommendations[:5], 1):
            print(f"   {i}. {profile.user.display_name} ({profile.user.age} ans)")
    else:
        print(f"\n❌ AUCUN PROFIL RECOMMANDÉ!")
        print(f"\n🔍 Diagnostic des exclusions:")
        
        # Analyser pourquoi il n'y a pas de recommandations
        interacted_ids = InteractionHistory.objects.filter(
            user=user,
            is_revoked=False
        ).values_list('target_user_id', flat=True)
        
        legacy_liked_ids = Like.objects.filter(
            from_user=user
        ).values_list('to_user_id', flat=True)
        
        legacy_disliked_ids = Dislike.objects.filter(
            from_user=user,
            expires_at__gt=timezone.now()
        ).values_list('to_user_id', flat=True)
        
        blocked_ids = user.blocked_users.values_list('id', flat=True)
        blocked_by_ids = User.objects.filter(blocked_users=user).values_list('id', flat=True)
        
        print(f"   - Exclus par InteractionHistory (actifs): {len(interacted_ids)}")
        print(f"   - Exclus par Like (legacy): {len(legacy_liked_ids)}")
        print(f"   - Exclus par Dislike actifs (legacy): {len(legacy_disliked_ids)}")
        print(f"   - Exclus par blocage: {len(blocked_ids)}")
        print(f"   - Exclus car ont bloqué l'utilisateur: {len(blocked_by_ids)}")
        
        total_excluded = len(set(interacted_ids) | set(legacy_liked_ids) | 
                            set(legacy_disliked_ids) | set(blocked_ids) | 
                            set(blocked_by_ids) | {user.id})
        
        print(f"\n   📊 TOTAL EXCLU: {total_excluded} utilisateurs")
        print(f"   📊 Profils disponibles après exclusions: {all_profiles - total_excluded + 1}")
        
        # Vérifier les filtres de préférences
        if hasattr(user, 'profile'):
            profile = user.profile
            print(f"\n   🎚️ Filtres actifs du profil:")
            print(f"   - Distance max: {profile.distance_max_km} km")
            print(f"   - Âge: {profile.age_min_preference}-{profile.age_max_preference} ans")
            print(f"   - Genres recherchés: {profile.genders_sought}")
            print(f"   - Types de relation: {profile.relationship_types_sought}")
            print(f"   - Seulement vérifiés: {profile.verified_only}")
            print(f"   - Seulement en ligne: {profile.online_only}")


def check_interaction_history_sync():
    """Vérifier la synchronisation entre les anciennes tables et InteractionHistory."""
    print_section("SYNCHRONISATION DES DONNÉES")
    
    # Compter les likes qui n'ont pas d'entrée dans InteractionHistory
    all_likes = Like.objects.all()
    print(f"📊 Likes dans la table Like: {all_likes.count()}")
    
    likes_without_history = 0
    for like in all_likes:
        has_history = InteractionHistory.objects.filter(
            user=like.from_user,
            target_user=like.to_user,
            interaction_type__in=[InteractionHistory.LIKE, InteractionHistory.SUPER_LIKE],
            is_revoked=False
        ).exists()
        
        if not has_history:
            likes_without_history += 1
    
    print(f"⚠️  Likes SANS entrée dans InteractionHistory: {likes_without_history}")
    
    # Compter les dislikes actifs qui n'ont pas d'entrée dans InteractionHistory
    active_dislikes = Dislike.objects.filter(expires_at__gt=timezone.now())
    print(f"\n📊 Dislikes actifs dans la table Dislike: {active_dislikes.count()}")
    
    dislikes_without_history = 0
    for dislike in active_dislikes:
        has_history = InteractionHistory.objects.filter(
            user=dislike.from_user,
            target_user=dislike.to_user,
            interaction_type=InteractionHistory.DISLIKE,
            is_revoked=False
        ).exists()
        
        if not has_history:
            dislikes_without_history += 1
    
    print(f"⚠️  Dislikes actifs SANS entrée dans InteractionHistory: {dislikes_without_history}")
    
    if likes_without_history > 0 or dislikes_without_history > 0:
        print(f"\n❌ PROBLÈME DÉTECTÉ!")
        print(f"   Les anciennes interactions ne sont PAS dans InteractionHistory.")
        print(f"   Cela signifie que le service de recommandation ne les voit PAS,")
        print(f"   ce qui explique pourquoi les profils déjà vus ne sont PAS exclus!")
        return False
    else:
        print(f"\n✅ Synchronisation OK")
        return True


def propose_migration_solution():
    """Proposer une solution de migration."""
    print_section("SOLUTION PROPOSÉE")
    
    print("🔧 Migration nécessaire des données historiques vers InteractionHistory")
    print("\nÉtapes recommandées:")
    print("\n1. Créer un script de migration pour copier:")
    print("   - Toutes les entrées de Like → InteractionHistory")
    print("   - Toutes les entrées de Dislike actifs → InteractionHistory")
    
    print("\n2. Modifier le code pour utiliser UNIQUEMENT InteractionHistory:")
    print("   - Mettre à jour RecommendationService.get_recommendations()")
    print("   - Supprimer les références aux tables Like/Dislike dans les exclusions")
    
    print("\n3. Ajouter un signal Django pour synchronisation automatique:")
    print("   - Quand Like est créé → créer InteractionHistory")
    print("   - Quand Dislike est créé → créer InteractionHistory")
    
    print("\n4. Optionnel: Conserver Like/Dislike pour l'historique")
    print("   - Mais NE PAS les utiliser dans la logique de découverte")


def main():
    """Fonction principale."""
    print_section("DIAGNOSTIC DU PROBLÈME DE DÉCOUVERTE")
    
    # Demander l'email de l'utilisateur à diagnostiquer
    print("Entrez l'email de l'utilisateur à diagnostiquer:")
    print("(Appuyez sur Entrée pour utiliser marie.claire@test.com)")
    user_email = input("> ").strip() or "marie.claire@test.com"
    
    try:
        user = User.objects.get(email=user_email)
    except User.DoesNotExist:
        print(f"❌ Utilisateur {user_email} non trouvé!")
        return
    
    # 1. Analyser les interactions de l'utilisateur
    print_section(f"ANALYSE DES INTERACTIONS - {user.email}")
    stats = analyze_user_interactions(user)
    
    # 2. Vérifier la synchronisation
    is_synced = check_interaction_history_sync()
    
    # 3. Tester le service de recommandation
    test_recommendation_service(user)
    
    # 4. Proposer une solution si problème détecté
    if not is_synced or stats['legacy_likes'] > 0 or stats['legacy_dislikes'] > 0:
        propose_migration_solution()
    
    # Résumé final
    print_section("RÉSUMÉ")
    
    if stats['history_active'] == 0 and (stats['legacy_likes'] > 0 or stats['legacy_dislikes'] > 0):
        print("❌ PROBLÈME CONFIRMÉ:")
        print(f"   - L'utilisateur a {stats['legacy_likes']} likes et {stats['legacy_dislikes']} dislikes")
        print(f"   - Mais seulement {stats['history_active']} interactions dans InteractionHistory")
        print(f"\n💡 CAUSE:")
        print(f"   Les interactions ont été créées AVANT l'implémentation d'InteractionHistory.")
        print(f"   Le code de RecommendationService utilise InteractionHistory pour exclure,")
        print(f"   donc il ne voit PAS les anciennes interactions!")
        print(f"\n🔧 SOLUTION:")
        print(f"   Exécuter le script de migration pour copier les données historiques.")
    elif stats['history_active'] > 0:
        print("✅ InteractionHistory contient des données")
        print(f"   - {stats['history_active']} interactions actives")
        print(f"\n🔍 Si la découverte est vide, vérifier:")
        print(f"   - Les filtres de préférences (âge, genre, distance)")
        print(f"   - Les profils disponibles dans la base de données")
    else:
        print("ℹ️  Aucune interaction détectée")
        print(f"   L'utilisateur n'a pas encore interagi avec de profils.")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
