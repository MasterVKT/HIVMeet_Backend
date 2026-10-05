# Frontend — Messagerie temps réel : rapport d'action complet

**Date** : 2026-07-31
**Auteur** : session backend (Claude), lecture seule sur `d:\Projets\HIVMeet\hivmeet`
**Destinataire** : agent AI en charge du développement frontend Flutter
**Objectif** : porter la messagerie HIVMeet au niveau fonctionnel standard des applications de chat grand public (WhatsApp, Signal, Telegram) — accusés de réception fiables en temps réel, badges exacts, aucune perte de message, aucune régression.

Ce rapport fait suite à deux livraisons backend :
1. [BACKEND_REALTIME_MESSAGING_REQUIREMENTS.md](BACKEND_REALTIME_MESSAGING_REQUIREMENTS.md) — demande initiale (session frontend précédente)
2. [BACKEND_REALTIME_MESSAGING_IMPLEMENTATION_REPORT.md](BACKEND_REALTIME_MESSAGING_IMPLEMENTATION_REPORT.md) — implémentation backend livrée le 2026-07-31 (119 puis 151 tests verts)

**Tout ce qui est décrit ici comme « backend » est déjà déployé sur cette branche.** Ce rapport ne liste que le travail frontend restant. Aucune modification frontend n'a été effectuée par cette session (accès lecture seule) — chaque section ci-dessous est actionnable directement par l'agent frontend.

---

## 0. Comment lire ce rapport

- **P0** : bloque le fonctionnement standard attendu (ticks manquants, badge faux). À faire en premier.
- **P1** : dégrade l'expérience ou casse un contrat existant (bug confirmé par lecture de code, pas une supposition).
- **P2** : amélioration de cohérence, non bloquante.
- Chaque item donne : le symptôme, le fichier:ligne exact, la cause, et le correctif à appliquer avec le style de code déjà en usage dans le projet (BLoC/Cubit + `RealtimeEventBus` + Clean Architecture).
- **§7 est hors périmètre messagerie** — trouvé en auditant la cohérence transverse, à traiter par la même équipe mais sans lien avec le temps réel.

---

## 1. Checklist « standard WhatsApp » — état actuel

| Comportement standard | État | Détail |
|---|---|---|
| Message envoyé → reçu par le serveur (✓ gris) | ✅ | `MessageStatus.sending` → `sent` géré |
| Message livré à l'appareil du destinataire (✓✓ gris) | ⚠️ **Backend prêt, frontend non branché** | §2.1 |
| Message lu par le destinataire (✓✓ violet) | ✅ | `message.read` déjà géré en direct dans `ChatBloc` |
| Badge de non-lus exact sur l'onglet Messages | ⚠️ **Approximation à corriger** | §2.2 |
| Liste des conversations mise à jour en temps réel, app en arrière-plan sur cet écran | ✅ | `ConversationsBloc` + `RealtimeEventBus` déjà réactifs |
| Aucun message perdu si deux arrivent à moins de 2s d'intervalle | ⚠️ **Risque confirmé** | §2.3 |
| Notification push dédupliquée avec le WebSocket | ✅ | dédup fenêtre 2s déjà en place, à affiner (§2.3) |
| Reconnexion automatique après coupure réseau, sans perte | ✅ | déjà implémenté (backoff + resync REST) |
| Indicateur de frappe (typing) | ✅ | déjà fonctionnel via WS |
| Présence en ligne / dernière activité | ✅ | déjà fonctionnel via WS |
| Appels entrants visibles même hors de l'écran de chat | N/A | backend prêt, UI d'appel = `// TODO` côté frontend, pas d'action requise maintenant |

---

## 2. P0 — Bloquant

### 2.1 `message.delivered` / `message_delivered` n'est reçu nulle part

**Symptôme** : le ✓✓ gris (delivered) n'apparaît jamais en direct. `MessageBubble._buildStatusIcon()` sait très bien le dessiner (`message_bubble.dart:327-328`), mais rien ne le déclenche avant un rechargement complet de la conversation.

**Cause exacte** : le backend émet désormais deux événements que le frontend ignore totalement :
- `{"type": "message.delivered", ...}` sur `/ws/conversations/{id}/` (le canal que `ChatWebSocketService` écoute déjà)
- `{"type": "message_delivered", ...}` sur `/ws/notifications/` (le canal que `NotificationWebSocketService` écoute déjà)

