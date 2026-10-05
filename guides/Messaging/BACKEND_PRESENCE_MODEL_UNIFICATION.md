# Backend requis — Unifier les deux définitions concurrentes de « présence en ligne »

**Contexte** : session d'implémentation frontend « Messagerie 100% » (voir `AUDIT_MESSAGES_PAGE.md`, §3.4.8 et F31). Le frontend affiche désormais un badge « en ligne » dans `ConversationCard` (F42) et dans l'AppBar du chat — ces deux affichages peuvent se contredire selon la source de données interrogée, ce qui rend le badge peu fiable.

---

## 1. État actuel exact (vérifié dans le code backend réel)

**Définition n°1 — `last_active` sur le modèle User**, utilisée par la liste des conversations et par l'endpoint de présence dédié :

```python
# messaging/serializers.py::ConversationSerializer.get_other_user, ligne 94
'is_online': (timezone.now() - other_user.last_active).total_seconds() < 300,
```

```python
# messaging/views.py::conversation_presence, lignes 239-264
other_user = match.get_other_user(request.user)
is_online = (timezone.now() - other_user.last_active).total_seconds() < 300
```

Ici, « en ligne » = `last_active` mis à jour il y a moins de 300 secondes (5 minutes), **peu importe si une connexion WebSocket est réellement active**.

**Définition n°2 — cache Redis par conversation**, utilisée par le WebSocket consumer :

```python
# messaging/consumers.py::_set_presence_online, lignes 470-479
async def _set_presence_online(self):
    cache_key = f'presence_{self.user.id}_{self.conversation_id}'
    cache.set(cache_key, {
        'status': 'online',
        'timestamp': timezone.now().isoformat(),
    }, timeout=3600)  # 1 hour TTL
```

```python
# messaging/consumers.py::_set_presence_offline, lignes 481-487
async def _set_presence_offline(self):
    cache_key = f'presence_{self.user.id}_{self.conversation_id}'
    cache.delete(cache_key)
```

Ici, « en ligne » = une entrée cache existe pour **cette conversation précise**, posée à la connexion WS et supposée retirée à la déconnexion (`disconnect()`, ligne 98-131) — mais avec un TTL de secours de **1 heure** si `disconnect()` n'est jamais appelé proprement (crash de l'app, perte réseau brutale sans fermeture propre de la socket).

Le broadcast `presence_update` (`consumers.py`, lignes 80-88 et 113-123) envoie le statut au groupe **au moment de connect/disconnect**, mais la source de vérité affichée dans `ConversationSerializer`/`conversation_presence` (Définition n°1) est **totalement indépendante** de ce cache (Définition n°2). Un utilisateur peut donc apparaître « en ligne » dans la liste des conversations (car `last_active` récent, par exemple parce qu'il a fait une autre action dans l'app il y a 2 minutes) alors qu'il n'a **aucune socket ouverte sur cette conversation précise**, et inversement.

## 2. Problème

Deux affichages du même badge « en ligne » peuvent se contredire dans la même session utilisateur (liste de conversations vs AppBar du chat ouvert), ce qui est déroutant. De plus, la Définition n°2 (cache) peut rester « online » jusqu'à 1h après une déconnexion brutale (app tuée sans fermeture propre), un signal trompeur pendant une heure entière.

## 3. Fix prescrit

### Option recommandée : une seule source de vérité — `last_active`, rafraîchi par heartbeat WS

Le frontend implémente déjà un heartbeat WebSocket (`ChatWebSocketService.sendPing`, appelé périodiquement — voir la session frontend, finition F27). Utiliser ce ping pour rafraîchir `last_active` côté serveur, et **abandonner le cache Redis par-conversation** comme source d'affichage (le garder uniquement, si besoin, pour l'indicateur de frappe qui a une sémantique différente et plus courte durée de vie).

```python
# messaging/consumers.py::ConversationConsumer.receive — dans la branche 'ping'
elif message_type == 'ping':
    await self._touch_last_active()
    await self.send(text_data=json.dumps({
        'type': 'pong',
        'timestamp': timezone.now().isoformat(),
    }))
```

```python
# messaging/consumers.py — nouvelle méthode
async def _touch_last_active(self):
    """Rafraîchit last_active à chaque ping reçu — le heartbeat WS devient
    la source de vérité pour la présence, remplaçant le cache Redis
    per-conversation qui pouvait diverger de cette valeur."""
    await database_sync_to_async(self._update_last_active_sync)()

def _update_last_active_sync(self):
    User.objects.filter(id=self.user.id).update(last_active=timezone.now())
```

```python
# messaging/consumers.py::connect — rafraîchir aussi à la connexion initiale
# (avant le premier ping, qui peut arriver plusieurs secondes après connect)
await self._touch_last_active()
```

Réduire la fenêtre « en ligne » de 300s à une valeur cohérente avec la fréquence du heartbeat frontend (F27 recommandait un ping toutes les 30s) — par exemple **90 secondes** (3x l'intervalle de ping, marge raisonnable pour tolérer un ping manqué) :

```python
# messaging/serializers.py::ConversationSerializer.get_other_user
'is_online': (timezone.now() - other_user.last_active).total_seconds() < 90,

# messaging/views.py::conversation_presence
is_online = (timezone.now() - other_user.last_active).total_seconds() < 90
```

### Nettoyage du cache Redis per-conversation devenu inutile pour la présence

Si `_set_presence_online`/`_set_presence_offline` (lignes 470-487) et le broadcast `presence_update` associé (lignes 80-88, 113-123) ne servent plus qu'à un affichage redondant avec `last_active`, ils peuvent être **retirés** pour simplifier — le broadcast `presence_update` au moment du connect/disconnect reste utile pour la mise à jour temps réel immédiate côté frontend (`ChatBloc._onWsPresenceUpdate`), mais la valeur de `last_active` (rafraîchie par ping) devient la source de vérité pour tout chargement REST (liste conversations, endpoint presence dédié).

## 4. Impact frontend

Aucun changement requis côté client pour ce fix — `ChatWebSocketService` envoie déjà un ping initial à la connexion (`chat_websocket_service.dart::connect`, ligne 80). Si le heartbeat périodique (F27, `Timer.periodic(30s, sendPing)`) n'a pas encore été implémenté côté frontend au moment où ce fix backend est déployé, il devient un **prérequis** pour que `last_active` reste correctement rafraîchi tant que l'utilisateur garde un chat ouvert sans taper de message.

## 5. Critères de validation

- Ouvrir un chat sur l'appareil A, laisser l'app au premier plan sans interaction pendant 3 minutes → l'appareil B (l'autre participant) voit toujours A « en ligne » dans la liste des conversations ET dans l'AppBar du chat (les deux affichages concordent, grâce au heartbeat qui rafraîchit `last_active`).
- Tuer l'app sur l'appareil A (kill process, pas fermeture propre) → après 90 secondes maximum, B voit A passer à « hors ligne » (au lieu de rester « en ligne » jusqu'à 1h avec l'ancien cache Redis).
- Les deux affichages (liste de conversations, AppBar du chat ouvert) montrent systématiquement le même statut pour un même utilisateur au même instant.
