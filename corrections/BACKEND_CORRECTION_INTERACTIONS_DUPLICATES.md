# BACKEND - Correction des Doublons d'Interactions

**Version**: 1.0  
**Date**: 24 Mars 2026  
**Priorité**: HAUTE  
**Module**: Discovery / Interactions  
**Statut**: Action requise côté backend

---

## 📋 Table des Matières

1. [Description du Problème](#description-du-problème)
2. [Analyse des Causes](#analyse-des-causes)
3. [Spécifications Attendues](#spécifications-attendues)
4. [Solutions Proposées](#solutions-proposées)
5. [Code Backend à Implémenter](#code-backend-à-implémenter)
6. [Script de Nettoyage](#script-de-nettoyage)
7. [Tests de Validation](#tests-de-validation)
8. [Checklist de Correction](#checklist-de-correction)

---

## 🔴 Description du Problème

### Symptômes Observés
- Des profils qui ont déjà été "likés" ou "passés" apparaissent à nouveau dans la liste de découverte
- L'utilisateur voit des profils qu'il a déjà consultés précédemment
- Cela crée une mauvaise expérience utilisateur et de la confusion

### Impact sur l'Expérience Utilisateur
- ❌ Perception que l'application ne fonctionne pas correctement
- ❌ Gaspillage des likes gratuits sur des profils déjà vus
- ❌ Perte de confiance dans le système de matching

---

## 🔍 Analyse des Causes

### Cause N°1 : Interactions non persistées correctement

Lors d'un like ou d'un pass, l'interaction n'est peut-être pas correctement enregistrée dans la base de données, ce qui permet au profil de revenir.

### Cause N°2 : Doublons dans la table Interactions

Il peut y avoir des entrées en double pour les mêmes interactions (même utilisateur et même profil cible), ce qui peut perturber la logique d'exclusion.

### Cause N°3 : Logique d'exclusion défectueuse

Le endpoint `GET /discovery/` utilise peut-être une logique incorrecte pour exclure les profils déjà likés/passés :

```python
# Exemple de logique potentiellement incorrecte
already_interacted = Interaction.objects.filter(
    from_user=request.user,
    to_user__in=profiles  # Cette condition peut être incorrecte
)
```

### Cause N°4 : Cache non invalidée

Les profils consultés sont mis en cache mais le cache n'est pas invalidé après une interaction.

### Cause N°5 : Problème de relation entre modèles

La relation entre `Interaction`, `Profile` et `User` peut être mal définie, causant des problèmes de filtrage.

---

## 📋 Spécifications Attendues

### Comportement Correct
1. **Un profil liké ne doit jamais revenir** dans la découverte
2. **Un profil passé (dislike) ne doit jamais revenir** dans la découverte
3. **Après un "rewind"**, le profil doit revenir dans la découverte
4. **Après une "révocation"**, le profil doit revenir dans la découverte

### Requêtes SQL Attendues

```python
# Pour exclure les profils déjà likés ou passés :
excluded_profile_ids = Interaction.objects.filter(
    from_user=request.user,
    is_revoked=False  # Ne pas inclure les interactions révoquées
).values_list('to_user_id', flat=True)

# Profilrest à afficher = tous les profils - profils exclus
available_profiles = Profile.objects.exclude(
    user_id__in=excluded_profile_ids
).exclude(
    user=request.user  # Exclure son propre profil
)
```

---

## 🛠️ Solutions Proposées

### Solution 1 : Corriger la création des interactions

S'assurer que chaque like/pass crée une seule entrée dans la table Interactions :

```python
@transaction.atomic
def create_interaction(user, target_profile, interaction_type):
    # Vérifier si une interaction existe déjà
    existing = Interaction.objects.filter(
        from_user=user,
        to_user=target_profile.user,
        interaction_type=interaction_type
    ).first()
    
    if existing:
        if existing.is_revoked:
            # Restaurer l'interaction existante
            existing.is_revoked = False
            existing.save()
        return existing
    
    # Créer une nouvelle interaction
    return Interaction.objects.create(
        from_user=user,
        to_user=target_profile.user,
        interaction_type=interaction_type,
        is_revoked=False
    )
```

### Solution 2 : Implémenter une méthode de nettoyage des doublons

Créer un script de nettoyage pour supprimer les doublons :

```python
def clean_duplicate_interactions(user_id):
    """
    Supprime les interactions en double pour un utilisateur.
    Garde seulement la première interaction pour chaque profil cible.
    """
    from django.db.models import Min
    from apps.discovery.models import Interaction
    
    # Trouver les ID des premières interactions pour chaque profil cible
    first_interactions = Interaction.objects.filter(
        from_user_id=user_id
    ).values(
        'to_user_id', 'interaction_type'
    ).annotate(
        min_id=Min('id')
    ).values_list('min_id', flat=True)
    
    # Supprimer toutes les autres interactions
    deleted_count = Interaction.objects.filter(
        from_user_id=user_id
    ).exclude(
        id__in=first_interactions
    ).delete()[0]
    
    return deleted_count
```

### Solution 3 : Corriger la logique d'exclusion dans le endpoint Discovery

```python
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_discovery_profiles(request):
    """
    Retourne les profils à découvrir pour l'utilisateur.
    """
    user = request.user
    
    # Récupérer TOUS les profils avec lesquels l'utilisateur a déjà interagi
    # (likes, dislikes, super likes) - en excluant les interactions révoquées
    interacted_profile_ids = Interaction.objects.filter(
        from_user=user,
        is_revoked=False
    ).values_list('to_user_id', flat=True).distinct()
    
    # Exclure ces profils + le profil de l'utilisateur
    available_profiles = Profile.objects.filter(
        user__is_active=True,
        is_visible=True
    ).exclude(
        user_id__in=interacted_profile_ids
    ).exclude(
        user=user
    )
    
    # Appliquer les filtres supplémentaires
    # ...
    
    return available_profiles
```

### Solution 4 : Ajouter des index de base de données

S'assurer que les colonnes utilisées pour le filtrage sont indexées :

```python
# Dans models.py
class Interaction(models.Model):
    from_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='interactions_sent',
        db_index=True  # IMPORTANT
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_received',
        db_index=True  # IMPORTANT
    )
    interaction_type = models.CharField(
        max_length=20,
        db_index=True  # IMPORTANT
    )
    is_revoked = models.BooleanField(
        default=False,
        db_index=True  # IMPORTANT
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True  # IMPORTANT
    )
```

---

## 💻 Code Backend à Implémenter

### Fichier: `apps/discovery/services/interaction_service.py`

```python
from django.db.models import Min, Count, Q
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.discovery.models import Interaction, Profile
from apps.users.models import User


class InteractionService:
    """Service pour gérer les interactions de découverte."""
    
    @staticmethod
    @transaction.atomic
    def create_or_update_interaction(user, target_profile, interaction_type):
        """
        Crée ou met à jour une interaction.
        
        Args:
            user: L'utilisateur qui effectue l'interaction
            target_profile: Le profil cible
            interaction_type: 'like', 'dislike', 'super_like'
            
        Returns:
            Interaction: L'interaction créée ou mise à jour
        """
        target_user = target_profile.user
        
        # Vérifier si une interaction existe déjà
        existing = Interaction.objects.filter(
            from_user=user,
            to_user=target_user,
            interaction_type=interaction_type
        ).first()
        
        if existing:
            if existing.is_revoked:
                # Restaurer l'interaction existante
                existing.is_revoked = False
                existing.save()
            return existing
        
        # Créer une nouvelle interaction
        return Interaction.objects.create(
            from_user=user,
            to_user=target_user,
            interaction_type=interaction_type,
            is_revoked=False
        )
    
    @staticmethod
    def get_excluded_profile_ids(user):
        """
        Retourne les IDs des profils avec lesquels l'utilisateur a déjà interagi.
        
        Args:
            user: L'utilisateur connecté
            
        Returns:
            set: IDs des profils à exclure
        """
        # Ne pas inclure les interactions révoquées
        return set(
            Interaction.objects.filter(
                from_user=user,
                is_revoked=False
            ).values_list('to_user_id', flat=True).distinct()
        )
    
    @staticmethod
    def clean_duplicate_interactions(user_id):
        """
        Supprime les interactions en double pour un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            int: Nombre d'interactions supprimées
        """
        # Trouver les ID des premières interactions pour chaque profil cible
        first_interactions = Interaction.objects.filter(
            from_user_id=user_id
        ).values(
            'to_user_id', 'interaction_type'
        ).annotate(
            min_id=Min('id')
        ).values_list('min_id', flat=True)
        
        # Supprimer toutes les autres interactions
        deleted_count = Interaction.objects.filter(
            from_user_id=user_id
        ).exclude(
            id__in=first_interactions
        ).delete()[0]
        
        return deleted_count
    
    @staticmethod
    def has_interacted_with(user, target_user_id):
        """
        Vérifie si l'utilisateur a déjà interagi avec un profil.
        
        Args:
            user: L'utilisateur connecté
            target_user_id: ID du profil cible
            
        Returns:
            bool: True si une interaction existe
        """
        return Interaction.objects.filter(
            from_user=user,
            to_user_id=target_user_id,
            is_revoked=False
        ).exists()
    
    @staticmethod
    def get_interaction_type(user, target_user_id):
        """
        Retourne le type dinteraction avec un profil.
        
        Args:
            user: L'utilisateur connecté
            target_user_id: ID du profil cible
            
        Returns:
            str or None: Type d'interaction ('like', 'dislike', 'super_like')
        """
        interaction = Interaction.objects.filter(
            from_user=user,
            to_user_id=target_user_id,
            is_revoked=False
        ).first()
        
        return interaction.interaction_type if interaction else None
```

### Modification du Endpoint Discovery: `apps/discovery/views.py`

```python
from apps.discovery.services.interaction_service import InteractionService


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_discovery_profiles(request):
    """
    Retourne les profils à découvrir pour l'utilisateur.
    
    GET /api/v1/discovery/
    
    Paramètres:
        - page: Numéro de page
        - per_page: Nombre de profils par page
        - latitude: Latitude (optionnel)
        - longitude: Longitude (optionnel)
    
    Response:
        {
            "profiles": [...],
            "pagination": {...}
        }
    """
    user = request.user
    
    # IMPORTANT: Obtenir les IDs des profils à exclure
    excluded_profile_ids = InteractionService.get_excluded_profile_ids(user)
    
    # Logger pour debug
    print(f"[DISCOVERY] User {user.id}: {len(excluded_profile_ids)} profiles excluded")
    
    # Requête de base : exclure les profils déjà interagis
    queryset = Profile.objects.filter(
        user__is_active=True,
        is_visible=True
    ).exclude(
        user_id__in=excluded_profile_ids
    ).exclude(
        user=user
    ).select_related('user')
    
    # Appliquer les filtres supplémentaires (âge, genre, distance, etc.)
    # ...
    
    # Pagination
    page = int(request.query_params.get('page', 1))
    per_page = int(request.query_params.get('per_page', 10))
    
    start = (page - 1) * per_page
    end = start + per_page
    
    profiles = queryset[start:end]
    
    return Response({
        'profiles': [profile.to_discovery_dict() for profile in profiles],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': queryset.count(),
            'has_next': queryset.count() > end
        }
    })
```

### Modification des Endpoints de Like/Dislike: `apps/discovery/views.py`

```python
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic
def send_like(request):
    """
    Endpoint pour envoyer un like à un profil.
    """
    user = request.user
    target_profile_id = request.data.get('target_profile_id')
    
    # ... validation ...
    
    # Créer linteraction en utilisant le service
    interaction = InteractionService.create_or_update_interaction(
        user=user,
        target_profile=target_profile,
        interaction_type='like'
    )
    
    # Vérifier si c'est un match
    # ...
    
    return Response({
        'result': 'like_sent',
        'daily_likes_remaining': DailyLikesService.get_likes_remaining(user),
        # ...
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@transaction.atomic
def send_dislike(request):
    """
    Endpoint pour envoyer un dislike à un profil.
    """
    user = request.user
    target_profile_id = request.data.get('target_profile_id')
    
    # ... validation ...
    
    # Créer linteraction en utilisant le service
    interaction = InteractionService.create_or_update_interaction(
        user=user,
        target_profile=target_profile,
        interaction_type='dislike'
    )
    
    return Response({
        'result': 'dislike_sent',
        # ...
    })
```

---

## 🧹 Script de Nettoyage

### Fichier: `clean_interaction_duplicates.py`

```python
#!/usr/bin/env python
"""
Script pour nettoyer les doublons d'interactions dans la base de données.
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet.settings')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'env', 'hivmeet_backend'))
django.setup()

from django.db.models import Min
from apps.discovery.models import Interaction


def clean_duplicate_interactions():
    """Nettoie les interactions en double pour tous les utilisateurs."""
    
    print("=== Nettoyage des doublons d'interactions ===\n")
    
    # Obtenir tous les utilisateurs uniques
    users = Interaction.objects.values_list('from_user_id', flat=True).distinct()
    total_users = len(users)
    
    print(f"Nombre d'utilisateurs à traiter: {total_users}\n")
    
    total_deleted = 0
    
    for i, user_id in enumerate(users, 1):
        # Trouver les ID des premières interactions pour chaque profil cible
        first_interactions = Interaction.objects.filter(
            from_user_id=user_id
        ).values(
            'to_user_id', 'interaction_type'
        ).annotate(
            min_id=Min('id')
        ).values_list('min_id', flat=True)
        
        # Compter les doublons pour cet utilisateur
        duplicates = Interaction.objects.filter(
            from_user_id=user_id
        ).exclude(
            id__in=first_interactions
        ).count()
        
        if duplicates > 0:
            # Supprimer les doublons
            deleted = Interaction.objects.filter(
                from_user_id=user_id
            ).exclude(
                id__in=first_interactions
            ).delete()[0]
            
            total_deleted += deleted
            print(f"Utilisateur {user_id}: {deleted} doublons supprimés")
        
        # Afficher la progression
        if i % 10 == 0:
            print(f"Progression: {i}/{total_users} utilisateurs traités")
    
    print(f"\n=== Total: {total_deleted} interactions en double supprimées ===")


def verify_interactions():
    """Vérifie que chaque utilisateur n'a qu'une seule interaction par profil."""
    
    print("\n=== Vérification des interactions ===\n")
    
    users = Interaction.objects.values_list('from_user_id', flat=True).distinct()
    issues = []
    
    for user_id in users:
        # Grouper par profil cible et type d'interaction
        interactions = Interaction.objects.filter(
            from_user_id=user_id,
            is_revoked=False
        ).values('to_user_id', 'interaction_type').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if interactions:
            issues.append((user_id, list(interactions)))
    
    if issues:
        print(f"⚠️  {len(issues)} utilisateurs ont des problèmes:")
        for user_id, problem_list in issues[:10]:  # Afficher les 10 premiers
            print(f"  User {user_id}: {problem_list}")
    else:
        print("✅ Aucune anomalie trouvée!")
    
    return len(issues) == 0


if __name__ == '__main__':
    # Exécuter le nettoyage
    clean_duplicate_interactions()
    
    # Vérifier le résultat
    verify_interactions()
```

---

## 🧪 Tests de Validation

### Test 1 : Vérification de l'exclusion
```
Préconditions: Utilisateur avec des interactions existantes
Actions:
  1. Récupérer la liste des profils découverts
  
Résultats attendus:
  ✅ Aucun profil liké ou passé dans la liste
  ✅ Les profils avec interactions révoquées sont inclus
```

### Test 2 : Like après dislike
```
Préconditions: Profil disliké
Actions:
  1. Liker le profil
  
Résultats attendus:
  ✅ Linteraction dislike est marquée comme révoquée
  ✅ Une nouvelle interaction like est créée
  ✅ Le profil napparaît plus dans la découverte
```

### Test 3 : Rewind
```
Préconditions: Profil liké
Actions:
  1. Effectuer un rewind sur le profil
  
Résultats attendus:
  ✅ Linteraction like est marquée comme révoquée
  ✅ Le profil réapparaît dans la découverte
```

### Test 4 : Nettoyage des doublons
```
Préconditions: Interactions en double dans la base
Actions:
  1. Exécuter le script de nettoyage
  
Résultats attendus:
  ✅ Plus de doublons dans la table Interactions
  ✅ Chaque profil nest associé quà une seule interaction par type
```

---

## ✅ Checklist de Correction

### Backend (À faire par le développeur backend)

- [ ] **Créer le service `InteractionService`** dans `apps/discovery/services/`
- [ ] **Corriger la création des interactions** pour éviter les doublons
- [ ] **Corriger la logique d'exclusion** dans `get_discovery_profiles()`
- [ ] **Ajouter les index de base de données** sur les colonnes utilisées
- [ ] **Exécuter le script de nettoyage** `clean_interaction_duplicates.py`
- [ ] **Vérifier les interactions** après nettoyage
- [ ] **Ajouter des logs de debug** pour faciliter le diagnostic futur
- [ ] **Déployer les modifications** sur l'environnement de staging

### Tests à Effectuer

- [ ] **Test manuel**: Vérifier que les profils likés ne reapparaissent pas
- [ ] **Test manuel**: Vérifier que les profils dislikés ne reapparaissent pas
- [ ] **Test manuel**: Tester le workflow like → dislike → like
- [ ] **Test manuel**: Tester le rewind
- [ ] **Test automatisé**: Exécuter le script de nettoyage

---

## 📝 Notes Additionnelles

### Schéma de la table Interactions

```python
class Interaction(models.Model):
    INTERACTION_TYPES = [
        ('like', 'Like'),
        ('dislike', 'Dislike'),
        ('super_like', 'Super Like'),
    ]
    
    from_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_sent'
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_received'
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_TYPES
    )
    is_revoked = models.BooleanField(
        default=False,
        help_text="Indique si l'interaction a été annulée"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Contrainte d'unicité : un seul type dinteraction par profil cible
        unique_together = [
            ['from_user', 'to_user', 'interaction_type']
        ]
        indexes = [
            models.Index(fields=['from_user', 'is_revoked']),
            models.Index(fields=['to_user', 'is_revoked']),
            models.Index(fields=['created_at']),
        ]
```

### Commandes Django utiles

```bash
# Créer les migrations
python manage.py makemigrations discovery

# Appliquer les migrations
python manage.py migrate

# Nettoyer les doublons
python manage.py shell < clean_interaction_duplicates.py

# Vérifier les interactions
python manage.py shell < verify_interactions.py
```

---

## 🔗 Références

- Documentation API: `docs/FRONTEND_MATCHING_API.md`
- Modèle de données: `docs/Modèle de Données Frontend - HIVMeet.txt`

---

**Dernière mise à jour**: 24 Mars 2026  
**Créé par**: AI Agent (GitHub Copilot)  
**Pour**: Équipe de Développement HIVMeet Backend
