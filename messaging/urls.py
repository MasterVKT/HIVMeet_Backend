"""
URLs for messaging app.
"""
from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Conversations
    path('', views.ConversationListView.as_view(), name='conversation-list'),
    
    # Messages
    path('<uuid:conversation_id>/messages', views.get_conversation_messages, name='get-messages'),
    path('<uuid:conversation_id>/messages', views.send_message, name='send-message'),
    path('<uuid:conversation_id>/messages/mark-as-read', views.mark_messages_as_read, name='mark-as-read'),
    path('<uuid:conversation_id>/messages/<uuid:message_id>', views.delete_message, name='delete-message'),
]