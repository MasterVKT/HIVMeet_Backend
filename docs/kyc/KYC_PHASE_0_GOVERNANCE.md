# KYC phase 0 — gouvernance, accès et migration documentaire

> Statut : brouillon interne du 1er octobre 2026.
>
> Ce document n'est ni une approbation juridique, ni une activation KYC, ni
> une autorisation de production. Il ne modifie aucun comportement applicatif.
> Les phases 1 à 6 sont explicitement hors périmètre.

## Source de vérité

Le plan KYC situé dans ../KYC_IMPLEMENTATION_PLAN.md est la référence
fonctionnelle. Pour KYC API v1, ce document et
[KYC_V1_CONTRACT.openapi.yaml](KYC_V1_CONTRACT.openapi.yaml) sont les
brouillons canoniques : ce dernier définit les payloads, réponses, statuts et
erreurs ; celui-ci définit les habilitations, gates et compatibilités. Les
textes à soumettre sont dans
[KYC_PHASE_0_LEGAL_REVIEW_DRAFT.md](KYC_PHASE_0_LEGAL_REVIEW_DRAFT.md).

Les pages historiques recensées plus bas ne sont pas une source de conception
pour KYC v1. Elles restent une trace de l'existant jusqu'à leur migration selon
la politique de dépréciation.

La seule condition qui ouvre un droit social est :

    has_active_kyc(user, now)
      = verification.status == "verified"
        AND verification.expires_at > now

Les projections de compatibilité User.is_verified et
User.verification_status ne sont jamais une seconde source de vérité.

## Registre des décisions

| ID | Décision de cadrage | Statut | Validation attendue | Effet |
|---|---|---|---|---|
| KYC-0-01 | KYC actif obligatoire pour tout accès social et tout droit Premium effectif. | Retenu pour conception ; non activé | Produit, sécurité, juridique | Aucune exception de client, cache, webhook ou WebSocket. |
| KYC-0-02 | Preuves admises : identité officielle, document médical ou sérologique de moins de 90 jours, selfie avec défi à usage unique. | Retenu pour conception | Juridique/DPO et produit | Les trois preuves sont nécessaires à la revue. |
| KYC-0-03 | Revue humaine interne seulement ; ni biométrie automatisée, ni fournisseur externe, ni gabarit facial. | Retenu pour conception | Juridique/DPO, sécurité et opérations | Toute ancienne comparaison automatique est exclue. |
| KYC-0-04 | Stockage privé séparé, accès uniforme, KMS/CMEK et clés opaques ; aucune URL signée persistée. | Retenu pour conception | Sécurité/plateforme et juridique | Aucun objet KYC ni média d'autrui ne peut devenir public. |
| KYC-0-05 | Documents, codes, URL signées, chemins, e-mails complets et données médicales exclus des logs, analytics, notifications et exports. | Retenu pour conception | Sécurité, privacy engineering et DPO | Les événements se limitent à des métadonnées techniques minimales. |
| KYC-0-06 | Un abonnement reste historisé et résiliable, mais ses avantages sont suspendus dès que le KYC n'est plus actif. | Retenu pour conception | Produit, paiements et juridique | Reçus, support et résiliation restent accessibles. |
| KYC-0-07 | Une approbation juridique écrite est obligatoire avant toute activation en production. | Gate bloquant, non satisfait | Juridique/DPO désigné | Aucun acteur technique ne peut lever ce gate seul. |
| KYC-0-08 | Le contrat proposé est KYC API v1, version 1.0.0-draft.2 après extension technique phase 2. | Retenu pour revue | Backend, frontend et produit | Ce n'est pas une approbation de production. |

## Matrice d'habilitations contraignante

| Demandeur / état | Autorisé | Refusé côté serveur |
|---|---|---|
| Non connecté | Écrans publics, légaux et support public | Toute donnée ou fonction protégée |
| Connecté sans KYC actif : not_started, partiel, pending_review, rejected ou expired | Profil et photos propres ; parcours KYC ; consentements ; support ; export/suppression de compte ; information Premium, reçus et résiliation | Tout profil ou photo d'autrui ; discovery/recherche/filtres sociaux ; likes, super-likes, rewind et historique social ; matchs ; conversations, messages, appels, WebSockets et médias d'autrui ; achat, activation, modification ou réactivation Premium |
| Connecté avec KYC verified non expiré | Fonctions sociales usuelles ; droits Premium seulement si abonnement et paiement valides | Restrictions ordinaires de propriété, blocage, modération et paiement |
| Futur kyc_reviewer interne | Après MFA, dossier attribué, URL de consultation brève configurée à 5 minutes et auditée ; proposition de décision | Consultation non attribuée, export, accès social ou contournement MFA |
| Futur kyc_supervisor interne | Après MFA, attribution, décision ou révision auditée dans son périmètre | Accès global implicite, export ou effacement de trace d'audit |

