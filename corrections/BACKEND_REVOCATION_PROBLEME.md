# 🔴 Problème Backend : Révocation d'interactions ne fonctionne pas

## Symptômes observés

1. **Les profils révoqués ne réapparaissent PAS dans la découverte**
   - L'utilisateur annule un like/pass
   - Le frontend envoie `POST /api/v1/discovery/interactions/{id}/revoke`
   - Le backend retourne 200 OK
   - **MAIS** ensuite `GET /api/v1/discovery/profiles/` retourne toujours 0 profils

2. **Les listes semblent statiques**
   - Les mêmes profils apparaissent dans likes ET passes
   - Suspicion que les données ne reflètent pas l'état réel de la DB

## Logs frontend montrant le problème

```
📢 InteractionHistoryBloc: Notification révocation profil 51cd2e63-5a3c-4a8e-aee2-9495950652fd
📢 AppEvents: Interaction révoquée pour profil 51cd2e63-5a3c-4a8e-aee2-9495950652fd
🔔 DiscoveryBloc: Reçu notification révocation profil 51cd2e63-5a3c-4a8e-aee2-9495950652fd
🔄 DEBUG MatchRepositoryImpl: getDiscoveryProfiles - limit: 20
🔄 DEBUG MatchRepositoryImpl: Réponse reçue - status: 200
🔄 DEBUG MatchRepositoryImpl: Payload: {count: 0, results: []}  <-- ❌ TOUJOURS 0 !
```

## Cause probable

Le backend ne **supprime PAS** les interactions révoquées de la table `InteractionHistory` (ou ne les marque pas comme `is_revoked=True`).

**Résultat** : Le système de découverte considère toujours que l'utilisateur a déjà interagi avec ces profils, donc il ne les retourne pas.

## Solution Backend requise

### 1. Endpoint de révocation : `POST /api/v1/discovery/interactions/{id}/revoke`

**ACTUELLEMENT** :
```python
def revoke_interaction(request, interaction_id):
    interaction = InteractionHistory.objects.get(id=interaction_id, user=request.user)
    # ❌ Probablement juste interaction.delete() ou rien
    return Response(status=200)
```

**DOIT ÊTRE** :
```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_interaction(request, interaction_id):
    try:
        interaction = InteractionHistory.objects.get(
            id=interaction_id,
            user=request.user
        )
        
        # Option 1: Marquer comme révoqué (préférable pour l'historique)
        interaction.is_revoked = True
        interaction.revoked_at = timezone.now()
        interaction.save()
        
        # OU Option 2: Supprimer complètement
        # interaction.delete()
        
        return Response({
            'detail': 'Interaction révoquée avec succès',
            'profile_id': str(interaction.target_user.id)
        }, status=200)
        
    except InteractionHistory.DoesNotExist:
        return Response({'error': 'Interaction non trouvée'}, status=404)
```

### 2. Logique de découverte : `GET /api/v1/discovery/profiles/`

**ACTUELLEMENT** :
```python
# Exclut TOUTES les interactions (même révoquées)
already_interacted = InteractionHistory.objects.filter(
    user=request.user
).values_list('target_user_id', flat=True)
```

**DOIT ÊTRE** :
```python
# Exclut SEULEMENT les interactions actives (non révoquées)
already_interacted = InteractionHistory.objects.filter(
    user=request.user,
    is_revoked=False  # <-- IMPORTANT !
).values_list('target_user_id', flat=True)
```

### 3. Migration nécessaire

Ajouter le champ `is_revoked` au modèle `InteractionHistory` :

```python
# matching/migrations/XXXX_add_revoke_fields.py
from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):
    dependencies = [
        ('matching', 'previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='interactionhistory',
            name='is_revoked',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='interactionhistory',
            name='revoked_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
```

### 4. Modèle à jour

```python
# matching/models.py
class InteractionHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interactions')
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_interactions')
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_match = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False, db_index=True)  # ✅ NOUVEAU
    revoked_at = models.DateTimeField(null=True, blank=True)         # ✅ NOUVEAU
    
    class Meta:
        db_table = 'interaction_history'
        indexes = [
            models.Index(fields=['user', 'is_revoked']),  # Pour requêtes rapides
        ]
```

## Tests à effectuer après correction

1. **Tester la révocation d'un like** :
   ```
   1. Utilisateur like le profil A
   2. Le profil A disparaît de la découverte
   3. Utilisateur va dans "Profils likés" → Annule le like
   4. Le profil A réapparaît immédiatement dans la découverte ✅
   ```

2. **Tester la révocation d'un pass** :
   ```
   1. Utilisateur passe (dislike) le profil B
   2. Le profil B disparaît de la découverte
   3. Utilisateur va dans "Profils passés" → Annule le pass
   4. Le profil B réapparaît immédiatement dans la découverte ✅
   ```

3. **Vérifier les compteurs** :
   ```
   - Révoquer un like ne doit PAS recréditer le compteur de likes quotidiens
   - C'est intentionnel (comme Tinder/Bumble)
   ```

## Validation

Après correction backend, les logs frontend doivent montrer :
```
📢 AppEvents: Interaction révoquée pour profil XXX
🔔 DiscoveryBloc: Reçu notification révocation profil XXX
🔄 DEBUG MatchRepositoryImpl: Réponse reçue - status: 200
🔄 DEBUG MatchRepositoryImpl: Payload: {count: 1, results: [{...}]}  ✅ Au moins 1 profil !
✅ DEBUG DiscoveryBloc: Profils récupérés: 1
```

## Priorité

🔴 **HAUTE** - Fonctionnalité bloquante pour l'expérience utilisateur
