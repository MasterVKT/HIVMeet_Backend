"""
Builders de payload FCM data respectant le contrat frontend HIVMeet.

Le frontend Flutter lit exclusivement message.data (pas message.notification).
Toutes les valeurs sont des strings (contrainte FCM).

Clés communes: type, notification_id, title, body
Clés optionnelles par type:
  new_match  → match_id, from_user_id
  new_message → conversation_id, message_id, from_user_id
  like / super_like → from_user_id (vide si destinataire non-premium)
"""


def match_payload(match_id: str, other_user_display_name: str, other_user_id: str) -> dict:
    """Payload pour un nouveau match."""
    return {
        'type': 'new_match',
        'notification_id': f'match_{match_id}',
        'title': "C'est un match !",
        'body': f'Vous avez matché avec {other_user_display_name}',
        'match_id': str(match_id),
        'from_user_id': str(other_user_id),
        'conversation_id': str(match_id),
    }


def like_payload(
    notification_id: str,
    is_super: bool,
    liker_display_name: str,
    liker_id: str,
    recipient_is_premium: bool,
) -> dict:
    """Payload pour un like ou super-like.
    Si recipient_is_premium=False, l'identité du likeur est masquée.
    """
    notif_type = 'super_like' if is_super else 'like'

    if is_super:
        title = 'Vous avez reçu un Super Like !'
        body_premium = f'{liker_display_name} vous a Super Liké'
        body_anon = 'Quelqu\'un vous a Super Liké ! Passez Premium pour voir qui'
    else:
        title = 'Quelqu\'un vous a liké !'
        body_premium = f'{liker_display_name} vous a liké'
        body_anon = 'Passez Premium pour voir qui vous a liké'

    return {
        'type': notif_type,
        'notification_id': str(notification_id),
        'title': title,
        'body': body_premium if recipient_is_premium else body_anon,
        'from_user_id': str(liker_id) if recipient_is_premium else '',
    }


def message_payload(
    message_id: str,
    conversation_id: str,
    sender_display_name: str,
    sender_id: str,
    preview: str,
    notification_id: str | None = None,
    preview_enabled: bool = True,
) -> dict:
    """Payload pour un nouveau message."""
    title = sender_display_name if preview_enabled else 'Nouveau message'
    return {
        'type': 'new_message',
        # The persisted Notification UUID is authoritative.  The fallback is
        # retained only for tasks queued by the previous release.
        'notification_id': str(notification_id or f'msg_{message_id}'),
        'message_id': str(message_id),
        'title': title,
        'body': preview[:80] if preview_enabled and preview else '',
        'conversation_id': str(conversation_id),
        'from_user_id': str(sender_id),
        'sender_name': sender_display_name if preview_enabled else '',
        'preview_enabled': 'true' if preview_enabled else 'false',
    }


def subscription_expiry_payload(
    user_id: str,
    days_remaining: int,
    expiry_date: str,
) -> dict:
    """Payload pour une notification d'expiration d'abonnement.

    Args:
        user_id: ID de l'utilisateur destinataire.
        days_remaining: Nombre de jours avant expiration (7, 5, 3, 1 ou 0).
        expiry_date: Date d'expiration au format ISO (YYYY-MM-DD).

    Returns:
        Dictionnaire de données FCM. Le frontend utilise ``days_remaining``
        pour choisir le texte localisé et navigue vers ``/premium`` au tap.
    """
    return {
        'type': 'subscription_expiring',
        'notification_id': f'sub_expiry_{user_id}_{days_remaining}d',
        'title': 'Votre abonnement expire bientôt',
        'body': f'Plus que {days_remaining} jours pour renouveler votre abonnement Premium',
        'days_remaining': str(days_remaining),
        'expiry_date': expiry_date,
    }


def report_resolved_payload(
    report_id: str,
    status: str,
    resolution_summary: str,
) -> dict:
    """Payload pour une notification de résolution de signalement.

    Args:
        report_id: ID du signalement.
        status: Statut de résolution ('resolved' ou 'dismissed').
        resolution_summary: Résumé de la décision prise.

    Returns:
        Dictionnaire de données FCM. Le frontend affiche la décision complète
        dans un dialog au tap.
    """
    status_label = 'Résolu' if status == 'resolved' else 'Rejeté'
    return {
        'type': 'report_resolved',
        'notification_id': f'report_{report_id}',
        'title': 'Votre signalement a été traité',
        'body': f'Décision : {status_label}. {resolution_summary}',
        'report_id': str(report_id),
        'status': status,
        'resolution_summary': resolution_summary,
    }
