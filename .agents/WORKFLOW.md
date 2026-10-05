# Workflow local — backend HIVMeet

1. Lire `project-map.json`, ces règles, puis `.agents/skills/task-router` si le
   type de tâche n'est pas déjà déterminé.
2. Évaluer le scope : backend seul ou backend + frontend pour tout contrat, DTO,
   authentification, notification, donnée partagée ou changement visible client.
3. Appliquer la skill spécialisée, préférer une correction réversible et produire
   les tests proportionnés au risque (contrat, permission, migration, tâche async).
4. Appliquer avant livraison l'audit de complétude : exigences vers preuves,
   changements vers exigences, impact et validation indépendante.

Pour une tâche multiscopes, consulter `../../../.agents/project-map.json` et
éviter des corrections concurrentes : une seule correction possède le contrat.