Ni l'un ni l'autre n'a de branche dans leurs switch respectifs :
- `chat_websocket_service.dart:10-29` (`enum WsEventType`) n'a pas de valeur `messageDelivered`
- `chat_websocket_service.dart:266-283` (`_parseEventType`) ne reconnaît pas `'message.delivered'` → tombe dans `default` → `WsEventType.unknown`
- `chat_bloc.dart:511-559` (switch sur `wsEvent.type`) n'a donc pas de case correspondante — même en ajoutant l'enum, il faut ajouter la case
- `notification_websocket_service.dart:160-204` (`_onRawMessage`) ne reconnaît pas `'message_delivered'` → tombe dans `default` (silencieusement ignoré, pas de crash)

**Payload exact envoyé par le backend** (voir `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` §4.3 et §7.2 pour le détail complet) :

Sur `/ws/conversations/{id}/` :
```json
{
  "type": "message.delivered",
  "conversation_id": "uuid",
  "message_ids": ["uuid", "uuid"],
  "delivered_at": "2026-07-31T16:00:00.000000+00:00"
}
```

Sur `/ws/notifications/` (adressé à l'auteur des messages, pour mettre à jour ses ticks même hors de l'écran de chat) :
```json
{
  "type": "message_delivered",
  "conversation_id": "uuid",
  "message_ids": ["uuid"],
  "delivered_at": "2026-07-31T16:00:00.000000+00:00"
}
```

**Correctif — `chat_websocket_service.dart`** :

```dart
enum WsEventType {
  messageCreated,
  messageRead,
  messageDelivered,   // AJOUT
  typingIndicator,
  presenceUpdate,
  pong,
  error,
  unknown,
  reconnected,
  disconnected,
}
```

```dart
WsEventType _parseEventType(String raw) {
  switch (raw) {
    case 'message.created':
      return WsEventType.messageCreated;
    case 'message.read':
      return WsEventType.messageRead;
    case 'message.delivered':               // AJOUT
      return WsEventType.messageDelivered;
    case 'typing.indicator':
      return WsEventType.typingIndicator;
    // ... reste inchangé
  }
}
```

**Correctif — `chat_bloc.dart`** : suivre exactement le patron déjà utilisé pour `messageRead` (lignes 516-536), en dupliquant vers un nouvel événement interne `_WebSocketMessageDelivered` et un handler `_onWsMessageDelivered` qui met à jour `status`/`isDelivered`/`deliveredAt` **uniquement** sur les messages `isMine` dont l'id est dans `message_ids` — copier le corps de `_onWsMessageRead` (lignes 672-701) en remplaçant `MessageStatus.read`/`isRead`/`readAt` par `MessageStatus.delivered`/`isDelivered`/`deliveredAt`, avec cette garde supplémentaire :

```dart
void _onWsMessageDelivered(
  _WebSocketMessageDelivered event,
  Emitter<ChatState> emit,
) {
  final currentState = state;
  if (currentState is! ChatLoaded) return;

  var changed = false;
  final updatedMessages = _allMessages.map((message) {
    final shouldMarkDelivered =
        message.isMine && event.messageIds.contains(message.id);
    if (!shouldMarkDelivered) return message;
    // Un message déjà `read` ne doit jamais régresser vers `delivered` —
    // le read arrive potentiellement après un léger décalage réseau et
    // "lu" est un état strictement plus avancé que "livré".
    if (message.status == MessageStatus.read) return message;

    final updatedMessage = message.copyWith(
      status: MessageStatus.delivered,
      isDelivered: true,
      deliveredAt: event.deliveredAt ?? message.deliveredAt,
    );
    if (updatedMessage != message) changed = true;
    return updatedMessage;
  }).toList();

  if (!changed) return;
  _allMessages = updatedMessages;
  emit(currentState.copyWith(messages: _allMessages));
}
```

Ajouter la case dans le switch de `_onConnectWebSocket` (après le case `messageRead`, même structure de parsing des champs) et déclarer `_WebSocketMessageDelivered` dans `chat_event.dart` sur le modèle de `_WebSocketMessageRead`.

