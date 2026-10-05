# Rapport – Activation de la traçabilité visible pour GitHub Copilot

## Objectif

Rendre GitHub Copilot capable de fournir une preuve visible, dans ses réponses, du workflow utilisé lors de requêtes substantielles sur ce projet, en imitant le comportement des hooks Claude Code.

## Contexte

GitHub Copilot n’expose pas naturellement le flux interne de “router / skill selection / exécution de skill” comme Claude Code. Pour compenser, j’ai forcé la production d’une trace explicite dans les réponses en ajoutant des instructions de projet spécifiques au dépôt.

## Fichiers modifiés / ajoutés

### Modifié
- `.github/copilot-instructions.md`
  - Ajout d’une section `## 🔁 Workflow Hooks (mirrored from Claude Code)`
  - Ajout d’une consigne `Visible workflow trace (required for every substantive response)`

### Ajouté
- `.github/instructions/django-backend.instructions.md`
- `.github/instructions/api-contract.instructions.md`
- `.github/instructions/tests.instructions.md`

## Démarche suivie

1. Ouvrir le repo et identifier le mécanisme de configuration Copilot disponible :
   - fichier global de projet : `.github/copilot-instructions.md`
   - instructions par type de fichier : `.github/instructions/*.instructions.md`

2. Ajouter un bloc “Workflow Hooks” dans `.github/copilot-instructions.md` pour définir l’équivalent des hooks Claude Code :
   - `UserPromptSubmit equivalent`
     - Lire la guidance du routeur de tâches dans `.agents/skills/task-router/SKILL.md`
     - Identifier les skills pertinentes avant d’agir
   - `Stop equivalent`
     - Relire la requête originale mot pour mot
     - Vérifier que toutes les exigences sont couvertes
   - `PostToolUse equivalent`
     - Après chaque édition, réaliser une vérification minimale pertinente
     - Actualiser le graphe de connaissances si possible
   - `Project guardrails`
     - Ne pas hardcoder de secrets
     - Utiliser serializers DRF pour les données utilisateur
     - Protéger les endpoints
     - Logger avec contexte sans exposer de secrets

3. Ajouter une obligation de “trace visible” dans `.github/copilot-instructions.md` :
   - **CRITICAL** : Toute réponse DOIT commencer par un bloc de trace de workflow comme tout premier contenu, avant tout autre texte, explication ou code.
   - Format du bloc de trace :
     ```
     **Workflow: router consulted → relevant instructions loaded → plan formed → implementation/checks performed.**
     Instructions used: `django-backend`, `api-contract`, `tests`

     - Router consulted
     - Project instructions applied
     - Implementation performed
     - Verification performed
     ```
   - Adapter la ligne "Instructions used" pour ne lister que les fichiers d'instructions réellement pertinents.
   - Ce bloc n'est PAS optionnel. C'est la seule preuve visible de l'exécution du workflow dans GitHub Copilot, puisque l'UI n'expose pas les logs internes d'exécution des skills comme le fait Claude Code.
   - Si ce bloc est oublié, l'utilisateur n'a aucun moyen de vérifier que les règles du projet ont été chargées et appliquées.

4. Créer des instructions ciblées par type de fichier dans `.github/instructions/` :
   - `django-backend.instructions.md`
     - Appliquer à `**/*.py`
     - Renforcer les règles Django/DRF : structure modulaire, services, serializers, permissions, transaction, secrets, migrations
   - `api-contract.instructions.md`
     - Appliquer à `**/views*.py`
     - Renforcer le respect du contrat API : URL, méthodes, réponses, erreurs, pagination
   - `tests.instructions.md`
     - Appliquer à `**/tests/**/*.py`
     - Renforcer les règles de test : couverture des chemins principaux, tests comportementaux, régressions de sécurité

5. Vérifier que les changements sont limités au dépôt :
   - validation `git status --short -- .github`
   - résultat montrant uniquement des modifications dans `.github` et pas ailleurs

## Résultat concret

La configuration Copilot du projet contient maintenant :
- un guide de workflow visible,
- une incitation explicite à déclarer le processus suivi dans la réponse,
- des instructions de projet similaires à des hooks Claude Code,
- des règles ciblées par type de fichier pour garantir la cohérence du code.

## Mode opératoire pour reproduire dans un autre projet

1. Créer ou modifier `.github/copilot-instructions.md`.
2. Ajouter un bloc “Workflow Hooks” similaire à celui-ci :
   - `UserPromptSubmit equivalent`
   - `Stop equivalent`
   - `PostToolUse equivalent`
   - `Project guardrails`
   - `Visible workflow trace (required for every substantive response)`
3. Créer un dossier `.github/instructions/`.
4. Y ajouter des fichiers `*.instructions.md` adaptés aux types de fichiers du projet :
   - backend Python : `**/*.py`
   - API views : `**/views*.py`
   - tests : `**/tests/**/*.py`
   - frontend : `**/*.{js,ts,jsx,tsx}` si besoin
5. Dans chaque fichier, définir des règles concises et project-specific.
6. Vérifier localement avec `git status` que les changements sont confinés au projet.

## Recommandations pour un autre agent AI

- Prioriser le fichier projet `.github/copilot-instructions.md`.
- Ajouter un point “trace visible dans la réponse” pour compenser le manque de logs internes.
- Exiger une attestation courte du workflow suivi dans la réponse pour les modifications non triviales.
- Utiliser les instruction files `applyTo` pour imposer des règles par chemin/type de fichier.

## Note importante

Cette démarche ne change pas le comportement global de GitHub Copilot sur l’ordinateur. Elle active la traçabilité uniquement dans le périmètre du dépôt en question, via des fichiers de configuration de projet.

---

### Exemple de phrase à insérer dans les réponses Copilot

> Workflow: router consulted -> relevant instructions loaded -> plan formed -> implementation/checks performed.  
> Instructions used: `django-backend`, `api-contract`, `tests`.
