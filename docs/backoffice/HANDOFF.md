# HANDOFF — Back-office d'administration HIVMeet

> Rapport de passation, mis à jour **à la fin de chaque phase**. Tout agent/modèle doit
> pouvoir reprendre le travail exactement comme l'agent précédent : mêmes critères, mêmes
> contraintes, même cohérence. Lire en entier avant d'agir.

## 1. État global
| Phase | Intitulé | Statut |
|---|---|---|
| 0 | Skills + socle documentaire | **TERMINÉE** (2026-10-08) — arrêt, en attente de « continue » |
| 1 | Fondation isolée (settings, gate, audit) ★ | à faire |
| 2 | MFA staff ★ | à faire |
| 3 | Utilisateurs & sanctions ★ | à faire |
| 4 | Signalements ★ | à faire |
| 5 | Revue KYC ★ | à faire |
| 6 | Modération contenu ★ | à faire |
| 7 | Tableau de bord ★ | à faire |
| 8 | RGPD ★ | à faire |
| 9 | Abonnements & paiements (optionnel) | à faire |
| 10 | CMS ressources (optionnel) | à faire |
| 11 | Durcissement & livraison ★ | à faire |

★ = minimum requis. Détail de chaque phase : `docs/backoffice/PLAN.md`.

## 2. Contexte à ne jamais perdre
- **HIVMeet** : app de rencontre pour personnes vivant avec le VIH. Backend Django 4.2 / DRF
  (`D:\Projets\HIVMeet\env\hivmeet_backend`), frontend Flutter (`D:\Projets\HIVMeet\hivmeet`).
  Tout enregistrement identifiable est une **donnée de santé de catégorie spéciale**.
- **Demande** : un back-office « minimum requis pour une assez bonne administration », calé
  sur le fonctionnement **réellement implémenté** (qui diffère des spécifications initiales).
- **Décisions de l'utilisateur (figées)** : app Django dédiée server-rendered ; revue KYC
  complète ; sanction = désactivation `is_active` avec motif + audit ; MFA TOTP obligatoire
  pour tout le staff.
