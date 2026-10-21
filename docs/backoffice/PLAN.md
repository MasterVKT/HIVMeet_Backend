# Plan — Back-office d'administration HIVMeet

## Context
HIVMeet (Django 4.2 / DRF, PostgreSQL, Redis, Celery, Channels ; données de santé : tous les utilisateurs vivent avec le VIH) n'a pour toute administration que l'admin Django générique, incomplet et parfois trompeur :
- signalements non listables (`Report` non enregistré, seul `POST auth/reports/<id>/resolve`) ;
- actions admin `Verification` qui contournent `decide_kyc_case` ;
- revue KYC inutilisable en production (enrôlement MFA réservé DEBUG/TESTING) ;
- aucune suspension hors `is_active` ;
- modération photo aveugle ;
- demandes RGPD bloquées en `pending` ;
- aucun tableau de bord ;
- 3 mécanismes de rôles non reliés : `User.role`, `is_staff`, groupes `kyc_reviewer`/`kyc_supervisor`.

**Objectif** : un back-office minimal mais suffisant, calé sur le fonctionnement **réellement implémenté**, conçu phase par phase, avec skills dédiés en amont et un rapport hand-off permettant à tout autre agent de reprendre.

**Décisions utilisateur (figées)**
1. App Django dédiée server-rendered (templates + formulaires, sans framework JS).
2. Revue KYC complète.
3. Sanction = désactivation simple (`is_active`) avec motif et audit.
4. MFA TOTP obligatoire pour tout le staff.
5. **CONTRAINTE CRUCIALE — indépendance totale** : aucune modification pouvant impacter le fonctionnement actuel de l'application ; le back-office doit être indépendant de l'app.

## Contrat d'indépendance (règle n°1, opposable à toutes les phases)
- **Zones d'écriture autorisées** :
  - `backoffice/**`
  - `docs/backoffice/**`
  - `.agents/skills/backoffice-*/**`
  - `.claude/skills/backoffice-*/**`
  - lignes ajoutées dans `.agents/skills/task-router/SKILL.md` et `.agents/skills/BACKEND_SKILLS_CATALOG.md` (gouvernance, sans effet runtime)
  - `docker-compose.backoffice.yml` (nouveau fichier)
- **Tout le reste en lecture seule**, notamment :
  - `hivmeet_backend/settings.py`, `urls.py`, `test_runner.py`, `requirements.txt`, `docker-compose.yml`, `Dockerfile`, `env.example` ;
  - le code, l'admin Django et les migrations des 7 apps existantes.
- **Runtime isolé** :
  - `backoffice/conf/settings.py` fait `from hivmeet_backend.settings import *`, puis :
    - ajoute `backoffice` à `INSTALLED_APPS`, retire `daphne` et `corsheaders` ;
    - définit son propre `MIDDLEWARE`, son `ROOT_URLCONF = 'backoffice.conf.urls'` et son `WSGI_APPLICATION` ;
    - cookies distincts (`bo_sessionid`, `bo_csrftoken`, SameSite Strict) ;
    - `STATIC_ROOT` séparé ;
    - pas d'admin Django monté.
  - `backoffice/conf/settings_test.py` dérive de `hivmeet_backend.test_settings`.
  - L'app mobile/API **ne charge jamais** `backoffice` : absent de ses `INSTALLED_APPS` et de ses URL, donc sa suite de tests et son `makemigrations` sont inchangés.
  - Lancement :
    - dev : `python manage.py runserver 8001 --settings=backoffice.conf.settings` ;
    - prod : process gunicorn séparé (même image, `DJANGO_SETTINGS_MODULE` différent) via `docker-compose.backoffice.yml`.
