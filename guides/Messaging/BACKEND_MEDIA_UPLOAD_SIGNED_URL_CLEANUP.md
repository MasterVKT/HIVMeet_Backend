# Backend requis — Nettoyage du flux « URL signée » média (généralement obsolète après bascule frontend)

**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`, §4.5 « Endpoint média — 2 flows incohérents »). Le frontend vient de **basculer sur le flux multipart** (`POST /conversations/{id}/messages/media/`) pour tout envoi de média — c'était l'« Option A » recommandée par l'audit. Ce fichier documente pourquoi et ce qu'il reste à faire côté backend.

---

## 1. État actuel exact (vérifié dans le code backend réel)

Deux flux d'envoi de média coexistent aujourd'hui côté backend :

**Flux A — URL signée** (`generate_media_upload_url`, `messaging/views.py`, lignes 267-287) :
```python
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_media_upload_url(request):
    """POST /api/v1/conversations/generate-media-upload-url/"""
    file_name = request.data.get('file_name') or 'upload.bin'
    content_type = request.data.get('content_type') or 'application/octet-stream'
    file_path_on_storage = f"messages/{request.user.id}/{uuid.uuid4()}_{file_name}"
    upload_url = f"https://storage.googleapis.com/hivmeet-media/{file_path_on_storage}"

    return Response({
        'upload_url': upload_url,
        'file_path_on_storage': file_path_on_storage,
        'content_type': content_type,
        'expires_in_seconds': 900,
    }, status=status.HTTP_200_OK)
```
**Ce n'est pas une vraie URL signée** : c'est une simple concaténation de chaîne vers un bucket GCS public, sans policy IAM, sans `Signature`/`X-Goog-Signature`, sans intégration `google-cloud-storage`. **N'importe quel client pourrait faire un `PUT` HTTP arbitraire sur ce chemin** sans autorisation réelle — c'est une vulnérabilité, pas juste une fonctionnalité incomplète. Ensuite, le message est créé via `POST /conversations/{id}/messages/` avec `media_file_path_on_storage` — mais `conversation_messages` (vue, lignes 78-151) et `MessageService.send_message` (`messaging/services.py`, lignes 92-161) **ne construisent jamais `media_url`** à partir de `media_file_path` sur ce chemin — le champ reste vide (`media_url = models.URLField(blank=True)` jamais rempli). Résultat : un message créé via ce flux a `media_url: ""` dans `MessageSerializer` — le frontend ne pourrait jamais afficher le média même si l'upload réussissait.

**Flux B — multipart direct** (`SendMediaMessageView`, `messaging/views.py`, lignes 394-435 ; `MessageService.create_media_message`, `messaging/services.py`, lignes 263-291) :
```python
@staticmethod
def create_media_message(sender, match, media_file, media_type, text='', client_message_id=None):
    media_file_path = f"messages/{match.id}/{uuid4()}_{media_file.name}"
    media_url = f"{getattr(settings, 'MEDIA_URL', '/media/')}{media_file_path}"

    message, error = MessageService.send_message(
        sender=sender, match=match, content=text, message_type=media_type,
        media_file_path=media_file_path, client_message_id=client_message_id,
    )
    if not message:
        raise ValueError(error or "Unable to create media message")

    message.media_url = media_url
    message.save(update_fields=['media_url'])
    return message