- **EXIGENCE CRUCIALE (ajoutée par l'utilisateur en cours de plan)** : *ne jamais apporter de
  modification pouvant impacter le fonctionnement actuel de l'application, dont
  l'implémentation et le fonctionnement doivent rester indépendants de la gestion*.
  → traduit par le contrat d'indépendance (skill `backoffice-independence-guard`).
- **Règle de conduite** : après chaque phase terminée, produire/mettre à jour ce rapport puis
  **s'arrêter et attendre une demande explicite** de l'utilisateur avant la phase suivante.

## 3. Phase 0 — terminée
### Livrables (tous dans les zones d'écriture autorisées)
- Skills canoniques `.agents/skills/` + adaptateurs `.claude/skills/` :
  `backoffice-independence-guard` (+ `scripts/check_independence.py`),
  `backoffice-development`, `backoffice-security`, `backoffice-testing`,
  `backoffice-phase-handoff`.
- Gouvernance (lignes ajoutées seulement) : `.agents/skills/task-router/SKILL.md`
  (5 lignes de registre, 2 scénarios, 5 résumés) et `.agents/skills/BACKEND_SKILLS_CATALOG.md`
  (section « Back-office Skill Set » + raccourci).
- Docs : `docs/backoffice/PLAN.md` (plan approuvé), ce `HANDOFF.md`,
  `RECOMMANDATIONS_HORS_PERIMETRE.md` (18 défauts de l'app, non corrigés),
  `independence-baseline.json` (empreintes SHA-256 de 797 fichiers hors zones autorisées).
- **Aucun fichier de l'application n'a été modifié.** Aucune migration, aucune dépendance.

### Choix de conception de la Phase 0
- Skills créés **en groupe** (ils se référencent mutuellement), le garde d'abord, puis la
  baseline **avant** toute autre écriture.
- Le garde empreinte le **contenu** (pas `git status`) car la worktree contient déjà ~92
  fichiers modifiés par l'utilisateur : seule une comparaison de contenu distingue ses
  changements des nôtres.
- Baseline stockée dans `docs/backoffice/` pour être partagée entre sessions.

### Preuves
Voir la section « Journal des phases » (résultats réels des commandes de validation).

## 4. Phase suivante : P1 — Fondation isolée
**Entrée** : l'utilisateur écrit explicitement de continuer avec la phase 1. Avant d'écrire :
`check_independence verify` → PASS; relire `backoffice-development` + `backoffice-security`.

**À réaliser** (détail dans `PLAN.md`) : `backoffice/conf/{settings,settings_test,urls,wsgi}.py`;
app (`apps`, `models`, `access.py`, `roles.py`, `audit.py`, `middleware.py`, `checks.py`);
migrations `0001` (`StaffAuditLog`) et `0002` (groupes `backoffice_admin`, `backoffice_moderator`,
`backoffice_support`); templates `base/login/denied` + CSS; étape mot de passe **sans**
`login()`; gate fail-closed jusqu'à la P2; helper de tests `login_staff`; tests de fondation.

**Points d'attention** :
- `settings.py` du back-office : `from hivmeet_backend.settings import *`, retirer `daphne`
  et `corsheaders`, middleware propre (sans `RateLimit/PremiumRequired/PremiumStatus`),
  `ROOT_URLCONF`, cookies distincts. Vérifier que l'import n'a **aucun effet de bord**
  (le module principal valide `kyc_runtime` au démarrage ; relire `settings.py` en fin de
  fichier pour les garde-fous de production).
- Tests : PostgreSQL `hivmeet_test` local (`postgres/postgres`), migrations désactivées dans
  `test_settings.py:53-60` → groupes via `ensure_backoffice_groups()`.
- Le runner de tests de l'application (`test_runner.py`) ne doit pas être modifié : lancer
  `manage.py test backoffice --settings=backoffice.conf.settings_test` avec un label explicite.
- Ne jamais `migrate` sans label.

## 5. Contraintes permanentes (à appliquer comme l'agent précédent)
1. **Indépendance totale** (voir skill guard) : écrire uniquement dans `backoffice/`,
   `docs/backoffice/`, `.agents|.claude/skills/backoffice-*`, `docker-compose.backoffice.yml`.
2. **Pas de nouvelle dépendance pip** ; TOTP/QR internes ou sans QR.
3. **Sécurité** : superuser sans accès implicite; MFA avant `login()`; motif + audit sur toute
   écriture; masquage des emails; jamais de contenu de messages, bio, localisation ni document
   KYC hors flux audité.
4. **Réutiliser** les fonctions publiques existantes; réimplémenter (avec test de parité) la
   logique inline; ne pas refactorer l'existant.
5. **i18n** : msgids anglais `gettext_lazy`, catalogue FR dans `backoffice/locale`; pas de CDN,
   pas de script inline.
6. **Worktree sale** : ne jamais `git reset/checkout/stash/clean`; ne stager que `backoffice/` et
   les fichiers de la phase.
7. **Langue** : réponses en français. Style caveman actif en session (terse), code/commits en
   langage normal.
8. **Fin de phase** : tests → `verify` → audit de complétude → HANDOFF → **arrêt**.

## 6. Limites connues de l'environnement
- Le hook Stop de Claude Code ne reçoit pas `last_assistant_message` : le signal
  `HIVMEET_COMPLETION_AUDIT: PASS` n'est pas reconnu et le hook relance jusqu'à 2 fois, puis
  se verrouille (`blocked-after-two-corrections`). Constaté à plusieurs reprises dans cette
  session (cf. `lifecycle_hook.py:229-264`, `agent-integrations.json`). Ne pas créer de 3e
  boucle ; livrer les preuves. Le correctif éventuel (lire `transcript_path`) est un travail
  de gouvernance séparé, **non fait**, à valider par l'utilisateur.
- Tests nécessitant PostgreSQL local; l'état de ce service n'a pas été vérifié en Phase 0.
- `.pyc` suivis par git : toujours `PYTHONDONTWRITEBYTECODE=1`.

## 7. Journal des phases
### Phase 0 — 2026-10-08 — TERMINÉE
Commandes exécutées (avec `PYTHONDONTWRITEBYTECODE=1`) et résultats réels :
| Contrôle | Résultat |
|---|---|
| `check_independence.py snapshot` | baseline écrite : 797 fichiers (avant toute autre écriture) |
| `check_independence.py verify` après les 5 skills, 2 fichiers de gouvernance et 3 docs | **PASS** ; seuls `task-router/SKILL.md` et `BACKEND_SKILLS_CATALOG.md` signalés « gouvernance » (ajouts prévus) |
| `python manage.py check` (settings principaux) | « no issues (0 silenced) » |
| `python manage.py makemigrations --check --dry-run` (principaux) | « No changes detected » |
| `validate_skill_tree` (fonction du validateur, backend) | 0 erreur : nom frontmatter = dossier, adaptateurs présents pour les 5 skills |
| Apparition des skills | les 5 `backoffice-*` listés par Claude Code juste après création (rechargement à chaud OK) ; `backoffice-independence-guard` invoqué avec succès |
| `validate_governance.py` complet | **FAIL — antérieur à la Phase 0, non lié** : « missing Codex prompt/stop hooks: …\env\hivmeet_backend ». Cause : `.codex/hooks.json` ne déclare volontairement que `UserPromptSubmit` (description : Stop désactivé car Codex n'expose pas le message final). Fichier inchangé depuis le 2026-10-01, propre dans git. **Non corrigé** (hors zones autorisées) ; décision de gouvernance pour l'utilisateur. |

Écart à signaler : aucun test applicatif n'a été lancé en Phase 0 (aucun code exécutable créé,
hors le script du garde, validé par exécution réelle ci-dessus). La disponibilité de
PostgreSQL local pour les tests reste **à vérifier au début de la P1**.

**Arrêt obligatoire : ne pas démarrer la P1 sans demande explicite de l'utilisateur.**