- **Migrations** : uniquement `python manage.py migrate backoffice --settings=backoffice.conf.settings`. Ne **jamais** lancer `migrate` sans label, sinon des migrations en attente de la worktree seraient appliquées. Dépendance unique : `swappable_dependency(AUTH_USER_MODEL)`. Les tables `backoffice_*` sont additives ; rollback : `migrate backoffice zero`.
- **Réutilisation** : appeler les fonctions et tâches publiques existantes, sans les modifier :
  - `decide_kyc_case`, `assign_kyc_case`, `issue_reviewer_document_url`, `reviewer_role` (`profiles/kyc_review.py:62,222,249,294`) ;
  - `send_fcm_to_user` (`notifications/fcm.py:87`) ;
  - `reconcile_mycoolpay_payment` (`subscriptions/tasks.py:37`) ;
  - `process_account_deletion` (`profiles/tasks.py:162`) ;
  - le stockage privé (`profiles/private_storage.py`).

  Logique privée nécessaire (ex. résolution de signalement inline dans `authentication/views.py:736-850`) : **réimplémentée dans `backoffice/services/`** avec tests de parité, sans refactor de l'existant. Pas d'import de fonctions `_privées` sauf lecture unavoidable, documentée.
- **Aucune nouvelle dépendance** pip :
  - TOTP RFC 6238 implémenté dans `backoffice/mfa/` (hmac/hashlib) ;
  - chiffrement via `cryptography` (déjà présent) ;
  - pas de QR : URI `otpauth://` + secret base32 affichés une fois.
