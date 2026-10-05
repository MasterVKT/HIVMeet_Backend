# Backend requis — Requêtes N+1 sur la liste des conversations

**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`, §3.4.14). Optimisation de performance — non bloquant fonctionnellement, mais impact direct sur la latence perçue de `ConversationsPage`, en particulier maintenant que le frontend a corrigé la pagination (§ voir le reste de la session) : chaque page de 20 conversations chargée génère désormais un nombre de requêtes SQL proportionnel, ce qui va se voir plus souvent qu'avant (l'infinite scroll fonctionnait mal — il rechargeait toujours la page 1 — donc ce coût N+1 était en pratique moins visité).

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
    ).select_related(
        'user1__profile',
        'user2__profile',
    ).order_by('-last_message_at')
    ...
```

`select_related('user1__profile', 'user2__profile')` évite le N+1 sur le profil lui-même, mais **pas sur les photos** :

```python
# messaging/serializers.py::ConversationSerializer.get_other_user, lignes 83-97
def get_other_user(self, obj):
    request = self.context.get('request')
    if request and request.user:
        other_user = obj.get_other_user(request.user)
        photo = other_user.profile.photos.filter(is_main=True).first() if hasattr(other_user, 'profile') else None
        return {
            'user_id': str(other_user.id),
            'display_name': other_user.display_name,
            'main_photo_url': photo.photo_url if photo else None,
            'is_online': (timezone.now() - other_user.last_active).total_seconds() < 300,
            'last_active': other_user.last_active,
        }
    return None
```

`other_user.profile.photos.filter(is_main=True).first()` déclenche **une requête SQL par conversation de la page** (20 requêtes pour une page de 20 résultats), en plus de :

```python
# messaging/serializers.py::ConversationSerializer.get_last_message, lignes 99-115
def get_last_message(self, obj):
    request = self.context.get('request')
    if not request:
        return None
    message = Message.objects.filter(match=obj).order_by('-created_at').first()
    ...
```

Une **deuxième** requête par conversation pour le dernier message. Au total, une page de 20 conversations génère environ **1 (liste) + 20 (photos) + 20 (dernier message) = 41 requêtes SQL**, alors qu'avec un prefetch correct cela devrait tenir en 3 requêtes.

## 2. Problème

Latence proportionnelle au nombre de conversations affichées, qui grandit linéairement avec `page_size`. Sur une base de données distante (production, pas SQLite local), chaque aller-retour réseau supplémentaire coûte plusieurs millisecondes — 40 requêtes séquentielles peuvent facilement ajouter 100-300ms à la réponse.

## 3. Fix prescrit

### 3.1 Photos — `Prefetch` avec queryset filtré

```python
# messaging/views.py — ajouter les imports
from django.db.models import Prefetch
from matching.models import Match

# profiles.models.Photo — vérifier le nom exact du related_name utilisé par
# `user.profile.photos` (probablement `Photo` avec related_name='photos' sur
# une FK vers Profile) avant d'appliquer ce patch.

def get_queryset(self):
    user = self.request.user
    photos_prefetch = Prefetch(
        'photos',
        queryset=Photo.objects.filter(is_main=True),
        to_attr='main_photo_list',
    )

    queryset = Match.objects.filter(
        Q(user1=user) | Q(user2=user),
        status=Match.ACTIVE,
    ).exclude(
        last_message_at__isnull=True,
    ).select_related(
        'user1__profile',
        'user2__profile',
    ).prefetch_related(
        Prefetch('user1__profile__photos', queryset=Photo.objects.filter(is_main=True), to_attr='main_photo_list'),
        Prefetch('user2__profile__photos', queryset=Photo.objects.filter(is_main=True), to_attr='main_photo_list'),
    ).order_by('-last_message_at')

    status_filter = self.request.query_params.get('status')
    if status_filter == 'archived':
        return queryset.none()
    return queryset
```

```python
# messaging/serializers.py::ConversationSerializer.get_other_user

def get_other_user(self, obj):
    request = self.context.get('request')
    if request and request.user:
        other_user = obj.get_other_user(request.user)
        profile = getattr(other_user, 'profile', None)
        # Utilise le prefetch (main_photo_list) au lieu d'une requête .filter().first()
        main_photos = getattr(profile, 'main_photo_list', None) if profile else None
        photo = main_photos[0] if main_photos else None
        return {
            'user_id': str(other_user.id),
            'display_name': other_user.display_name,
            'main_photo_url': photo.photo_url if photo else None,
            'is_online': (timezone.now() - other_user.last_active).total_seconds() < 300,
            'last_active': other_user.last_active,
        }
    return None
```

*(Le nom exact `Photo`, son `related_name`, et si le prefetch doit cibler `user1__profile__photos` ou une relation différente dépend du modèle `profiles.models` réel — non lu lors de cette session car hors périmètre `messaging/`. À adapter par l'équipe backend selon le schéma réel avant d'appliquer.)*

### 3.2 Dernier message — annotation ou prefetch, pas de requête par ligne

Option la plus simple sans changer la forme de la réponse : `Prefetch` avec un queryset ordonné + limité, consommé côté serializer :

```python
# messaging/views.py — ajouter au queryset
.prefetch_related(
    Prefetch('messages', queryset=Message.objects.order_by('-created_at'), to_attr='prefetched_messages'),
)
```

```python
# messaging/serializers.py::ConversationSerializer.get_last_message
def get_last_message(self, obj):
    request = self.context.get('request')
    if not request:
        return None

    prefetched = getattr(obj, 'prefetched_messages', None)
    message = prefetched[0] if prefetched else None
    if not message:
        return None

    return {
        'message_id': str(message.id),
        'content_preview': message.content[:100] if message.content else _('Media'),
        'sender_id': str(message.sender_id),
        'sent_at': message.created_at,
        'is_read_by_me': message.sender == request.user or message.status == Message.READ,
    }
```

**Attention** : `Prefetch('messages', queryset=Message.objects.order_by('-created_at'), to_attr='prefetched_messages')` sans limite va charger **tous** les messages de chaque conversation en mémoire (juste pour n'en garder qu'un). Pour une conversation avec des milliers de messages, c'est pire que le N+1 initial. Deux approches plus sûres :
- Utiliser une sous-requête annotée (`Subquery`/`OuterRef`) pour ne récupérer que l'ID du dernier message par conversation, puis un second `Message.objects.filter(id__in=...)` pour les charger tous en une requête.
- Ou accepter le compromis : le N+1 sur le dernier message est moins grave que celui sur les photos (une seule colonne consultée), et prioriser uniquement le fix des photos (3.1) si le temps est limité.

**Recommandation** : appliquer 3.1 (photos) en priorité — c'est le gain le plus sûr et le moins risqué. Pour 3.2 (dernier message), utiliser l'approche `Subquery`/`OuterRef` si le volume de messages par conversation est significatif en production, sinon le prefetch simple avec limite explicite (`Message.objects.order_by('-created_at')[:1]` par sous-requête corrélée) suffit.

## 4. Impact frontend

Aucun. Le contrat de réponse JSON (`ConversationSerializer`) reste strictement identique — c'est une optimisation interne pure.

## 5. Critères de validation

- Avec `django-debug-toolbar` ou `django.db.connection.queries` en DEBUG, `GET /conversations/?page=1&page_size=20` génère un nombre de requêtes **constant** (indépendant du nombre de conversations retournées), pas proportionnel.
- Le contenu de la réponse JSON (`other_user.main_photo_url`, `last_message.*`) reste identique à avant l'optimisation — vérifier avec un test de non-régression comparant la réponse avant/après sur un jeu de données fixe.
