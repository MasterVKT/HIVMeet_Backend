# HIVMeet — Backend agent entry point

Lire dans cet ordre :

1. `.agents/project-map.json`
2. `.agents/PROJECT_RULES.md`
3. `.agents/WORKFLOW.md`
4. `.agents/skills/task-router/SKILL.md` si la tâche n'est pas déjà clairement
   couverte par une skill.

Le backend est un service Django REST Framework manipulant des données de santé
sensibles. Charger les règles détaillées seulement lorsqu'elles sont nécessaires.
Le graphe de revue est la première source pour explorer l'impact; recourir à la
recherche textuelle si le graphe ne couvre pas la question.

Une intervention qui touche contrat API, DTO, authentification, notification ou
donnée exposée au client implique le frontend défini par la carte. Préserver les
modifications non liées déjà présentes et ne jamais réinitialiser le dépôt.

Avant la réponse finale, appliquer l'audit de complétude et donner : fichiers
modifiés, conformité, validation de non-régression et impact frontend éventuel.
