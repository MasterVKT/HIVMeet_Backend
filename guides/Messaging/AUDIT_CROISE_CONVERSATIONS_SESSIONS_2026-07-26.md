# Audit croisé — évolutions Conversations/Messaging

**Date :** 26 juillet 2026  
**Nature :** revue de cohérence inter-sessions, contrat REST/WebSocket et intégration Flutter.  
**Décision :** correctifs requis avant de considérer la fonctionnalité de lecture comme entièrement fiable ; aucune régression qui annule les cinq objectifs principaux n’a été constatée.

---

## 1. Périmètre et limites de traçabilité

Les contenus des trois conversations antérieures demandées ne sont pas directement accessibles depuis ce fil. Le périmètre a donc été reconstitué à partir des rapports locaux, de leur chronologie de modification et de l’état réel du dépôt.

Les trois rapports immédiatement antérieurs à `BACKEND_CONVERSATIONS_N1_QUERY.md` sont :

1. `BACKEND_CONVERSATION_FILTER_UNREAD.md` ;
2. `BACKEND_READ_RECEIPT_WS_BROADCAST.md` ;
3. `BACKEND_AUTO_MARK_READ_ON_GET.md`.

Le premier est aussi cité explicitement dans la demande. L’audit porte donc sur les cinq sujets distincts suivants :

| Sujet | État observé |
|---|---|
| Filtre `status=unread` | Implémenté côté SQL dans `ConversationListView` |
| Accusés de lecture WebSocket | Implémentés de `MessageService` au consumer |
| GET de messages sans auto-marquer lu | Implémenté |
| N+1 de la liste de conversations | Préchargement photos + dernier message implémenté |
| Masquage/suppression de conversation | État par utilisateur, migration et `DELETE` implémentés |

Le dépôt est déjà fortement modifié hors de ce périmètre (85 fichiers détectés par le graphe). Les constats ci-dessous se limitent au code de messagerie, à ses contrats et à ses consommateurs Flutter ; aucun changement existant non lié n’a été modifié.

---

## 2. Méthode et éléments vérifiés

- Rapports Markdown de la messagerie, code source Django, migration `messaging.0002`, routes, serializers, services, signals et consumer Channels.
- Graphe de dépendances : la liste de conversations, l’envoi, les compteurs de non-lus, les reçus de lecture et le WebSocket sont les flux concernés. Le graphe ne rattache pas encore automatiquement les tests de `ConversationListView`, mais les tests réels ont été vérifiés manuellement.
- Contrats `docs/API_DOCUMENTATION.md` et `docs/FRONTEND_MESSAGING_API.md`.
- Client Flutter en lecture seule : `MessagingApi`, repository, use cases, `ConversationsBloc`, `ChatBloc`, `ChatWebSocketService` et pages conversations/chat.

### Validations exécutées

| Contrôle | Résultat |
|---|---|
| `python manage.py check` | OK |
| `python manage.py makemigrations --check --dry-run` | OK |
| `python manage.py showmigrations messaging` | `0001` et `0002_conversation_hidden_state` appliquées |
| 9 tests ciblés REST/WebSocket | OK — 9/9, y compris filtre, pagination, N+1, lecture explicite, masquage et reçu WebSocket |
| Suite complète `messaging.tests` + WebSocket | Dépasse la limite locale de 60 s ; non concluante dans ce contexte |
| `dart analyze` ciblé | Non lancé : le SDK Flutter local échoue avant l’analyse avec `Unable to find git in your PATH`, alors que `git` est disponible dans PowerShell. C’est un défaut d’environnement/outillage, pas un diagnostic de code Flutter. |

---

## 3. Cohérence des travaux — ce qui reste effectivement actif

Les évolutions ne s’annulent pas entre elles :

1. Le `GET /conversations/?status=unread` annote le compteur du participant authentifié puis filtre en base. Il conserve le filtrage des conversations masquées et la pagination.
2. Le masquage est bien un état `ConversationHiddenState` par utilisateur : il n’efface ni le `Match` ni l’historique de l’autre participant. Un message entrant efface uniquement l’état du destinataire et réaffiche donc la conversation attendue.
3. Le préchargement N+1 est compatible avec les deux filtres : photos principales et dernier message sont chargés sans réintroduire de requête par ligne ; le test mesuré plafonne à cinq requêtes, pagination comprise.
4. Le GET des messages est maintenant en lecture seule. Les compteurs et les statuts ne changent que via les endpoints explicites de lecture, qui diffusent ensuite `message.read` au groupe WebSocket.
5. Flutter sait désormais décoder `message.read` et met à jour les messages envoyés par l’utilisateur courant. Cette partie du contrat est alignée.

