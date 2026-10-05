"""
WebSocket consumer pour les notifications temps réel d'un utilisateur.

URL  : ws/notifications/
Auth : JWT token via header Authorization: Bearer <jwt>
       ou paramètre query ?token=<jwt> (fallback pour clients WS sans headers)
Groupe channel : user_{user_id}

Les événements reçus correspondent aux group_send émis vers le groupe
user_{id} :
  matching/signals.py
    type=new_match     → handler new_match()
    type=like          → handler like()
    type=super_like    → handler super_like()  (délègue à like, is_super=True)
  messaging/signals.py
    type=new_message   → handler new_message()
    type=incoming_call → handler incoming_call()
    type=call_update   → handler call_update()
  messaging/services.py
    type=message_read  → handler message_read()

Client → serveur : {"type": "ping"} → {"type": "pong", "timestamp": ...}.
Le JWT n'est validé qu'à la connexion : il n'y a pas de refresh in-band, le
client se reconnecte avec un token frais à l'expiration (cf.
docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md).
"""
import json
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from matching.models import Match
from messaging.presence import PresenceService
from profiles.kyc import has_active_kyc

logger = logging.getLogger('hivmeet.notifications.ws')
User = get_user_model()


class UserNotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer pour les notifications personnelles d'un utilisateur."""

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def connect(self):
        await self._authenticate_user()
        if not self.user:
            await self.close(code=4000)
            return
        if not await self._has_active_kyc():
            await self.close(code=4403)
            return

        self.group_name = f"user_{self.user.id}"
        self.presence_session_id = f'notifications:{self.channel_name}'

        try:
            # Le channel layer (Redis en prod) peut être injoignable — ne
            # pas laisser l'exception remonter et avorter le handshake HTTP
            # brutalement (le client verrait un échec de handshake plutôt
            # qu'une fermeture propre, et retenterait en boucle serrée).
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        except Exception:
            logger.error(
                "WS notifications: channel layer unavailable for user %s",
                self.user.id,
            )
            await self.close(code=4999)
            return

        logger.info(f"WS notifications: user {self.user.id} connected")
        snapshot = await self._set_user_presence_online()
        await self._broadcast_presence_to_active_conversations(snapshot)

        # Ce socket vit pour toute la session : sa connexion signifie que
        # l'appareil est en ligne, ce qui correspond exactement à l'accusé de
        # réception « delivered » des messageries grand public. On bascule donc
        # les messages entrants encore `sent` de TOUTES les conversations
        # actives. Après le premier passage la requête ne ramène plus rien, une
        # reconnexion en backoff reste donc peu coûteuse.
        await self._mark_incoming_delivered()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            except Exception:
                pass
            snapshot = await self._set_user_presence_offline()
            await self._broadcast_presence_to_active_conversations(snapshot)
            logger.debug(f"WS notifications: user {self.user.id} disconnected ({close_code})")

    # ------------------------------------------------------------------ #
    # Event handlers — type doit correspondre exactement au champ "type"
    # passé dans group_send (matching/signals.py).
    # ------------------------------------------------------------------ #

    async def new_match(self, event: dict):
        """Nouveau match : envoyé aux deux participants."""
        await self.send(text_data=json.dumps({
            "type": "new_match",
            "match_id": event.get("match_id"),
            "matched_user_id": event.get("matched_user_id"),
        }))

    async def match_removed(self, event: dict):
        await self.send(text_data=json.dumps({
            "type": "match_removed",
            "match_id": event.get("match_id"),
        }))

    async def like(self, event: dict):
        """Like ou super-like reçu."""
        await self.send(text_data=json.dumps({
            "type": event.get("type", "like"),
            "notification_id": event.get("notification_id"),
            "from_user_id": event.get("from_user_id", ""),  # vide si non-premium
            "like_id": event.get("like_id"),
            "is_super": event.get("is_super", "false"),
        }))

    async def super_like(self, event: dict):
        """Super-like reçu — délègue à like avec type explicite."""
        await self.like({**event, "type": "super_like"})

    async def new_message(self, event: dict):
        """Nouveau message (pour notifications cross-conversation)."""
        payload = {
            "type": "new_message",
            "conversation_id": event.get("conversation_id"),
            "message_id": event.get("message_id"),
            "from_user_id": event.get("from_user_id"),
            "preview": event.get("preview"),
            "unread_count": event.get("unread_count"),
        }
        # Keep the legacy frame shape when a worker queued before the
        # canonical-notification rollout has no optional metadata.  New
        # events retain both fields, which lets Flutter deduplicate by the
        # persisted UUID and present the sender name.
        for key in ("sender_name", "notification_id"):
            value = event.get(key)
            if value is not None and value != "":
                payload[key] = value
        await self.send(text_data=json.dumps(payload))

    async def message_read(self, event: dict):
        """Accusé de lecture destiné à l'auteur des messages lus.

        Émis par messaging/services.py vers le groupe user_{sender_id} afin que
        les coches passent en « lu » même si l'auteur n'a pas la conversation
        ouverte.
        """
        await self.send(text_data=json.dumps({
            "type": "message_read",
            "conversation_id": event.get("conversation_id"),
            "reader_id": event.get("reader_id"),
            "message_ids": event.get("message_ids", []),
            "read_at": event.get("read_at"),
        }))

    async def message_read_alert(self, event: dict):
        """Persisted Premium read alert, distinct from the universal receipt."""
        await self.send(text_data=json.dumps({
            "type": "message_read",
            "notification_id": event.get("notification_id"),
            "conversation_id": event.get("conversation_id"),
            "reader_id": event.get("reader_id"),
            "reader_name": event.get("reader_name"),
            "representative_message_id": event.get("representative_message_id"),
            "message_count": event.get("message_count"),
            "read_at": event.get("read_at"),
        }))

    async def incoming_call(self, event: dict):
        """Appel entrant — permet de sonner sans socket de conversation ouverte."""
        await self.send(text_data=json.dumps({
            "type": "incoming_call",
            "call": event.get("call", {}),
        }))

    async def call_update(self, event: dict):
        """Changement d'état d'un appel (répondu / terminé / refusé)."""
        await self.send(text_data=json.dumps({
            "type": "call_update",
            "call": event.get("call", {}),
        }))

    async def message_delivered(self, event: dict):
        """Accusé de réception destiné à l'auteur des messages livrés."""
        await self.send(text_data=json.dumps({
            "type": "message_delivered",
            "conversation_id": event.get("conversation_id"),
            "message_ids": event.get("message_ids", []),
            "delivered_at": event.get("delivered_at"),
        }))
    async def subscription_expiring(self, event: dict):
        """Notification d'expiration d'abonnement prochaine.

        Émise par ``subscriptions.tasks.send_expiration_reminders`` vers le
        groupe ``user_{id}``. Le frontend navigue vers ``/premium`` au tap.
        """
        await self.send(text_data=json.dumps({
            "type": "subscription_expiring",
            "notification_id": event.get("notification_id"),
            "days_remaining": event.get("days_remaining"),
            "expiry_date": event.get("expiry_date"),
        }))

    async def report_resolved(self, event: dict):
        """Notification de résolution de signalement.

        Émise quand un admin résout un signalement. Le frontend affiche la
        décision complète dans un dialog au tap.
        """
        await self.send(text_data=json.dumps({
            "type": "report_resolved",
            "notification_id": event.get("notification_id"),
            "report_id": event.get("report_id"),
            "status": event.get("status"),
            "resolution_summary": event.get("resolution_summary"),
        }))
    # ------------------------------------------------------------------ #
    # Client → serveur
    # ------------------------------------------------------------------ #

    async def receive(self, text_data=None, bytes_data=None):
        """Gère les messages émis par le client.

        Seul `ping` est supporté, avec le même contrat que
        messaging/consumers.py ConversationConsumer, pour que le client puisse
        vérifier la vivacité de cette connexion au niveau applicatif.
        """
        if not text_data:
            return
        if not await self._has_active_kyc():
            await self.close(code=4403)
            return

        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Invalid JSON",
                "code": "INVALID_JSON",
            }))
            return

        if not isinstance(data, dict):
            return

        if data.get("type") in ("ping", "presence.heartbeat"):
            snapshot = await self._set_user_presence_online()
            await self._broadcast_presence_to_active_conversations(snapshot)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({
                    "type": "pong",
                    "timestamp": snapshot['server_timestamp'].isoformat(),
                }))

    # ------------------------------------------------------------------ #
    # Effets de bord à la connexion
    # ------------------------------------------------------------------ #

    async def _mark_incoming_delivered(self):
        """Marque `delivered` les messages entrants de toutes les conversations."""
        try:
            def _mark():
                # Import tardif : notifications ne doit pas dépendre de
                # messaging au chargement du module (messaging importe déjà
                # notifications pour les payloads FCM).
                from messaging.services import MessageService

                receipts = MessageService.mark_incoming_as_delivered(user=self.user)
                MessageService.broadcast_delivery_receipts(receipts)

            await database_sync_to_async(_mark)()
        except Exception:
            # Best-effort : ne doit jamais empêcher la connexion.
            logger.warning("WS notifications: accusé de réception échoué")

    # ------------------------------------------------------------------ #
    # Auth — même logique que messaging/consumers.py ConversationConsumer
    # ------------------------------------------------------------------ #

    async def _set_user_presence_online(self):
        """Refresh the notification socket's own foreground session."""
        # ``receive`` is intentionally safe before ``connect`` has completed.
        # Besides protecting a malformed socket frame, this keeps the ping
        # contract deterministic for consumer-level tests and avoids treating
        # an unauthenticated connection as a presence session.
        if not getattr(self, 'user', None):
            return {
                'visibility': False,
                'is_online': False,
                'last_active': None,
                'server_timestamp': timezone.now(),
            }
        try:
            return await database_sync_to_async(PresenceService.heartbeat)(
                self.user, self.presence_session_id
            )
        except Exception:
            logger.exception('WS notifications: presence heartbeat failed')
            return await database_sync_to_async(PresenceService.snapshot_for)(self.user)

    async def _has_active_kyc(self):
        """Re-evaluate KYC before social WebSocket traffic."""
        return await database_sync_to_async(has_active_kyc)(self.user)

    async def send(self, text_data=None, bytes_data=None, close=False):
        """Stop delivery when current KYC access is absent or expires."""
        if getattr(self, 'user', None) and not await self._has_active_kyc():
            await self.close(code=4403)
            return
        await super().send(text_data=text_data, bytes_data=bytes_data, close=close)

    async def _set_user_presence_offline(self):
        if not getattr(self, 'user', None):
            return {
                'visibility': False,
                'is_online': False,
                'last_active': None,
                'server_timestamp': timezone.now(),
            }
        try:
            return await database_sync_to_async(PresenceService.disconnect)(
                self.user, getattr(self, 'presence_session_id', '')
            )
        except Exception:
            logger.exception('WS notifications: presence disconnect failed')
            return await database_sync_to_async(PresenceService.snapshot_for)(self.user)

    async def _broadcast_presence_to_active_conversations(self, snapshot):
        """Notify open chats while preserving the owner visibility preference."""
        if not getattr(self, 'user', None):
            return

        def _conversation_ids():
            return list(
                Match.objects.filter(
                    Q(user1=self.user) | Q(user2=self.user),
                    status=Match.ACTIVE,
                ).values_list('id', flat=True)
            )

        try:
            ids = await database_sync_to_async(_conversation_ids)()
            payload = {
                'type': 'presence_update',
                'user_id': str(self.user.id),
                'visibility': bool(snapshot.get('visibility')),
                'is_online': bool(snapshot.get('is_online')),
                'last_active': (
                    snapshot['last_active'].isoformat()
                    if snapshot.get('last_active') is not None
                    else None
                ),
                'server_timestamp': snapshot['server_timestamp'].isoformat(),
            }
            for conversation_id in ids:
                await self.channel_layer.group_send(
                    f'conversation_{conversation_id}', payload
                )
        except Exception:
            logger.warning('WS notifications: presence broadcast failed')

    async def _authenticate_user(self):
        """
        Extrait et valide le JWT depuis :
        1. Header Authorization: Bearer <token>
        2. Query string ?token=<token> (fallback WS sans headers)
        Stocke l'instance User dans self.user, ou None si échec.
        """
        self.user = None
        try:
            token = None

            # Essayer le header Authorization en premier
            headers = dict(self.scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode()
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

            # Fallback : query string ?token=
            if not token:
                raw_query = self.scope.get('query_string', b'').decode()
                query = parse_qs(raw_query)
                token = (query.get('token') or [None])[0]

            if not token:
                logger.warning("WS notifications: connexion sans token refusée")
                return

            # Décoder le JWT et charger l'utilisateur
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                self.user = await database_sync_to_async(User.objects.get)(id=user_id)
            except (InvalidToken, TokenError) as exc:
                logger.warning(f"WS notifications: token JWT invalide — {exc}")
            except User.DoesNotExist:
                logger.warning(f"WS notifications: user {user_id} introuvable")

        except Exception as exc:
            logger.error(f"WS notifications: erreur d'authentification — {exc}")
