# Audit de complétude — KYC phase 3

## Périmètre et limite

Cette livraison fournit exclusivement le backend de simulation de la revue
humaine interne. Elle ne constitue pas une autorisation de traiter des pièces
réelles ni d'activer le KYC en production. Les fixtures sont synthétiques et
la lecture directe n'existe qu'avec `DEBUG`/`TESTING` et le stockage `memory`.

## Exigences → preuves

| Exigence de phase 3 | Preuve de code et test | Gate hors développement |
|---|---|---|
| Rôles, MFA, interface restreinte et attribution | Groupes explicites `kyc_reviewer`/`kyc_supervisor`, appareil TOTP chiffré, assertion hachée de cinq minutes, `KycReviewAssignment`, routes `/api/v1/internal/kyc/`. Les tests refusent un non-authentifié, un acteur sans MFA et un acteur hors périmètre. | SSO/MFA d'entreprise, provisionnement IAM et formation des opérateurs. |
| Décision humaine atomique et motifs standardisés | `KycReviewDecision`, transaction, HMAC d'idempotence, motifs contraints ; synchronisation de la projection historique et notification utilisateur générique. Le statut public sûr rend le code de refus, jamais le commentaire interne. | Validation Produit/Juridique de la grille de motifs et de la procédure de recours. |
| Consultation brève, attribution et audit | URL GET V4 temporaire pour le stockage cible ; audit d'attribution, lecture et décision sans URL, clé, contenu ou commentaire. En mémoire, l'URL est une valeur factice sans clé et une route séparée permet seulement les fixtures synthétiques. | Bucket réel privé, CMEK/KMS, IAM et vérification opérationnelle. |
| Alertes d'anomalie | Tâche périodique de volume de consultations, dédupliquée par contrainte de base ; notification et audit limités à une catégorie générique. | Seuils, astreinte et traitement d'incident approuvés. |
| Notification, SLA, support et purge | `verification_update`, alerte SLA générique, planification immédiate de purge après décision ; les tests exécutent la purge de fixture après révocation. Aucun ticketing Support n'existe encore : l'événement générique est le raccordement sûr pour le parcours client ultérieur. | Canal Support, procédure d'incident et contenus validés par Produit/Support/Juridique. |
| Approbation, refus, révocation, expiration et purge | `profiles.tests.test_kyc_phase3` couvre ces chemins, dont le passage `verified`, le code de refus, `revoked` → purge, et l'expiration. | Recette avec opérateurs habilités uniquement après les gates précédents. |

## Changements → exigences

| Changement | Exigence satisfaite |
|---|---|
| `profiles/models.py`, migrations `0014` et `0015` | Persistance additive des appareils MFA, assertions, attributions, décisions et déduplication d'alerte. |
| `profiles/kyc_review.py`, `profiles/private_storage.py` | Autorisation par rôle/MFA/attribution, chiffrement de commentaire, décision atomique, URL réviseur et simulation mémoire strictement bornée. |
| `profiles/views.py`, `profiles/urls_kyc_review.py`, `hivmeet_backend/api_urls.py`, serializers | Interface interne fermée, réponses `no-store`, données de file minimisées et contrat de décision. |
| `profiles/tasks.py`, `hivmeet_backend/celery.py`, `hivmeet_backend/settings.py`, `env.example` | SLA, anomalie, valeurs de développement sûres et planification Celery. |
| `docs/API_DOCUMENTATION.md`, `docs/kyc/KYC_PHASE_3_IMPLEMENTATION.md`, contrat OpenAPI | Contrat interne, limites de développement et gates explicités. |
| `profiles/tests/test_kyc_phase3.py` | Preuves indépendantes de permissions, décisions, purge, expiration, simulation et alertes. |

## Impact backend / frontend

- Backend : deux migrations additives et des routes internes séparées sont
  ajoutées. Le contrat KYC utilisateur v1 conserve ses statuts et expose déjà
  le motif de refus normalisé via l'état sûr.
- Frontend : aucun fichier Flutter n'a été modifié. Le client n'appelle pas les
  routes internes ; la consommation du statut, de `verification_update` et le
  parcours utilisateur restent volontairement en phase 4.

## Validation indépendante

- `HIVMEET_TEST_DB_NAME=hivmeet_kyc_phase3_validation_20261005_l python manage.py test profiles.tests.test_kyc_phase3 profiles.tests.test_kyc_phase1 profiles.tests.test_kyc_phase2 profiles.tests.test_location_and_photos --settings=hivmeet_backend.test_settings` : **66 tests réussis** sur une base PostgreSQL isolée puis détruite.
- Sous environnement de développement temporaire avec SQLite mémoire :
  `python manage.py check` et `python manage.py makemigrations profiles --check --dry-run` : réussis, aucune migration manquante.
- `python manage.py sqlmigrate profiles 0014_kycreviewassignment_kycreviewdecision_and_more` et `python manage.py sqlmigrate profiles 0015_kycreviewanomalyalert` : SQL PostgreSQL généré sans erreur.
- `python -m compileall -q profiles hivmeet_backend` et `git diff --check` : réussis.
- Limite connue : une tentative de migration complète en SQLite mémoire échoue
  avant la phase 3 sur l'incompatibilité préexistante de
  `profiles.0001_initial` avec SQLite (`near "[3]"`). Elle n'a modifié aucune
  base persistante et ne remet pas en cause la validation PostgreSQL des tests
  ni la génération SQL de 0014/0015. Une application réelle des migrations
  sur une base PostgreSQL jetable reste une vérification de release, pas une
  activation de production.
