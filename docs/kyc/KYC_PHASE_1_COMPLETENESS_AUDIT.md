# Audit de complétude — KYC phase 1

> Périmètre : socle backend d'état et d'habilitation uniquement. Aucune action
> des phases 2 à 6, aucune activation de production et aucune approbation
> juridique ou produit ne sont implicites dans ce document.

## Exigences vers preuves

| Exigence de phase 1 | Preuve de réalisation |
|---|---|
| Domaine, contraintes et projection non vérifiante | `KycAttempt`, `KycDocument`, `KycUploadIntent`, `KycAuditEvent`, migrations `0010` et `0011`. La projection lit seulement `Verification.user_id` et crée `not_started`; elle ne lit aucun chemin ni statut historique. |
| Source d'autorisation unique | `has_active_kyc(user, now)` exige exclusivement une tentative `verified` avec `expires_at > now`; `Verification` et les champs hérités sont seulement des projections. |
| États, défi, quota, transaction et idempotence | Verrous de ligne, contrainte d'une tentative ouverte, défi HMAC/hash à durée limitée et usage unique, quota des créations/réémissions, conflits d'idempotence sûrs. |
| API et erreurs sûres | `GET` de statut sans code, hash, URL, chemin ni objet; nouvelles routes `start`, `upload-intents`, `submit`; routes historiques bloquées en `410`. L'intention d'upload répond `503` tant que le stockage de phase 2 n'existe pas. |
| Habilitation transverse | Permission `HasActiveKycVerification` sur les 59 routes HTTP sociales/Premium montées, et contrôle à la connexion, réception et émission des deux WebSockets sociaux. |
| Premium effectif | `is_premium_user` exige le KYC actif. Un webhook peut enregistrer un paiement réussi, mais ne finalise pas l'entitlement tant que le KYC est inactif. |

## Changements vers exigences

| Changement | Exigence couverte |
|---|---|
| Modèles, migrations et `profiles/kyc.py` | 1 et 2 |
| Serializers, vues, routes et contrat OpenAPI | 3 |
| Routes profiles, matching, messaging, calls, notifications, feed et subscriptions; consumers WebSocket | 4 |
| Tests KYC, WebSocket, routes et paiement | 5 |

## Validation indépendante et non destructive

- `python manage.py test ... --settings=hivmeet_backend.test_settings --keepdb` : 40 tests réussis, y compris les 59 résolutions de routes, les refus `403 kyc_required`, les deux WebSockets, les anciennes routes `410` et le webhook Premium sans KYC.
- `python manage.py makemigrations profiles --check --dry-run` : aucune migration manquante.
- `python manage.py migrate profiles 0011 --plan` : plan inspecté uniquement; aucune migration appliquée.
- `python manage.py check`, compilation ciblée, analyse YAML OpenAPI et `git diff --check` : réussis.

## Impact et gates

- Backend : les anciens clients reçoivent désormais `403 kyc_required` sur les
  droits sociaux/Premium et `410 kyc_legacy_endpoint_deprecated` sur les deux
  anciennes routes de documents. Les informations Premium, reçus et
  résiliation restent ouvertes conformément à la matrice.
- Frontend : aucun fichier du dépôt Flutter canonique n'a été modifié. Son
  adaptation est explicitement une phase 4; toute intervention future devra
  commencer par son routeur/orchestrateur. Les appels sociaux et Premium
  existants doivent gérer `kyc_required`.
- Gate juridique/DPO : validation écrite de finalité, base légale,
  conservation, résidence, textes FR/EN et procédure d'incident avant toute
  activation de production.
- Gate phase 2 : bucket privé KMS/CMEK, IAM/CORS, URLs courtes, validation
  d'objet, scan/quarantaine, purge et privatisation des photos. Une URL de
  photo publique déjà connue reste hors de portée de la seule garde API et
  interdit toute prétention de conformité de production avant cette phase.
- Gate phase 3 : revue humaine interne, rôles/MFA, décision atomique et audit
  de consultation. Aucune biométrie automatisée ni fournisseur KYC externe
  n'est introduit.