**Correctif — `notification_websocket_service.dart`** : ajouter un case `'message_delivered'` dans `_onRawMessage`, publiant sur le bus. Nécessite un nouveau membre `RealtimeEventType.messageDelivered` (voir §2.1bis).

**Pourquoi la garde `status == read`** : sans elle, un accusé de livraison arrivant en retard (paquet réordonné) pourrait faire régresser visuellement un message déjà marqué lu — un bug que WhatsApp évite précisément par cette règle de monotonie (`sent < delivered < read`, jamais de retour arrière).

### 2.1bis Nouveau membre `RealtimeEventType.messageDelivered`

`realtime_event.dart:9-25` doit gagner un membre `messageDelivered`, avec le même profil que `messageRead` (porte `conversationId`). Puis :

- `realtime_event_bus.dart:65-70` (`_dedupeKeyFor`) : **pas besoin d'entrée dédiée** — `message_delivered` n'arrive que par un seul canal (`/ws/notifications/`), il n'y a rien à dédupliquer contre. Ajouter simplement le cas dans le `switch` exhaustif pour qu'il retourne `null` (comme `messageRead` aujourd'hui) — sinon le compilateur Dart signalera un switch non exhaustif.
- `conversations_bloc.dart:69-92` (`_onRealtimeEvent`) : la liste de conversations n'affiche aucun tick de statut (vérifié dans `conversation_card.dart` — seul le badge de non-lus est affiché). `messageDelivered` n'a donc **aucun effet observable** sur cet écran ; ajouter le cas dans le `switch` pour satisfaire l'exhaustivité, sans action (`break` ou regroupé avec les cas déjà no-op comme `likeReceived`).
- `unread_cubit.dart:39-52` (`_onRealtimeEvent`) : même chose — `delivered` ne change jamais un compteur de non-lus (le backend le garantit explicitement, voir le rapport backend §3). Ajouter le cas au `switch`, sans action.

---

### 2.2 `UnreadCubit` n'utilise pas l'endpoint dédié — badge sous-estimé au-delà de 20 conversations

**Symptôme** : un utilisateur avec des messages non lus dans plus de 20 conversations actives voit un badge global inférieur au vrai total.

**Fichier** : `unread_cubit.dart:59-83` (`refresh()`). Somme actuellement `page.conversations.fold(...unreadCount)` sur `GetConversations(filter: all)` — plafonné à `page_size=20`.

**Le fix attendu existe déjà côté backend** : `GET /api/v1/conversations/unread-count/` → `{"unread_count": <int>}`, somme serveur exacte sur toutes les conversations actives non masquées (voir rapport backend §2.3 et `docs/API_DOCUMENTATION.md`).

**Correctif, en 3 étapes suivant l'architecture existante** :

**a) `messaging_api.dart`** — ajouter à côté de `getConversations` :
```dart
/// Compteur global exact de non-lus (toutes conversations, pas seulement
/// la première page).
/// GET /conversations/unread-count/
Future<Response<Map<String, dynamic>>> getUnreadCount() async {
  return await _apiClient.get('/conversations/unread-count/');
}
```

**b) `message_repository.dart` + `message_repository_impl.dart`** — ajouter au contrat :
```dart
// message_repository.dart (interface)
Future<Either<Failure, int>> getUnreadCount();
```
```dart
// message_repository_impl.dart
@override
Future<Either<Failure, int>> getUnreadCount() async {
  try {
    final response = await _messagingApi.getUnreadCount();
    final count = response.data?['unread_count'] as int? ?? 0;
    return Right(count);
  } on DioException catch (e) {
    return Left(ServerFailure(message: e.message ?? 'Erreur de serveur'));
  }
}
```

