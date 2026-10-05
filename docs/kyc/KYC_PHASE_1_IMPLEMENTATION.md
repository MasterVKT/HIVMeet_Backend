# KYC phase 1 — socle backend d'état et d'habilitation

> Statut : implémentation backend de phase 1. Les phases de stockage privé,
> scan, revue interne, notifications et Flutter ne sont pas engagées ici.
> L'activation KYC de production reste bloquée par la validation Juridique/DPO.

## État livré

- La source d'autorisation sociale est uniquement KycAttempt avec statut
  verified et expires_at strictement futur.
- Verification et les champs User de vérification restent des projections de
  compatibilité ; aucun ancien chemin de document ni ancien statut n'ouvre un
  droit social.
- Une tentative ouverte est unique par utilisateur. Les mutations utilisent
  transaction, verrou de ligne et clé d'idempotence.
- Le défi selfie est borné à 30 minutes, à usage unique, dérivé côté serveur
  et vérifié par hash. Sa valeur claire n'est pas persistée.
- Les nouvelles routes retournent seulement des états sûrs. Les anciennes
  routes qui acceptaient un chemin client sont bloquées par une réponse 410.
- Les intentions d'upload valident les contraintes mais retournent une réponse
  503 tant que la phase 2 n'a pas livré bucket privé, URL courte et validation
  d'objet. Aucun stockage KYC de repli n'est utilisé.
- Les routes sociales, les mutations Premium, les notifications, le feed et
  les WebSockets vérifient le KYC actif. Les lectures Premium, reçus et la
  résiliation restent ouvertes selon la matrice de phase 0.

Un webhook de paiement peut consigner un paiement réussi, mais ne peut pas
finaliser l'entitlement Premium tant que `has_active_kyc` est faux. Le
rapprochement ultérieur ne peut finaliser cet entitlement qu'après la même
vérification.

## Migrations et intégrité

| Migration | Type | Effet | Risque et contrôle |
|---|---|---|---|
| 0010_kycattempt_kycauditevent_kycdocument_kycuploadintent_and_more | Schéma additif | Tables KYC, index et contraintes d'unicité | Aucune colonne existante modifiée. Vérifier le plan de migration avant déploiement et appliquer hors transaction longue si le SGBD l'exige. |
| 0011_create_legacy_kyc_reverification_attempts | Données, idempotent | Une tentative not_started d'origine legacy_projection par projection Verification existante | Ne lit ni chemin ni contenu historique ; n'accorde jamais verified. La contrainte d'une tentative ouverte évite les doublons. |

Rollback contrôlé :

1. Désactiver les nouveaux appels clients et garder les routes historiques
   bloquées, car leur réactivation réexposerait le chemin client non fiable.
2. Revenir 0011 supprime uniquement les tentatives legacy_projection intactes.
3. Revenir 0010 retire les tables KYC seulement après confirmation qu'aucune
   tentative utilisateur n'a été créée. Sinon restaurer depuis sauvegarde et
   suivre un runbook approuvé ; aucune suppression automatique de données KYC.
4. Le rollback ne redonne jamais un accès social/Premium en se fondant sur
   Verification, User.is_verified ou un document historique.

## Surfaces protégées

La permission DRF HasActiveKycVerification est déclarée dans les routes de
profil d'autrui, discovery/filtres/interactions/historique, matchs,
conversations/messages/médias/appels, notifications, feed, likes reçus et
mutations Premium. Les deux consumers WebSocket réévaluent aussi cette
condition à la connexion, à chaque message reçu et avant l'envoi d'un payload.

La phase 2 reste nécessaire pour empêcher une URL de média public déjà connue
d'être consommée hors API. Cette limitation est volontairement visible et ne
doit pas être considérée comme une autorisation de production.
