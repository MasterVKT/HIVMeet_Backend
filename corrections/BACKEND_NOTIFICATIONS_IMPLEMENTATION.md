# Implémentation Backend — Système de Notifications HIVMeet

**Version** : 1.0  
**Date** : 2026-06-10  
**Auteur** : Rapport généré pour agent IA backend  
**Contexte frontend** : Implémentation frontend complète livrée en parallèle (voir ci-dessous)

---

## 1. Contexte & État Actuel

### Ce qui existe côté backend

| Composant | Fichier | Statut |
|-----------|---------|--------|
| Endpoint enregistrement token FCM | `authentication/views.py` → `RegisterFCMTokenView` | ✅ Opérationnel |
| Endpoint suppression token FCM | `authentication/views.py` → `RemoveFCMTokenView` | ✅ Opérationnel |
| URL pattern | `authentication/urls.py` → `fcm-token` | ✅ Opérationnel |
| `User.add_fcm_token()` | `authentication/models.py` | ✅ Opérationnel |
| Signal `handle_new_match` | `matching/signals.py` | ✅ Fire Celery + WS `user_{id}` |
| Signal `handle_like_notification` | `matching/signals.py` | ✅ Fire Celery + WS `user_{id}` |
| Task `send_match_notification` | `matching/tasks.py` | ✅ FCM multicast |
| Task `send_like_notification` | `matching/tasks.py` | ⚠️ Premium-gaté (voir §2.1) |
| Task `send_new_message_notification` | `messaging/tasks.py` (à vérifier) | ❓ À vérifier |

### Ce qui est implémenté côté frontend (livraison simultanée)

- `NotificationService` : init FCM, `requestPermission`, `onMessage`, `onMessageOpenedApp`, `getInitialMessage`, token refresh, registration/suppression via `/auth/fcm-token`.
- `NotificationsLocalStore` : persistence locale `shared_preferences`, 100 entrées max.
- `NotificationsBloc` : fusionne store local + nouveaux matches + conversations non lues. Expose `unreadCount` pour badge.
- `NotificationsPage` : liste, tap→navigation, pull-to-refresh, état vide, "tout marquer lu".
- Route `/notifications` enregistrée dans go_router.
- Icône cloche + badge rouge dans l'AppBar des onglets Matches et Messages.
- `AndroidManifest.xml` : `POST_NOTIFICATIONS` ajouté.
- **Navigation sur tap** :
  - `new_match` → `/matches`
  - `new_message` → `/chat/{conversation_id}`
  - `like` / `super_like` → `/notifications`

### Payload FCM attendu par le frontend

Le frontend lit `message.data` (pas `notification`). Les clés **exactes** à fournir dans le payload `data` :

```json
{
  "type": "new_match | new_message | like | super_like | system",
  "notification_id": "uuid-unique-pour-dedup",
  "title": "Texte affiché dans la notif locale",
  "body": "Corps de la notification",
  "conversation_id": "uuid-du-match (= conversation_id si type=new_message)",
  "match_id": "uuid-du-match (si type=new_match)",
  "from_user_id": "uuid-de-l-expéditeur (si type=like|super_like|new_message)"
}
```

> **Important** : Toujours renseigner `notification_id` pour que le store local déduplique correctement. Utiliser `str(uuid.uuid4())` ou `f"{type}_{object_id}"`.

---

## 2. Blocages à Corriger

### 2.1 Gate premium sur le push « like »

**Fichier** : `matching/tasks.py`, lignes 72-73

```python
# PROBLÈME ACTUEL
if not user.is_premium:
    return
```

Ce garde supprime la notification **pour tous les utilisateurs non-premium**, indépendamment de leurs préférences. L'intention probable était : les utilisateurs non-premium ne *voient pas* qui les a likés (fonctionnalité premium), mais ils devraient quand même recevoir une notification anonymisée "Quelqu'un vous a liké".

**Correction requise** :

Remplacer le bloc `if not user.is_premium: return` par une logique respectant les préférences :

