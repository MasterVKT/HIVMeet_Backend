# KYC phase 2 — stockage privé, analyse et photos

> Statut : implémentation technique locale terminée ; aucun bucket de
> production, aucune migration de données réelle et aucune activation de
> production ne sont affirmés par ce document. Les gates phase 0 restent
> bloquants, en particulier l'avis juridique/DPO écrit.

## Garanties implémentées

| Sujet | Implémentation | Garantie / échec sûr |
|---|---|---|
| Buckets | `infra/kyc_private_storage/` définit deux buckets distincts KYC et médias profil, UBLA, prévention d'accès public, CMEK, IAM du seul compte runtime, chiffrement par l'agent GCS, signature V4 par workload identity, CORS minimal et protection Terraform contre la destruction de bucket. | Aucun binding `allUsers` ou `allAuthenticatedUsers`; aucun secret Terraform ni clé JSON. Le gate runtime vérifie aussi UBLA, CMEK, prévention d'accès public, CORS et IAM. Le plan réel doit être revu avant apply. |
| Configuration | `KYC_*` et `PROFILE_MEDIA_*` dans `env.example` et `settings.py`; identifiants de buckets/clés seulement. L'intention d'upload est valable 30 minutes par défaut, comme le défi selfie. | `memory` est limité aux tests/développement. En production, le démarrage refuse un backend non GCS, des buckets/CMEK absents ou identiques, un compte runtime absent, une rétention KYC non positive, un scanner autre que ClamAV, un exécutable ClamAV vide, ou toute limite/TTL/durée de quarantaine/timeout de scan non positive. La commande de gate confirme aussi que ce compte possède `roles/storage.objectAdmin` sur chaque bucket et refuse tout autre principal avec rôle d'accès aux objets. Les photos sont bornées à 5 MiB et par nombre de pixels, y compris hors endpoint HTTP ; une lifecycle KYC ne supprime pas une photo de profil active selon son seul âge. |
| Intentions KYC | `POST upload-intents` persiste une déclaration opaque/idempotente puis émet une URL PUT V4 non persistée, liée au MIME, à la taille déclarée, à l'expiration et à `ifGenerationMatch=0`. Le client doit envoyer `Content-Length` exactement égal à la déclaration. Les réponses KYC, y compris le défi selfie et l'URL PUT, portent `Cache-Control: no-store`, `Pragma: no-cache` et `X-Content-Type-Options: nosniff`. | Aucun chemin, URL, code, hash, document, e-mail ou donnée médicale dans les modèles de réponse, audit ou tâche. Toute clé d'idempotence présente dans un audit est une empreinte HMAC non réversible, jamais la valeur client brute. |
| Validation | `POST upload-intents/complete` ne reçoit que l'identifiant opaque et met en file `verify_kyc_upload`. La tâche vérifie objet, taille, MIME déclaré/réel, SHA-256, parseur structurel borné (pixels image, pages et objets PDF) et antivirus. | Scanner indisponible, objet absent, incohérence, PDF chiffré/trop complexe ou malware : quarantaine et expiration; aucun document ne devient utilisable. Il n'y a ni biométrie ni fournisseur KYC externe. |
| Expiration/purge | Beat expire les intentions toutes les 5 min, les KYC validés arrivés à échéance toutes les 15 min et les purges dues toutes les 10 min; les tâches sont bornées, idempotentes et reprennent avec backoff. | L'expiration persiste `expired`, invalide la projection et programme la purge; la suppression est vérifiée avant `purged`. `purge_attempts`, `next_purge_attempt_at`, `purged_at` et `deletion_verified_at` conservent une preuve minimale. |
| Suppression de compte | La tâche de suppression efface et vérifie d'abord les objets KYC et médias, puis seulement laisse les lignes cascader. | Une indisponibilité de stockage relance la suppression et conserve les handles DB au lieu d'orpheliner un objet. |
| Photos | Les nouvelles photos et les scripts de peuplement sont recréés sous clés opaques en stockage privé; les images sont bornées avant traitement. Les DTO fournissent une route API authentifiée, lue via le backend, seulement pour le propriétaire ou un demandeur KYC actif. | Le droit est réévalué à chaque GET; aucune URL GET signée de bucket n'est émise, persistée ou exposée. Sans KYC actuel, aucune photo d'autrui n'est lue. L'ancien `StorageManager` refuse aussi les chemins KYC et `profiles/`, pour empêcher toute réintroduction de lecture/écriture générique. |
| Médias de messagerie | Les réponses REST/WebSocket exposent seulement la route de téléchargement authentifiée existante; les valeurs de stockage historiques sont ignorées. Le serveur de développement refuse les préfixes directs sensibles avant le handler statique. | Un compte sans KYC actif ne peut pas télécharger un média d'autrui; les copies temporaires/caches client devront être gérées par la phase 4. L’ingress et le stockage de production doivent refuser les préfixes directs équivalents. |
| Photos historiques | États `legacy_public → migration_copied → private` ou `migration_failed`, marqueur de source héritée vérifiée et tâche de copie/vérification/bascule/suppression. | La migration ne marque qu'une paire complète de chemins historiques sous `profiles/<user_id>/`; toute référence croisée, incomplète ou créée après cutover est refusée sans lecture ni suppression. Une copie partielle est compensée; si sa suppression ne peut être prouvée, ses clés opaques restent attachées à une ligne `migration_failed` pour intervention. La ligne ne bascule en privé qu'après copie lue et vérifiée puis suppression de l'original; un retry revérifie les deux objets privés. Source absente, fichier invalide/surdimensionné ou copie absente : échec fermé et intervention opérateur. |

