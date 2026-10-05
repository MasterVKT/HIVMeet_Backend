# Plan de remédiation backend — Conversations et messagerie

**Destinataires :** équipe Django, Channels, base de données et QA backend  
**Source :** [audit croisé du 26 juillet 2026](AUDIT_CROISE_CONVERSATIONS_SESSIONS_2026-07-26.md)  
**But :** rétablir durablement l’intégrité des non-lus, rendre l’envoi atomique, compléter le contrat WebSocket média et stabiliser les contrats REST consommés par Flutter.

---

## 1. Résultat attendu et invariants non négociables

Après déploiement, les invariants suivants doivent être vrais en base et sur tous les canaux de sortie :

1. Pour chaque `Match` et participant, `user1_unread_count`/`user2_unread_count` est égal au nombre de messages reçus dont le statut est `sent` ou `delivered`.
2. Une lecture partielle ne marque ni ne compte comme lus les messages postérieurs au curseur explicitement fourni.
3. Un envoi de message produit soit **toutes** les écritures attendues (message, dernier message, compteur, réapparition), soit aucune. Aucun WebSocket, push ou enregistrement de notification ne part avant le commit.
4. Un même `client_message_id` ne peut créer qu’un seul message pour un même couple `(match, sender)`, y compris lors de deux requêtes concurrentes.
5. Un événement `message.created` fournit à Flutter les mêmes données média utiles que la réponse REST.
6. La liste conserve l’absence de N+1, un ordre déterministe et des paramètres strictement validés.
7. Masquer une conversation reste individuel ; ce mécanisme n’est pas un archivage.

Les messages, identifiants d’utilisateur, tokens et URLs privées ne doivent jamais être inclus dans les logs applicatifs. Les traces doivent se limiter aux IDs techniques nécessaires et à des compteurs agrégés.

---

## 2. Contrat cible partagé avec le frontend

Ce tableau est la source de coordination. Le rapport frontend reprend exactement les mêmes décisions ; aucune équipe ne doit inventer une variante locale.

| Surface | Contrat final |
|---|---|
| `GET /api/v1/conversations/` | JWT requis. `status` vaut exclusivement `all` (défaut), `unread` ou `archived`. Toute autre valeur, ou pagination invalide, renvoie `400` avec `error` et `details`. `archived` demeure une réponse `200` vide de compatibilité tant qu’un vrai produit d’archivage n’existe pas. |
| Liste de conversations | Ordre stable `-last_message_at`, puis `-id`; `next`/`previous` conservent les paramètres de requête. Les conversations masquées sont exclues avant le filtre `unread`. |
| `PUT /conversations/{id}/messages/mark-as-read/` | Marque les messages entrants non lus jusqu’au dernier message entrant visible. `200` retourne au minimum `messages_marked` et **le** `unread_count_for_me` recalculé. Curseur absent : tous les entrants non lus. Curseur d’une autre conversation, expéditeur ou valeur incohérente : `400`, sans fuite d’information. |
| `PUT /conversations/{id}/messages/{message_id}/read/` | Reste compatible, mais utilise le même service canonique et le même recalcul. Il marque seulement cet ID. |
| `DELETE /conversations/{id}/` | `204` idempotent pour le participant actif ; masquage individuel, jamais suppression physique. Un message entrant validé supprime l’état de masquage du seul destinataire. `404` pour une conversation indisponible/non accessible. |
| `POST` texte ou média | La déduplication est par `(match, sender, client_message_id)`; un retry retourne le message canonique, sans second effet de bord. Le média reste exclusivement multipart via `/messages/media/`. |
| WS `message.created` | `message_id`, `conversation_id`, `sender_id`, `content`, `message_type`, `media_url`, `media_type`, `media_thumbnail_url`, `sent_at`, `client_message_id`. Les trois champs média sont `null` pour un texte. |
| WS `message.read` | `reader_id`, `message_ids`, `read_at`, diffusé après commit à tous les appareils autorisés de la conversation. |
| Endpoints retirés | Ne pas réintroduire `GET /conversations/{id}/` ni `POST /conversations/generate-media-upload-url/`. Le frontend les retire. |

