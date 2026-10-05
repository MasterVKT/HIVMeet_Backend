# Plan de remédiation frontend — Conversations et messagerie

**Destinataires :** équipe Flutter, BLoC, QA mobile et design produit  
**Source :** [audit croisé du 26 juillet 2026](AUDIT_CROISE_CONVERSATIONS_SESSIONS_2026-07-26.md) et plan backend associé  
**But :** exposer de manière sûre le filtre non lu et le masquage de conversation, consommer les réponses et événements backend sans état local faux, et supprimer les contrats morts.

---

## 1. Précondition : contrat backend à consommer

Ce plan ne demande pas à Flutter de contourner un défaut serveur. Les changements UI doivent être intégrés après disponibilité sur staging du contrat suivant :

| Surface | Consommation Flutter attendue |
|---|---|
| Liste | `GET /conversations/?page=&page_size=&status=all|unread|archived`. Une valeur invalide est un `400`; l’UI ne présente que `all` et `unread` car l’archivage n’est pas un produit livré. |
| Lecture | `PUT .../mark-as-read/` retourne `messages_marked`, `unread_count_for_me` et éventuellement `read_at`. La valeur serveur est l’autorité pour le badge. |
| Suppression | `DELETE /conversations/{id}/` retourne `204` et masque seulement pour l’utilisateur courant. `404` signifie que la conversation n’est déjà plus disponible ; l’élément peut rester retiré localement. |
| Média WS | `message.created` contient toujours les trois clés `media_url`, `media_type`, `media_thumbnail_url`, nulles pour un texte. |
| Lecture WS | `message.read` contient `reader_id`, `message_ids`, `read_at`, sans contenu de message. |
| Dépréciations | Aucun appel à `GET /conversations/{id}/` ni à l’URL signée média. Le seul upload est multipart `/messages/media/`. |

Si l’un de ces points n’est pas présent sur staging, conserver l’action correspondante masquée et ouvrir un écart de contrat : ne jamais interpréter silencieusement une réponse `400`, `404` ou `405` comme un succès générique.

---

## 2. Architecture cible et fichiers à faire évoluer

| Couche | Fichiers ciblés | Changement |
|---|---|---|
| Data source | `lib/data/datasources/remote/messaging_api.dart` | Ajouter `deleteConversation`; conserver `getConversations(status:)` mais avec conversion depuis un enum. Retirer `getConversation` et `generateMediaUploadUrl`. |
| Repository domain | `lib/domain/repositories/message_repository.dart` | Ajouter `ConversationFilter` au contrat de liste et `deleteConversation`. Retirer les signatures des deux endpoints morts. |
| Repository data | `lib/data/repositories/message_repository_impl.dart` | Propager le filtre, mapper les erreurs, implémenter DELETE et retirer les mappers de l’upload signé devenus inutiles. |
| Use cases | `lib/domain/usecases/message/get_conversations.dart`, nouveau `delete_conversation.dart` | Ajouter le filtre au paramètre et le préserver dans `nextPage`; créer le use case de suppression. Supprimer `domain/usecases/chat/generate_media_upload_url.dart`. |
| Presentation state | `lib/presentation/blocs/conversations/*` | État du filtre actif, événement de changement de filtre, suppression optimiste avec rollback contrôlé et message d’action i18n. |
| UI | `lib/presentation/pages/conversations/conversations_page.dart` | Sélecteur All/Non lus, confirmation de masquage, action destructive réactivée seulement après injection du use case. |
| Temps réel | `lib/core/services/chat_websocket_service.dart`, `lib/presentation/blocs/chat/chat_bloc.dart` | Conserver la logique `message.read` existante et tester qu’un `message.created` média hydrate les trois URLs. |
| i18n/DI/tests | `assets/translations/fr.json`, `assets/translations/en.json`, fichiers générés DI et `test/**` | Ajouter les chaînes, régénérer DI et couvrir les nouveaux états. |

La présentation ne doit jamais appeler `MessagingApi` directement : la page émet un événement, le BLoC utilise un use case, le use case passe par l’interface repository et l’implémentation appelle la datasource.

---

## 3. Implémentation méthodique

### Phase A — typer le filtre sans casser la pagination