La garde est exécutée avant toute résolution de profil, photo, URL média,
compteur, aperçu, pagination, notification, cache, WebSocket et autorisation
Premium. Une URL délivrée antérieurement doit devenir inutilisable après
expiration, rejet ou révocation.

## Contrat, versions et compatibilité

| Élément | Décision de phase 0 |
|---|---|
| Base de route | /api/v1/user-profiles/me/verification/ est conservée pour KYC v1. |
| Version de contrat | 1.0.0-draft.2, extension technique de phase 2 à signer par backend, frontend et produit avant activation. |
| Version backend minimale | Capacité serveur KYC v1 qui implémente entièrement le schéma signé. Le numéro de release déployable reste à attribuer par Release. |
| Version mobile minimale proposée | 1.1.0, postérieure à la base observée 1.0.0+1. Le build précis doit être figé par Produit/Release après la phase 4. |
| Client trop ancien | Aucun accès social ou Premium par compatibilité. Après activation, erreur sûre kyc_required et orientation vers mise à jour ou KYC. |
| Projections existantes | Compatibilité en lecture seulement ; une unique autorisation consulte has_active_kyc. |
| Langues et erreurs | Clés stables et textes FR/EN ; jamais de détail médical, de pièce ou d'exception brute. |

Les versions minimales sont des propositions, pas des versions publiées. Elles
ne peuvent devenir effectives avant le gate Produit/Release.

## Feature flag planifié et communication

Cette phase ne crée ni n'active de flag. La phase 1 devra proposer un seul
contrôle serveur, revu par sécurité :

| Champ planifié | Valeurs | Règle |
|---|---|---|
| KYC_SOCIAL_ACCESS_ENFORCEMENT | disabled, preproduction, enforced | `enforced` est obligatoire en production. `disabled` ou `preproduction` font échouer le démarrage d'un processus déclaré production. |
| KYC_PRODUCTION_LEGAL_APPROVAL + référence | booléen + identifiant non sensible d'avis écrit | Obligatoires avec `enforced` en production; le garde runtime ne vaut pas approbation juridique et ne peut être renseigné que par le déploiement autorisé. |
| KYC_CONTRACT_VERSION | kyc-v1 | Associée uniquement à des métriques techniques agrégées et non sensibles. |
| Passage à enforced | Changement contrôlé et journalisé | Possible uniquement après les gates ci-dessous ; aucune cohorte ne peut conserver un accès social sans KYC. |
| Retour arrière | Retour applicatif contrôlé | Ne restaure jamais bucket public, URL permanente, document purgé ou droit non mérité. |

Le flag ne transporte ni liste d'utilisateurs, ni statut médical, document,
code selfie ou e-mail.

Avant toute activation, Produit et Support doivent faire valider un préavis
FR/EN aux comptes existants, un écran qui mène au consentement et au support,
une explication de suspension des avantages Premium, et des notifications
génériques de décision/expiration. Aucun de ces messages ne contient une
donnée médicale, pièce, code, URL, chemin ou e-mail complet.

## Gates externes

| Gate bloquant | Propriétaire attendu | Preuve attendue | Impact tant qu'il manque |
|---|---|---|---|
| Finalités, bases légales, consentement et données de santé | Juridique et DPO officiellement désignés | Avis daté et périmètre validé | Pas de collecte ni activation production |
| Résidence, transferts, sous-traitants et DPIA si requise | Juridique/DPO | Juridictions, garanties et analyse d'impact | Pas de stockage KYC production |
| Rétention des brouillons, objets, sauvegardes, tentatives, audit et purge | Juridique/DPO et sécurité | Barème signé par catégorie | Pas de purge irréversible ni lifecycle production |
| Droits des personnes, incident, export, effacement et contact DPO | Juridique/DPO et support | Procédures validées FR/EN | Pas de lancement utilisateur |
| KMS/CMEK, IAM, bucket privé, CORS, sauvegardes et MFA | Sécurité/plateforme | Revue d'architecture et test | Pas d'upload ni revue interne |
| Matrice, contrat et minimums de version | Produit, backend, frontend et paiements | Sign-off et plan de migration | Pas d'enforcement ni dépréciation effective |
| Go/no-go final | Juridique/DPO, produit, sécurité et exploitation | Approbations écrites indépendantes | La valeur enforced est interdite |