`status=archived` ne doit pas être utilisé comme alias de la suppression : « archivé » et « masqué » sont des concepts distincts. L’UI ne proposera donc que `all` et `unread` dans cette itération.

---

## 3. Ordre d’implémentation backend

### Phase A — préparer les données, les contraintes et l’observabilité

**Fichiers principaux :** `messaging/models.py`, `matching/models.py`, nouvelle migration `messaging.0003_*`, tests de migration si le projet en contient.

1. Ajouter une contrainte conditionnelle unique sur `Message(match, sender, client_message_id)` lorsque `client_message_id != ''`.
2. Avant la contrainte, exécuter une migration de données déterministe : pour chaque doublon historique, conserver l’identifiant d’origine sur le message le plus ancien et remplacer les identifiants des autres par `legacy-{message_uuid}`. Ne supprimer aucun message. Ne pas logguer les valeurs d’identifiants clients, car elles peuvent embarquer un UUID de conversation.
3. Ajouter l’index composé qui sert réellement aux lectures/recalculs : `(match, sender, status, created_at, id)` ; vérifier son nom et l’ordre supportés par PostgreSQL. Conserver les index existants nécessaires au préchargement N+1.
4. Documenter que cette migration de données est non réversible au sens métier. La procédure de rollback est le retour au snapshot sauvegardé avant migration, puis le rollback du code et de la contrainte.
5. Remplacer ou déprécier les méthodes `Match.increment_unread()` et `Match.reset_unread()` pour empêcher leur emploi avec une instance non verrouillée. `Message.mark_as_read()` ne doit plus remettre un compteur global à zéro ; la mise à jour de compteur relève uniquement du service transactionnel.

**Critère de sortie :** l’environnement de staging applique la migration sans doublon de clé, et un retry concurrent ne peut plus créer deux messages avec le même identifiant client.

### Phase B — rendre l’envoi entièrement atomique

**Fichiers principaux :** `messaging/services.py`, `messaging/signals.py`, `matching/models.py`, `messaging/tests.py`.

1. Dans `MessageService.send_message()`, ouvrir `transaction.atomic()` et recharger le `Match` par PK avec `select_for_update()` avant toute écriture.
2. Vérifier à nouveau l’appartenance et le statut `ACTIVE` sur l’objet verrouillé, puis rechercher un doublon avec **`match`, `sender` et `client_message_id`**. Le code actuel omet `sender`, ce qui peut retourner le message du mauvais participant si deux clients choisissent le même ID.
3. Créer le message, mettre à jour `last_message_at`/`last_message_preview`, incrémenter le compteur du destinataire sur la ligne verrouillée et supprimer `ConversationHiddenState(match, recipient)` dans la même transaction.
4. En cas d’`IntegrityError` de la contrainte d’idempotence, sortir proprement de la sous-transaction puis relire le message canonique par les trois clés. Répondre avec ce message sans réémettre de notification ni de WebSocket.
5. Faire de `create_media_message()` un simple adaptateur de stockage : si le stockage réussit mais que la transaction métier échoue, supprimer le blob best-effort. Si le message est un retry idempotent, supprimer le nouveau blob et retourner le média canonique existant.
6. Déplacer les effets externes du signal `post_save` dans une fonction de dispatch appelée via `transaction.on_commit()`: notification Celery, ligne `Notification` et `group_send`. Le callback ne doit charger que le message committé par PK et être best-effort avec log sans contenu sensible.
7. Préserver le comportement pour les créations directes de `Message` qui existent encore dans les tests et tâches internes : le signal programme aussi son dispatch via `on_commit`, mais aucune notification ne part si la transaction est annulée.

