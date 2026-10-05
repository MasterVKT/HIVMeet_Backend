# Phase 3 — accès mensuel Free

## Migration

`matching.0003_free_match_access` ajoute l'état d'accès d'un match, les deux
compteurs de messages et le registre `MonthlyFreeAccess`. Sa migration de données
attribue `full` à tous les matches actifs existants : aucune conversation déjà
ouverte ne sera verrouillée.

## Mise en production

1. Déployer le backend et appliquer la migration avec
   `python manage.py migrate matching 0003_free_match_access`.
2. Laisser `HIVMEET_FREE_MATCH_ACCESS_ENABLED=false` pendant la diffusion de
   l'application Flutter compatible avec les nouveaux champs de match.
3. Activer `HIVMEET_FREE_MATCH_ACCESS_ENABLED=true` seulement lorsque les deux
   versions sont disponibles. Les contrôles REST et WebSocket sont alors actifs.

Le flag est désactivé par défaut. Tant qu'il est désactivé, les matches restent
en accès complet et les anciens clients continuent de fonctionner.

## Retour arrière

Remettre d'abord `HIVMEET_FREE_MATCH_ACCESS_ENABLED=false`. Cela restaure
immédiatement l'accès complet sans modifier les messages ni les matches. Garder
la migration en place préserve le registre mensuel pour une réactivation future.
Ne pas exécuter la migration arrière sur une base en production : elle supprimerait
les compteurs et le registre de consommation. Un retour de schéma exige une
sauvegarde restaurable validée au préalable.
