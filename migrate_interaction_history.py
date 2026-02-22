"""
Script de migration des données historiques vers InteractionHistory.

Ce script copie toutes les interactions existantes des tables Like et Dislike
vers la nouvelle table InteractionHistory, permettant ainsi au système de 
découverte de correctement exclure les profils déjà vus.
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from matching.models import Like, Dislike, InteractionHistory

User = get_user_model()


def migrate_likes():
    """Migrer tous les likes vers InteractionHistory."""
    print("\n" + "="*80)
    print("  MIGRATION DES LIKES")
    print("="*80 + "\n")
    
    all_likes = Like.objects.all()
    total = all_likes.count()
    migrated = 0
    skipped = 0
    errors = 0
    
    print(f"📊 Total de likes à migrer: {total}")
    
    for like in all_likes:
        try:
            # Déterminer le type d'interaction
            interaction_type = (
                InteractionHistory.SUPER_LIKE 
                if like.like_type == Like.SUPER 
                else InteractionHistory.LIKE
            )
            
            # Vérifier si l'interaction existe déjà
            existing = InteractionHistory.objects.filter(
                user=like.from_user,
                target_user=like.to_user,
                interaction_type=interaction_type
            ).first()
            
            if existing:
                skipped += 1
                print(f"⏭️  Déjà existant: {like.from_user.display_name} → {like.to_user.display_name}")
                continue
            
            # Créer l'entrée dans InteractionHistory
            InteractionHistory.objects.create(
                user=like.from_user,
                target_user=like.to_user,
                interaction_type=interaction_type,
                is_revoked=False,
                created_at=like.created_at
            )
            
            migrated += 1
            print(f"✅ Migré: {like.from_user.display_name} → {like.to_user.display_name} ({interaction_type})")
            
        except Exception as e:
            errors += 1
            print(f"❌ Erreur: {like.from_user.display_name} → {like.to_user.display_name}")
            print(f"   {str(e)}")
    
    print(f"\n📊 Résultat de la migration des likes:")
    print(f"   ✅ Migrés: {migrated}")
    print(f"   ⏭️  Déjà existants: {skipped}")
    print(f"   ❌ Erreurs: {errors}")
    
    return migrated, skipped, errors


def migrate_dislikes():
    """Migrer tous les dislikes actifs vers InteractionHistory."""
    print("\n" + "="*80)
    print("  MIGRATION DES DISLIKES")
    print("="*80 + "\n")
    
    # Migrer TOUS les dislikes, pas seulement les actifs
    # Car on veut l'historique complet
    all_dislikes = Dislike.objects.all()
    total = all_dislikes.count()
    migrated = 0
    skipped = 0
    errors = 0
    
    print(f"📊 Total de dislikes à migrer: {total}")
    
    for dislike in all_dislikes:
        try:
            # Vérifier si l'interaction existe déjà
            existing = InteractionHistory.objects.filter(
                user=dislike.from_user,
                target_user=dislike.to_user,
                interaction_type=InteractionHistory.DISLIKE
            ).first()
            
            if existing:
                skipped += 1
                print(f"⏭️  Déjà existant: {dislike.from_user.display_name} → {dislike.to_user.display_name}")
                continue
            
            # Déterminer si le dislike est expiré
            is_expired = dislike.expires_at <= timezone.now()
            
            # Créer l'entrée dans InteractionHistory
            InteractionHistory.objects.create(
                user=dislike.from_user,
                target_user=dislike.to_user,
                interaction_type=InteractionHistory.DISLIKE,
                is_revoked=is_expired,  # Si expiré, considérer comme révoqué
                created_at=dislike.created_at,
                revoked_at=dislike.expires_at if is_expired else None
            )
            
            status = "expiré" if is_expired else "actif"
            migrated += 1
            print(f"✅ Migré: {dislike.from_user.display_name} → {dislike.to_user.display_name} ({status})")
            
        except Exception as e:
            errors += 1
            print(f"❌ Erreur: {dislike.from_user.display_name} → {dislike.to_user.display_name}")
            print(f"   {str(e)}")
    
    print(f"\n📊 Résultat de la migration des dislikes:")
    print(f"   ✅ Migrés: {migrated}")
    print(f"   ⏭️  Déjà existants: {skipped}")
    print(f"   ❌ Erreurs: {errors}")
    
    return migrated, skipped, errors


def verify_migration(user_email=None):
    """Vérifier la migration pour un utilisateur ou tous."""
    print("\n" + "="*80)
    print("  VÉRIFICATION DE LA MIGRATION")
    print("="*80 + "\n")
    
    if user_email:
        try:
            user = User.objects.get(email=user_email)
            users = [user]
        except User.DoesNotExist:
            print(f"❌ Utilisateur {user_email} non trouvé!")
            return
    else:
        users = User.objects.all()[:5]  # Vérifier les 5 premiers
    
    for user in users:
        likes_count = Like.objects.filter(from_user=user).count()
        dislikes_count = Dislike.objects.filter(from_user=user).count()
        history_count = InteractionHistory.objects.filter(user=user).count()
        
        print(f"👤 {user.display_name} ({user.email}):")
        print(f"   Likes: {likes_count} | Dislikes: {dislikes_count} | History: {history_count}")
        
        if history_count >= (likes_count + dislikes_count):
            print(f"   ✅ Migration OK")
        else:
            print(f"   ⚠️  Manquant: {(likes_count + dislikes_count) - history_count} interactions")


@transaction.atomic
def main():
    """Fonction principale de migration."""
    print("\n" + "="*80)
    print("  MIGRATION DES DONNÉES HISTORIQUES VERS INTERACTIONHISTORY")
    print("="*80)
    
    print("\n⚠️  ATTENTION: Cette opération va copier toutes les interactions")
    print("   existantes vers la nouvelle table InteractionHistory.")
    print("\n   Continuer? (oui/non): ", end='')
    
    response = input().strip().lower()
    if response not in ['oui', 'o', 'yes', 'y']:
        print("\n❌ Migration annulée.")
        return
    
    # Migration des likes
    likes_migrated, likes_skipped, likes_errors = migrate_likes()
    
    # Migration des dislikes
    dislikes_migrated, dislikes_skipped, dislikes_errors = migrate_dislikes()
    
    # Résumé final
    print("\n" + "="*80)
    print("  RÉSUMÉ FINAL")
    print("="*80 + "\n")
    
    total_migrated = likes_migrated + dislikes_migrated
    total_skipped = likes_skipped + dislikes_skipped
    total_errors = likes_errors + dislikes_errors
    
    print(f"📊 Total:")
    print(f"   ✅ Migrés: {total_migrated} interactions")
    print(f"   ⏭️  Déjà existants: {total_skipped}")
    print(f"   ❌ Erreurs: {total_errors}")
    
    if total_errors == 0:
        print(f"\n🎉 MIGRATION RÉUSSIE!")
    else:
        print(f"\n⚠️  Migration terminée avec {total_errors} erreurs")
    
    # Vérification pour Marie
    print("\n")
    verify_migration("marie.claire@test.com")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