**Critère de sortie :** une panne forcée après `Message.objects.create()` laisse zéro message, zéro compteur, zéro réapparition et zéro événement externe ; deux envois concurrents n’augmentent le compteur qu’une fois chacun et n’émettent qu’un événement par message distinct.

### Phase C — centraliser le marquage de lecture et recalculer exactement les non-lus

**Fichiers principaux :** `messaging/services.py`, `messaging/views.py`, `messaging/serializers.py`, `matching/models.py`, `messaging/models.py`, `messaging/tests.py`.

1. Introduire un résultat interne immuable, par exemple `ReadReceiptResult(messages_marked, message_ids, read_at, unread_count_for_me)`. Les deux endpoints de lecture l’utilisent ; aucun endpoint ne réimplémente la règle de compteur.
2. Dans le service canonique, ouvrir une transaction, verrouiller le `Match`, identifier l’autre participant et verrouiller les messages candidats.
3. Pour le bulk : valider que `last_read_message_id`, s’il existe, appartient à ce match et à l’autre participant. Construire la borne avec `(created_at, id)` afin qu’un même timestamp ne rende pas la lecture ambiguë. Pour le single : limiter strictement au `message_id` du chemin.
4. Mettre à jour les seuls messages entrants `sent`/`delivered`, capturer leurs IDs avant l’update, puis compter les messages entrants encore `sent`/`delivered`. Écrire ce compte exact dans le champ du participant (`user1_unread_count` ou `user2_unread_count`) pendant que le match est verrouillé.
5. Après commit, diffuser `message.read` uniquement si au moins un statut a changé, puis programmer le push de lecture existant. Le push et le WebSocket portent le même `read_at` et les mêmes IDs.
6. Faire retourner par la vue `messages_marked`, `unread_count_for_me` et `read_at` lorsqu’un marquage a eu lieu. Conserver l’enveloppe d’erreur `{error, details}` pour les `400`.
7. Ne jamais recalculer le compteur à partir de données exposées au client. La base est l’autorité ; Flutter consomme la valeur renvoyée.

**Critère de sortie :** après deux messages entrants, la lecture du premier laisse le second `sent`, le compteur à `1`, le badge et `status=unread` actifs, et le reçu WebSocket ne contient que le premier ID.

### Phase D — durcir la liste et la pagination

**Fichiers principaux :** `messaging/serializers.py`, `messaging/views.py`, `messaging/tests.py`.

1. Créer un serializer de paramètres de liste (`ConversationListQuerySerializer`) : `status` à choix fermé, `page >= 1`, `page_size` entre `1` et `50`.
2. Le valider avant la construction du queryset et utiliser ses valeurs validées. Une valeur inconnue ne doit jamais tomber silencieusement sur `all`.
3. Appliquer `order_by('-last_message_at', '-id')` au queryset. Garder le `Prefetch` borné du dernier message avec l’ordre `-created_at, -id`.
4. Ajouter un serializer analogue pour les paramètres du GET messages (`limit`, `page_size`, `before_message_id`) afin d’empêcher les `ValueError` issus de `int()` et les réponses `500` sur une entrée malformée.
5. Corriger en même temps le calcul `has_more` des messages pour qu’il soit relatif au curseur actuel et non au nombre total de messages visibles ; `next` doit être `null` sur la dernière page réelle.

**Critère de sortie :** `status=unexpected`, `page=0` et `page_size=abc` retournent `400`; deux conversations au même timestamp n’apparaissent ni deux fois ni zéro fois sur les pages successives.

### Phase E — compléter le transport WebSocket et la documentation

**Fichiers principaux :** `messaging/consumers.py`, `messaging/signals.py`, `tests/test_websocket_messaging.py`, `docs/API_DOCUMENTATION.md`, `docs/FRONTEND_MESSAGING_API.md`, `docs/MESSAGES_BACKEND_WEBSOCKET_FRONTEND.md`.