- **Gel des défauts découverts** : ils sont consignés dans `docs/backoffice/RECOMMANDATIONS_HORS_PERIMETRE.md` pour décision séparée de l'utilisateur, jamais corrigés ici.
  - refresh token ignore `is_active` (`authentication/views.py:485-526`) ;
  - consumers WS ignorent `is_active` (`messaging/consumers.py:500-503`, `notifications/consumers.py:407-409`) ;
  - suppression RGPD probablement en `ProtectedError` pour les utilisateurs ayant une `KycReviewDecision` (PROTECT, `profiles/models.py:927`) ;
  - exports servis en DEBUG (`urls.py:63-66` n'inclut pas `exports`) ;
  - emails en clair dans les logs de signalement (`authentication/views.py:695,776`) ;
  - `/metrics/` public et cassé (`health.py:229`) ;
  - messages éditables dans l'admin ;
  - `User.role` non éditable ;
  - `WebhookEvent` jamais écrit ;
  - paiements `kyc_required_for_activation` jamais repris.
- **Garde vérifiable** : script `check_independence.py` (skill guard), avec snapshot SHA-256 de tous les fichiers hors zones autorisées. Exclusions : `.git`, `__pycache__`, `*.pyc`, `.venv`, `media`, `staticfiles*`, `private_uploads`, `celerybeat-schedule*`, logs. Le snapshot est pris **avant toute écriture**, puis comparé en fin de chaque phase. Les tests sont lancés avec `PYTHONDONTWRITEBYTECODE=1`, car des `.pyc` sont suivis par git.

## Phase 0 — Skills + socle documentaire (création groupée)
Les skills se référencent mutuellement (développement → sécurité → tests → garde → hand-off). Ils sont donc créés en une passe cohérente, puis rendus opérationnels et vérifiés ensemble. Format imposé par `validate_governance.py` :
- canonique `.agents/skills/<nom>/SKILL.md` (frontmatter `name` = dossier) ;
- adaptateur `.claude/skills/<nom>/SKILL.md` = pointeur « Lire et suivre `../../../.agents/skills/<nom>/SKILL.md`. ».

Ordre de création et contenu des skills :
1. **`backoffice-independence-guard`** (créé en premier, script compris), puis **snapshot baseline** immédiat.
   - Contenu : contrat d'indépendance et zones autorisées.
   - Script `scripts/check_independence.py` : `snapshot` / `verify` / `report`.
   - Procédure si écart : attribuer, annuler son propre écart, ou signaler une modification de l'utilisateur.
   - Interdits : `migrate` sans label, `makemigrations` hors `backoffice`, `git reset`/`checkout`/`stash`.
2. **`backoffice-development`** : constitution et recette de module.
   - Arborescence `backoffice/` : `conf/`, `access.py`, `audit.py`, `mfa/`, `services/`, `views/`, `templates/backoffice/`, `static/backoffice/`, `tests/`, `management/commands/`, `locale/`.
   - Patron vue :
     - vues Django pures avec mixin `BackofficeAccessMixin(capability=...)` ;
     - formulaire de confirmation POST avec motif pour toute action destructive ;
     - `transaction.atomic`, puis notifications en `on_commit` ;
     - `Paginator` à 25 éléments.
   - Règles de réutilisation et liste des fonctions existantes autorisées.
   - i18n : msgids anglais `gettext_lazy`, catalogue FR dans `backoffice/locale`.
   - CSS écrit main, sans CDN.
   - Checklist module.
3. **`backoffice-security`**
   - Matrice des capacités.
   - Gate : actif + groupe back-office + session MFA. Pas d'accès implicite pour un superuser.
   - Flux MFA en deux étapes, step-up 300 s.
   - Verrouillage en cache, clés `bo:` hachées HMAC.
   - Audit `StaffAuditLog` avec whitelist de métadonnées.
   - Masquage des emails (`j***@d***.tld`).
   - Jamais affichés : contenu des messages, localisation, bio, document KYC hors flux audité.
   - Headers : CSP stricte, `no-store`, `noindex`, `frame-ancestors 'none'`.
   - Logs : ids seulement.
4. **`backoffice-testing`**
   - Patrons `Client.force_login` (session back-office pré-vérifiée MFA via helper).
   - Matrice de permission : anonyme, sans groupe, mauvais rôle, bon rôle.
   - Assertions : audit créé, absence de données sensibles dans le HTML, `assertNumQueries`.
   - Groupes via `ensure_backoffice_groups()`, car les migrations sont désactivées en test.
   - Commandes :
     - `PYTHONDONTWRITEBYTECODE=1 python manage.py test backoffice --settings=backoffice.conf.settings_test`
     - non-régression app : `python manage.py check` et `makemigrations --check --dry-run` avec les settings principaux, plus les suites ciblées existantes, inchangées.
5. **`backoffice-phase-handoff`**
   - Procédure de fin de phase :
     - `check_independence verify` ;
     - tests ;
     - audit de complétude (`hivmeet-backend-completion-audit`) ;
     - mise à jour de `docs/backoffice/HANDOFF.md` (statut, fichiers, décisions, preuves, commandes, limites, prochaine phase, critères d'entrée) ;
     - **arrêt obligatoire** en attente d'un « continue » explicite.
   - Note : le hook Stop Claude ne voit pas le signal PASS (limite connue, `agent-integrations.json` : `configured_but_not_activated`) ; 2 reprises maximum, puis livraison.

Également en Phase 0 :
- lignes ajoutées au `task-router` (registre + scénario « back-office : `backoffice-development` + `backoffice-security` ») et au `BACKEND_SKILLS_CATALOG.md` ;
- `docs/backoffice/PLAN.md` (copie de ce plan, source de vérité dans le dépôt) ;
- `docs/backoffice/HANDOFF.md` (squelette + état Phase 0) ;
- `docs/backoffice/RECOMMANDATIONS_HORS_PERIMETRE.md`.

**Opérationnalité** : Claude Code recharge à chaud `.claude/skills/`. On vérifie l'apparition des 5 skills dans la liste et on invoque `backoffice-independence-guard`. Repli : lecture directe des `SKILL.md`, à noter dans le HANDOFF. Validation : `python D:/Projets/HIVMeet/.agents/skills/hivmeet-governance/scripts/validate_governance.py` → PASS, puis `check_independence verify` → zéro écart.

## Phases d'implémentation (une session chacune ; ★ = minimum requis)
Chaque phase se termine par : tests verts, `verify` sans écart, HANDOFF mis à jour, arrêt.

**★ P1 — Fondation isolée**
- Contenu :
  - `backoffice/conf/{settings,settings_test,urls,wsgi}.py` ;
  - app (`apps`, `models`, `access.py`, `roles.py`, `audit.py`, `middleware.py` actif seulement via settings back-office, `checks.py`) ;
  - migrations `0001` (`StaffAuditLog` append-only : UUID, actor `SET_NULL` + `actor_ref`, action slug, `target_type`/`target_id` en chaînes, `reason`, `metadata` whitelistée, `ip_hash` HMAC, index) et `0002` (groupes `backoffice_admin`, `backoffice_moderator`, `backoffice_support` ; reverse no-op) ;
  - templates `base`/`login`/`denied`, CSS ;
  - étape mot de passe (sans `login()` avant TOTP) ;
  - gate fail-closed jusqu'à P2.
- Tests : redirections, refus générique, verrouillage, headers.
- Preuve d'indépendance : settings principaux inchangés, `manage.py check` principal OK, `makemigrations --check` principal inchangé.

**★ P2 — MFA staff**
- Modèles propres `backoffice.StaffMfaDevice` (secret Fernet, clé `BACKOFFICE_MFA_ENCRYPTION_KEY`, dérivée de `SECRET_KEY` seulement en DEBUG/TESTING ; `last_totp_counter` anti-rejeu) et `StaffMfaEnrollmentToken` (haché, 24 h, usage unique). Aucun usage des tables MFA KYC.
- Commande `backoffice_bootstrap_admin --email` (TTY requis, secret affiché une fois).
- Enrôlement par jeton émis par un admin.
- Step-up 300 s.
- Reset MFA : purge des sessions + audit.

**★ P3 — Utilisateurs & sanctions**
- Recherche exacte email/UUID (pas de navigation libre).
- Fiche masquée : nom affiché, dates, actif, statut KYC (libellé), premium, compteurs de signalements, historique de sanctions issu de l'audit.
- Désactivation/réactivation avec motif : uniquement `is_active` + audit.
- Gestion des groupes staff : admin seulement, pas d'auto-modification, garde « dernier admin ».
- Ajout ou retrait des groupes KYC audité (cela donne aussi accès à l'API KYC existante : sémantique existante).
- Limites (refresh/WS) documentées, pas corrigées.

**★ P4 — Signalements**
- File par statut/motif (le plus ancien d'abord), prise en charge (`under_review`), résolution/rejet.
- Service back-office réimplémentant **à l'identique** les effets de `resolve_report_view` : statut, `resolved_by`/`at`, `Notification` `report_resolved`, FCM via `send_fcm_to_user`, `group_send` `user_<id>`.
- Tests de parité avec les payloads de l'API existante.
- Champ « message visible par le signaleur » (`resolution_notes`) distinct du motif interne (audit).
- Raccourci vers la désactivation de P3.

**★ P5 — Revue KYC**
- Rôle via `reviewer_role()`, sinon 403, y compris pour un admin.
- Pages :
  - mes dossiers ;
  - non assignés (superviseur) ;
  - assignation (`assign_kyc_case`) ;
  - détail (requêtes en lecture, contrôle d'assignation équivalent) ;
  - accès document : POST + step-up → `issue_reviewer_document_url`. En GCS, lien 5 min. En `local`/`memory`, flux dev via `read_reviewer_document_for_development` ; `PrivateStorageUnavailable` est géré.
  - décision via `decide_kyc_case` (codes `DECISION_REASON_CODES`, clé d'idempotence uuid4, mapping des exceptions) ;
  - boîte d'alertes superviseur (`Notification` `system` `kyc_review*`).
- Rappel : la revue réelle reste soumise à l'accord juridique/DPO (`docs/kyc/KYC_PHASE_3_IMPLEMENTATION.md`).

**★ P6 — Modération contenu**
- Posts et commentaires du feed : approuver/rejeter avec notes, mêmes champs que les actions admin existantes.
- Photos : proxy staff `no-store` (lecture via le stockage privé existant, audit de la vue pleine taille), bascule `is_approved` + `moderation_notes`.
- File : uploads récents + photos d'utilisateurs signalés.

**★ P7 — Tableau de bord**
- KPI filtrés par capacité, cache 60 s :
  - signalements en attente / en cours ;
  - feed en attente ;
  - KYC pending / non assigné / en retard ;
  - paiements pending et `kyc_required` ;
  - RGPD pending / confirmé ;
  - exports échoués ;
  - inscriptions sur 7 jours.
- Aucune ventilation par attribut de santé ou de profil. `/metrics/` non réutilisé.

**★ P8 — RGPD**
- Liste des demandes de suppression : confirmer, annuler, traiter maintenant. Admin seulement, motif obligatoire, appel de la tâche existante.
- Affichage de l'échec éventuel (`ProtectedError` connu, documenté).
- Exports : statut uniquement, jamais de téléchargement staff.

**P9 — Abonnements & paiements (optionnel)**
- Listes en lecture (utilisateur masqué).
- « Réconcilier » → `reconcile_mycoolpay_payment.delay`.
- Reprise d'un paiement `kyc_required_for_activation` via service back-office appelant `SubscriptionService.create_subscription` (`select_for_update`, admin, audité).

**P10 — CMS ressources (optionnel)** : catégories et ressources FR/EN, publier/mettre en avant (l'admin Django couvre déjà ce besoin).

**★ P11 — Durcissement & livraison**
- Catalogue FR compilé.
- Checks de déploiement (cache Redis, clé MFA présente).
- `docker-compose.backoffice.yml`.
- Runbook (bootstrap, enrôlement, perte d'appareil, rotation de clé, allow-list IP/VPN nginx recommandée).
- Skills `security-permissions` + `backend-release-readiness`.
- Finalisation de `RECOMMANDATIONS_HORS_PERIMETRE.md`.

Hors plan : diffusion massive de notifications (risque de vie privée sur l'écran de verrouillage).

## Matrice des capacités (résumé)
| Capacité | admin | moderator | support | kyc_reviewer | kyc_supervisor |
|---|---|---|---|---|---|
| tableau de bord | ✓ | ✓ | ✓ | ✓ | ✓ |
| users.search / view (masqué) | ✓ | ✓ | ✓ | | |
| users.view_pii (audité) | ✓ | | | | |
| users.deactivate | ✓ | ✓ | | | |
| users.reactivate | ✓ | | | | |
| staff.manage | ✓ | | | | |
| reports.\* | ✓ | ✓ | | | |
| moderation.\* | ✓ | ✓ | | | |
| payments.view / reconcile | ✓ | | ✓ | | |
| gdpr.view | ✓ | | ✓ | | |
| gdpr.act | ✓ | | | | |
| audit.view | ✓ | | | | |
| kyc.\* | | | | ✓ | ✓ (+ file, assignation, alertes) |

Un modérateur ne peut pas désactiver un membre du staff ni un superuser.

## Impact frontend
**Nul.** Aucun contrat, payload, statut ni code client modifié. Les actions du back-office produisent exactement les effets déjà possibles via l'API ou l'admin existants : désactivation `is_active`, notification `report_resolved` identique, `is_approved` photo, décisions KYC.

## Vérification (à chaque phase)
```
PYTHONDONTWRITEBYTECODE=1 python manage.py test backoffice --settings=backoffice.conf.settings_test
python manage.py check                                   # settings principaux : inchangé
python manage.py makemigrations --check --dry-run         # principal : aucune migration nouvelle
python manage.py check --settings=backoffice.conf.settings
python manage.py makemigrations backoffice --check --dry-run --settings=backoffice.conf.settings
PYTHONDONTWRITEBYTECODE=1 python manage.py test <suites existantes touchées en lecture> --settings=hivmeet_backend.test_settings
python .agents/skills/backoffice-independence-guard/scripts/check_independence.py verify
python D:/Projets/HIVMeet/.agents/skills/hivmeet-governance/scripts/validate_governance.py
```
Plus un test manuel : `runserver 8001 --settings=backoffice.conf.settings` → login → TOTP → module de la phase.

## Exécution
Phase 0 maintenant ; ensuite arrêt et attente d'un « continue » explicite entre chaque phase. `docs/backoffice/HANDOFF.md` permet à tout agent de reprendre avec les mêmes critères.
