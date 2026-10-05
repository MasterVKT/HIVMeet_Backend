# Audit de complétude — KYC phase 2

> Périmètre : stockage, analyse, purge et médias privés. Ce document prouve
> les changements locaux et les contrôles exécutés; il ne prétend pas qu'une
> infrastructure ou une validation externe a eu lieu.

## Exigences → preuves

| Exigence de phase 2 | Preuve locale | Gate restant |
|---|---|---|
| Bucket KYC distinct, UBLA, CMEK, IAM, CORS minimal, aucun secret | `infra/kyc_private_storage/{main,variables,outputs}.tf`; buckets/clefs distincts, agent GCS CMEK, signature V4 uniquement pour PUT KYC par workload identity, prévention de destruction, absence de CORS sur les médias profil et lifecycle seulement pour les objets KYC; `verify_private_storage` vérifie UBLA, CMEK, prévention d'accès public, CORS, absence de binding public, présence de `roles/storage.objectAdmin` pour le compte runtime configuré et absence de tout autre principal avec rôle d'accès objet; configuration sans secret. | Apply, revue IAM/KMS/CORS/soft-delete et preuve indépendante des droits IAM effectifs projet/dossier/organisation, que l'API bucket ne retourne pas. |
| Pas d'activation KYC production sans avis écrit ni stockage privé configuré | `hivmeet_backend.kyc_runtime` bloque le démarrage d'un environnement déclaré `production` sauf mode `enforced`, approbation et référence non sensible; il refuse aussi tout backend non GCS, buckets/CMEK absents ou identiques, compte runtime absent, rétention, TTL, quarantaine, timeout de scan ou limites de taille/parseur non positifs, scanner non ClamAV ou exécutable ClamAV vide. Les tests couvrent les refus. | La variable/référence ne remplace jamais l'avis écrit, ni le contrôle réel d'IAM/KMS : le propriétaire de déploiement doit les vérifier avant de les renseigner. |
| Intentions/signatures contraintes et validation d'objet | `profiles.private_storage`, `profiles.kyc.issue_kyc_upload_intent`, vues/serializer `complete`, tâche `verify_kyc_upload`. | Scanner réel et test sur bucket réel. |
| Aucune biométrie automatisée ni fournisseur KYC externe | Le flux technique ne fait que vérifier intégrité, structure et antivirus; la recherche statique dans les dépendances et modules concernés ne trouve aucun fournisseur KYC ni fonction de comparaison/reconnaissance biométrique. | La revue humaine interne, ses rôles et son MFA restent strictement de phase 3. |
| Quarantaine, expiration, retry et purge vérifiée | `KycDocument` champs phase 2, tâches Celery bornées/idempotentes, schedules beat (`expire_kyc_upload_intents`, `expire_verified_kyc_attempts`, `purge_due_kyc_documents`) et preuve `deletion_verified_at`. | Observabilité/exploitation réelle et barème juridique. |
| Aucun KYC en logs, analytics, notifications ou export | Audit whitelist `KycAuditEvent`, corrélation d'idempotence HMAC non réversible, tâches à messages génériques, export sans modèles KYC, e-mail complet, code, URL signée ou chemin; les messages de demande sont opaques. | Revue centralisée des pipelines externes de logs/analytics. |
| Références KYC historiques non réutilisées | `0011_create_legacy_kyc_reverification_attempts` ne projette que l'identifiant utilisateur; `VerificationSerializer` masque les chemins/code et les deux routes historiques sont en `410`. | Inventaire, révocation d'accès et purge des objets historiques par Plateforme après décision Juridique/DPO; aucune suppression automatique ne peut devancer la politique de conservation. |
| Photos de profil privées et servies après autorisation actuelle | `ProfilePhoto` clés/états privés, `profile_photo_storage`, route API authentifiée à contrôle KYC par GET, serializers consommateurs, scripts de peuplement, retrait de `make_public` et de toute URL GET signée. | Migration des objets legacy et scan d'accès public de l'environnement réel. |
| Migration copier/vérifier/basculer/supprimer | `migrate_legacy_profile_photo`, commande bornée et runbook; une paire legacy est acceptée seulement sous `profiles/<owner_id>/`, contrôle binaire/poids, compensation des copies partielles et revérification des copies lors d'un retry. | Exécution de cohortes approuvées; toute ligne `migration_failed` doit être traitée. |
| Médias de messagerie non publics | `MessageSerializer`, service et WebSocket renvoient uniquement la route REST authentifiée; aucun DTO ne livre les anciennes valeurs de stockage. Le serveur DEBUG refuse les préfixes directs sensibles. | L’ingress et le stockage de production doivent interdire les mêmes accès directs; adaptation du transport/caches Flutter en phase 4. |

