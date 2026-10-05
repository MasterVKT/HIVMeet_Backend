# Plan d’implémentation KYC — HIVMeet

> Statut : plan d’exécution approuvé fonctionnellement, sans implémentation lancée.
>
> Périmètre : backend Django/DRF, stockage, tâches asynchrones, paiements, notifications,
> administration de revue et application Flutter.
>
> Date de l’audit : 1er octobre 2026.

## 1. Objectif et règle d’accès de référence

L’objectif est de livrer un processus KYC manuel, sûr, traçable et réellement
appliqué à toute l’application. Il repose sur trois preuves :

1. une pièce d’identité officielle avec photo ;
2. un document médical ou sérologique daté de moins de 90 jours ;
3. un selfie présentant un code de défi à usage unique.

La seule condition qui ouvre les droits sociaux est :

```text
kyc_actif = verification.status == "verified"
             ET verification.expires_at > maintenant
```

`User.is_verified` et `User.verification_status` restent des projections de
compatibilité ; elles ne doivent jamais devenir une seconde source de vérité.
La décision humaine est obligatoire. Il n’y a ni fournisseur KYC externe, ni
comparaison biométrique automatisée, ni conservation de gabarit facial.

### 1.1 Matrice d’habilitations contraignante

| État du compte | Actions encore permises | Actions interdites côté serveur |
|---|---|---|
| Non connecté | Écrans publics, légaux et support public | Toute donnée ou fonction protégée |
| Connecté mais `not_started`, partiel, `pending_review`, `rejected` ou `expired` | Profil et photos propres, parcours KYC, consentements, support, export/suppression de compte, lecture d’information Premium, reçus et résiliation | Profils et photos d’autrui, recherche/découverte, likes, super-likes, rewind, matchs, conversations, appels, médias d’autrui, filtres sociaux, achat/activation/modification/réactivation Premium |
| `verified` non expiré | Toutes les fonctionnalités sociales habituelles ; Premium si abonnement et paiement valides | Restrictions métier ordinaires uniquement |

Un abonnement déjà acquis demeure historisé et peut être résilié, mais ses
avantages effectifs sont suspendus dès que le KYC n’est plus actif. Les URL de
médias d’autrui doivent cesser d’être utilisables après expiration, rejet ou
révocation.

Cette règle tranche une contradiction documentaire : l’ancienne mention de
« 20 likes pour un non vérifié » est incompatible avec la règle
*verified-only* pour l’espace social. Après activation du KYC obligatoire,
un compte sans KYC actif a zéro droit social ; le quota de 30 likes/24 h est
celui d’un compte vérifié, sous réserve des règles Premium applicables.

## 2. Décisions de conception non négociables

- Stockage : bucket KYC dédié, privé, à accès uniforme, chiffré côté serveur
  avec KMS/CMEK et comptes de service à privilège minimal.
- Capture mobile : contrôles locaux de cadrage, lisibilité, détection de
  document et rédaction ; aucun traitement distant de biométrie. Android
  utilisera ML Kit natif et iOS Vision/VisionKit derrière une abstraction
  Flutter commune, avec saisie manuelle de secours.
- Revue : rôles internes `kyc_reviewer` et `kyc_supervisor`, MFA obligatoire,
  attribution explicite d’un dossier et journal d’accès/décision immuable.
- Confidentialité : jamais de pièce, code selfie, URL signée, chemin de
  stockage, email complet ni détail médical dans logs, analytics, Crashlytics,
  notifications ou export de données.
- Formats proposés : identité et document médical JPEG/JPG/PNG/PDF, 10 MiB
  maximum ; selfie JPEG/JPG/PNG, 5 MiB maximum. La signature binaire, la
  taille et le décodage réel priment sur l’extension et l’en-tête client.
- Durées proposées : URL d’upload de 30 minutes ; défi selfie à usage unique
  de 30 minutes ; KYC validé valable 180 jours. Ces valeurs sont configurées,
  testées et documentées.
- Purge : les fichiers bruts sont supprimés après décision finale, expiration
  ou suppression de compte. La durée des brouillons, tentatives abandonnées,
  sauvegardes et journaux doit être validée juridiquement avant production.

