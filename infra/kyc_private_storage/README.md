# Infrastructure privée KYC et photos

Ce module Terraform crée deux buckets distincts, privés et à UBLA : un pour
les documents KYC et un pour les photos de profil. Il ne contient aucun secret
et ne doit pas être appliqué avant les gates Juridique/DPO, sécurité et
plateforme de phase 0.

Préconditions obligatoires :

- clés CMEK créées, rotation et droits KMS vérifiés pour le compte runtime ;
- agent de service Cloud Storage limité aux deux clés CMEK et compte runtime
  autorisé à signer les PUT V4 KYC par workload identity, sans clé JSON
  persistante ; les photos de profil sont lues uniquement via l'API ;
- durée de rétention KYC approuvée par écrit ; les photos de profil actives ne
  reçoivent pas de suppression lifecycle basée seulement sur leur âge ;
- origines mobile/web exactes, sans joker CORS ;
- service account runtime avec signature V4, aucun binding public et aucun
  autre principal doté d'un accès objet, y compris par héritage ;
- plan Terraform relu et sauvegarde/runbook de migration validés.

Après `terraform apply` en environnement autorisé, exécuter :

```powershell
python manage.py verify_private_storage --scope all
```

Puis définir seulement les identifiants de ressource dans l’environnement,
dont `PRIVATE_STORAGE_RUNTIME_SERVICE_ACCOUNT`, qui doit être identique à
`runtime_service_account` du module Terraform. Cette identité est vérifiée
dans le binding `roles/storage.objectAdmin`; elle n'est jamais une clé de
service.

`verify_private_storage` inspecte la politique attachée au bucket. Il ne peut
pas prouver les droits hérités projet/dossier/organisation : avant l'activation,
Plateforme/Sécurité doit donc produire une revue d'IAM effective (par exemple
Cloud Asset Inventory ou Policy Analyzer) confirmant qu'aucun autre principal
ne peut lire, écrire, lister ou administrer les objets. Les éléments de preuve
ne doivent contenir ni nom d'objet, ni URL signée, ni donnée KYC.

Déployer workers/beat, effectuer une cohorte de migration de photos et vérifier
que les lignes `migration_copied` et `legacy_public` sont à zéro avant toute
généralisation. Ne jamais placer de clé de service, URL signée ou document dans
Terraform state, logs, tickets ou exports.
