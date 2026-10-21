# Recommandations hors périmètre — défauts de l'application existante

> **Statut : NON CORRIGÉS, volontairement.** Le back-office doit rester indépendant du
> fonctionnement actuel de l'application (exigence de l'utilisateur). Ces points ont été
> découverts pendant l'exploration (2026-10-08). Chacun est une **décision à prendre
> séparément par l'utilisateur** ; aucune phase du back-office ne doit les corriger.
> Références de lignes relevées sur la worktree du 2026-10-08 (qui contient des
> modifications non commitées) : à re-vérifier avant d'agir.

| # | Défaut | Où | Conséquence | Effet sur le back-office |
|---|---|---|---|---|
| 1 | Le refresh de token ignore `is_active` | `authentication/views.py:485-526` | Un compte désactivé obtient encore des access tokens | La désactivation (P3) bloque login et appels REST, pas le refresh |
| 2 | Les consumers WebSocket ignorent `is_active` | `messaging/consumers.py:500-503`, `notifications/consumers.py:407-409` | Un compte désactivé peut garder/ouvrir un socket | À documenter dans l'écran de désactivation |
| 3 | Suppression RGPD probablement bloquée par `ProtectedError` pour tout utilisateur ayant une `KycReviewDecision` | `KycReviewDecision.attempt` en PROTECT (`profiles/models.py:927`), `process_account_deletion` (`profiles/tasks.py:202-214`) | La tâche repasse en `confirmed` et réessaie sans fin | P8 affiche l'échec ; **à confirmer par un test** puis décision DPO (anonymiser la décision ou règle de rétention) |
| 4 | Exports RGPD servis publiquement en DEBUG | regex de refus `hivmeet_backend/urls.py:63-66` sans `exports` | Fuite en environnement DEBUG | Sans effet prod ; le staff ne télécharge jamais d'export |
| 5 | Emails en clair dans les logs de signalement | `authentication/views.py:695`, `:776` | Donnée personnelle dans les logs | Le back-office ne journalise que des identifiants |
| 6 | `/metrics/` public et en erreur | `hivmeet_backend/health.py:199,229` (`Subscription.is_active` est une propriété) | Exposition de compteurs, requête qui échoue | Non réutilisé par le tableau de bord (P7) |
| 7 | Messages affichés et éditables en clair dans l'admin Django | `messaging/admin.py:11-42` | Exposition de contenu privé | Le back-office n'affiche jamais le contenu des messages |
| 8 | `User.role` non éditable dans l'admin, non posé par `createsuperuser` | `authentication/models.py:170`, `authentication/admin.py:23-44` | Seul `resolve_report_view` s'en sert | Non synchronisé : les accès back-office reposent sur des groupes |
| 9 | `WebhookEvent` jamais écrit | `subscriptions/models.py:589` | Table morte, purge hebdomadaire sans objet | Pas d'écran dédié |
| 10 | Paiement `SUCCESS` non honoré si KYC inactif (`kyc_required_for_activation`), jamais repris | `subscriptions/payment_gateway.py:498-511` | Utilisateur ayant payé sans Premium | P9 (optionnel) propose une reprise administrée |
| 11 | Demandes de suppression jamais confirmées (jetons inutilisés) | `profiles/views_settings.py:330` (TODO), `profiles/admin.py:131` | Restent `pending` | P8 : confirmation manuelle par un admin, avec motif |
| 12 | Exports RGPD : `download_url` jamais fourni, aucun email, `expired` jamais posé | `profiles/tasks.py:98-160` | Fonction inachevée côté utilisateur | P8 : statut seulement |
| 13 | Enrôlement MFA des relecteurs KYC refusé hors DEBUG/TESTING | `profiles/kyc_review.py:124` | L'API KYC interne est inutilisable en production | Le back-office a son propre MFA ; ne répare pas l'API interne |
| 14 | `AuditLogMiddleware` et `SecurityHeadersMiddleware` définis mais non activés | `hivmeet_backend/security.py:130-138,182` | Pas d'audit/CSP globaux | Le back-office a les siens, isolés |
| 15 | `rosetta.urls` inclus alors que `rosetta` est absent de `INSTALLED_APPS` | `hivmeet_backend/urls.py:53`, `settings.py:75` | Incohérence de configuration | Sans effet |
| 16 | `_cleanup_user_data` importe `messaging.models.Conversation` (inexistant) | `profiles/tasks.py:225` | Erreur avalée silencieusement | À signaler au moment de P8 |
| 17 | Le blocage d'utilisateur n'est pas appliqué en messagerie ; `Match.BLOCKED` jamais posé | `matching/models.py:147`, `profiles/views_settings.py:144-231` | Un utilisateur bloqué peut encore écrire | Hors périmètre ; pas de modération des conversations |
| 18 | `CORS_ALLOW_CREDENTIALS=True` + regex localhost pour tout chemin | `hivmeet_backend/settings.py:339-377` | Surface CORS large | Le back-office retire `corsheaders` de ses settings |

À mettre à jour par chaque phase si un nouveau défaut est découvert (ajouter une ligne, ne
rien corriger).