```python
# CORRECTION
notification_settings = user.profile.notification_settings  # dict JSON
if not notification_settings.get('profile_like_notifications', True):
    return  # L'utilisateur a désactivé les notifs de like dans ses paramètres

# Construire le payload selon le niveau premium
if user.is_premium:
    # Premium : révèle l'identité du lieur
    title = f"{from_user.profile.display_name} vous a {'super liké' if is_super else 'liké'} !"
    body = "Cliquez pour voir son profil"
    from_user_id_payload = str(from_user.id)
else:
    # Non-premium : notification anonymisée
    title = "Quelqu'un vous a liké !"
    body = "Passez Premium pour voir qui vous a liké"
    from_user_id_payload = ""  # Ne pas révéler l'identité

notification_type = "super_like" if is_super else "like"
# Continuer avec l'envoi FCM (voir §2.3)
```

### 2.2 Groupe WS `user_{id}` sans consumer abonné

**Problème** : `matching/signals.py` diffuse sur `channel_layer.group_send(f"user_{user.id}", ...)` pour les likes et matches. Mais `hivmeet_backend/asgi.py` ne route que `ws/conversations/<uuid>/` vers `ConversationConsumer`. Le groupe `user_{id}` n'a **aucun abonné** — ces messages sont perdus.

**Correction requise** : Créer un `UserNotificationConsumer` et l'enregistrer dans le routeur ASGI.

#### 2.2.1 Nouveau consumer — `notifications/consumers.py`

Créer le fichier `hivmeet_backend/notifications/consumers.py` (ou dans `matching/` si pas de nouvelle app) :

```python
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
# Réutiliser le même mécanisme d'auth JWT que messaging/consumers.py
# (extraire la méthode _authenticate_user dans un module partagé ou la dupliquer)

User = get_user_model()

class UserNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer pour les notifications temps réel d'un utilisateur.
    URL : ws/notifications/
    Auth : JWT token via query param ?token=<jwt> (même pattern que ConversationConsumer)
    Groupe channel : user_{user_id}
    """

    async def connect(self):
        # 1. Authentifier via JWT (même logique que ConversationConsumer._authenticate_user)
        await self._authenticate_user()
        if not hasattr(self, 'user') or not self.user:
            await self.close(code=4000)
            return

        self.group_name = f"user_{self.user.id}"

        # 2. Rejoindre le groupe personnel
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Handler appelé par group_send depuis signals.py
    async def new_match(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_match",
            "match_id": event.get("match_id"),
            "other_user": event.get("other_user"),
            "timestamp": event.get("timestamp"),
        }))

    async def like(self, event):
        await self.send(text_data=json.dumps({
            "type": "like",
            "from_user_id": event.get("from_user_id"),  # vide si non-premium
            "is_super": event.get("is_super", False),
            "timestamp": event.get("timestamp"),
        }))

    async def super_like(self, event):
        await self.like({**event, "is_super": True})

    async def new_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_message",
            "conversation_id": event.get("conversation_id"),
            "from_user_id": event.get("from_user_id"),
            "preview": event.get("preview"),
            "timestamp": event.get("timestamp"),
        }))

    async def _authenticate_user(self):
        """
        Extrait et valide le JWT depuis query string.
        Copier/extraire depuis messaging/consumers.py ConversationConsumer._authenticate_user.
        Stocker dans self.user.
        """
        # TODO: extraire la logique JWT dans un module partagé
        # channels/auth_utils.py → authenticate_websocket_user(scope) -> User | None
        pass
```

#### 2.2.2 Enregistrer dans `asgi.py`

```python
# hivmeet_backend/asgi.py — modifications
from messaging.consumers import ConversationConsumer
from notifications.consumers import UserNotificationConsumer  # ou matching.consumers

websocket_urlpatterns = [
    path('ws/conversations/<uuid:conversation_id>/', ConversationConsumer.as_asgi()),
    path('ws/notifications/', UserNotificationConsumer.as_asgi()),
]
```

#### 2.2.3 Format des events `group_send` dans `signals.py`

Les `group_send` existants dans `signals.py` doivent avoir un champ `type` qui correspond exactement au nom de méthode du consumer (avec `_` remplaçant `-`) :