1. Déclarer un enum de domaine `ConversationFilter { all, unread, archived }` avec une seule conversion contrôlée vers la valeur API. Ne pas propager des chaînes libres dans le BLoC.
2. Étendre `GetConversationsParams` avec `filter`, par défaut `all`; `initial()` l’accepte et `nextPage()` le conserve. L’inclure dans `Equatable.props`.
3. Étendre `MessageRepository.getConversations`, l’implémentation et `MessagingApi.getConversations` afin de transmettre ce filtre à chaque page.
4. Dans `ConversationsState`, ajouter `activeFilter`. Lors d’un changement de filtre : annuler le chargement infini en cours si nécessaire, remettre `_currentPage` à `1`, vider les caches de liste/recherche, puis recharger la page 1 avec le filtre choisi.
5. Garder la recherche locale comme une projection de la liste filtrée par le serveur. Le passage de filtre ne doit pas conserver une recherche qui masque silencieusement le résultat ; soit effacer la recherche, soit afficher explicitement son état vide.
6. Dans l’UI, proposer un contrôle accessible « Toutes » / « Non lus ». Ne pas proposer « Archivées » : le backend le supporte seulement comme valeur de compatibilité vide, pas comme fonctionnalité produit.

**Acceptation :** le deuxième chargement en infinite scroll conserve `unread`; le retour depuis un chat rafraîchit la liste avec le filtre actif, pas avec `all`.

### Phase B — exposer le masquage de conversation de manière optimiste et réversible

1. Ajouter `MessagingApi.deleteConversation(conversationId)` utilisant `DELETE /conversations/{id}/` sans body.
2. Ajouter `MessageRepository.deleteConversation` puis `DeleteConversation` avec un paramètre typé `conversationId`.
3. Ajouter l’événement `DeleteConversation` au BLoC et injecter le nouveau use case. Avant l’appel, prendre un snapshot cohérent de `_allConversations`, de la projection recherchée, du total non lu et du filtre actif.
4. Retirer immédiatement l’élément de la source `_allConversations`, recalculer la projection visible et `totalUnreadCount`, puis appeler le use case.
5. Traiter les réponses ainsi :

| Résultat | Comportement UI |
|---|---|
| `204` | Conserver le retrait optimiste. |
| `404` | Conserver le retrait : la conversation est déjà inaccessible, donc la liste locale doit converger. Rafraîchir discrètement à la prochaine opportunité. |
| `401` | Restaurer le snapshot et déclencher le flux d’authentification/rafraîchissement existant. |
| `403`, `429`, réseau, `5xx` | Restaurer exactement le snapshot et afficher un message localisé, sans remplacer la liste par un écran d’erreur. |

6. Éviter `ConversationsError` pour une erreur d’action, car cet état remplace aujourd’hui toute la liste. Ajouter plutôt un champ transitoire `actionError` à `ConversationsLoaded` (puis un événement de consommation) ou un état d’effet one-shot qui préserve les données.
7. Dans le menu long-press, ajouter un dialogue de confirmation explicite : « Masquer cette conversation ? Les nouveaux messages la feront réapparaître. » L’étiquette doit employer le verbe **masquer**, pas « supprimer définitivement ».
8. Au retour d’un chat, ou après un pull-to-refresh, conserver le filtre et ne pas réinjecter localement une conversation masquée.

**Acceptation :** A masque une conversation ; elle disparaît immédiatement chez A, reste visible chez B, puis réapparaît chez A après un message entrant de B, texte ou média.

### Phase C — fiabiliser la lecture et les badges

1. Le flux chat existant continue d’envoyer le dernier message entrant réellement visible au endpoint bulk. Ne jamais déclencher un marquage depuis un préchargement d’historique ou une page hors viewport.
2. Faire évoluer le résultat repository/use case de lecture pour remonter `unreadCountForMe` retourné par le serveur. Après succès, le `ConversationsBloc` remplace son estimation optimiste par cette valeur exacte et recalcule `totalUnreadCount`.
3. Si la requête de lecture échoue, ne pas déclarer localement un message lu. Conserver le badge jusqu’à une réponse `200` ou un événement de synchronisation fiable.
4. Conserver le traitement actuel de `message.read` dans `ChatBloc`: il ne transforme en `read` que les messages `isMine == true` lorsque `reader_id != currentUserId` et que l’ID appartient à `message_ids`.
5. Traiter l’événement envoyé au lecteur comme une confirmation multi-appareil, mais ne pas utiliser son contenu pour décrémenter aveuglément le badge de la liste : la réponse REST `unread_count_for_me` est l’autorité.

**Acceptation :** avec deux messages entrants et un seul lu, le chat marque seulement le bon message, le badge reste à `1` et le filtre Non lus conserve la conversation.

### Phase D — recevoir les médias temps réel et retirer les appels morts