**c) Nouveau usecase `GetUnreadCount`** (`lib/domain/usecases/message/get_unread_count.dart`), calqué sur `get_conversations.dart` :
```dart
@injectable
class GetUnreadCount implements UseCase<int, NoParams> {
  final MessageRepository repository;
  GetUnreadCount(this.repository);

  @override
  Future<Either<Failure, int>> call(NoParams params) =>
      repository.getUnreadCount();
}
```
(Vérifier si `NoParams` existe déjà dans `core/usecases/usecase.dart` — sinon suivre le patron d'un usecase existant sans paramètres du projet.)

**d) `unread_cubit.dart`** — remplacer le corps de `refresh()` :
```dart
Future<void> refresh() async {
  final generation = ++_refreshGeneration;
  final result = await _getUnreadCount(NoParams());
  if (generation != _refreshGeneration || isClosed) return;

  result.fold(
    (_) {
      // Échec silencieux : le badge garde sa dernière valeur connue.
    },
    (count) {
      if (!isClosed) emit(count);
    },
  );
}
```
et injecter `GetUnreadCount` dans le constructeur à la place de `GetConversations` (mettre à jour le site d'injection — probablement via `get_it`/`injectable`, régénérer avec `flutter pub run build_runner build --delete-conflicting-outputs` puisque le projet utilise `injectable_generator`).

Le commentaire de doc du fichier (`unread_cubit.dart:59-65`) qui référence explicitement cette limitation connue doit être mis à jour pour refléter le nouveau comportement.

---

### 2.3 Fenêtre de déduplication à 2s peut avaler un message légitime

**Symptôme** : si le même expéditeur envoie deux messages dans la même conversation à moins de 2 secondes d'intervalle (cas courant : envois rapides successifs, ou double-tap accidentel sur "envoyer"), **le second `RealtimeEvent` de type `newMessage` est silencieusement supprimé** par la déduplication.

**Fichier** : `realtime_event_bus.dart:39-70`. `_dedupeKeyFor` construit la clé `'${event.type.name}:$conversationId'` — identique pour deux messages différents de la même conversation dans la fenêtre de 2s (`_dedupeWindow`).

**Impact réel, précisé** :
- `UnreadCubit` : **aucun impact** — il ne fait que déclencher un `refresh()` débouncé (source de vérité = serveur), un événement supprimé ne change rien au résultat final.
- `ConversationsBloc._onConversationRealtimeSignal` (`conversations_bloc.dart:281-330`) : **impact réel**. Le patch optimiste utilise `event.preview`/`event.senderId` du dernier `RealtimeEvent` reçu pour mettre à jour `lastMessage` affiché dans la liste — si le second message d'une paire rapprochée est avalé, la carte de conversation peut afficher un aperçu obsolète (le premier message au lieu du second) jusqu'à la prochaine réconciliation (débouncée à 600ms après le dernier signal, donc généralement rattrapé — mais avec un flash visible incorrect entre-temps).
- Le message lui-même n'est **jamais perdu côté persistance ou côté écran de chat ouvert** : `ChatBloc` reçoit ses événements directement via `ChatWebSocketService` (canal `/ws/conversations/{id}/`), qui **ne passe pas par `RealtimeEventBus`** — aucune déduplication ne s'applique à cette voie. La perte est donc limitée à l'aperçu affiché dans la liste des conversations, pas à la conversation elle-même.

**Correctif** : le backend expose désormais `message_id` sur les deux canaux qui alimentent le bus (WebSocket notifications ET FCM — voir rapport backend §2.1, §4). Resserrer la clé de dédup :

```dart
String? _dedupeKeyFor(RealtimeEvent event) {
  switch (event.type) {
    case RealtimeEventType.newMessage:
      final conversationId = event.conversationId;
      if (conversationId == null || conversationId.isEmpty) return null;
      // Clé par message si l'id est connu (les deux sources — WS et FCM —
      // le portent désormais) ; fallback sur l'ancien comportement sinon
      // pour ne pas régresser une source qui l'omettrait.
      final messageId = event.messageId;
      return messageId != null && messageId.isNotEmpty
          ? '${event.type.name}:$conversationId:$messageId'
          : '${event.type.name}:$conversationId';
    case RealtimeEventType.messageRead:
      final conversationId = event.conversationId;
      if (conversationId == null || conversationId.isEmpty) return null;
      return '${event.type.name}:$conversationId';
    // ... reste inchangé
  }
}
```

Cela nécessite d'ajouter un champ `messageId` à `RealtimeEvent` (`realtime_event.dart:32-61`) et de le remplir dans les deux producteurs :
- `notification_websocket_service.dart:183-191` (case `'new_message'`) : le backend envoie désormais `data['message_id']`, l'ajouter au `RealtimeEvent` publié
- `notification_service.dart:169-177` (FCM, case `'new_message'`) : vérifier que le payload FCM `data` contient bien `message_id` — le backend le construit à partir de `message_payload()` (`notifications/payloads.py`), qui n'inclut **pas** `message_id` dans le payload FCM data actuellement (seulement `notification_id`, `conversation_id`, `from_user_id`, `title`, `body`). **Si ce champ manque côté FCM, la clé de dédup resserrée ne s'applique qu'à la source WebSocket** — toujours une amélioration nette (élimine le problème pour l'utilisateur avec l'app au premier plan, le cas le plus fréquent), sans risque de régression pour la source FCM qui retombe sur l'ancien comportement par le fallback ci-dessus.

---

## 3. P1 — Contrats à respecter

### 3.1 `message_read` reçu sur `/ws/notifications/` n'a plus besoin d'être ignoré par `ChatBloc`

Non-action requise — `ChatBloc` ne s'abonne pas à `RealtimeEventBus` pour les messages, seulement à `ChatWebSocketService` (canal direct), donc pas de double traitement à craindre. Mentionné ici uniquement pour confirmer qu'aucun changement n'est nécessaire sur ce point : le rapport backend §2.1 le documente comme potentiellement redondant, ce ne l'est pas dans l'implémentation actuelle du frontend.

### 3.2 `notification_id` FCM change de forme — vérifier toute dépendance à sa stabilité par expéditeur

Le backend est passé de `msg_<sender_id>` (identique pour tous les messages d'un même expéditeur) à `msg_<message_id>` (unique par message). `notification_service.dart:216-236` (`_buildAppNotification`) utilise `data['notification_id']` comme `AppNotification.id` :

```dart
final id = data['notification_id'] as String? ??
    '${DateTime.now().millisecondsSinceEpoch}';
```

**Aucune correction requise** — ce champ était déjà traité comme un identifiant opaque, pas comme une clé de regroupement. L'effet du changement backend est strictement positif : avant, deux messages successifs du même expéditeur généraient le même `AppNotification.id` et se remplaçaient l'un l'autre dans tout store/liste indexé par id (`_store.add(notification)`, `notification_service.dart:143`) — silencieusement perdant la notification du premier message. Vérifier simplement qu'aucun test frontend n'a été écrit en dur autour de l'ancienne valeur `msg_<sender_id>` (recherche `grep -rn "notification_id" test/`).

### 3.3 Documentation interne à mettre à jour (commentaires de code)

Plusieurs commentaires de doc dans le code Flutter référencent explicitement l'état *avant* le patch backend et doivent être mis à jour pour ne pas induire en erreur la prochaine session :

- `notification_websocket_service.dart:18-23` : *"Aujourd'hui ce groupe ne reçoit que `new_match` / `like` / `super_like`"* → obsolète, `new_message`/`message_read`/`message_delivered`/`incoming_call`/`call_update` y sont désormais aussi diffusés.
- `unread_cubit.dart:59-65` : voir §2.2, à réécrire une fois le fix appliqué.
- `realtime_event_bus.dart:9-16` : la mention *"une fois le patch backend appliqué"* est maintenant caduque — le patch est appliqué.

Ce sont des commentaires, sans effet fonctionnel, mais leur exactitude conditionne la qualité des futures sessions d'agent sur ce code.

---

## 4. P2 — Cohérence, non bloquant

### 4.1 `incoming_call` / `call_update` sur `/ws/notifications/` : aucun consommateur, normal

`notification_websocket_service.dart:160-204` ignore ces deux types (branche `default`). C'est correct en l'état : `chat_page.dart` contient un `// TODO: Implémenter les appels WebRTC` et aucune UI d'appel n'existe encore. **Ne rien faire maintenant** — mais le jour où l'écran d'appel sera construit, le canal `user_{id}` est déjà prêt côté backend (voir `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` §4.10/4.11/§7.2) : il suffira d'ajouter les cases `'incoming_call'`/`'call_update'` dans `_onRawMessage` en suivant exactement le patron de `'new_message'`.

### 4.2 Refresh JWT in-band sur WebSocket : décision produit actée, rien à faire

Le backend a délibérément choisi de ne **pas** implémenter de refresh de token in-band (surface d'attaque inutile sur une app de santé). Le frontend gère déjà correctement ce choix — `ChatWebSocketService`/`NotificationWebSocketService` récupèrent un token frais à chaque tentative de connexion, y compris les reconnexions en backoff. **Aucune action requise.** Documenté ici uniquement pour clore explicitement ce point du rapport backend initial (§P2) côté frontend.

---

## 5. Analyse des échecs pré-existants — répartition backend / frontend

Le rapport backend précédent mentionnait deux catégories d'échecs de tests **backend**, toutes deux corrigées dans cette session (151 tests backend passent désormais avec `manage.py test` sans argument, contre un `ImportError` bloquant auparavant) :

| Échec pré-existant | Source | Statut |
|---|---|---|
| `profiles/tests.py` vs `profiles/tests/` (conflit de découverte) | Backend | ✅ Corrigé — stub vide supprimé |
| `subscriptions.tests` — `birth_date` NOT NULL, `Decimal`, namespace `reverse()` | Backend | ✅ Corrigé — 22 tests passent |
| 3 scripts racine (`test_revocation_workflow.py` et 2 autres) plantaient `manage.py test` | Backend (hygiène) | ✅ Corrigé — renommés hors du pattern de découverte |
| **Cache de statut premium jamais invalidé à la révocation** | Backend | ✅ **Bug de sécurité fonctionnelle corrigé** (voir §6) |
| **`GET /subscriptions/current/` renvoyait `{}` sans abonnement** | Backend | ✅ Corrigé |

**Aucun de ces échecs n'avait de source frontend.** En revanche, l'audit de cohérence transverse demandé a fait remonter un bug frontend réel, sans lien avec la messagerie, décrit en §7.

---

## 6. Contexte : bug de sécurité fonctionnelle corrigé côté backend (premium)

Sans action frontend requise, mais à connaître car il change un comportement observable : `PremiumFeatureService.check_premium_status` et `subscriptions.utils.is_premium_user` **lisaient/écrivaient la même clé de cache Redis avec deux définitions différentes du statut premium**, et **aucune invalidation n'avait lieu à l'annulation ou l'expiration d'un abonnement** — un utilisateur dont l'abonnement venait d'être révoqué gardait l'accès aux fonctionnalités premium (appels, médias) jusqu'à 5 minutes après (TTL du cache).

Les deux définitions sont maintenant unifiées, et le cache est invalidé sur : achat, annulation, expiration, et toute écriture directe des champs `is_premium`/`premium_until` sur `User`. **Conséquence frontend attendue** : un test manuel qui annule un abonnement doit désormais voir le gate premium se refermer immédiatement (avant : jusqu'à 5 min de délai). Si un test d'intégration frontend s'appuyait sur ce délai de grâce non intentionnel, il faut le corriger — aucune fenêtre de code trouvée qui en dépendrait dans l'audit effectué.

---

## 7. Hors périmètre messagerie — bug frontend confirmé, à corriger séparément

Trouvé en vérifiant la cohérence du contrat `subscriptions` pendant l'audit ci-dessus (§5-6 l'ont mis en lumière). **Sans lien avec le temps réel de la messagerie**, mais bloque une fonctionnalité premium dont dépendent les messages média et les appels — à signaler à l'équipe/agent responsable de l'écran Premium.

**Symptôme** : `getCurrentSubscription()` et `cancelSubscription()` retournent toujours `null`/aucun abonnement, même quand l'utilisateur en a un actif.

**Cause** : `premium_repository_impl.dart:45` et `:144-145` lisent `payload['subscription']` :
```dart
final sub = payload['subscription'] as Map<String, dynamic>?;
if (sub == null) return const Right(null);
```
Mais `CurrentSubscriptionSerializer`/`EmptySubscriptionSerializer`/`CancelSubscriptionResponseSerializer` (`subscriptions/serializers.py:59-98`, `subscriptions/views.py:213`) renvoient les champs **directement à la racine** de la réponse — il n'y a jamais eu de clé `"subscription"` dans le payload JSON réel :
```json
{
  "subscription_id": "sub_xxx",
  "plan_id": "...",
  "status": "active",
  "features_summary": { ... }
}
```
`payload['subscription']` vaut donc toujours `null`, quel que soit l'état réel de l'abonnement.

**Correctif suggéré** :
```dart
Future<Either<Failure, UserSubscription?>> getCurrentSubscription() async {
  try {
    final response = await _subscriptionsApi.getCurrentSubscription();
    final payload = response.data!;
    if (payload['status'] == 'none' || payload['subscription_id'] == null) {
      return const Right(null);
    }
    return Right(_mapJsonToUserSubscription(payload));
  } on DioException catch (e) {
    return Left(ServerFailure(message: e.message ?? 'Erreur de serveur'));
  }
}
```
Même correction pour le site d'appel en `:144-145` (`cancelSubscription`). Vérifier `_mapJsonToUserSubscription` lit bien des clés à plat (`subscription_id`, `plan_id`, `status`, `current_period_start`, `current_period_end`, `auto_renew`, `cancel_at_period_end`, `features_summary`) — c'est déjà cohérent avec le serializer backend, seul l'enrobage `payload['subscription']` est faux.

**Pourquoi c'est mentionné ici malgré le hors-périmètre** : `check_feature_availability(user, 'media_messaging')` et `'calls'` côté backend gate déjà correctement l'envoi de médias et les appels (testé, fonctionne) — mais si l'écran Premium frontend affiche systématiquement "aucun abonnement actif" à cause de ce bug, l'utilisateur ne peut pas vérifier visuellement que son achat a été pris en compte, ce qui est une régression d'expérience directement adjacente au flux "passer premium pour débloquer les médias/appels" documenté dans la messagerie.

---

## 8. Plan de vérification suggéré (après implémentation)

```dart
// Test manuel / test d'intégration à ajouter :
// 1. Ouvrir la conversation A, l'envoyer un message depuis un second compte B
//    connecté uniquement sur /ws/notifications/ (pas sur /ws/conversations/A/) :
//    le tick du message de A doit passer à "delivered" (✓✓ gris) sans
//    rechargement.
// 2. B ouvre ensuite la conversation : le tick de A passe à "read" (✓✓ violet).
// 3. Envoyer 2 messages consécutifs à <2s d'intervalle depuis A vers B pendant
//    que B est sur l'écran ConversationsPage (pas ChatPage) : la carte de
//    conversation doit refléter le second message, pas le premier.
// 4. Avoir >20 conversations non lues sur un compte de test : le badge global
//    doit correspondre à la somme réelle, pas être plafonné à 20.
```

Côté backend, `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md` et `docs/FRONTEND_MESSAGING_API.md` documentent chaque payload exact à utiliser comme référence pendant l'implémentation — ne pas re-déduire les formats depuis ce rapport, il vise l'exhaustivité des *gaps*, pas la spec canonique des payloads.

---

## 9. Vérification de cohérence — synthèse

- **Aucune modification frontend recommandée ici ne requiert de changement backend supplémentaire** : tous les payloads consommés (§2.1, §2.2, §2.3) sont déjà émis par le backend actuellement déployé sur cette branche.
- **Aucun contrat existant n'est modifié rétroactivement** : les ajouts (`messageDelivered`, `getUnreadCount`) sont additifs — aucun champ ni endpoint existant n'est retiré ou renommé, donc aucun risque de régression sur le code frontend qui ne serait pas touché par ce rapport.
- **§7 est indépendant et sans interaction avec §2-4** : le fix suggéré ne touche que `premium_repository_impl.dart`, un fichier absent de toute la chaîne de messagerie temps réel.
- **Le fix §2.3 (dédup par `messageId`) est rétro-compatible par construction** (fallback explicite sur l'ancien comportement si `messageId` est absent) — aucun risque de casser la dédup WS↔FCM existante pour `new_match`/`like`/`super_like`, qui ne portent pas de `conversationId` et ne sont donc jamais concernés par `_dedupeKeyFor`.
- Suite au fix §2.2, `UnreadCubit` cesse de dépendre de `GetConversations` — vérifier qu'aucun autre composant n'instancie `UnreadCubit` en supposant sa dépendance actuelle (recherche `GetConversations` dans les sites d'injection de `UnreadCubit`).