Le point important est donc qu’il n’y a pas de « tâche annulée » parmi ces cinq objectifs. Les problèmes ci-dessous sont des défauts de cohérence restants ou des intégrations inachevées.

---

## 4. Anomalies et solutions proposées

### Critique — le compteur de non-lus peut être remis à zéro alors que des messages restent non lus

**Preuve.** `MessageService.mark_single_message_as_read()` marque un seul message, puis appelle `message.match.reset_unread(user)`. De même, `mark_messages_as_read()` remet le compteur à zéro après avoir marqué les messages jusqu’à un curseur. Si un message plus récent reste `sent`/`delivered`, son statut est correct mais `user*_unread_count` devient faussement nul.

**Impact croisé.** Le filtre nouvellement ajouté `status=unread` repose précisément sur ces compteurs dénormalisés. Une conversation contenant encore un message non lu peut donc disparaître du filtre et son badge peut passer à zéro. La diffusion `message.read` reste exacte pour les IDs effectivement lus, ce qui rend l’incohérence visible entre le chat, le badge et la liste.

**Solution.** Dans une transaction atomique, verrouiller le `Match`, appliquer le marquage puis recalculer le nombre de messages reçus encore en `sent`/`delivered` avant d’écrire le champ du participant. Ne jamais appeler `reset_unread()` pour un marquage partiel. Prévoir aussi un ordre de curseur stable `(created_at, id)`.

**Tests à ajouter.** Deux messages reçus : marquer seulement le premier doit laisser le second non lu, le compteur à `1` et la conversation dans `status=unread`. Ajouter le même cas avec un nouveau message arrivé entre la lecture et la mise à jour.

---

### Élevée — l’envoi de message, le compteur et la réapparition ne forment pas une seule unité atomique

**Preuve.** `MessageService.send_message()` crée le message, met à jour `last_message_at`, incrémente le compteur puis supprime l’état de masquage du destinataire, sans `transaction.atomic()`. Le signal `post_save` peut déjà envoyer notification et événement WebSocket immédiatement après la création du message.

**Impact croisé.** En cas d’erreur après la création (compteur, mise à jour du match ou suppression d’état), l’API peut répondre en erreur alors que le message existe déjà et a possiblement été diffusé. Le client peut retirer son envoi optimiste tandis que le correspondant reçoit le message. Cela compromet directement la réapparition après masquage et la fiabilité des compteurs alimentant `unread`.

**Solution.** Encapsuler les écritures de `send_message()` dans `transaction.atomic()` avec verrouillage du `Match` ou mises à jour `F()` appropriées. Déclencher les effets externes du signal (WebSocket, Celery, notification) via `transaction.on_commit()` afin qu’aucun événement ne soit publié si la transaction est annulée. Appliquer le même principe au chemin média qui délègue à `send_message()`.

**Tests à ajouter.** Injecter une erreur après la création du message et vérifier l’absence de message, de compteur, de réapparition, de notification et d’événement WebSocket. Ajouter deux envois concurrents au même destinataire pour vérifier qu’aucune incrémentation n’est perdue.

---

### Élevée — les champs média WebSocket sont émis puis perdus par le consumer

**Preuve.** `messaging.signals.handle_new_message` place `media_url`, `media_type` et `media_thumbnail_url` dans l’événement de groupe. `ConversationConsumer.message_created()` ne les recopie pas dans le JSON envoyé au client. Le `ChatBloc` Flutter lit pourtant ces trois clés.

**Impact.** Un média reçu en temps réel arrive sans URL ni miniature côté Flutter ; il ne peut être rendu correctement qu’après un rechargement REST. Ce défaut touche le même flux temps réel que les reçus de lecture et masque partiellement le succès du travail de contrat WebSocket.

**Solution.** Faire suivre les trois champs avec `event.get(...)` dans `ConversationConsumer.message_created()`, puis ajouter un test WebSocket de bout en bout sur image, audio et vidéo. Le test actuel valide le signal, mais pas la transformation signal → consumer → Flutter.

---

### Moyenne — le backend est prêt pour supprimer/masquer et filtrer, mais Flutter ne les expose pas

**Preuve.** `MessagingApi.getConversations()` accepte `status`, mais `MessageRepository`, `GetConversationsParams`, `ConversationsBloc` et l’UI ne le propagent pas. Pour le masquage, aucune méthode `deleteConversation`, aucun contrat repository/use case et aucun événement BLoC n’existent ; `ConversationsPage` conserve explicitement le commentaire indiquant que le backend ne fournit pas l’endpoint.

**Impact.** Le `DELETE` et `status=unread` ne sont pas annulés côté backend, mais restent inaccessibles dans le parcours utilisateur. Le commentaire Flutter est désormais factuellement obsolète et peut faire réintroduire une mauvaise hypothèse plus tard.

**Solution.**

