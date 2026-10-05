"""
WebSocket consumers for real-time messaging.

Handles:
- Real-time message delivery
- Typing indicators
- Presence status (online/offline)
- WebRTC call signaling (ICE candidates, offer, answer)
"""

import json
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from matching.models import Match
from matching.free_access import FreeMatchAccessService
from profiles.kyc import has_active_kyc
from .presence import PresenceService
from .services import MessageService

logger = logging.getLogger('hivmeet.messaging.websocket')
User = get_user_model()


class ConversationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time conversation management.
    
    Handles:
    - Real-time message delivery
    - Typing indicators
    - Presence status
    - WebRTC signaling
    """

    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Extract conversation_id from URL
            self.conversation_id = self.scope['url_route']['kwargs'].get('conversation_id')
            
            if not self.conversation_id:
                await self.close(code=4001)  # Conversation not found
                return
            
            # Authenticate user via JWT
            await self._authenticate_user()
            
            if not hasattr(self, 'user') or not self.user:
                await self.close(code=4000)  # Invalid token
                return
            if not await self._has_active_kyc():
                await self.close(code=4403)
                return
            
            # Verify user has access to this conversation
            match = await self._get_active_match()
            if not match:
                await self.close(code=4001)  # Conversation not found
                return

            has_access = await database_sync_to_async(
                lambda: FreeMatchAccessService.state_for(match, self.user)[
                    'can_view_profile'
                ]
            )()
            if not has_access:
                await self.close(code=4003)
                return
            
            self.match = match
            self.group_name = f'conversation_{self.conversation_id}'
            # A connection-scoped id makes one device disconnect independent
            # from any other device logged into the same account.
            self.presence_session_id = f'chat:{self.channel_name}'
            
            # Join room group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            await self.accept()

            # The same presence service powers REST snapshots, WebSocket state
            # and delivery receipts. Only its privacy-safe payload is sent.
            payload = await self._set_presence_online()

            # Being subscribed to this conversation means the incoming messages
            # have reached the client: flip them to delivered so the sender
            # can render the second tick.
            await self._mark_incoming_delivered()
            await self._broadcast_presence(payload)

            logger.info('Conversation websocket connected: conversation_id=%s', self.conversation_id)
            
        except Exception:
            logger.error('Conversation websocket connection failed')
            await self.close(code=4999)  # Internal error

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            if not hasattr(self, 'group_name'):
                return
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            
            # End only this socket's device session. A sibling notification
            # or chat session keeps the participant online.
            if hasattr(self, 'user'):
                payload = await self._set_presence_offline()
                await self._broadcast_presence(payload)

                logger.info('Conversation websocket disconnected: conversation_id=%s', self.conversation_id)
        
        except Exception:
            logger.error('Conversation websocket disconnection failed')

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            if not await self._has_active_kyc():
                await self.close(code=4403)
                return
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'message.send':
                await self._handle_message_send(data)
            elif message_type == 'typing.start':
                await self._handle_typing_start(data)
            elif message_type == 'typing.stop':
                await self._handle_typing_stop(data)
            elif message_type in ('ping', 'presence.heartbeat'):
                payload = await self._set_presence_online()
                # Heartbeats make the 90-second server expiry observable to
                # open chats without exposing a device identifier.
                await self._broadcast_presence(payload)
                if message_type == 'ping':
                    await self.send(text_data=json.dumps({
                        'type': 'pong',
                        'timestamp': payload['server_timestamp'],
                    }))
            elif message_type == 'ice.candidate':
                await self._handle_ice_candidate(data)
            elif message_type == 'offer':
                await self._handle_offer(data)
            elif message_type == 'answer':
                await self._handle_answer(data)
            else:
                logger.warning('Unknown conversation websocket message type')
                
        except json.JSONDecodeError:
            logger.warning('Invalid JSON received')
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON',
                'code': 'INVALID_JSON',
            }))
        except Exception:
            logger.error('Conversation websocket message processing failed')
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Server error',
                'code': 'INTERNAL_ERROR',
            }))

    # Message handlers
    async def _handle_message_send(self, data):
        """Handle real-time message sending."""
        try:
            content = data.get('content', '').strip()
            client_message_id = data.get('client_message_id')
            
            if not content:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message cannot be empty',
                    'code': 'EMPTY_MESSAGE',
                }))
                return
            
            # Persist via service (fires post_save signal → broadcasts + push)
            message, error = await self._create_message(
                content=content,
                client_message_id=client_message_id,
            )

            if not message:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Unable to send this message',
                    'code': getattr(error, 'code', 'CREATION_FAILED'),
                }))
                return

            logger.info('Message created: message_id=%s', message.id)
            
        except Exception:
            logger.error('Conversation websocket message send failed')
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to send message',
                'code': 'SEND_FAILED',
            }))

    async def _handle_typing_start(self, data):
        """Handle typing indicator start."""
        try:
            # Set typing indicator in cache (TTL 10 seconds)
            cache_key = f'typing_{self.conversation_id}_{self.user.id}'
            cache.set(cache_key, True, timeout=10)
            
            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': str(self.user.id),
                    'status': 'typing',
                }
            )
            
        except Exception:
            logger.error('Conversation websocket typing-start handling failed')

    async def _handle_typing_stop(self, data):
        """Handle typing indicator stop."""
        try:
            # Clear typing indicator from cache
            cache_key = f'typing_{self.conversation_id}_{self.user.id}'
            cache.delete(cache_key)
            
            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': str(self.user.id),
                    'status': 'stopped',
                }
            )
            
        except Exception:
            logger.error('Conversation websocket typing-stop handling failed')

    async def _handle_ice_candidate(self, data):
        """Handle WebRTC ICE candidate."""
        try:
            candidate = data.get('candidate')
            sdp_mid = data.get('sdpMid')
            sdp_m_line_index = data.get('sdpMLineIndex')
            
            if not candidate:
                return
            
            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'ice_candidate',
                    'from_user_id': str(self.user.id),
                    'candidate': candidate,
                    'sdpMid': sdp_mid,
                    'sdpMLineIndex': sdp_m_line_index,
                }
            )
            
        except Exception:
            logger.error('Conversation websocket ICE handling failed')

    async def _handle_offer(self, data):
        """Handle WebRTC offer."""
        try:
            offer = data.get('offer')
            call_id = data.get('call_id')
            
            if not offer:
                return
            
            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'webrtc_offer',
                    'from_user_id': str(self.user.id),
                    'call_id': call_id,
                    'offer': offer,
                }
            )
            
        except Exception:
            logger.error('Conversation websocket offer handling failed')

    async def _handle_answer(self, data):
        """Handle WebRTC answer."""
        try:
            answer = data.get('answer')
            call_id = data.get('call_id')
            
            if not answer:
                return
            
            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'webrtc_answer',
                    'from_user_id': str(self.user.id),
                    'call_id': call_id,
                    'answer': answer,
                }
            )
            
        except Exception:
            logger.error('Conversation websocket answer handling failed')

    # Group event handlers (from channel_layer.group_send)
    async def message_created(self, event):
        """Handle message created event from group."""
        await self.send(text_data=json.dumps({
            'type': 'message.created',
            'message_id': event['message_id'],
            'conversation_id': event['conversation_id'],
            'sender_id': event['sender_id'],
            'content': event['content'],
            'message_type': event.get('message_type', 'text'),
            'media_url': event.get('media_url'),
            'media_type': event.get('media_type'),
            'media_thumbnail_url': event.get('media_thumbnail_url'),
            'media_download_url': event.get('media_download_url'),
            'media_mime_type': event.get('media_mime_type'),
            'media_size_bytes': event.get('media_size_bytes'),
            'media_file_name': event.get('media_file_name'),
            'media_duration_ms': event.get('media_duration_ms'),
            'sent_at': event['sent_at'],
            'client_message_id': event.get('client_message_id'),
        }))

    async def message_updated(self, event):
        """Forward a canonical text edit to both conversation participants."""
        await self.send(text_data=json.dumps({
            'type': 'message.updated',
            'conversation_id': event.get('conversation_id'),
            'message_id': event.get('message_id'),
            'content': event.get('content', ''),
            'edited_at': event.get('edited_at'),
        }))

    async def message_deleted(self, event):
        """Replace globally retracted messages without removing chronology."""
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'conversation_id': event.get('conversation_id'),
            'message_ids': event.get('message_ids', []),
        }))

    async def message_read(self, event):
        """Forward a read receipt to every connected conversation client."""
        await self.send(text_data=json.dumps({
            'type': 'message.read',
            'reader_id': event['reader_id'],
            'message_ids': event['message_ids'],
            'read_at': event['read_at'],
        }))

    async def message_delivered(self, event):
        """Forward a delivery receipt to every connected conversation client."""
        await self.send(text_data=json.dumps({
            'type': 'message.delivered',
            'conversation_id': event.get('conversation_id'),
            'message_ids': event.get('message_ids', []),
            'delivered_at': event.get('delivered_at'),
        }))

    async def typing_indicator(self, event):
        """Handle typing indicator event from group."""
        # Don't send own typing status back to self
        if event['user_id'] == str(self.user.id) and event['status'] == 'typing':
            return
        
        await self.send(text_data=json.dumps({
            'type': 'typing.indicator',
            'user_id': event['user_id'],
            'status': event['status'],
        }))

    async def presence_update(self, event):
        """Handle presence update event from group."""
        # Don't send own presence back to self
        if event['user_id'] == str(self.user.id):
            return
        
        await self.send(text_data=json.dumps({
            'type': 'presence.update',
            'user_id': event['user_id'],
            'visibility': bool(event.get('visibility')),
            'is_online': bool(event.get('is_online')),
            'last_active': event.get('last_active'),
            'server_timestamp': event.get('server_timestamp'),
        }))

    async def ice_candidate(self, event):
        """Handle ICE candidate event from group."""
        # Only send to users that are not the sender
        if event['from_user_id'] == str(self.user.id):
            return
        
        await self.send(text_data=json.dumps({
            'type': 'ice.candidate',
            'from_user_id': event['from_user_id'],
            'candidate': event['candidate'],
            'sdpMid': event.get('sdpMid'),
            'sdpMLineIndex': event.get('sdpMLineIndex'),
        }))

    async def webrtc_offer(self, event):
        """Handle WebRTC offer event from group."""
        # Only send to users that are not the sender
        if event['from_user_id'] == str(self.user.id):
            return
        
        await self.send(text_data=json.dumps({
            'type': 'webrtc.offer',
            'from_user_id': event['from_user_id'],
            'call_id': event.get('call_id'),
            'offer': event['offer'],
        }))

    async def webrtc_answer(self, event):
        """Handle WebRTC answer event from group."""
        # Only send to users that are not the sender
        if event['from_user_id'] == str(self.user.id):
            return

        await self.send(text_data=json.dumps({
            'type': 'webrtc.answer',
            'from_user_id': event['from_user_id'],
            'call_id': event.get('call_id'),
            'answer': event['answer'],
        }))

    async def incoming_call(self, event):
        """Handle incoming call event broadcast by the call signal."""
        call = event['call']
        # Don't notify the caller themselves
        if call.get('caller_id') == str(self.user.id):
            return
        await self.send(text_data=json.dumps({
            'type': 'incoming_call',
            'call': call,
        }))

    async def call_update(self, event):
        """Handle call status update event broadcast by the call signal."""
        await self.send(text_data=json.dumps({
            'type': 'call_update',
            'call': event['call'],
        }))

    # Helper methods
    async def _authenticate_user(self):
        """Authenticate user from JWT token in headers."""
        try:
            token = None

            # Try token from Authorization header first
            headers = dict(self.scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode()
            
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

            # Fallback to query string token for clients that cannot set WS headers
            if not token:
                raw_query = self.scope.get('query_string', b'').decode()
                query = parse_qs(raw_query)
                token = (query.get('token') or [None])[0]

            if not token:
                self.user = None
                return
            
            # Decode JWT
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                self.user = await database_sync_to_async(User.objects.get)(id=user_id)
            except (InvalidToken, TokenError, User.DoesNotExist):
                self.user = None
                
        except Exception:
            logger.error('Conversation websocket authentication failed')
            self.user = None

    async def _get_active_match(self):
        """Verify user has access to conversation."""
        try:
            match = await database_sync_to_async(
                lambda: Match.objects.filter(
                    Q(user1=self.user) | Q(user2=self.user),
                    id=self.conversation_id,
                    status=Match.ACTIVE,
                ).select_related('user1', 'user2').first()
            )()
            return match
        except Exception:
            logger.error('Conversation websocket match lookup failed')
            return None

    async def _has_active_kyc(self):
        """Re-evaluate KYC before every WebSocket entry point."""
        return await database_sync_to_async(has_active_kyc)(self.user)

    async def send(self, text_data=None, bytes_data=None, close=False):
        """Prevent post-expiry social payload delivery on an open socket."""
        if getattr(self, 'user', None) and not await self._has_active_kyc():
            await self.close(code=4403)
            return
        await super().send(text_data=text_data, bytes_data=bytes_data, close=close)

    async def _set_presence_online(self):
        """Refresh this socket's 30s heartbeat in the shared service."""
        try:
            return await database_sync_to_async(PresenceService.heartbeat)(
                self.user, self.presence_session_id
            )
        except Exception:
            logger.exception('Conversation websocket presence heartbeat failed')
            return await database_sync_to_async(PresenceService.snapshot_for)(self.user)

    async def _set_presence_offline(self):
        """Disconnect this socket only; other device sessions remain active."""
        try:
            return await database_sync_to_async(PresenceService.disconnect)(
                self.user, getattr(self, 'presence_session_id', '')
            )
        except Exception:
            logger.exception('Conversation websocket presence disconnect failed')
            return await database_sync_to_async(PresenceService.snapshot_for)(self.user)

    async def _broadcast_presence(self, snapshot):
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
        await self.channel_layer.group_send(self.group_name, payload)

    async def _mark_incoming_delivered(self):
        """Flip this conversation's incoming messages to ``delivered``."""
        try:
            def _mark():
                receipts = MessageService.mark_incoming_as_delivered(
                    user=self.user,
                    match=self.match,
                )
                MessageService.broadcast_delivery_receipts(receipts)
                return receipts

            await database_sync_to_async(_mark)()
        except Exception:
            # A delivery receipt is an enhancement; never fail the connection.
            logger.warning('Conversation websocket delivery receipt failed')

    async def _create_message(self, content, client_message_id=None):
        """Persist a text message via the service layer (fires post_save signal)."""
        try:
            def _send():
                message, error = MessageService.send_message(
                    sender=self.user,
                    match=self.match,
                    content=content,
                    client_message_id=client_message_id,
                )
                return message, error

            message, error = await database_sync_to_async(_send)()
            if error:
                logger.error('Conversation websocket message service rejected a send')
                return None, error
            return message, None

        except Exception:
            logger.error('Conversation websocket message creation failed')
            return None, None
