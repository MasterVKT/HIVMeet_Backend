# Frontend requis — intégration des accusés de lecture WebSocket

## 1. Objet et périmètre

Ce document est destiné à l'agent chargé du frontend Flutter. Il décrit les
changements nécessaires pour afficher en temps réel, chez l'expéditeur, qu'un
message a été lu par son interlocuteur.

Le prérequis backend est le rapport
`BACKEND_READ_RECEIPT_WS_BROADCAST.md` : le serveur doit diffuser l'événement
WebSocket décrit ci-dessous après un marquage explicite via l'API REST. Le
frontend **ne doit pas** émettre cet événement par WebSocket et ne doit pas
ajouter de nouvel appel REST. Il conserve les appels existants à
`PUT /conversations/{conversation_id}/messages/mark-as-read/` quand un message
est réellement visible.

Ce chantier ne modifie ni le contenu d'un message, ni la pagination, ni les
compteurs de conversations. Il met uniquement à jour l'état local des messages
que l'utilisateur courant a envoyés.

## 2. Contrat WebSocket à consommer

### Connexion existante

La connexion existante reste inchangée :

```
{wsBaseUrl}/ws/conversations/{conversation_id}/?token={jwt}
```

Elle est déjà gérée par `ChatWebSocketService`. L'événement est reçu uniquement
pour la conversation ouverte, car le backend le diffuse au groupe
`conversation_{conversation_id}` après avoir contrôlé que le lecteur appartient
au match actif.

### Événement entrant

```json
{
  "type": "message.read",
  "reader_id": "uuid-du-lecteur",
  "message_ids": ["uuid-message-1", "uuid-message-2"],
  "read_at": "2026-07-25T15:00:00.000000+00:00"
}
```

| Champ | Type | Obligatoire | Usage frontend |
| --- | --- | --- | --- |
| `type` | `string` | Oui | Doit être exactement `message.read`. |
| `reader_id` | `string` UUID | Oui | Identifie le lecteur. L'événement est ignoré s'il s'agit de l'utilisateur courant. |
| `message_ids` | `List<string>` UUID | Oui | Identifiants des messages réellement marqués lus ; seuls les messages locaux envoyés par l'utilisateur courant sont modifiés. |
| `read_at` | `string` ISO-8601 UTC | Oui | Horodatage du marquage ; utilisé pour les champs `readAt` et `readAtByRecipient` locaux. |

Le backend peut retransmettre l'événement au lecteur lui-même, notamment pour
un second appareil. C'est normal : le BLoC doit l'ignorer pour cet utilisateur,
car il ne doit pas transformer des messages reçus en messages « lus par un
destinataire ».

### Tolérance aux données invalides

Le code frontend doit ignorer silencieusement un événement dont `reader_id` est
vide, dont `message_ids` n'est pas une liste exploitable, ou dont la liste est
vide. `read_at` doit être analysé avec `DateTime.tryParse`; une valeur invalide
ne doit jamais faire tomber le chat. Dans ce cas, le statut peut être mis à
jour, avec les dates existantes conservées.

Les identifiants, le JWT et le contenu de messages ne doivent pas être écrits
dans les logs de production.

## 3. État actuel vérifié

Les fichiers suivants existent et sont les cibles exactes :

1. `lib/core/services/chat_websocket_service.dart`
   - `WsEventType` ne contient pas `messageRead`.
   - `_parseEventType` ne reconnaît pas `message.read`.
2. `lib/presentation/blocs/chat/chat_event.dart`
   - contient les événements internes WebSocket pour un message, le typing et
     la présence, mais aucun événement pour un reçu de lecture.
3. `lib/presentation/blocs/chat/chat_bloc.dart`
   - s'abonne déjà à `ChatWebSocketService.events` dans `_onConnectWebSocket`.
   - sait déjà remplacer les messages de `_allMessages` et émettre un
     `ChatLoaded.copyWith(messages: ...)`.
4. `lib/domain/entities/message.dart`
   - `MessageStatus.read`, `isRead`, `readAt`, `readAtByRecipient` et
     `Message.copyWith` existent déjà.
5. `lib/presentation/widgets/chat/message_bubble.dart`
   - affiche déjà `Icons.done_all` en violet pour `MessageStatus.read`.

Par conséquent, ne pas modifier les entités de domaine, le repository, les use
cases, l'API REST, les écrans, les chaînes ARB ou `MessageBubble` pour ce
travail. Aucun texte visible n'est introduit.

## 4. Implémentation demandée

### Étape 1 — reconnaître l'événement dans le service WebSocket

