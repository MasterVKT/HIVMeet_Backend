# Problème Redis - Serveur Non Démarré

**Date**: 29 Mars 2026  
**Statut**: 🔴 Problème Backend Identifié  
**Priorité**: HAUTE  

---

## Description du Problème

 Lors d'une tentative de like sur la page de découverte, une erreur 500 est retournée par le backend avec le message suivant :

```
redis.exceptions.ConnectionError: Error 10061 connecting to 127.0.0.1:6379. 10061.
```

## Analyse des Logs

### Logs Frontend
```
D/FlutterGeolocator( 7014): Attaching Geolocator to activity
[Swipe right/like action triggered]
ERROR 2026-03-29 01:05:07,644 log 11244 10064 Internal Server Error: /api/v1/discovery/interactions/like
redis.exceptions.ConnectionError: Error 10061 connecting to 127.0.0.1:6379. 10061.
ERROR 2026-03-29 01:05:07,709 runserver 11244 14544 HTTP POST /api/v1/discovery/interactions/like 500 [3.20, 127.0.0.1:51622]
```

### Cause Racine

Le serveur Redis n'est pas en cours d'exécution sur la machine backend. Redis est utilisé par Django Channels pour les fonctionnalités temps réel (WebSocket notifications).

## Impact sur l'Utilisateur

- ❌ Impossible de liker un profil sur la page de découverte
- ❌ Erreur 500 lors de l'envoi d'un like
- ✅ Les dislikes fonctionnent (pas besoin de Redis)

## Solutions Proposées

### Option 1 : Démarrer Redis (Recommandée)

**Windows**:
```cmd
redis-server
```

**macOS/Linux**:
```bash
redis-server
```

### Option 2 : Configuration Docker

```yaml
# docker-compose.yml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
```

## Vérification

Pour vérifier que Redis est fonctionnel :
```bash
redis-cli ping
# Devrait retourner: PONG
```

## Fichiers Concernés

- Backend: `hivmeet_backend/matching/signals.py` (utilise channel_layer pour notifications)
- Configuration: `hivmeet_backend/hivmeet_backend/asgi.py` (channels setup)

## Résolution

1. **Démarrer Redis** sur le serveur backend
2. **Redémarrer le serveur Django** après le démarrage de Redis
3. **Vérifier** que les likes fonctionnent maintenant

---

*Document créé automatiquement par l'agent AI lors du diagnostic des erreurs de l'application HIVMeet.*