```python
# Pour un like (signals.py handle_like_notification)
await channel_layer.group_send(
    f"user_{to_user.id}",
    {
        "type": "like",          # → consumer.like()
        "from_user_id": str(from_user.id) if to_user.is_premium else "",
        "is_super": is_super_like,
        "timestamp": timezone.now().isoformat(),
    }
)

# Pour un match (signals.py handle_new_match)
await channel_layer.group_send(
    f"user_{user.id}",
    {
        "type": "new_match",     # → consumer.new_match()
        "match_id": str(match.id),
        "other_user": {
            "id": str(other_user.id),
            "display_name": other_user.profile.display_name,
            "photo_url": other_user.profile.main_photo_url,
        },
        "timestamp": timezone.now().isoformat(),
    }
)
```

### 2.3 Tokens FCM vides / périmés

**Problème** : `send_match_notification` / `send_like_notification` lisent `user.fcm_tokens`. Si vide → pas de push. Si token périmé → FCM retourne une erreur que le backend ne gère pas.

**Corrections** :

1. **Flux d'enregistrement** : Le frontend appelle `POST /auth/fcm-token` au login. Vérifier que `User.add_fcm_token()` déduplique correctement par `(fcm_token, device_type)`.

2. **Purge des tokens invalides** : Après un envoi FCM multicast, inspecter `batch_response.responses` et supprimer les tokens qui retournent `registration-token-not-registered` ou `invalid-registration-token` :

```python
# Dans matching/tasks.py, après batch_response = messaging.send_each_for_multicast(message)
for idx, response in enumerate(batch_response.responses):
    if not response.success:
        error_code = response.exception.code if response.exception else None
        if error_code in ('registration-token-not-registered', 'invalid-registration-token'):
            invalid_token = registration_tokens[idx]
            # Supprimer le token de la liste de l'utilisateur
            user.fcm_tokens = [t for t in user.fcm_tokens if t.get('token') != invalid_token]
            user.save(update_fields=['fcm_tokens'])
```

---

## 3. Endpoint REST de Notifications (Source Serveur)

> **Priorité** : Optionnel dans un premier temps — le frontend fonctionne via store local. Implémenter pour remplacer le store dérivé par une vraie source serveur.  
> Quand livré, signaler au frontend pour qu'il bascule `NotificationsBloc.LoadNotifications` vers cet endpoint (TODO déjà en place dans le code).

### 3.1 Modèle Django

**App** : Créer `hivmeet_backend/notifications/` (ou ajouter dans `matching/`) :

**`notifications/models.py`** :

```python
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    TYPES = [
        ('new_match', 'Nouveau match'),
        ('new_message', 'Nouveau message'),
        ('like', 'Like reçu'),
        ('super_like', 'Super like reçu'),
        ('system', 'Système'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications'
    )
    type = models.CharField(max_length=20, choices=TYPES)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict)  # match_id, conversation_id, from_user_id, etc.
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.type}] {self.user.email} - {self.title}"
```

**Migration** : `python manage.py makemigrations notifications && python manage.py migrate`

### 3.2 Sérialiseur

**`notifications/serializers.py`** :

```python
from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'body', 'data', 'is_read', 'created_at']
        read_only_fields = ['id', 'type', 'title', 'body', 'data', 'created_at']
```

### 3.3 Vues DRF

**`notifications/views.py`** :

**`GET /api/v1/notifications/`** — Liste paginée des notifications de l'utilisateur connecté

- Authentification : `IsAuthenticated`
- Filtre optionnel : `?unread=true` pour uniquement les non lues
- Pagination : `page` + `page_size` (défaut 20, max 50)
- Réponse 200 :

```json
{
  "count": 42,
  "next": "http://api/.../notifications/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "type": "new_match",
      "title": "Nouveau match !",
      "body": "Vous avez matché avec Marie",
      "data": {"match_id": "uuid", "from_user_id": "uuid"},
      "is_read": false,
      "created_at": "2026-06-10T12:00:00Z"
    }
  ]
}
```

**`GET /api/v1/notifications/unread-count/`** — Compte des non lues

- Réponse 200 : `{"unread_count": 5}`

**`PUT /api/v1/notifications/{id}/read/`** — Marquer une notification comme lue