Les exports existants sérialisent le profil et des données de compte minimisées
seulement; ils n'incluent ni `KycDocument`, ni `KycUploadIntent`, ni objet,
code, URL signée, chemin, information médicale ou e-mail complet.

## Procédure d'exploitation à faire approuver

1. Juridique/DPO fixe par écrit finalités, résidence, durée de rétention,
   sauvegardes/soft-delete et condition de purge; Sécurité/Plateforme approuve
   CMEK, IAM, CORS, signature V4 par workload identity, agent GCS, scanner et
   compte runtime. Seul le déploiement autorisé peut ensuite définir
   `HIVMEET_DEPLOYMENT_ENVIRONMENT=production`,
   `KYC_SOCIAL_ACCESS_ENFORCEMENT=enforced`,
   l'approbation juridique et sa référence non sensible, ainsi que les deux
   buckets/CMEK distincts, le compte runtime, la rétention approuvée et ClamAV :
   sans cette posture cohérente, le processus refuse de démarrer.
2. Plateforme exécute et fait relire `terraform plan` puis `terraform apply`
   dans l'environnement autorisé. Le versioning est désactivé : une purge ne
   doit pas devenir une simple version non courante. La politique éventuelle de
   soft-delete/sauvegarde doit respecter le barème juridique et être vérifiée
   explicitement, car elle n'est pas décidée par ce dépôt.
3. Plateforme renseigne les identifiants de ressource et le scanner dans le
   gestionnaire de secrets, jamais dans Git, puis exécute :

   ```powershell
   python manage.py verify_private_storage --scope all
   python manage.py migrate
   ```

   Cette commande contrôle les bindings directs du bucket. Plateforme/Sécurité
   doit compléter le gate par une analyse IAM effective projet/dossier/
   organisation, attestant qu'aucun autre principal ne peut accéder aux objets;
   les outils client Cloud Storage ne retournent pas ces droits hérités.

4. Exploitation déploie worker Celery et beat. Vérifier les tâches
   `expire_kyc_upload_intents`, `expire_verified_kyc_attempts` et
   `purge_due_kyc_documents`, les alarmes de retry et les marqueurs de
   suppression, sans inclure de valeur sensible dans les logs/alertes.
5. Avant toute activation, Plateforme inventorie les objets historiques pointés
   par la projection `Verification` sans les lire ni les requalifier. Avec
   Juridique/DPO, elle consigne la rétention applicable, révoque tout accès
   public éventuel et ne purge que sur instruction écrite. Ces références ne
   sont jamais une preuve KYC et les routes historiques restent en `410`.
6. Après sauvegarde/revue du plan de migration, lancer une cohorte bornée :

   ```powershell
   python manage.py migrate_legacy_profile_photos --batch-size 100
   ```

   Contrôler les comptes par états (`legacy_public`, `migration_copied`,
   `migration_failed`, `private`) sans exporter ni consigner les URLs. Stopper
   immédiatement si une copie ne peut être vérifiée ou si la suppression legacy
   n'est pas confirmée. Ne généraliser qu'une fois `legacy_public` et
   `migration_copied` à zéro, les échecs traités et l'absence d'objet public
   attestée par Plateforme.
7. L'activation production reste interdite tant que les gates juridiques,
   sécurité, plateforme, produit et phase 4/5 ne sont pas satisfaits. Cette
   phase n'active aucun flag de production.

## Contrat et compatibilité

Le contrat [KYC_V1_CONTRACT.openapi.yaml](KYC_V1_CONTRACT.openapi.yaml) ajoute
la confirmation asynchrone `upload-intents/complete`. `202 processing` ne
signifie ni acceptation technique ni décision humaine. Les anciennes routes de
chemins KYC restent en `410`; elles ne redeviennent pas disponibles.

Les guides frontend ont été réalignés sur le contrat, mais aucun source Flutter
n'a été modifié dans cette phase. Le client actuel appelle encore les routes
KYC historiques, qui répondent `410` de façon sûre. Sa phase 4 devra les
remplacer par le module KYC v1 : conserver l'URL PUT uniquement en mémoire, ne
jamais y mettre de bearer token, appeler `complete`, gérer `202`, lire les
photos par la route API authentifiée et ne jamais stocker les
URL/codes/documents.

## Gates encore externes

| Gate | Propriétaire attendu | Impact tant qu'il manque |
|---|---|---|
| Avis légal/DPO, DPIA, résidence, rétention, sauvegardes et textes finaux | Juridique/DPO | Aucun upload, lifecycle irréversible ou KYC en production. |
| Création/révision buckets, CMEK, IAM, CORS, soft-delete et scanner | Plateforme/Sécurité | Aucune preuve d'absence d'objet public ni de chiffrement réel. |
| Revue de cohortes et suppression des photos legacy | Plateforme/Exploitation | Les URLs historiques hors API peuvent subsister; pas de déclaration de conformité production. |
| Inventaire, révocation et purge des objets KYC hérités | Juridique/DPO, Plateforme/Exploitation | Les anciennes références `Verification` restent non fiables et potentiellement présentes hors du nouveau stockage; aucune conformité de stockage production ne peut être déclarée. |
| Rôles, MFA et revue humaine | Sécurité/Opérations, phase 3 | Les objets techniquement acceptés ne peuvent pas être validés KYC. |
| Parcours client, cache et upload mobile | Frontend, phase 4 | Le client ne doit pas encore être considéré compatible KYC v1. |
