"""
ASGI config for hivmeet_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import django

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')

# Initialize Django
django.setup()

# Import WebSocket consumers after Django setup
from messaging.consumers import ConversationConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    path('ws/conversations/<uuid:conversation_id>/', ConversationConsumer.as_asgi()),
]

# ASGI application with protocol routing
application = ProtocolTypeRouter({
    # HTTP and WebSocket requests
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