1. Dans `ConversationConsumer.message_created()`, transférer explicitement `media_url`, `media_type` et `media_thumbnail_url` de l’événement de groupe. Utiliser `event.get()` pour les textes et préserver les valeurs `null`.
2. Vérifier que `message.read` conserve le comportement multi-appareil : le lecteur et l’expéditeur connectés reçoivent l’événement, sans contenu de message.
3. Réécrire les sections Messaging des trois documents à partir du contrat de la section 2, en UTF-8 sans BOM. Ne pas réaliser une réécriture globale non liée ; normaliser les fins de ligne dans un commit documentaire séparé si nécessaire.
4. Retirer le label « Production-ready » tant que les phases A à E ne sont pas livrées et validées.

---

## 4. Matrice de tests backend obligatoire

| Risque | Test attendu |
|---|---|
| Lecture partielle | Deux messages entrants, lecture du premier, compteur `1`, un seul ID WS, conversation présente dans `unread`. |
| Lecture concurrente/envoi | `TransactionTestCase` avec deux transactions : le compteur final égale le nombre de messages réellement non lus. |
| Idempotence | Deux POST texte et deux POST média concurrents avec même clé : un seul message canonique, un seul incrément, un seul dispatch. |
| Rollback métier | Erreur injectée après création : aucune écriture ni effet externe visible après rollback. |
| Réapparition | A masque ; B envoie texte puis média ; A retrouve la conversation dans les deux cas. |
| WebSocket média | `WebsocketCommunicator` reçoit les trois champs média, exactement égaux au message persisté. |
| WebSocket lecture | Émetteur et lecteur reçoivent les mêmes IDs/read_at après commit ; aucun événement si zéro mise à jour. |
| Paramètres REST | `400` pour valeurs invalides, `401` sans JWT, `404` hors participant, `204` DELETE idempotent. |
| Pagination | Timestamps égaux, `page_size=1`, pages disjointes et ordre stable. |
| Performance | 1, 2 et 20 conversations : même budget de requêtes, sans précharger tout l’historique. |

Exécuter ensuite :

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test messaging.tests tests.test_websocket_messaging --keepdb
```

La suite complète doit aboutir dans CI sans la limite interactive locale. Ajouter le test PostgreSQL de concurrence si la base locale de développement ne reproduit pas le verrouillage.

---

## 5. Procédure de déploiement et de rollback

1. Sauvegarder la base avant la migration de données et compter les doublons de clés clients sans les afficher.
2. Déployer les migrations, puis le code backend, puis les workers Celery/Channels. Ne déployer Flutter qu’après validation du contrat de la section 2 sur staging.
3. Vérifier après déploiement, par requête agrégée interne, que chaque compteur dénormalisé égale le nombre de messages non lus ; ne produire que les nombres d’écarts, jamais les conversations concernées dans les logs centraux.
4. Surveiller les erreurs de callback `on_commit`, les `IntegrityError` d’idempotence gérées, le taux de `400` de paramètres et la latence de liste.
5. En cas de régression, désactiver d’abord l’exposition UI du filtre/suppression côté Flutter, restaurer le snapshot si la migration de données doit être annulée, puis revenir au release backend précédent. Ne jamais supprimer des messages pour « réparer » un compteur.

---

## 6. Conditions de passage au frontend

L’équipe frontend peut livrer l’UI une fois que staging prouve :

- la réponse de lecture contient `unread_count_for_me` exact ;
- le `DELETE` respecte le masquage individuel et la réapparition après texte **et** média ;
- les payloads WebSocket média complets sont reçus ;
- les valeurs invalides de filtre retournent `400` et le statut `archived` reste explicitement vide ;
- la documentation UTF-8 est publiée avec les exemples de réponse exacts.

Toute divergence doit être traitée comme un blocage de contrat, non comme un fallback silencieux côté Flutter.
