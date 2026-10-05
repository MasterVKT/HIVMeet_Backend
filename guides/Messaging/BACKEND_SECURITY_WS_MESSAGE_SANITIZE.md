# Backend requis — Sanitization contournée sur le WebSocket (message.send)

**Sévérité** : Élevée (sécurité — XSS/injection potentielle).
**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`, §9 « Risques sécurité »). Bug backend pur — aucune action frontend possible pour le corriger, le contenu part directement du client vers le serveur via la socket.

---

## 1. État actuel exact (vérifié dans le code backend réel)

Le endpoint REST `POST /api/v1/conversations/{id}/messages/` sanitize correctement le contenu via `SendMessageSerializer` :

```python
# messaging/serializers.py, lignes 16-20 et 141-150
DISALLOWED_MESSAGE_PATTERNS = (
    r'javascript\s*:',
    r'data:text/html',
    r'<\s*script',
)

class SendMessageSerializer(serializers.Serializer):
    ...
    def validate_content(self, value):
        """Sanitize text content and reject obviously unsafe payloads."""
        raw_value = value or ''
        for pattern in DISALLOWED_MESSAGE_PATTERNS:
            if re.search(pattern, raw_value, flags=re.IGNORECASE):
                raise serializers.ValidationError(
                    _('Content contains unsupported or unsafe markup.')
                )
        sanitized_value = strip_tags(raw_value).strip()
        return sanitized_value
```

Mais le path **WebSocket** (`ws/conversations/<uuid:conversation_id>/`, type de message `message.send`) **contourne entièrement ce serializer** :

```python
# messaging/consumers.py, lignes 174-210
async def _handle_message_send(self, data):
    """Handle real-time message sending."""
    try:
        content = data.get('content', '').strip()
        client_message_id = data.get('client_message_id')

        if not content:
            await self.send(text_data=json.dumps({...}))
            return

        # Persist via service (fires post_save signal → broadcasts + push)
        message = await self._create_message(
            content=content,
            client_message_id=client_message_id,
        )
        ...

# lignes 489-509
async def _create_message(self, content, client_message_id=None):
    """Persist a text message via the service layer (fires post_save signal)."""
    def _send():
        message, error = MessageService.send_message(
            sender=self.user,
            match=self.match,
            content=content,              # <-- contenu brut, jamais passé par SendMessageSerializer
            client_message_id=client_message_id,
        )
        return message, error
    ...
```

`MessageService.send_message` (`messaging/services.py`, lignes 92-161) fait uniquement `normalized_content = content or ''` — **aucun `strip_tags`, aucune regex de blocage**. Un message envoyé via WebSocket avec `content: "<script>...</script>"` ou `javascript:alert(1)` est persisté **tel quel** en base et rediffusé à l'autre participant via `message.created` (et potentiellement rendu dans un futur client web ou une WebView sans échappement).

## 2. Problème

Une seule des deux voies d'entrée (REST vs WS) applique la sanitization. C'est une faille de validation classique : le contrôle de sécurité existe, mais n'est pas appliqué de manière centralisée. Impact : injection de contenu malveillant (XSS si consommé par un rendu HTML quelque part, corruption d'affichage côté clients qui font confiance au contenu stocké).

## 3. Fix prescrit

Centraliser la sanitization dans `MessageService.send_message` lui-même (source de vérité unique, appelée par **les deux** chemins REST et WS), plutôt que de dupliquer la logique du serializer dans le consumer.

```python
# messaging/services.py — ajouter en haut du fichier
import re
from django.utils.html import strip_tags

DISALLOWED_MESSAGE_PATTERNS = (
    r'javascript\s*:',
    r'data:text/html',
    r'<\s*script',
)


class MessageContentRejected(ValueError):
    """Levée quand le contenu d'un message contient un pattern interdit."""
    pass


def sanitize_message_content(raw_content: str) -> str:
    """Sanitize partagé REST + WebSocket. Lève MessageContentRejected si le
    contenu matche un pattern explicitement dangereux (au lieu de le
    silencieusement nettoyer), pour rester cohérent avec le comportement
    REST existant (400 Bad Request côté client)."""
    raw_value = raw_content or ''
    for pattern in DISALLOWED_MESSAGE_PATTERNS:
        if re.search(pattern, raw_value, flags=re.IGNORECASE):
            raise MessageContentRejected('Content contains unsupported or unsafe markup.')
    return strip_tags(raw_value).strip()
```

```python
# messaging/services.py::MessageService.send_message — appliquer avant la création
@staticmethod
def send_message(
    sender, match, content, message_type=Message.TEXT,
    media_file_path=None, client_message_id=None,
):
    ...
    if message_type == Message.TEXT:
        try:
            content = sanitize_message_content(content)
        except MessageContentRejected as exc:
            return None, str(exc)
    ...
    # reste de la méthode inchangé (normalized_content = content or '', etc.)
```

```python
# messaging/serializers.py — SendMessageSerializer.validate_content réutilise
# la même fonction au lieu de dupliquer la regex (garantit qu'un futur
# changement de pattern se propage aux deux chemins automatiquement)
from .services import sanitize_message_content, MessageContentRejected

def validate_content(self, value):
    try:
        return sanitize_message_content(value)
    except MessageContentRejected as exc:
        raise serializers.ValidationError(_(str(exc)))
```

```python
# messaging/consumers.py::_handle_message_send — gérer le rejet
async def _handle_message_send(self, data):
    try:
        content = data.get('content', '').strip()
        client_message_id = data.get('client_message_id')

        if not content:
            await self.send(text_data=json.dumps({
                'type': 'error', 'message': 'Message cannot be empty', 'code': 'EMPTY_MESSAGE',
            }))
            return

        message = await self._create_message(content=content, client_message_id=client_message_id)

        if not message:
            # _create_message retourne None si MessageService a rejeté le
            # contenu (sanitization) OU si la création a échoué pour une
            # autre raison — le message d'erreur exact est déjà loggé côté
            # _create_message.
            await self.send(text_data=json.dumps({
                'type': 'error', 'message': 'Failed to create message', 'code': 'CREATION_FAILED',
            }))
            return
        ...
```

Aucun changement nécessaire dans `_create_message` (lignes 489-509) : il appelle déjà `MessageService.send_message`, qui appliquera désormais la sanitization automatiquement — la correction se fait à la source, pas en dupliquant la validation dans le consumer.

## 4. Impact frontend

Aucun. Le frontend envoie déjà le contenu brut saisi par l'utilisateur via `ChatWebSocketService.sendTextMessage` (actuellement dead code — le REST reste le chemin principal d'envoi, voir `lib/core/services/chat_websocket_service.dart`) et via `SendTextMessage` REST. Les deux chemins bénéficieront automatiquement du fix sans aucune modification client.

## 5. Critères de validation

- Envoyer `{"type": "message.send", "content": "<script>alert(1)</script>", "client_message_id": "test-1"}` sur la socket → réponse `{"type": "error", "code": "CREATION_FAILED"}`, **aucun** `Message` créé en base avec ce contenu.
- Le comportement REST existant (déjà correct) reste inchangé — pas de régression sur `POST /conversations/{id}/messages/`.
- Un message texte normal (emoji, accents, retours à la ligne) passe toujours sans altération via les deux chemins.
