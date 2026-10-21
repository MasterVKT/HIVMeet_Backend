# KYC phase 3 — revue humaine interne

> Statut : implémentation backend locale. Elle ne constitue pas une
> autorisation de collecte ou de revue réelle en production.

## Transport local simplifie

En developpement ou test, `KYC_STORAGE_BACKEND=local` utilise le transport
`backend_multipart` : le client envoie le champ `file` a la route KYC
authentifiee, le serveur compare taille et SHA-256 a l'intention emise, puis
range le fichier sous `PRIVATE_STORAGE_LOCAL_ROOT`, hors de `MEDIA_ROOT`.
Il n'y a ni bucket Cloud, ni CORS de bucket, ni URL signee dans ce parcours.
Les documents de recette restent synthetiques et la revue manuelle conserve
les seules decisions `verified`, `rejected` et `revoked`.

Sur un hote Windows, la recette avec un vrai worker Celery Redis doit utiliser
`python -m celery -A hivmeet_backend worker --pool=solo`; le pool prefork est
reserve aux environnements POSIX, dont le conteneur Docker Linux.

## Garanties

- Les seuls rôles sont les groupes Django explicites `kyc_reviewer` et
  `kyc_supervisor`, créés par la migration `0014`. Aucun rôle applicatif
  général ni superutilisateur ne donne un accès implicite aux dossiers.
- Toute route `/api/v1/internal/kyc/` exige une session authentifiée, un rôle
  KYC et une assertion MFA TOTP hachée de cinq minutes. Le bootstrap TOTP est
  volontairement limité à `DEBUG` ou aux tests ; hors de ce cadre, une clé de
  chiffrement de revue explicite est requise et l'accès échoue fermé.
- Un superviseur attribue explicitement un dossier `pending_review` à un
  réviseur et à son propre périmètre. Le réviseur, comme le superviseur, ne
  consulte ou ne décide que les dossiers qui lui sont attribués.
- Les décisions `verified`, `rejected` et `revoked` utilisent des motifs
  standardisés. Elles sont transactionnelles, idempotentes, ferment
  l'attribution, mettent à jour la projection historique, programment la
  purge immédiate des objets bruts et créent une notification générique.
- Le commentaire optionnel est chiffré, n'est jamais renvoyé par l'API,
  l'audit, les exports, les notifications ou les logs. Les journaux d'audit
  ne contiennent que l'acteur, son rôle, l'événement et un code sûr.
- L'accès à un document techniquement accepté émet une URL GET courte
  (cible : cinq minutes), non persistée et avec réponse HTTP `no-store`.
  Aucun chemin, objet, URL ou détail médical ne figure dans la liste de cas.
- En développement/test exclusivement, une route de lecture directe permet la
  revue de fixtures en mémoire après les mêmes contrôles MFA et d'attribution.
  Elle est refusée hors de ce mode et ne doit jamais recevoir de pièce réelle.
- Une tâche SLA alerte les superviseurs avec un message générique lorsque des
  dossiers dépassent le délai configuré, sans inclure de compte, pièce ou
  détail médical.
- Une seconde tâche détecte un volume exceptionnel de consultations de pièces
  dans une fenêtre configurée. Sa déduplication est transactionnelle ; les
  notifications et l'audit ne contiennent qu'une catégorie technique sûre,
  jamais le dossier, la pièce, l'URL, le compte ou une donnée médicale.

## Limites et gates

Les assertions MFA locales, le stockage mémoire et le scanner de test ne sont
utilisables qu'avec des fixtures synthétiques. Une revue réelle reste bloquée
par l'intégration MFA d'entreprise, la clé de chiffrement gérée, les rôles
opérationnels, la formation des réviseurs et les validations Juridique/DPO et
Sécurité. Il n'y a ni biométrie automatisée ni fournisseur KYC externe.

L'application ne possède pas encore de ticketing Support dédié. Le raccordement
de phase 3 est donc la notification générique `verification_update` : il peut
être consommé par le parcours d'assistance de phase 4, sans jamais transmettre
une pièce par e-mail, chat ou support. La procédure et le canal Support réels
restent un gate Produit/Support avant toute revue de personnes réelles.
