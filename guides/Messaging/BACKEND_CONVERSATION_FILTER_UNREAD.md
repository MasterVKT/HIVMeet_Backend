# Backend requis — Filtre `unread` sur la liste des conversations

**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`, §4.3 « Contrats — écarts frontend doc vs backend réel »). Non bloquant pour la session actuelle (le frontend n'expose actuellement aucun sélecteur de filtre dans `ConversationsPage` — le menu « more_vert » qui aurait pu l'exposer a été retiré faute de spécification produit claire, voir `AUDIT_MESSAGES_PAGE.md` §11.7). Ce fichier documente le gap pour une itération future.

---

## 1. État actuel exact (vérifié dans le code backend réel)

```python
# messaging/views.py::ConversationListView.get_queryset, lignes 57-73
def get_queryset(self):
    user = self.request.user
    queryset = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        status=Match.ACTIVE,
    ).exclude(
        last_message_at__isnull=True,
    ).select_related('user1__profile', 'user2__profile').order_by('-last_message_at')

    status_filter = self.request.query_params.get('status')
    if status_filter == 'archived':
        return queryset.none()
    return queryset
```

`MessagingApi.getConversations` (frontend, `lib/data/datasources/remote/messaging_api.dart`) envoie déjà un paramètre `status` avec les valeurs possibles `"all"|"unread"|"archived"` (commentaire dans le code), mais **seul `archived` est géré côté backend** (et retourne toujours une liste vide — voir aussi `BACKEND_MESSAGING_DELETE_CONVERSATION.md` pour le sujet archivage). `status=unread` n'est **pas du tout traité** : le paramètre est silencieusement ignoré et la vue retourne toutes les conversations, peu importe leur statut de lecture.

`Match.get_unread_count(user)` existe déjà et est utilisé par `ConversationSerializer.get_unread_count_for_me` (`messaging/serializers.py`, ligne 117-122) — la donnée nécessaire pour filtrer est donc disponible, juste pas exploitée côté queryset.

## 2. Problème

Aucun filtre serveur pour n'afficher que les conversations avec messages non lus. Si un futur écran/filtre frontend en a besoin, il faudrait aujourd'hui filtrer côté client après avoir chargé toutes les pages — inefficace et contraire au pattern de pagination déjà en place.

## 3. Fix prescrit

`Match.get_unread_count(user)` doit être inspecté pour savoir s'il s'appuie sur un champ dénormalisé (`unread_count_user1`/`unread_count_user2` typiquement) ou sur une requête calculée à la volée. En supposant un champ dénormalisé par utilisateur (pattern le plus probable vu `match.increment_unread(recipient)`/`match.reset_unread(user)` déjà utilisés dans `messaging/services.py`) :

```python
# messaging/views.py::ConversationListView.get_queryset

def get_queryset(self):
    user = self.request.user
    queryset = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        status=Match.ACTIVE,
    ).exclude(
        last_message_at__isnull=True,
    ).select_related('user1__profile', 'user2__profile').order_by('-last_message_at')

    status_filter = self.request.query_params.get('status')
    if status_filter == 'archived':
        return queryset.none()

    if status_filter == 'unread':
        # Filtrer sur le compteur non-lu spécifique à `user` (unread_count_user1
        # si user == user1, unread_count_user2 si user == user2). Utiliser une
        # annotation conditionnelle pour rester en une seule requête.
        queryset = queryset.annotate(
            unread_for_me=Case(
                When(user1=user, then=F('unread_count_user1')),
                When(user2=user, then=F('unread_count_user2')),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).filter(unread_for_me__gt=0)

    return queryset
```

*(Adapter les noms de champs `unread_count_user1`/`unread_count_user2` aux noms réels utilisés par `Match.increment_unread`/`Match.reset_unread`/`Match.get_unread_count` dans `matching/models.py` — non lus lors de cette session car hors périmètre `messaging/`, à vérifier par l'équipe backend avant d'appliquer ce patch.)*

Ajouter les imports nécessaires en haut de `messaging/views.py` : `from django.db.models import Case, When, Value, IntegerField, F`.

## 4. Impact frontend (si/quand ce filtre est implémenté)

- `MessagingApi.getConversations` envoie déjà `status` — aucun changement de contrat nécessaire côté client pour ce paramètre précis.
- Il faudrait exposer un sélecteur de filtre dans `ConversationsPage` (actuellement retiré, voir menu « more_vert » supprimé) — décision produit à prendre séparément sur la pertinence UX d'un tel filtre.
- `ConversationsBloc`/`GetConversationsParams` n'a actuellement aucun champ `status` — à ajouter si ce filtre est un jour exposé côté UI.

## 5. Critères de validation

- `GET /conversations/?status=unread` retourne uniquement les conversations où `unread_count_for_me > 0` pour l'utilisateur authentifié.
- `GET /conversations/` (sans filtre) et `GET /conversations/?status=all` continuent de retourner toutes les conversations actives, comportement inchangé.
- La pagination (`page`/`page_size`) continue de fonctionner correctement combinée au filtre.
