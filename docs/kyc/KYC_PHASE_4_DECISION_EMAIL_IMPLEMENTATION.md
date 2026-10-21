# KYC phase 4 - notification e-mail de decision

## Flux

La decision humaine KYC reste l'unique origine de la transition. Dans la meme
transaction, le backend ecrit la decision, la tentative, la projection
historique, les droits associes, la notification interne `verification_update`
et un unique `KycDecisionEmailDelivery`.

Une fois la transaction validee, la tache Celery
`send_kyc_decision_email` relit le compte, confirme que Firebase porte encore
la meme adresse validee, puis envoie un e-mail SMTP bilingue et neutre. La table
de livraison ne contient aucune adresse e-mail, piece, motif, commentaire ou
resultat KYC. Les tentatives, les etats et les codes d'erreur generiques sont
les seuls elements persistants.

## Fiabilite

- Rejouer la decision avec la meme cle d'idempotence retourne la decision
  existante sans creer de seconde livraison.
- Les pannes SMTP transitoires suivent un backoff borne et restent dans l'etat
  `retrying`; une tache Beat recupere aussi les tentatives dues ou interrompues.
- Les e-mails refuses de facon permanente deviennent `failed`; une adresse
  absente, desactivee ou non validee devient `suppressed`. Aucun de ces etats
  ne modifie la decision ou les droits KYC deja enregistres.
- Le message SMTP utilise un `Message-ID` opaque stable pour aider les relais
  SMTP qui dedoublonnent les reprises apres une interruption de worker.
- L'administration Django expose les etats de livraison en lecture seule, sans
  adresse de destinataire, motif, commentaire ni contenu KYC, afin de reperer
  les lignes `failed` durables.

## Configuration et exploitation

En production, `HIVMEET_DEPLOYMENT_ENVIRONMENT=production` exige le backend
Django SMTP et `EMAIL_HOST`. Configurer `EMAIL_HOST`, `EMAIL_PORT`,
`EMAIL_USE_TLS` ou `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
`EMAIL_TIMEOUT` et `DEFAULT_FROM_EMAIL` hors du depot. Le backend console ne
constitue pas une livraison et reste reserve au developpement local.

Le `docker-compose` de developpement utilise Mailpit, expose seulement sur
`127.0.0.1`, comme boite SMTP de recette. Il permet de verifier le protocole
SMTP et le contenu neutre sans contacter de fournisseur externe ni une boite
reelle. Le parcours KYC local reste un envoi multipart prive vers le backend;
il ne depend d'aucun stockage Cloud.

La migration `0016_kycdecisionemaildelivery` est additive et reversible via
`python manage.py migrate profiles 0015`. Avant un retour arriere, laisser les
decisions existantes intactes; la suppression de leurs lignes de livraison ne
modifie pas les droits KYC.