## Changements → exigences

| Changement | Couvre |
|---|---|
| Migrations `profiles/0012_phase2_private_storage.py` et `0013_phase2_legacy_photo_cutover.py` | États, handles de purge, preuve de suppression, clés privées et classification contrôlée des seules références photo préexistantes, sans retirer les colonnes legacy. |
| `private_storage.py`, `storage/manager.py`, settings, `env.example`, dépendance `pypdf` | Adaptateur GCS/mémoire, CMEK/configuration fail-closed, validation MIME/parseur/antivirus bornée par pixels, pages et objets PDF, plafond binaire, clés opaques contrôlées à chaque opération, refus des chemins KYC/profil par l'adaptateur legacy, exceptions fournisseur non chaînées et gate prévention d'accès public/CORS/IAM du compte runtime. |
| `kyc.py`, serializers, views, urls, tasks, Celery beat | Upload direct opaque, completion asynchrone, scan/quarantaine, expiration des intentions et des KYC vérifiés, purge/retry. La signature V4 lie MIME, taille déclarée (`Content-Length`) et `ifGenerationMatch=0`; les contrôles après upload restent obligatoires. Toutes les réponses KYC portent une politique HTTP `no-store`/`nosniff`, notamment celles contenant le défi selfie ou l'URL PUT transitoire. L'helper d'audit filtre les métadonnées et empreinte par HMAC toute clé d'idempotence avant persistance ; le rejeu accepte aussi, temporairement, les lignes historiques brutes. |
| Projection `Verification` et tests d'intégration | Compatibilité d'état sans confiance dans les chemins/documents/codes historiques; les parcours sociaux/Premium exigent désormais une `KycAttempt` active et le contrat historique est refusé en `410`. |
| `photo_storage.py`, serializers, route média, scripts de peuplement/nettoyage et consommateurs sociaux | Création/lecture/suppression privée de photos, sans livraison à un non-KYC et sans URL GET signée de bucket; suppression legacy vérifiée avant cascade de compte; toute copie historique partielle est compensée ou reste traçable sur une ligne en échec; aucun script de nettoyage ne journalise de chemin de stockage. |
| `messaging/{serializers,services,signals,views}.py`, URLs et contrat média | Les médias de conversation ne sont exposés que par la route participant+KYC existante avec `no-store`; les URL de bucket, chemins et thumbnails historiques sont masqués. |
| Terraform, commande de vérification et commande de migration | Provisionnement déclaratif, contrôle d'exploitation et migration progressive. |
| Contrat OpenAPI et documentation phase 2 | Contrat client, runbook et gates explicites; `docs/API_DOCUMENTATION.md` et les guides backend/frontend `FRONTEND_PROFILES_API.md` renvoient au KYC v1. Les routes v0 n'y figurent que comme dépréciées en `410`; les anciennes spécifications et inventaires sont explicitement archivés. Elles ne peuvent donc plus coexister comme contrat actif. |

## Validation indépendante et non destructive