## 3. Audit de l’existant

### 3.1 Backend et stockage

Le modèle `profiles.Verification` et les endpoints actuels constituent un
début de flux, mais ne satisfont pas les garanties ci-dessus.

- `GET /api/v1/user-profiles/me/verification/` crée actuellement un code
  selfie comme effet de bord ; une lecture doit être sans mutation.
- Le code utilise `random`, pas `secrets`, et son cycle de vie n’est pas
  borné de manière fiable.
- L’URL signée est produite pour une clé déterministe incluant l’identifiant
  utilisateur. Le client peut ensuite soumettre un `file_path_on_storage`
  arbitraire : le backend ne prouve ni l’existence, ni la propriété, ni le
  contenu de l’objet.
- Les validations ne contrôlent que l’extension, le MIME déclaré et une taille
  déclarée ; aucun hash, détection binaire, décodage, antivirus, quarantaine
  ou protection contre les PDF/images malveillants n’existe.
- Les signaux ne synchronisent de façon complète que certaines décisions
  `verified`/`rejected`. Il n’existe pas de tâche robuste d’expiration, purge,
  reprise ou notification KYC.
- La revue passe par des actions d’administration génériques, sans rôle KYC
  dédié, MFA, attribution, URL de consultation temporaire ou journal d’accès.
- Le middleware d’audit n’est pas activé de façon fiable pour les routes KYC
  actuelles ; les chemins de logs existants peuvent exposer des données
  personnelles.
- Les photos de profil utilisent actuellement un mécanisme de stockage public.
  Une simple garde API ne suffit donc pas : une URL déjà connue contournerait
  la règle « aucune photo d’autrui ».
- Le CORS permissif, l’absence de bucket KYC séparé et l’absence de politiques
  IAM/lifecycle spécifiques sont incompatibles avec des documents médicaux.

### 3.2 Fonctionnalités métier non encore protégées

La vérification n’est aujourd’hui qu’un attribut affiché ou un filtre
optionnel. Elle n’est pas une permission transverse.

- Matching, découverte, profils, photos, likes, historique, matchs,
  messagerie, appels et téléchargements média ne sont pas tous centralement
  filtrés par le KYC actif.
- Les utilitaires et webhooks Premium évaluent le paiement, mais pas une
  habilitation KYC indépendante et atomique.
- L’expiration ou une révocation n’invalident pas systématiquement les droits
  Premium effectifs, les caches et les URL de médias déjà délivrées.

### 3.3 Application Flutter

Le parcours actuel est intégré à `ProfileBloc` et enchaîne trois sélections
de fichiers, trois PUT vers URL signée et une soumission finale. Il manque :

- un domaine KYC typé, un état d’accès global et une garde de navigation ;
- consentement/version de politique, explication de confidentialité, aperçu,
  reprise, progression, annulation, retry et états complets de rejet/expiration ;
- capture native guidée, contrôle local de qualité, véritable rédaction
  destructive et nettoyage sécurisé des temporaires ;
- gestion des permissions/reprise après interruption et des notifications KYC ;
- protection contre capture d’écran, cache persistant, logs et diagnostics
  contenant des données KYC ;
- textes FR/EN cohérents et permissions Android/iOS explicitant l’usage KYC.

### 3.4 Documentation et conformité

Les documents de spécification se contredisent sur le caractère optionnel du
KYC, les endpoints, les tailles de fichiers, le chiffrement client et la
conservation. Les documents API historiques décrivent également des routes
multipart différentes de l’implémentation actuelle. Une source de vérité
versionnée est indispensable.

## 4. Architecture cible

### 4.1 Modèle de données et machine d’états

Conserver `Verification` comme projection courante compatible, et introduire :

- `KycAttempt` : tentative, propriétaire, version de consentement, dates,
  statut public et verrou d’activité ;
- `KycDocument` : type, clé opaque, hash, taille, MIME réel, état interne de
  scan et date de purge ;
- `KycUploadIntent` : propriétaire, type, contraintes de contenu, expiration,
  usage unique, clé d’idempotence et objet attendu ;
- `KycAuditEvent` : acteur, rôle, événement, horodatage, dossier et métadonnée
  technique minimale, sans pièce ni donnée médicale.

