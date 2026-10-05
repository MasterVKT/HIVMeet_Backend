"""
URLs for messaging app.
"""
from django.urls import path
from . import views
from profiles.kyc import protect_view_with_active_kyc

app_name = 'messaging'

urlpatterns = [
    # Conversations
    path('', protect_view_with_active_kyc(views.ConversationListView.as_view()), name='conversation-list'),
    path('unread-count/', protect_view_with_active_kyc(views.conversations_unread_count), name='conversations-unread-count'),
    # Messages
    path('<uuid:conversation_id>/messages/', protect_view_with_active_kyc(views.conversation_messages), name='conversation-messages'),
    path('<uuid:conversation_id>/messages/media/', protect_view_with_active_kyc(views.SendMediaMessageView.as_view()), name='send-media-message'),
    path('<uuid:conversation_id>/messages/<uuid:message_id>/media/', protect_view_with_active_kyc(views.download_message_media), name='download-message-media'),
    path('<uuid:conversation_id>/messages/mark-as-read/', protect_view_with_active_kyc(views.mark_messages_as_read), name='mark-as-read'),
    path('<uuid:conversation_id>/messages/delete/', protect_view_with_active_kyc(views.delete_messages), name='delete-messages'),
    path('<uuid:conversation_id>/messages/<uuid:message_id>/', protect_view_with_active_kyc(views.edit_message), name='edit-message'),
    # Alias kept for legacy reverse() callers; dispatch is handled by edit_message.
    path('<uuid:conversation_id>/messages/<uuid:message_id>/', protect_view_with_active_kyc(views.edit_message), name='delete-message'),
    path('<uuid:conversation_id>/messages/<uuid:message_id>/read/', protect_view_with_active_kyc(views.mark_single_message_as_read), name='mark-single-read'),
    path('<uuid:conversation_id>/typing/', protect_view_with_active_kyc(views.typing_indicator), name='typing-indicator'),
    path('<uuid:conversation_id>/presence/', protect_view_with_active_kyc(views.conversation_presence), name='conversation-presence'),
    
    # Premium call features
    path('calls/initiate-premium/', protect_view_with_active_kyc(views.InitiatePremiumCallView.as_view()), name='initiate-premium-call'),

    # Keep generic conversation routes last so more specific paths retain precedence.
    path('<uuid:conversation_id>/restore/', protect_view_with_active_kyc(views.restore_conversation), name='restore-conversation'),
    path('<uuid:conversation_id>/', protect_view_with_active_kyc(views.delete_conversation), name='delete-conversation'),
]