| Vérification | Résultat |
|---|---|
| `HIVMEET_TEST_DB_NAME=hivmeet_phase2_kyc_validation_20261002_ab python manage.py test profiles.tests.test_kyc_phase1 profiles.tests.test_kyc_phase2 profiles.tests.test_location_and_photos --settings=hivmeet_backend.test_settings` | Réussi : 55 tests sur une base de test isolée. Couvre aussi l'empreinte HMAC de clé d'idempotence et la compatibilité de rejeu historique, la durée par défaut de 30 minutes de l'intention d'upload, la signature V4 qui lie `Content-Type` et `Content-Length`, l'interdiction HTTP de mise en cache du défi selfie et de l'URL PUT, le compte runtime, son rôle IAM requis et le refus d'un second principal avec accès objet, le refus au démarrage production d'une configuration de stockage privée incomplète, y compris exécutable ClamAV vide, TTL, quarantaine, timeout et limites de scan non positifs, en plus des intentions opaques/idempotentes, JPEG et PDF médical parsés réellement, refus d'un PDF au-delà du nombre de pages ou d'objets autorisé, scan accepté, incohérence/quarantaine/purge idempotente, expiration des KYC vérifiés, reprise de purge, photos nouvelles, lecture propriétaire, refus sans KYC, révocation dès l'expiration KYC, refus direct de `/media/kyc/`, absence d'e-mail complet dans export/message de demande, garde runtime d'avis juridique production, non-livraison et non-suppression d'une écriture brute legacy, source legacy croisée/incomplète refusée, compensation de copie partielle, suppression de compte sans objet orphelin, rejet des clés hors espace privé et des chemins KYC/profil par l'adaptateur legacy, CORS/prévention d'accès public et commande de vérification mémoire. |
| `HIVMEET_TEST_DB_NAME=hivmeet_phase2_clamav_gate_20261002_a python manage.py test profiles.tests.test_kyc_phase2 --settings=hivmeet_backend.test_settings` | Réussi : 31 tests. Confirme en particulier le refus d'un rôle direct `roles/viewer` ou `roles/storage.objectViewer` accordé à un second principal, le refus des limites production invalides et d’un exécutable ClamAV vide, ainsi que le rejet local d'un PDF au-delà de la borne de pages ou d'objets ; la vérification des rôles hérités au-dessus du bucket reste une preuve plateforme distincte. |
| `HIVMEET_TEST_DB_NAME=hivmeet_phase2_contract_20261002_t python manage.py test profiles.tests.test_kyc_phase1 --settings=hivmeet_backend.test_settings` | Réussi : 11 tests. Confirme entre autres le refus `410 kyc_legacy_endpoint_deprecated` des deux contrats KYC v0 et l’habilitation KYC transversale. |
| Import contrôlé des settings production | Refus vérifié avec approbation mais stockage privé incomplet; démarrage accepté seulement avec environnement `production`, mode `enforced`, approbation/référence non sensible, GCS, deux buckets/CMEK distincts, compte runtime, rétention positive et ClamAV. Aucun service ou bucket externe n'a été sollicité. |
| `HIVMEET_TEST_DB_NAME=hivmeet_phase2_message_contract_20261002_k python manage.py test messaging.tests messaging.tests_media_download messaging.tests_phase2 messaging.test_remediation --settings=hivmeet_backend.test_settings` | Réussi : 91 tests. Couvre la permission KYC sur REST/WebSocket, téléchargement média réservé au participant KYC, absence de lien direct `/media/messages/`, DTO/événement sans URL de stockage ni thumbnail et cache de réponse privé. |
| `HIVMEET_TEST_DB_NAME=hivmeet_phase2_legacy_integration_20261002_h python manage.py test tests.test_integration --settings=hivmeet_backend.test_settings` | Réussi : 5 parcours d'intégration. Les flux discovery, messagerie et Premium établissent un KYC actif avant l'accès; le statut KYC ne divulgue pas de code ni de chemin et les deux routes historiques retournent `410`. |
| Migrations réelles sur PostgreSQL éphémère | Réussi le 2026-10-02 : application complète, rollback `profiles 0013 → 0011`, réapplication `0012/0013`, état `[X]` confirmé, puis destruction vérifiée de `hivmeet_phase2_migration_validation_20261002_f`. |
| `python manage.py check --settings=hivmeet_backend.test_settings` | Réussi : aucune anomalie système. |
| `HIVMEET_DEPLOYMENT_ENVIRONMENT=development`, `KYC_SOCIAL_ACCESS_ENFORCEMENT=disabled`, `DEBUG=True`, puis `python manage.py makemigrations profiles --check --dry-run` | Réussi : aucune migration manquante. Les settings de test désactivent intentionnellement les migrations; les variables sont limitées au sous-processus de contrôle et ne modifient aucun fichier. |
| `python -m compileall -q hivmeet_backend profiles` et analyse YAML OpenAPI | Réussies. |
| Recherche statique fournisseur/biométrie | Réussie : aucune occurrence de fournisseur KYC connu ou de comparaison/reconnaissance biométrique dans `requirements.txt`, `profiles`, `hivmeet_backend`, `messaging`, `subscriptions`, `matching` et `resources` (hors caches Python). |
| Revue des journaux KYC locaux | Les appels `logger` des flux KYC/stockage/purge/migration sont génériques; les clés d'objet, documents, codes selfie, URL signées, e-mails complets et informations médicales restent exclusivement dans les opérations internes nécessaires et ne sont pas interpolés dans un message de log. |
| Audit documentaire KYC v1/v0 | Les guides profils backend et frontend ont été réalignés sur les routes KYC v1; les archives qui conservent des exemples v0 portent un avertissement explicite et renvoient à OpenAPI. Les deux routes v0 restent testées en `410`. |
| Terraform `fmt` et `validate` | Réussis sur une copie temporaire du module avec Terraform 1.6.6 téléchargé depuis l’éditeur, archive SHA-256 vérifiée, puis `terraform fmt -check -diff`, `terraform init -backend=false` et `terraform validate -no-color`. Aucun `plan`, `apply`, état de dépôt ou ressource cloud n’a été créé. Le plan/apply réel, les credentials et la preuve IAM/KMS/CORS effective restent un gate Plateforme. |