- Réponse 200 : `{"id": "uuid", "is_read": true, ...}`
- Réponse 404 si inexistante ou n'appartient pas à l'utilisateur

**`PUT /api/v1/notifications/read-all/`** — Marquer toutes comme lues

- Réponse 200 : `{"marked_read": 12}`

```python
# notifications/views.py — squelette
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get('unread') == 'true':
            qs = qs.filter(is_read=False)
        return qs

class UnreadCountView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return Response({"unread_count": count})

class MarkReadView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_object(self):
        return get_object_or_404(
            Notification, pk=self.kwargs['pk'], user=self.request.user
        )
    
    def update(self, request, *args, **kwargs):
        notif = self.get_object()
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notif).data)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    count = Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    return Response({"marked_read": count})
```

### 3.4 URLs

**`notifications/urls.py`** :

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('unread-count/', views.UnreadCountView.as_view(), name='notification-unread-count'),
    path('<uuid:pk>/read/', views.MarkReadView.as_view(), name='notification-mark-read'),
    path('read-all/', views.mark_all_read, name='notification-read-all'),
]
```

**`hivmeet_backend/urls.py`** — Ajouter :
```python
path('api/v1/notifications/', include('notifications.urls')),
```

### 3.5 Création automatique de Notification dans `signals.py`

À chaque like, match, ou nouveau message, créer une `Notification` en base **en plus** de l'envoi FCM :

```python
# Dans matching/signals.py, fonction handle_new_match (après l'envoi Celery)
from notifications.models import Notification  # si app créée

Notification.objects.create(
    user=user1,
    type='new_match',
    title='Nouveau match !',
    body=f'Vous avez matché avec {user2.profile.display_name}',
    data={
        'match_id': str(match.id),
        'from_user_id': str(user2.id),
        'type': 'new_match',
        'notification_id': str(uuid.uuid4()),
    }
)
# Idem pour user2 (avec user1 comme from_user_id)

# Dans handle_like_notification
Notification.objects.create(
    user=to_user,
    type='super_like' if is_super else 'like',
    title='Nouveau super like !' if is_super else 'Quelqu\'un vous a liké',
    body=from_user.profile.display_name if to_user.is_premium else 'Passez Premium pour voir qui',
    data={
        'from_user_id': str(from_user.id) if to_user.is_premium else '',
        'is_super': is_super,
        'type': 'super_like' if is_super else 'like',
        'notification_id': str(uuid.uuid4()),
    }
)
```

---

## 4. Contrats Payload FCM (Référence Complète)

Le frontend lit exclusivement `message.data` (pas `message.notification`). Voici les contrats **exacts** par type :

### `new_match`
```json
{
  "type": "new_match",
  "notification_id": "match_{match_uuid}",
  "title": "C'est un match !",
  "body": "Vous avez matché avec {display_name}",
  "match_id": "{match_uuid}",
  "from_user_id": "{other_user_uuid}"
}
```

### `new_message`
```json
{
  "type": "new_message",
  "notification_id": "msg_{message_uuid}",
  "title": "{sender_display_name}",
  "body": "{message_preview_max_80_chars}",
  "conversation_id": "{match_uuid}",
  "from_user_id": "{sender_uuid}"
}
```

### `like`
```json
{
  "type": "like",
  "notification_id": "like_{like_uuid}",
  "title": "Quelqu'un vous a liké !",
  "body": "{display_name} vous a liké" ,
  "from_user_id": "{liker_uuid_si_premium_sinon_vide}"
}
```

### `super_like`
```json
{
  "type": "super_like",
  "notification_id": "superlike_{like_uuid}",
  "title": "Vous avez reçu un Super Like !",
  "body": "{display_name} vous a Super Liké",
  "from_user_id": "{liker_uuid_si_premium_sinon_vide}"
}
```

> **Note** : Firebase cloud messaging exige que la payload `data` ne contienne que des **strings**. Utiliser `"true"/"false"` pour les booléens, pas `true/false`.

---

## 5. Infra Locale de Test

### 5.1 Redis (requis pour Channels + Celery)

```bash
# Windows — via Docker
docker run -d -p 6379:6379 redis:alpine

