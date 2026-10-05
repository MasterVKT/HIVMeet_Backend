"""Rules shared by persisted Premium read-receipt alerts."""

from __future__ import annotations

from subscriptions.utils import is_premium_user


MESSAGE_READ_NOTIFICATIONS = 'message_read_notifications'


def is_read_receipt_alert_enabled(user) -> bool:
    """Return whether ``user`` opted in to Premium read-receipt alerts.

    The absence of the preference is an enabled default for an active Premium
    user.  Only the boolean value ``False`` is an explicit opt-out; this keeps
    legacy or partial settings documents forward-compatible.
    """
    if not is_premium_user(user):
        return False
    settings = user.notification_settings or {}
    return settings.get(MESSAGE_READ_NOTIFICATIONS, True) is not False