1. Ajouter `status` (enum typé) au repository, use case et `ConversationsBloc`, puis un contrôle UX uniquement après décision produit.
2. Ajouter `deleteConversation` dans `MessagingApi` et les couches Clean Architecture, avec un événement BLoC de retrait optimiste et rollback en cas de `401/404/5xx`.
3. Réactiver l’action dans le menu seulement après ces deux étapes et mettre à jour son commentaire/documentation.

---

### Moyenne — deux méthodes Flutter pointent toujours vers des endpoints absents

**Preuve.** `MessagingApi.getConversation()` appelle `GET /conversations/{id}/`, alors que cette route UUID n’accepte maintenant que `DELETE` : un appel GET reçoit donc `405`, non `404`. `generateMediaUploadUrl()` appelle l’ancien endpoint d’URL signée, retiré du backend ; il reçoit `404`. Le flux normal d’envoi de média utilise bien le multipart actuel et n’est pas concerné.

**Solution.** Retirer ces méthodes, leur use case et leur enregistrement DI s’ils ne font plus partie du produit. Sinon, définir et implémenter un contrat backend explicite plutôt que de conserver des appels morts. Ajouter des tests de contrat pour garantir `405/404` ou le nouveau comportement choisi.

---

### Moyenne — validation de query params et pagination non entièrement déterministe

**Preuve.** Toute valeur de `status` autre que `unread` ou `archived` est silencieusement traitée comme `all`, bien que le contrat documente un ensemble fermé. La liste est ordonnée uniquement par `-last_message_at`; deux conversations avec le même horodatage peuvent changer d’ordre entre deux pages.

**Impact.** Une faute cliente peut produire une liste complète au lieu d’une erreur exploitable. Des pages successives peuvent théoriquement dupliquer ou omettre un élément lors d’horodatages identiques.

**Solution.** Valider `status` via un serializer de paramètres de requête et retourner `400` pour une valeur invalide. Employer `order_by('-last_message_at', '-id')` et tester explicitement deux timestamps identiques sur les pages 1 et 2.

---

### Basse — documentation d’intégration endommagée par l’encodage

**Preuve.** Les ajouts de `docs/API_DOCUMENTATION.md` et une grande partie de `docs/FRONTEND_MESSAGING_API.md` affichent des séquences telles que `dÃ©faut`, `authentifiÃ©` et `1â€“50` au lieu de texte UTF-8 valide.

**Impact.** Le code reste exécutable, mais le contrat destiné à Flutter est moins fiable, difficile à relire et dangereux pour les générateurs/outils qui utilisent la documentation comme source de vérité.

**Solution.** Convertir les deux fichiers en UTF-8 sans BOM, vérifier le diff sémantique après normalisation des fins de ligne et ajouter une vérification d’encodage dans CI ou la revue de documentation.

---

## 5. Couverture de test : acquis et manques

| Flux | Couvert et validé | Manque à couvrir |
|---|---|---|
| `status=unread` | Isolation par participant, `all`, `archived`, pagination | Valeur `status` invalide, ordre égal, compteur partiellement lu |
| N+1 liste | Nombre constant de requêtes, contenu photo/dernier message | Pagination sous horodatage identique et données volumineuses |
| GET lecture seule | Aucun statut/compteur/FCM modifié, pagination cursor | Comportement sur paramètres invalides |
| Reçu de lecture | REST, tolérance channel layer indisponible, WebSocket aux deux participants | Cohérence de compteur lors d’une lecture partielle/concurrente |
| Masquage | Visibilité A/B, idempotence, réapparition entrante | Erreur transactionnelle et envoi média réaffichant une conversation |
| Média WebSocket | Signal vérifié | Consumer et client réels : URLs/médias absents aujourd’hui |

---

## 6. Ordre de remédiation conseillé

1. **Corriger l’intégrité transactionnelle et le recalcul des non-lus** : c’est ce qui protège simultanément les badges, le filtre `unread`, les reçus et la réapparition.
2. **Corriger le consumer média** et ajouter le test WebSocket de bout en bout.
3. **Finaliser le contrat Flutter** : suppression optimiste, suppression des endpoints morts et propagation optionnelle de `status`.
4. **Durcir les paramètres de liste** et l’ordre de pagination.
5. **Réparer l’encodage de la documentation** après validation du contrat final.

---

## 7. Recommandation de merge

Les cinq objectifs initiaux sont présents et les neuf validations ciblées réussissent. En revanche, ne pas qualifier le module de « production-ready » tant que les deux défauts élevés (compteurs partiels et atomicité d’envoi) ne sont pas corrigés. La mise à disposition UI de la suppression et du filtre peut être planifiée séparément, mais le consumer média doit être corrigé avant de promettre la réception média temps réel.