# Vérifier
redis-cli ping  # → PONG
```

### 5.2 Celery Worker

```bash
# Depuis hivmeet_backend/ avec venv activé
celery -A hivmeet_backend worker -l info
```

En **développement sans Redis** : passer `CELERY_TASK_ALWAYS_EAGER = True` dans `settings/local.py` — les tâches s'exécutent synchroniquement dans le processus Django (pas besoin de worker séparé). ⚠️ Ne pas activer en staging/prod.

### 5.3 Firebase Admin (push FCM)

1. Télécharger la clé de service depuis la console Firebase : `Paramètres du projet > Comptes de service > Générer une nouvelle clé privée`.
2. Placer le fichier JSON dans un emplacement sécurisé (hors repo).
3. Configurer la variable d'environnement :

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/serviceAccountKey.json"
```

Ou via `settings/local.py` :
```python
import firebase_admin
from firebase_admin import credentials
cred = credentials.Certificate("/path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)
```

### 5.4 Procédure de test push bout en bout

1. **Enregistrer un token FCM** : lancer l'app Flutter en debug, se connecter → le `NotificationService` appelle `POST /auth/fcm-token`. Vérifier dans les logs Django que le token est bien enregistré.

2. **Déclencher un like** : depuis un second compte, liker le premier compte → `handle_like_notification` signal se déclenche → `send_like_notification.delay()` s'exécute.

3. **Vérifier** : log Celery worker doit montrer `send_like_notification` exécutée. L'appareil du liké reçoit la notification push (si Celery + Redis + Firebase Admin configurés).

4. **Vérifier WS** : connecter l'app, ouvrir les DevTools réseau, inspecter `ws://host/ws/notifications/` — un frame JSON doit arriver à chaque like/match.

---

## 6. Checklist d'Acceptation

- [ ] **Like → notif push au liké** — non-premium reçoit une notif anonymisée, premium reçoit le nom du lieur
- [ ] **Super like → notif push distincte** — titre "Super Like !" distinguable d'un like simple
- [ ] **Match → notif push aux deux utilisateurs** — les deux reçoivent simultanément
- [ ] **Nouveau message → notif push au destinataire** — uniquement si ce dernier n'est pas dans la conversation (à implémenter : vérifier `last_activity_at` ou présence WS du destinataire avant d'envoyer)
- [ ] **Tokens invalides purgés** — après un envoi FCM avec erreur `registration-token-not-registered`
- [ ] **Gate premium corrigée** — non-premium reçoit la notif anonymisée, ne reçoit pas le nom
- [ ] **Consumer WS `user_{id}` opérationnel** — `ws/notifications/` accessible après authentification
- [ ] **Endpoint `GET /api/v1/notifications/`** — retourne la liste paginée triée par date décroissante
- [ ] **Endpoint `GET /api/v1/notifications/unread-count/`** — retourne le bon compte
- [ ] **Endpoint `PUT /api/v1/notifications/{id}/read/`** — marque une notification comme lue
- [ ] **Endpoint `PUT /api/v1/notifications/read-all/`** — marque toutes comme lues
- [ ] **Page in-app alimentée par l'endpoint** (après migration frontend du store local vers l'API)
- [ ] **Notifications créées en base** à chaque like/match/message (via signals.py)

---

## 7. Migration Frontend — Store Local vers API

Une fois l'endpoint `/api/v1/notifications/` livré, modifier `NotificationsBloc._loadDerived()` dans `lib/presentation/blocs/notifications/notifications_bloc.dart` :

```dart
// Remplacer _loadDerived() par un appel repository :
// 1. Créer NotificationsApi dans lib/data/datasources/remote/notifications_api.dart
//    → GET /api/v1/notifications/ + unread-count + mark-read + read-all
// 2. Créer NotificationsRepository + impl
// 3. Dans NotificationsBloc.LoadNotifications :
//    - Appeler repository.getNotifications()
//    - Ne plus fusionner avec MatchRepository/MessageRepository
//    - Garder NotificationsLocalStore pour les notifs reçues en push quand l'app est fermée
//      (les insérer en base via un endpoint dédié ou les fusionner côté client)
```

Un TODO est déjà présent dans `notifications_bloc.dart` pour ce basculement.
