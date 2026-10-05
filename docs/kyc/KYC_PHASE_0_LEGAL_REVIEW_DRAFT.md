# KYC phase 0 — brouillon de revue juridique et textes FR/EN

> Brouillon interne à soumettre. Les textes ne sont ni approuvés, ni publiés,
> ni réputés suffisants dans une juridiction donnée.

## Dossier de validation

| Sujet | Décision attendue | Statut |
|---|---|---|
| Finalités exactes et nécessité/proportionnalité | Texte validé | En attente |
| Bases légales, données de santé et consentement | Qualification par juridiction | En attente |
| Mineurs, capacité à consentir et populations vulnérables | Règle d'éligibilité | En attente |
| Résidence, hébergement et transferts | Liste des juridictions et garanties | En attente |
| Sous-traitants, KMS/CMEK et accès réviseurs | Contrats et privilège minimal | En attente |
| Brouillons, objets, sauvegardes, décisions, audit et purge | Barème par catégorie et déclencheur | En attente |
| Accès, rectification, effacement, opposition, export et recours | Procédure et délais | En attente |
| Revue humaine, MFA, formation, confidentialité et incident | Procédure opérationnelle | En attente |
| Langues, accessibilité et version du consentement | Textes finaux FR/EN | En attente |

La décision écrite doit nommer signataire, juridiction, version des textes,
date, limites et conditions. Un accord produit ou technique ne remplace pas
l'avis Juridique/DPO.

## Écran d'information proposé — FR

### Vérification d'identité et de sécurité

Pour accéder aux fonctionnalités sociales et aux avantages Premium effectifs,
HIVMeet prévoit de demander une pièce d'identité officielle, un document
médical ou sérologique daté de moins de 90 jours et un selfie montrant un défi
temporaire à usage unique.

Votre dossier est examiné par une équipe interne habilitée. HIVMeet ne prévoit
ni comparaison biométrique automatisée, ni création de modèle facial, ni
fournisseur KYC externe.

Les documents ne doivent pas être envoyés par e-mail, chat ou support. Ne
partagez jamais votre code de défi, un lien de téléversement ou une copie de
vos documents. Les durées de conservation, vos droits, le contact DPO et la
procédure d'incident seront affichés après validation juridique.

### Consentement proposé — FR

Je confirme avoir lu l'information de confidentialité KYC, compris que mon
dossier sera soumis à une revue humaine interne et compris les effets d'un KYC
inactif sur l'accès social et Premium.

Je demande le traitement de la pièce d'identité, du document médical ou
sérologique récent et du selfie avec défi nécessaires à cette vérification,
dans les limites des informations de confidentialité validées.

Cases distinctes à valider :

- Je confirme que la pièce transmise est une pièce d'identité officielle.
- Je confirme que le document médical ou sérologique date de moins de 90 jours.
- Je comprends que le défi selfie est personnel, temporaire et à usage unique.
- Je confirme avoir été informé de mes droits et du contact Support/DPO.

## Information screen draft — EN

### Identity and safety verification

To access social features and effective Premium benefits, HIVMeet plans to
request an official identity document, a medical or serological document dated
within the last 90 days, and a selfie showing a temporary single-use challenge.

Your case is reviewed by authorised internal staff. HIVMeet does not plan to
use automated biometric comparison, create a facial template, or use an
external KYC provider.

Documents must not be sent by email, chat, or support. Never share your
challenge code, an upload link, or copies of your documents. Retention periods,
your rights, DPO contact, and the incident procedure will be displayed after
legal validation.

### Proposed consent — EN

I confirm that I have read the KYC privacy information, understand that my
case will receive internal human review, and understand how inactive KYC
affects access to social and Premium features.

I request processing of the identity document, recent medical or serological
document, and challenge selfie required for this verification, within the
limits of the approved privacy information.

Separate checkboxes to validate:

- I confirm that the submitted identity document is an official identity document.
- I confirm that the medical or serological document is less than 90 days old.
- I understand that the selfie challenge is personal, temporary, and single-use.
- I confirm that I have been informed of my rights and how to contact Support/DPO.

## Messages sûrs proposés

| Situation | FR | EN |
|---|---|---|
| KYC requis | La vérification est requise pour accéder à cette fonctionnalité. | Verification is required to access this feature. |
| Dossier en revue | Votre dossier est en cours de revue. | Your case is under review. |
| Décision | Une mise à jour de vérification est disponible dans l'application. | A verification update is available in the app. |
| Expiration | Votre vérification a expiré. Reprenez le parcours pour retrouver l'accès. | Your verification has expired. Restart the flow to regain access. |
| Refus | Votre dossier ne peut pas être validé dans son état actuel. Consultez l'application pour connaître les prochaines étapes. | Your case cannot be validated in its current state. See the app for next steps. |

Les messages n'incluent aucun diagnostic, détail de pièce, code, URL signée,
chemin de stockage ou e-mail complet. Les motifs visibles sont normalisés et
validés séparément ; les commentaires internes restent hors notifications et
exports.

## Condition juridique de sortie

La revue est achevée seulement lorsque les textes finaux FR/EN, la version du
consentement et les durées/conditions de conservation sont approuvés par écrit.
Sans eux, le flag de production reste désactivé et aucun KYC ne peut être
activé en production.
