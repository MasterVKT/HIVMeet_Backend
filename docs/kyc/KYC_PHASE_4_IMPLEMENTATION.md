# KYC phase 4 — parcours mobile et intégration développement

> Statut : implémentation technique de développement. Elle ne constitue pas
> une autorisation de collecte réelle, de revue réelle ni d’activation KYC en
> production.

## Portée

Le client Flutter consomme exclusivement le contrat utilisateur KYC v1 :

- lecture du statut ;
- création/reprise d’une tentative avec consentement explicite ;
- intentions d’upload, PUT direct, confirmation et soumission ;
- réception de l’état sûr et de la notification générique
  `verification_update` ;
- affichage des états non commencé, incomplet, en revue, vérifié, refusé et
  expiré.

La revue demeure strictement humaine et interne : le mobile ne consomme jamais
les routes `/api/v1/internal/kyc/`.

## Garanties client

- Un statut inconnu, expiré, refusé ou en échec de rafraîchissement est
  restrictif. Les routes sociales, profils d’autrui, likes, matchs,
  conversations, notifications sociales, feed et Premium redirigent vers le
  parcours de vérification. Le backend reste l’autorité finale.
- L’upload direct n’emploie aucun bearer token, exige HTTPS, refuse les
  redirections et ne transmet que les en-têtes signés `Content-Type` et
  `Content-Length`. L’URL temporaire ne figure ni dans les logs, ni dans les
  propriétés comparables de l’état UI.
- Les captures sont copiées dans un répertoire temporaire réservé, puis
  effacées après envoi, abandon, arrière-plan ou déconnexion. Les caches
  d’images sont purgés lorsqu’un droit KYC actif est perdu.
- Android active `FLAG_SECURE` pendant l’écran KYC. iOS obscurcit l’écran au
  changement de cycle de vie ; les deux plateformes effacent le brouillon.
- Pour les pièces identité et médicale, Android emploie le scanner de document
  ML Kit local (cadrage/recadrage) et iOS utilise Vision pour détecter un
  rectangle de document. Aucun visage n’est détecté, comparé ou envoyé : le
  selfie reste un défi à usage unique destiné à une revue humaine.
- Les textes du flux sont présents en français et en anglais. Les erreurs sont
  mappées vers des clés sûres sans détail médical, code de défi, chemin,
  document ou URL.

## Limite volontaire de la simulation locale

`KYC_STORAGE_BACKEND=memory` émet une URL `https://uploads.invalid/...` non
routable. Cette valeur est délibérée : elle permet les tests backend
hermétiques avec des fixtures synthétiques, sans créer d’endpoint local qui
recevrait des preuves KYC sur HTTP, avec un bearer, ou dans un stockage public.

Conséquence : les tests Flutter couvrent la machine d’état et les tests Django
injectent des octets synthétiques directement dans l’adaptateur mémoire ; un
PUT réel depuis un téléphone ne doit pas être présenté comme validé dans ce
mode.

Pour une recette mobile de bout en bout, le propriétaire Plateforme doit
fournir un environnement de développement isolé avec URL HTTPS de confiance,
stockage privé distinct, CORS PUT minimal et URL PUT courte. Les objets doivent
rester synthétiques. Ce n’est ni une activation production ni une autorisation
de traiter des documents réels.

## Gates hors développement

Avant tout usage réel, les gates juridique/DPO, sécurité/plateforme, IAM/CMEK,
antivirus, MFA des réviseurs, procédures Support et formation définis par les
phases 0 à 3 restent obligatoires. Aucun flag, code mobile ou configuration de
cette phase ne les contourne.