```
Ce flux **construit bien `media_url`**, applique le gate premium (`check_feature_availability(user, 'media_messaging')`) et la limite de taille (10MB, `messaging/views.py:416-417` + `messaging/serializers.py:188-196`) — **il fonctionne réellement de bout en bout**.

## 2. Ce qui a changé côté frontend

`MessageRepositoryImpl.sendMessage` (`lib/data/repositories/message_repository_impl.dart`) a été modifié pour **n'utiliser que le Flux B** (`MessagingApi.sendMediaMessage`, multipart). Le code qui appelait `generate_media_upload_url` puis faisait un `PUT` direct vers l'URL retournée a été **supprimé côté frontend**. La méthode `generateMediaUploadUrl` reste exposée dans l'interface `MessageRepository`/`MessagingApi` (un use case `GenerateMediaUploadUrl` y est toujours enregistré en DI) mais n'est plus appelée par le flux d'envoi de message.

## 3. Fix prescrit — deux options

### Option recommandée : supprimer le Flux A côté backend

Puisque plus aucun client HIVMeet connu n'utilise le flux URL signée, et qu'il constitue une vulnérabilité active (upload non authentifié vers un chemin prévisible) :

1. Supprimer la route `POST /conversations/generate-media-upload-url/` (`messaging/urls.py`, ligne 12) et la vue `generate_media_upload_url` (`messaging/views.py`, lignes 267-287).
2. Vérifier qu'aucun champ `media_file_path_on_storage` n'est plus jamais renseigné par un client actif avant de retirer la branche correspondante dans `SendMessageSerializer.validate` (`messaging/serializers.py`, lignes 152-170) et `conversation_messages` POST (`messaging/views.py`, lignes 129-151) — **ou la conserver en dead-code documenté** si une régression client mobile plus ancienne (version d'app non mise à jour) est encore possible en production. Décision produit à trancher selon le taux d'adoption de la nouvelle version de l'app.
3. Documenter dans `API_DOCUMENTATION.md` que `POST /conversations/{id}/messages/media/` (multipart) est l'unique chemin média supporté.

### Option alternative : corriger le Flux A pour un vrai usage futur (upload direct depuis navigateur web, hors scope mobile)

Si un futur client web a besoin d'uploader directement vers GCS sans passer par le serveur Django (cas d'usage légitime pour de gros fichiers), alors il faut réellement signer l'URL :

```python
# messaging/views.py — nécessite google-cloud-storage installé et
# GOOGLE_APPLICATION_CREDENTIALS / FIREBASE_STORAGE_BUCKET configurés
from google.cloud import storage

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_media_upload_url(request):
    file_name = request.data.get('file_name') or 'upload.bin'
    content_type = request.data.get('content_type') or 'application/octet-stream'
    file_path_on_storage = f"messages/{request.user.id}/{uuid.uuid4()}_{file_name}"

    client = storage.Client()
    bucket = client.bucket(settings.FIREBASE_STORAGE_BUCKET)
    blob = bucket.blob(file_path_on_storage)

    upload_url = blob.generate_signed_url(
        version='v4',
        expiration=timedelta(minutes=15),
        method='PUT',
        content_type=content_type,
    )

    return Response({
        'upload_url': upload_url,
        'file_path_on_storage': file_path_on_storage,
        'content_type': content_type,
        'expires_in_seconds': 900,
    }, status=status.HTTP_200_OK)
```

Et il faudrait alors AUSSI corriger `conversation_messages`/`MessageService.send_message` pour construire `media_url` à partir de `media_file_path_on_storage` (comme le fait déjà `create_media_message` pour le Flux B), sinon le bug « media_url jamais rempli » persiste.

**Recommandation** : Option 1 (suppression). Le flux multipart couvre déjà tous les cas d'usage mobile actuels, et maintenir un endpoint non sécurisé « au cas où » est un risque net négatif.

## 4. Impact frontend

Aucun changement frontend supplémentaire requis quelle que soit l'option choisie — le flux actif (multipart) fonctionne déjà de bout en bout et n'est pas concerné par ce nettoyage.

## 5. Critères de validation

- Si Option 1 : `POST /conversations/generate-media-upload-url/` retourne `404` (route supprimée) ; l'envoi de média via l'app mobile continue de fonctionner normalement (test manuel : envoyer une photo dans un chat premium).
- Si Option 2 : l'URL retournée par `generate_media_upload_url` contient réellement un paramètre de signature GCS (`X-Goog-Signature` ou équivalent v4) ; un `PUT` vers cette URL sans le paramètre de signature échoue avec `403` (comportement GCS standard) ; un message créé via ce flux a bien `media_url` non vide dans la réponse `MessageSerializer`.