Aucune de ces preuves n'a été fournie ou inférée. L'absence de l'avis
juridique bloque explicitement toute activation de production.

## Inventaire des contradictions documentaires

| Source constatée | Écart avec KYC v1 | Résolution imposée |
|---|---|---|
| docs/API_DOCUMENTATION.md, lignes 232-243 | Trois routes historiques sans schéma, statuts détaillés, erreurs sûres ni garde KYC. | Le schéma OpenAPI KYC v1 devient le contrat de payload ; les routes historiques suivent la dépréciation. |
| docs/FRONTEND_PROFILES_API.md, lignes 248-285 | Routes request/upload, multipart et chiffrement client. | Remplacer à terme par start, upload-intents et submit ; KMS/CMEK côté serveur et abstraction de capture remplacent ce texte. |
| docs/backend-specs.md, lignes 195-214 | Routes anciennes et comparaison automatique selfie/pièce. | Revue humaine interne uniquement, sans biométrie ni fournisseur externe. |
| docs/backend-specs.md, lignes 277-280 | 20 likes autorisés à un compte standard non vérifié. | Zéro droit social hors KYC actif ; 30 likes/24 h ne concerne qu'un compte KYC actif, sous réserve de Premium. |
| docs/backend-data-model.md, lignes 358-370 et 405-424 | URL de documents, code selfie et données sensibles dans une structure accessible utilisateur/admin. | Objets privés à clés opaques ; aucun URL, chemin ou code dans le contrat public. |
| docs/backend-data-model.md, lignes 642-646 | isVerified présenté comme duplication exploitable en accès. | Projection de compatibilité uniquement ; has_active_kyc est la source d'autorisation. |
| Spécifications historiques de statut | pending, approved ou pending_documents concurrencent les statuts actuels. | Les huit statuts publics du schéma KYC v1 sont exclusifs. |
| Documentation de photos et médias | Médias publics ou multipart non liés au KYC du demandeur. | Phase 2 doit les privatiser et les servir après autorisation actuelle. |
| Documentation Premium historique | Paiement/plan évalué sans garde KYC atomique. | KYC actif avant achat, activation, modification et tout avantage Premium. |

L'inventaire doit être mis à jour à chaque changement de contrat. Aucun
document contradictoire ne doit devenir une seconde norme.

## Politique de dépréciation

Les routes suivantes restent inchangées pendant la phase 0 :

| Route historique | Remplacement prévu |
|---|---|
| POST /api/v1/user-profiles/me/verification/generate-upload-url/ | POST /api/v1/user-profiles/me/verification/upload-intents/ |
| POST /api/v1/user-profiles/me/verification/submit-documents/ | POST /api/v1/user-profiles/me/verification/submit/ |
| Routes historiques /user-profiles/verification/request et /user-profiles/verification/upload | POST /start/, puis POST /upload-intents/ et POST /submit/ |

La phase 0 ne supprime, ne réoriente et ne masque aucune route. Après la phase
1, une dépréciation devra documenter les alternatives, exposer l'indicateur
OpenAPI et, si supporté, les en-têtes Deprecation et Sunset. Aucune date de
retrait ne peut être fixée avant signature du contrat, minimum mobile confirmé,
parcours Flutter disponible, communication aux comptes existants et validation
juridique. Le retrait exige en outre migration des clients supportés, plan de
retour arrière validé et preuve qu'aucun ancien client ne contourne KYC pour un
droit social ou Premium.

Les pages historiques qui mentionnent multipart, chiffrement client,
biométrie, KYC optionnel, URL/chemins de documents ou conservation non validée
doivent être signalées obsolètes pour KYC v1 avant publication produit.

## Sortie de phase 0

Les seuls livrables sont les brouillons de gouvernance, contrat, habilitations,
dépréciation, flag et textes de validation. Cette phase n'autorise pas
modèles, migrations, endpoints, stockage, tâches Celery, permissions, Flutter,
rôles de revue ni activation de production.