Dans `lib/core/services/chat_websocket_service.dart` :

1. Ajouter `messageRead` à `WsEventType`, à côté de `messageCreated`.
2. Ajouter le mapping suivant dans `_parseEventType` :

```dart
case 'message.read':
  return WsEventType.messageRead;
```

Ne pas modifier la connexion, l'authentification, le ping, le flux broadcast ou
les mécanismes de reconnexion existants. Ce changement rend l'événement typé,
mais ne décide pas encore comment modifier les messages : cette responsabilité
reste dans le BLoC.

### Étape 2 — introduire un événement interne BLoC typé

Dans `lib/presentation/blocs/chat/chat_event.dart`, ajouter à côté des autres
événements WebSocket :

```dart
class _WebSocketMessageRead extends ChatEvent {
  final String readerId;
  final Set<String> messageIds;
  final DateTime? readAt;

  const _WebSocketMessageRead({
    required this.readerId,
    required this.messageIds,
    required this.readAt,
  });

  @override
  List<Object?> get props => [readerId, messageIds, readAt];
}
```

L'événement est volontairement interne (préfixe `_`) : il est créé par le flux
WebSocket et n'est jamais déclenché par l'écran.

### Étape 3 — relayer l'événement typé vers le BLoC

Dans le constructeur de `ChatBloc`, enregistrer :

```dart
on<_WebSocketMessageRead>(_onWsMessageRead);
```

Dans le `switch` de `_onConnectWebSocket`, ajouter le cas `messageRead`. Ne pas
faire de casts non vérifiés de `message_ids` : convertir défensivement les
valeurs utiles en `Set<String>` et ignorer les valeurs vides.

Exemple compatible avec le contrat :

```dart
case WsEventType.messageRead:
  final readerId = wsEvent.data['reader_id'] as String? ?? '';
  final rawIds = wsEvent.data['message_ids'];
  final messageIds = rawIds is List
      ? rawIds
          .map((value) => value.toString())
          .where((id) => id.isNotEmpty)
          .toSet()
      : <String>{};
  final readAtRaw = wsEvent.data['read_at'] as String?;

  if (readerId.isEmpty || messageIds.isEmpty) break;

  add(_WebSocketMessageRead(
    readerId: readerId,
    messageIds: messageIds,
    readAt: readAtRaw == null ? null : DateTime.tryParse(readAtRaw),
  ));
```

La conversion par `toString()` est acceptable ici car le protocole backend
garantit des UUID sous forme texte ; elle évite un crash si un serveur ancien
ou un proxy sérialise une valeur de façon inattendue.

### Étape 4 — mettre à jour seulement les messages expédiés localement

Ajouter `_onWsMessageRead` dans `chat_bloc.dart`. Son invariant est essentiel :

- ignorer l'événement si le BLoC n'est pas `ChatLoaded` ;
- ignorer l'événement si `readerId` est vide ou égal à
  `_authService.currentUser?.id` ;
- ne modifier que les messages dont `message.isMine == true` **et** dont l'ID
  appartient à `messageIds` ;
- pour chaque message ciblé, définir `status: MessageStatus.read` et
  `isRead: true` ;
- si `readAt` est valide, l'affecter à `readAt` et `readAtByRecipient` ;
- ne pas recharger la conversation et ne pas appeler l'API REST ;
- ne rien émettre si aucun message local ne change.

Pseudo-code recommandé :

```dart
void _onWsMessageRead(
  _WebSocketMessageRead event,
  Emitter<ChatState> emit,
) {
  final currentState = state;
  if (currentState is! ChatLoaded) return;

  final currentUserId = _authService.currentUser?.id ?? '';
  if (event.readerId.isEmpty || event.readerId == currentUserId) return;

  var changed = false;
  final updatedMessages = _allMessages.map((message) {
    final shouldMarkRead = message.isMine && event.messageIds.contains(message.id);
    if (!shouldMarkRead) return message;

    changed = true;
    return message.copyWith(
      status: MessageStatus.read,
      isRead: true,
      readAt: event.readAt ?? message.readAt,
      readAtByRecipient: event.readAt ?? message.readAtByRecipient,
    );
  }).toList();

  if (!changed) return;
  _allMessages = updatedMessages;
  emit(currentState.copyWith(messages: _allMessages));
}
```

Cette opération est idempotente : recevoir plusieurs fois le même événement
produit le même état `read`. Elle conserve l'ordre de `_allMessages`, tous les
médias, réactions et métadonnées grâce à `Message.copyWith`.

## 5. Comportements attendus et cas limites

