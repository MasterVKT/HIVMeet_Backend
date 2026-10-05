# Skills Orchestrator — HIVMeet

All project skills are in `.agents/skills/` (single source of truth, 22 skills).

## Règle : router-first obligatoire

**TOUJOURS commencer par charger le router avant toute requête** :
1. Lire `.agents/skills/task-router/SKILL.md`
2. Appliquer son arbre de décision pour identifier la ou les skills appropriées
3. Charger les skills sélectionnées et suivre leur workflow jusqu'à la fin

## Règle : double-check obligatoire avant chaque réponse

1. Relire la requête originale mot pour mot
2. Vérifier chaque exigence contre ce qui a été fait
3. Corriger tout écart silencieusement
4. Envoyer seulement après vérification complète

## Référence

- Router : `.agents/skills/task-router/SKILL.md`
- Catalog complet : `.agents/skills/BACKEND_SKILLS_CATALOG.md`