Les huit statuts publics restent : `not_started`, `pending_id`,
`pending_medical`, `pending_selfie`, `pending_review`, `verified`, `rejected`,
`expired`. Les états techniques de document (`issued`, `uploaded`, `scanning`,
`quarantined`, `accepted`, `purged`) ne sont pas exposés comme nouveaux
statuts métier.

Toutes les mutations utilisent transaction, verrou de ligne et clé
d’idempotence. Une tentative active est unique ; une transition illégale
renvoie `409`, une intention ou un défi expiré `410`, le quota `429`.

### 4.2 Contrat API canonique

Le contrat restera sous `/api/v1/user-profiles/me/verification/` afin de
limiter la rupture, mais sera versionné dans OpenAPI et dans
`docs/API_DOCUMENTATION.md`.

| Opération | Requête | Réponse sûre |
|---|---|---|
| `GET /` | aucune | statut, tentative, états sûrs des documents, dates, motif de refus normalisé ; jamais de chemin, URL ou fichier |
| `POST /start/` | version de consentement, confirmations | tentative, défi selfie, échéances ; aucune pièce |
| `POST /upload-intents/` | type, MIME, taille, SHA-256, clé d’idempotence | `upload_id`, URL PUT courte, en-têtes requis, expiration |
| `POST /submit/` | tentative, trois `upload_id`, code selfie, clé d’idempotence | `202 pending_review` ou erreur normalisée |
| `POST /internal/kyc/cases/{id}/decision/` | décision, motif normalisé, commentaire interne minimal | nouvelle projection et audit |

Les routes `generate-upload-url/` et `submit-documents/` ne doivent pas être
supprimées brutalement : elles sont dépréciées, renvoient un code d’erreur
documenté après la fenêtre de migration, puis sont retirées après adoption de
la version mobile minimale.

Les erreurs suivent une enveloppe unique et internationalisable :
`400` validation, `401` authentification, `403` permission KYC/rôle,
`409` état/idempotence, `410` expiration, `413` taille, `429` quota,
`503` stockage ou scanner indisponible. Aucun détail médical, chemin, URL ou
exception brute ne sort du serveur.

### 4.3 Permission transverse

Créer un service unique `has_active_kyc(user, now)` et une permission DRF
`HasActiveKycVerification`. L’utiliser dans chaque point d’entrée donnant un
accès à autrui ou créant un effet social : profils, photos, résolution de
médias, discovery, filtres, likes, super-likes, rewind, matchs, conversations,
messages, appels, WebSockets, médias de chat et Premium.

Le filtre doit s’appliquer aussi aux querysets et serializers afin de ne pas
laisser passer une information via un compteur, une prévisualisation, une
pagination, une notification ou une URL déjà résolue. La vérification doit
précéder toute autorisation Premium. Les actions de résiliation, support,
export et suppression demeurent explicitement ouvertes.

### 4.4 Stockage et traitement

- Créer un bucket KYC privé distinct, UBLA activé, CORS minimal pour PUT signé,
  IAM par service account et chiffrement KMS/CMEK.
- Employer des clés aléatoires non corrélables à l’utilisateur ; ne jamais
  rendre un objet public ni stocker une URL signée en base.
- Après upload direct, une tâche Celery vérifie propriété, objet, taille, hash,
  signature binaire, décodage, métadonnées, antivirus et quarantaine.
- N’accepter `pending_review` qu’après validation technique complète.
- Émettre les URL de lecture réviseur seulement après MFA, autorisation et
  audit ; durée courte configurée (cible : 5 minutes).
- Migrer les photos de profil vers stockage privé et les servir par URL courte
  après contrôle de la permission KYC du demandeur. Révoquer les caches et
  URL lors de perte de droit.
- Programmer scan, expiration, relance de purge et vérification de suppression
  avec retries idempotents ; une règle lifecycle est le filet de sécurité.

### 4.5 Revue humaine et notifications

Les réviseurs appliquent une grille explicite : document officiel lisible,
document médical daté de moins de 90 jours, défi visible dans le selfie et
cohérence visuelle humaine sans modèle biométrique. Un refus exige un motif
standardisé présentable à l’utilisateur ; l’éventuel commentaire interne est
restreint et court.