1. `ChatBloc` lit déjà `mediaUrl`, `mediaType` et `mediaThumbnailUrl` dans l’événement `message.created`. Ne pas ajouter de fallback qui invente une URL ; vérifier que les valeurs désormais fournies par le backend sont simplement passées à l’entité `Message`.
2. Tester l’affichage avec image, vidéo et audio, puis avec texte pour lequel les trois champs sont nuls.
3. Retirer proprement `getConversation` de la datasource, de l’interface repository et de son implémentation. Une navigation vers le chat part toujours d’une conversation de liste et charge ses messages, elle ne dépend pas d’un GET conversation inexistant.
4. Retirer `generateMediaUploadUrl`, `MediaUploadTarget` s’il n’a plus d’autre consommateur, son use case et les enregistrements DI associés. Le chemin unique est `sendMediaMessage` multipart ; aucune URL de stockage ne doit être demandée ou construite sur le client.
5. Après suppression, rechercher les symboles retirés dans tout `lib/`, régénérer les fichiers injectables avec la commande habituelle du projet et traiter toute référence restante comme une erreur de compilation.

---

## 4. Gestion des erreurs, confidentialité et i18n

1. Mapper les familles HTTP vers des messages traduits, jamais vers `error` brut reçu du serveur. Les messages FR/EN à ajouter couvrent : filtre invalide, masquage impossible, restauration après échec, conversation indisponible, confirmation et annulation.
2. Le dialogue de masquage ne doit afficher que le nom déjà public de l’interlocuteur, et seulement si le design le prévoit. Il ne doit jamais exposer statut VIH, email, token, ID, localisation précise ou contenu de dernier message dans le message d’erreur.
3. Ne pas écrire le token WebSocket, des payloads de message ou des identifiants de conversation dans les logs de production. Les `debugPrint` doivent être conditionnés au mode debug et ne pas inclure de contenu sensible.
4. Un `401` conserve le comportement centralisé de renouvellement/connexion. Le BLoC ne tente pas de boucles de retry silencieuses sur DELETE ; l’utilisateur garde le contrôle.

---

## 5. Tests frontend et validation intégrée

| Niveau | Cas requis |
|---|---|
| Data source | `status` correctement sérialisé ; DELETE sans body ; aucun appel aux deux endpoints retirés. |
| Repository | Pagination conserve le filtre ; réponse lecture mappe `unread_count_for_me`; `204` DELETE est un succès. |
| BLoC conversations | Changement de filtre réinitialise page/caches ; page 2 conserve le filtre ; suppression optimiste ; rollback réseau/5xx ; `404` reste retiré ; total non lu cohérent. |
| BLoC chat/WS | `message.read` ne modifie que les messages envoyés ; événement média hydrate URL/type/thumbnail ; texte garde les valeurs nulles. |
| Widget | Sélecteur accessible, dialogue de masquage, état vide Non lus, message d’erreur localisé sans perte de liste. |
| Parcours intégré | Masquer → message texte entrant → réapparition ; masquage → média entrant → réapparition et rendu média ; lecture partielle → badge/filtre exacts. |

Exécuter après l’implémentation :

```powershell
flutter analyze
dart format lib/ test/
flutter test
flutter build apk --debug
```

Le SDK local qui ne voit pas Git doit être réparé avant de considérer `flutter analyze` comme validé ; un échec d’outillage ne vaut pas validation de code. Conserver un test de contrat contre staging pour les réponses `400`, `401`, `404`, `204`, `200` et les deux événements WebSocket.

---

## 6. Séquence de livraison coordonnée

1. Backend livre d’abord les transactions, le recalcul exact, les payloads WS et la documentation contractuelle sur staging.
2. QA valide la matrice backend, en particulier concurrence, lecture partielle et média temps réel.
3. Flutter intègre les couches Data → Domain → BLoC → UI dans cet ordre, sans exposer le bouton tant que le test de contrat staging n’est pas vert.
4. QA mobile exécute les parcours croisés à deux comptes et deux appareils.
5. Déployer le backend puis Flutter. Le mécanisme de masquage déjà existant est rétrocompatible : une ancienne version Flutter continue de l’ignorer, une version nouvelle n’interprète pas `archived` comme un masquage.

---

## 7. Définition de terminé

Le travail frontend est terminé seulement lorsque :

- la liste All/Non lus est paginée avec un enum typé ;
- l’action « Masquer » est confirmée, optimiste et correctement restaurée en cas d’échec ;
- les badges reposent sur la réponse serveur de lecture ;
- les médias entrants WebSocket s’affichent sans rechargement REST ;
- les deux endpoints morts et leurs dépendances DI sont supprimés ;
- FR et EN sont complets, les tests passsent et le build debug réussit ;
- les tests de contrat staging prouvent l’accord avec le plan backend associé.
