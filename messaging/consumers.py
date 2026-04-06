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
from .models import Message
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
            
            # Verify user has access to this conversation
            match = await self._get_active_match()
            if not match:
                await self.close(code=4001)  # Conversation not found
                return
            
            self.match = match
            self.group_name = f'conversation_{self.conversation_id}'
            
            # Join room group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Set presence status to online
            await self._set_presence_online()
            
            # Broadcast that user is now online
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'presence_update',
                    'user_id': str(self.user.id),
                    'status': 'online',
                    'timestamp': timezone.now().isoformat(),
                }
            )
            
            logger.info(
                f'User {self.user.id} connected to conversation {self.conversation_id}'
            )
            
        except Exception as e:
            logger.error(f'Connection error: {str(e)}', exc_info=True)
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
            
            # Set presence status to offline
            if hasattr(self, 'user'):
                await self._set_presence_offline()
                
                # Broadcast that user is now offline
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'presence_update',
                        'user_id': str(self.user.id),
                        'status': 'offline',
                        'timestamp': timezone.now().isoformat(),
                    }
                )
                
                logger.info(
                    f'User {self.user.id} disconnected from conversation {self.conversation_id}'
                )
        
        except Exception as e:
            logger.error(f'Disconnection error: {str(e)}', exc_info=True)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'message.send':
                await self._handle_message_send(data)
            elif message_type == 'typing.start':
                await self._handle_typing_start(data)
            elif message_type == 'typing.stop':
                await self._handle_typing_stop(data)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat(),
                }))
            elif message_type == 'ice.candidate':
                await self._handle_ice_candidate(data)
            elif message_type == 'offer':
                await self._handle_offer(data)
            elif message_type == 'answer':
                await self._handle_answer(data)
            else:
                logger.warning(f'Unknown message type: {message_type}')
                
        except json.JSONDecodeError:
            logger.warning('Invalid JSON received')
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON',
                'code': 'INVALID_JSON',
            }))
        except Exception as e:
            logger.error(f'Error processing message: {str(e)}', exc_info=True)
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
            
            # Create message in database
            message = await self._create_message(
                content=content,
                client_message_id=client_message_id,
            )
            
            if not message:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to create message',
                    'code': 'CREATION_FAILED',
                }))
                return
            
            # Broadcast message to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'message_created',
                    'message_id': str(message.id),
                    'conversation_id': str(message.match_id),
                    'sender_id': str(message.sender_id),
                    'content': message.content,
                    'message_type': message.message_type,
                    'sent_at': message.created_at.isoformat(),
                    'client_message_id': client_message_id,
                }
            )
            
            logger.info(f'Message created: {message.id}')
            
        except Exception as e:
            logger.error(f'Error sending message: {str(e)}', exc_info=True)
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
            
        except Exception as e:
            logger.error(f'Error handling typing start: {str(e)}')

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
            
        except Exception as e:
            logger.error(f'Error handling typing stop: {str(e)}')

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
            
        except Exception as e:
            logger.error(f'Error handling ICE candidate: {str(e)}')

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
            
        except Exception as e:
            logger.error(f'Error handling offer: {str(e)}')

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
            
        except Exception as e:
            logger.error(f'Error handling answer: {str(e)}')

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
            'sent_at': event['sent_at'],
            'client_message_id': event.get('client_message_id'),
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
            'status': event['status'],
            'timestamp': event['timestamp'],
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
                
        except Exception as e:
            logger.error(f'Authentication error: {str(e)}')
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
        except Exception as e:
            logger.error(f'Error getting match: {str(e)}')
            return None

    async def _set_presence_online(self):
        """Set user presence to online in Redis."""
        try:
            cache_key = f'presence_{self.user.id}_{self.conversation_id}'
            cache.set(cache_key, {
                'status': 'online',
                'timestamp': timezone.now().isoformat(),
            }, timeout=3600)  # 1 hour TTL
        except Exception as e:
            logger.error(f'Error setting presence online: {str(e)}')

    async def _set_presence_offline(self):
        """Set user presence to offline in Redis."""
        try:
            cache_key = f'presence_{self.user.id}_{self.conversation_id}'
            cache.delete(cache_key)
        except Exception as e:
            logger.error(f'Error setting presence offline: {str(e)}')

    async def _create_message(self, content, client_message_id=None):
        """Create message in database."""
        try:
            # Check for deduplication
            if client_message_id:
                existing = await database_sync_to_async(
                    lambda: Message.objects.filter(
                        client_message_id=client_message_id,
                        match_id=self.conversation_id,
                        sender=self.user,
                    ).first()
                , thread_sensitive=False)()
                if existing:
                    return existing
            
            # Create message
            message = Message(
                match_id=self.conversation_id,
                sender=self.user,
                content=content,
                message_type=Message.TEXT,
                client_message_id=client_message_id or '',
                status=Message.SENT,
            )
            await database_sync_to_async(Message.objects.bulk_create, thread_sensitive=False)([message])
            
            # Update match last_message_at
            await database_sync_to_async(self._update_match_timestamp, thread_sensitive=False)()
            
            return message
            
        except Exception as e:
            logger.error(f'Error creating message: {str(e)}')
            return None

    def _update_match_timestamp(self):
        """Update match last_message_at timestamp."""
        try:
            Match.objects.filter(id=self.conversation_id).update(
                last_message_at=timezone.now()
            )
        except Exception as e:
            logger.error(f'Error updating match timestamp: {str(e)}')