L’approbation, le refus, l’expiration et la révocation mettent à jour dans la
même transaction la projection utilisateur, les droits effectifs, les caches,
les notifications génériques et la purge à planifier. Les notifications
`verification_update` ne révèlent ni diagnostic, ni pièce, ni motif détaillé.

### 4.6 Application mobile cible

Créer un module KYC Clean Architecture (`KycRepository`, source distante,
entités, use cases, `KycBloc/Cubit`) distinct de `ProfileBloc`.

Le parcours est : information et consentement, identité, document médical avec
rappel des 90 jours, selfie avec défi et compte à rebours, revue, upload,
attente, décision, refus/expiration et nouvelle tentative. Chaque étape
présente progression, validation locale, aperçu, reprise, annulation et retry.

L’application :

- utilise une abstraction `KycCapturePort` avec implémentations natives ;
- effectue la rédaction de manière destructive sur une copie, sans modifier
  l’original utilisateur ;
- envoie les fichiers par flux avec timeout, progression et retry individuel ;
- n’ajoute aucun bearer token à l’URL signée et refuse HTTP/redirections ;
- nettoie mémoire, fichiers temporaires et caches KYC au changement d’état,
  passage en arrière-plan, fin de parcours ou déconnexion ;
- protège les écrans KYC des captures lorsque possible ;
- actualise l’état KYC au démarrage, au retour au premier plan et après
  notification ;
- intercepte `kyc_required` et redirige vers le parcours sans masquer une
  erreur de sécurité côté serveur.

## 5. Phases d’exécution et critères d’arrêt

Chaque phase est autonome. Après sa recette complète, l’exécutant s’arrête et
attend une instruction explicite `continue` avant d’entamer la suivante.

### Phase 0 — Gouvernance, légalité et contrat

1. Obtenir l’approbation juridique : finalités, bases légales, consentement,
   résidence, durée de conservation, droits, DPO et procédure d’incident.
2. Valider formellement la matrice d’habilitations ci-dessus et l’exception de
   résiliation/facturation.
3. Publier OpenAPI, statuts, erreurs, politique de dépréciation et versions
   mobile/backend minimales.
4. Mettre les politiques légales et textes FR/EN au même niveau.
5. Créer le feature flag et le plan de communication aux comptes existants.

**Sortie :** approbations écrites, contrat unique, aucun KYC activé en
production.

### Phase 1 — Socle backend d’état et d’habilitation

1. Ajouter modèles, contraintes, migrations réversibles et migration de
   projection sans faire confiance aux anciens chemins de documents.
2. Implémenter machine d’états, tentatives, quota, défis, transactions et
   idempotence.
3. Implémenter les nouveaux serializers/endpoints et les erreurs sûres.
4. Installer la permission transverse sur toutes les surfaces sociales et
   Premium, WebSockets compris.
5. Ajouter tests unitaires et contractuels d’état/permission.

**Sortie :** l’API refuse de façon exhaustive les droits sociaux/Premium sans
KYC actif, même depuis un ancien client.

### Phase 2 — Stockage, scan et photos privées

1. Déployer bucket KYC, KMS/CMEK, IAM, CORS, politiques lifecycle et
   configuration sans secret dans le dépôt.
2. Implémenter intentions, signatures contraintes, validation d’objet,
   quarantaine et tâches Celery idempotentes.
3. Implémenter purge, expiration et preuve d’exécution.
4. Privatiser et re-cléer les photos de profil ; copier, vérifier, basculer,
   invalider, puis supprimer les originaux selon runbook approuvé.

**Sortie :** aucun objet KYC ou photo d’autrui n’est public ni accessible sans
autorisation actuelle.

### Phase 3 — Revue interne et événements

1. Créer rôles, MFA, interface restreinte, attribution, décision atomique et
   motifs standardisés.
2. Ajouter URL réviseur brèves, audit d’accès et alertes d’anomalie.
3. Brancher notifications génériques, SLA et support.
4. Tester approbation, refus, révocation, expiration et purge consécutive.

**Sortie :** chaque consultation/décision est attribuée, journalisée et ne
laisse pas de fichier brut après le cycle autorisé.

