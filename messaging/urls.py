"""
URLs for messaging app.
"""
from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Conversations
    path('', views.ConversationListView.as_view(), name='conversation-list'),
    path('generate-media-upload-url/', views.generate_media_upload_url, name='generate-media-upload-url'),
    
    # Messages
    path('<uuid:conversation_id>/messages/', views.conversation_messages, name='conversation-messages'),
    path('<uuid:conversation_id>/messages/media/', views.SendMediaMessageView.as_view(), name='send-media-message'),
    path('<uuid:conversation_id>/messages/mark-as-read/', views.mark_messages_as_read, name='mark-as-read'),
    path('<uuid:conversation_id>/messages/<uuid:message_id>/', views.delete_message, name='delete-message'),
    path('<uuid:conversation_id>/messages/<uuid:message_id>/read/', views.mark_single_message_as_read, name='mark-single-read'),
    path('<uuid:conversation_id>/typing/', views.typing_indicator, name='typing-indicator'),
    path('<uuid:conversation_id>/presence/', views.conversation_presence, name='conversation-presence'),
    
    # Premium call features
    path('calls/initiate-premium/', views.InitiatePremiumCallView.as_view(), name='initiate-premium-call'),
]