| Situation | Résultat attendu |
| --- | --- |
| A envoie, B ouvre le chat et marque les messages visibles comme lus | A voit immédiatement `done_all` violet sur les IDs inclus dans l'événement. |
| B reçoit l'événement sur un second appareil | B ne change aucun de ses messages, car `reader_id == currentUserId`. |
| L'événement contient un ID absent du cache local | Ignoré ; aucun rechargement ni erreur. |
| L'événement contient à la fois des messages de A et de B | Seuls les messages avec `isMine == true` sont modifiés. |
| L'événement arrive deux fois ou après un refresh REST | Idempotent ; statut `read` conservé. |
| `read_at` est invalide | Statut `read` mis à jour, dates locales conservées. |
| Le backend n'est pas encore déployé | Aucun événement `message.read`, donc aucune régression frontend. |
| Une ancienne application reçoit le nouvel événement | Elle le classe `unknown` et l'ignore ; aucun crash attendu. |

## 6. Tests requis

### Tests unitaires BLoC

Dans `test/presentation/blocs/chat/chat_bloc_test.dart`, utiliser un
`StreamController<WsEvent>.broadcast()` pour stubber le getter `events` de
`MockChatWebSocketService`. Après `LoadConversation` puis
`ConnectToWebSocket`, injecter un `WsEvent` de type `WsEventType.messageRead`.

Ajouter au minimum les tests suivants :

1. **Happy path** : un reçu de l'autre utilisateur marque uniquement le
   message local ciblé avec `MessageStatus.read`, `isRead == true` et les deux
   dates attendues.
2. **Isolation des messages** : un ID non ciblé et un message reçu
   (`isMine == false`) restent inchangés.
3. **Événement du lecteur courant** : aucun message n'est modifié.
4. **Données inexploitables** : `message_ids` absent/non-liste, liste vide ou
   `reader_id` vide n'émettent pas d'état erroné et ne lèvent pas d'exception.
5. **Idempotence** : deux événements identiques gardent le même résultat.

Le mock doit également stubber `getAccessToken`, `connect` et `events` pour que
le branchement réel de `_onConnectWebSocket` soit testé, pas uniquement le
handler isolé.

### Test du service WebSocket

Ajouter ou étendre un test de `ChatWebSocketService` pour vérifier que le JSON
entrant `{ "type": "message.read", ... }` est publié comme
`WsEventType.messageRead`. Si `_parseEventType` reste privé, le tester via un
petit serveur WebSocket local ou via le flux public `events`; ne pas exposer une
API de production uniquement pour un test.

### Validation manuelle sur deux sessions

1. Connecter A et B à la même conversation.
2. A envoie au moins deux messages.
3. Laisser A sur le chat ouvert ; B affiche les messages puis déclenche le
   marquage explicite existant.
4. Vérifier que, sans rechargement, les messages concernés de A passent de
   `sent`/`delivered` à `read` et affichent `done_all` violet.
5. Vérifier qu'un message non inclus dans `message_ids` reste inchangé.
6. Vérifier que B ne voit aucun changement erroné sur ses propres messages.
7. Couper le channel layer/Redis en environnement de test : le marquage REST
   doit toujours réussir ; seul l'affichage live est différé jusqu'au prochain
   chargement REST.

Exécuter ensuite :

```bash
dart format lib/core/services/chat_websocket_service.dart \
  lib/presentation/blocs/chat/chat_bloc.dart \
  lib/presentation/blocs/chat/chat_event.dart \
  test/presentation/blocs/chat/chat_bloc_test.dart
flutter test test/presentation/blocs/chat/chat_bloc_test.dart
flutter analyze
```

## 7. Déploiement et compatibilité

1. Déployer d'abord le backend qui diffuse `message.read`.
2. Déployer ensuite le frontend qui le reconnaît.

Cet ordre est sûr : les clients précédents ignorent le type inconnu, tandis que
les nouveaux clients continuent à fonctionner si le backend ne le diffuse pas
encore. Le contrat REST actuel de marquage et son format de réponse restent
inchangés.

## 8. Critères d'acceptation

- `message.read` est transformé en `WsEventType.messageRead`.
- Le BLoC ne modifie que les messages locaux ciblés et seulement quand le
  lecteur est l'autre participant.
- Les messages mis à jour ont `status == MessageStatus.read` et rendent déjà
  l'icône violette existante.
- Aucun appel REST, aucune navigation, aucun texte utilisateur et aucune
  donnée sensible supplémentaire ne sont introduits.
- Les tests unitaires et la validation à deux sessions passent.
- En cas de message WebSocket invalide ou dupliqué, le chat reste stable.