## Impact backend / frontend

- Backend : nouvelle migration additive; le stockage de mémoire n'est permis
  qu'en test/développement. En production, configuration incomplète ou scanner
  indisponible échoue sans accepter de document. L'ancien stockage générique
  ne rend plus de blob public.
- Frontend : le routeur frontend puis l'audit de contrat ont été chargés avant
  l'analyse ciblée. Les guides profils backend et pair ne présentent plus les
  routes KYC v0 comme actives. En revanche, `profile_api.dart`, le repository,
  l'entité et `verification_page.dart` Flutter appellent encore
  `generate-upload-url/`/`submit-documents/` et manipulent un chemin de
  stockage : ils reçoivent donc `410` de manière sûre. Leur remplacement par
  le module KYC v1 est strictement de phase 4 et n'a pas été commencé. Le guide
  pair `hivmeet/docs/FRONTEND_MESSAGING_API.md` a aussi été corrigé pour ne
  plus montrer de bucket ou de thumbnail brut; le téléchargement explicite
  emploie déjà `ApiClient`, mais l'aperçu inline repose encore sur
  `CachedNetworkImage`, qui ne porte pas l'en-tête d'authentification. La phase
  4 devra le remplacer par un rendu via le transport authentifié et purger les
  caches lors de perte de KYC, déconnexion ou suppression; elle devra commencer
  à nouveau par son routeur/orchestrateur.

## Conclusion de phase et bloqueurs

La réalisation locale de phase 2 est prête à être revue. La sortie production
« aucun objet KYC ou photo d'autrui public » n'est pas attestable avant le
provisionnement contrôlé et la migration réelle. Ce sont des gates externes,
pas des autorisations implicites : juridique/DPO, Sécurité/Plateforme,
Opérations et Frontend/Produit restent requis avant toute activation.