### Phase 4 — Flutter, capture et expérience d’accès

1. Créer le domaine KYC et l’intégrer à l’injection, routes et état global.
2. Construire le parcours complet et les écrans de statut.
3. Ajouter capture native, qualité, rédaction, permissions, sécurité des
   temporaires, upload résilient et gestion de reprise.
4. Installer les gardes d’accès, purge de cache média et gestion de
   notifications/reprise.
5. Ajouter traductions, permissions mobiles, tests unitaires/widget et tests
   d’intégration.

**Sortie :** un compte non vérifié est convenablement guidé mais ne peut jamais
voir une photo d’autrui ni débuter un paiement Premium.

### Phase 5 — Migration et déploiement progressif

1. Inventorier les données historiques sans les requalifier automatiquement ;
   demander une nouvelle vérification lorsque leur intégrité/provenance n’est
   pas démontrable.
2. Mettre en quarantaine ou purger les fichiers hérités selon la politique et
   conserver un audit non sensible.
3. Déployer dans l’ordre infrastructure, backend, version mobile minimale,
   feature flag, cohortes puis généralisation.
4. Mesurer conversion, échecs techniques, délais de revue, refus, purge,
   accès refusés et tentatives de contournement.
5. Préparer rollback applicatif sans réexposer médias ou documents.

**Sortie :** déploiement généralisé, surveillance active et possibilité de
retour arrière sûre.

### Phase 6 — Recette finale et release gate

Exécuter et faire signer :

- tests unitaires, intégration et contrat backend ;
- attaques : chemin forgé, objet d’un autre utilisateur, rejeu d’URL, hash ou
  MIME falsifié, fichier malveillant, course concurrente, défi expiré,
  dépassement de quota et escalade de rôle ;
- matrice complète des endpoints/consommateurs, y compris WebSockets,
  téléchargements et webhooks Premium ;
- tests Celery de scan, expiration, purge, retry et suppression de compte ;
- tests Flutter de parcours, erreurs, cache, garde, notifications,
  permissions, accessibilité et FR/EN ;
- E2E Android/iOS de chaque statut KYC, décision humaine, perte de droit et
  preuve de purge ;
- vérification de configuration production : IAM, KMS, CORS, TLS, logs,
  alertes, sauvegardes et feature flag.

**Sortie :** feu vert produit, sécurité, juridique et exploitation ; aucune
anomalie bloquante ouverte.

## 6. Stratégie de données, migration et retour arrière

Les migrations de schéma sont additives et réversibles tant que les anciens
champs restent en lecture. La migration de données est exécutée par lots,
avec métriques, journal non sensible et possibilité de suspension. Les
références de fichiers KYC historiques ne sont jamais considérées comme une
preuve fiable : elles restent hors de la décision d’accès et déclenchent une
nouvelle vérification.

Le rollback désactive le feature flag et les nouveaux parcours sans restaurer
de bucket public, d’URL permanente ou de droit social non mérité. Les actions
irréversibles de purge ne démarrent qu’après la validation juridique et le
runbook approuvé.

## 7. Exigences de documentation livrable

À l’issue de l’implémentation, mettre à jour simultanément :

- `docs/API_DOCUMENTATION.md` et OpenAPI ;
- contrat frontend/backend et exemples de payloads/erreurs ;
- politique de confidentialité, CGU, consentements et textes FR/EN ;
- guide de revue interne, matrice de rôles et procédure d’incident ;
- runbooks KMS/IAM, scan, purge, reprise et rollback ;
- matrice de tests et résultats de recette.

Les anciennes pages qui décrivent des uploads multipart, du chiffrement client
par mot de passe ou un KYC optionnel doivent être explicitement marquées
obsolètes ; elles ne doivent jamais coexister comme contrats concurrents.

## 8. Validation du présent plan

Ce plan couvre explicitement : règles d’accès utilisateur, pièces et revue
manuelle, API, état, stockage KMS, photos de profil, migration, données de
santé, frontend, Premium, notifications, tâches asynchrones, tests et mise en
production. Il ne remplace pas la décision juridique : celle-ci est un gate
bloquant avant toute activation de production.
