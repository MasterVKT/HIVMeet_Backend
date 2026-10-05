# My-CoolPay — recette du parcours hébergé HIVMeet

Ce document décrit la configuration externe nécessaire au code de paiement.
Les valeurs secrètes ne doivent jamais être ajoutées à Git, aux réponses API,
aux journaux ou à l'application Flutter.

Vérification documentaire effectuée le 16 septembre 2026 sur le
[workspace officiel My-CoolPay](https://www.postman.com/my-coolpay/my-coolpay-workspace/collection/q45oyma/my-coolpay-api-docs),
sa section
[Sandbox](https://www.postman.com/my-coolpay/my-coolpay-workspace/folder/84yotbg/8-sandbox-testing)
et sa documentation de
[callback](https://www.postman.com/my-coolpay/my-coolpay-workspace/folder/uj9qj2n/6-callback-handling-webhook).
La collection officielle affiche encore une dernière édition au 28 juillet
2022 : il faut donc revalider auprès du support tout identifiant de test et
toute adresse IP avant une homologation, même si les pages ont été relues à la
date ci-dessus.

## 0. Ce que la sandbox permet réellement

My-CoolPay n'expose pas de domaine `sandbox` distinct : le Paylink et
`checkStatus` utilisent toujours `https://my-coolpay.com/api`, l'environnement
étant déterminé par l'application et sa clé publique.

La sandbox publique partagée suffit pour :

- vérifier le payload et la création d'un Paylink hébergé ;
- ouvrir la page de paiement sans intégrer de secret dans Flutter ;
- relire un statut avec `GET /api/{public_key}/checkStatus/{transaction_ref}` ;
- vérifier côté HIVMeet qu'un état non terminal ou un échec n'accorde aucun
  droit Premium.

Elle ne suffit pas pour une recette complète : sa clé privée est masquée, ses
URL de retour/callback n'appartiennent pas à HIVMeet et la documentation ne
publie aucun portefeuille approvisionné ni jeu de numéros garantissant les
états `SUCCESS`, `CANCELED` et `FAILED`. Le numéro figurant dans l'exemple
Paylink est une donnée d'exemple, pas un scénario de succès contractuel ; lors
de la recette HIVMeet il a correctement produit un échec pour solde
insuffisant.

Le projet de référence `trading_platform` ne lève pas cette limite : il
reproduit correctement la création du Paylink avec la clé publique partagée,
mais ne vérifie ni callback signé ni `checkStatus` avant son ancienne route
d'activation. Cette route ne doit jamais être copiée.

Pour tester les quatre issues de bout en bout, demander au support My-CoolPay
(`support@my-coolpay.com`, WhatsApp `+237 654 197 288`, coordonnées publiées
dans la collection officielle) :

1. une application marchande dédiée aux essais, explicitement sans encaissement
   réel ;
2. sa clé publique et sa clé privée, transmises hors Git ;
3. les moyens de paiement, devises et scénarios de test activés ;
4. un compte/numéro de test approvisionné ou les valeurs déterministes donnant
   `SUCCESS`, `CANCELED`, `FAILED` et `PENDING` ;
5. l'IP source actuelle des callbacks et la confirmation que les quatre URL
   HTTPS HIVMeet sont enregistrées.

Sans confirmation explicite de ces cinq points, la recette publique reste une
preuve de Paylink et de non-activation sur échec, pas une preuve de paiement
réussi.

## 1. Variables du backend HTTPS

Configurer dans le gestionnaire de secrets de l'environnement de recette :

```dotenv
MYCOOLPAY_PUBLIC_KEY=<public-key-test-merchant>
MYCOOLPAY_PRIVATE_KEY=<private-key-test-merchant>
MYCOOLPAY_BASE_URL=https://my-coolpay.com/api
MYCOOLPAY_CALLBACK_URL=https://<backend-https>/api/v1/webhooks/payments/mycoolpay/
MYCOOLPAY_SUCCESS_URL=https://<backend-https>/api/v1/subscriptions/payment-return/success/
MYCOOLPAY_CANCEL_URL=https://<backend-https>/api/v1/subscriptions/payment-return/cancel/
MYCOOLPAY_FAILURE_URL=https://<backend-https>/api/v1/subscriptions/payment-return/failure/
MYCOOLPAY_CALLBACK_ALLOWED_IPS=15.236.140.89
MYCOOLPAY_TRUSTED_PROXY_IPS=<ip-du-reverse-proxy-si-présent>
MYCOOLPAY_PAYMENT_HOSTS=my-coolpay.com
MYCOOLPAY_ALLOWED_OPERATORS=MCP,CM_MOMO,CM_OM,CARD
MYCOOLPAY_ENABLED_CURRENCIES=XAF,EUR
MYCOOLPAY_DEFAULT_CURRENCY=XAF
```

Les quatre URL doivent être HTTPS, sans query string ni fragment, et avoir
exactement les chemins indiqués. `MYCOOLPAY_TRUSTED_PROXY_IPS` ne contient que
les proxies contrôlés par HIVMeet ; sans cette liste, `X-Forwarded-For` est
ignoré. Adapter l'IP callback seulement à partir d'une communication officielle
du fournisseur.

## 2. Tableau de bord de l'application marchande de test

Enregistrer les quatre URL ci-dessus dans les champs callback, succès,
annulation et échec de l'application de test. La clé privée reste uniquement
dans les secrets backend. Redémarrer Gunicorn, Celery worker et Celery Beat
après injection des variables.

La création de l'application suit les prérequis officiels : nom, page
d'accueil, logo HTTPS, trois URL de redirection, URL de callback et adresse de
notification. My-CoolPay annonce une validation automatique dans les 24 heures.
Ne lancer la recette qu'après validation effective et apparition des deux clés
dans le tableau de bord.

Le backend refuse les achats tant que l'ensemble de cette configuration n'est
pas sûr. La vérification non sensible se fait avec :

```http
GET /api/v1/subscriptions/payment-capabilities/
Authorization: Bearer <jwt-test>
```

La recette ne commence que si `available` et
`callback_verification_available` valent `true`.

## 3. Contrat de retour et de confirmation

Les pages HTTPS renvoient un `302` vers l'un des liens suivants :

```text
hivmeet://payment/result?status=success
hivmeet://payment/result?status=cancelled
hivmeet://payment/result?status=failed
```

Ces liens ne contiennent aucun identifiant et ne confirment jamais un paiement.
Flutter restaure le `payment_id` chiffré localement puis interroge l'endpoint
authentifié `GET /api/v1/subscriptions/payments/{payment_id}/`. Seul
`payment_status=succeeded` avec `fulfilled=true` est un succès.

Chaque appui sur Acheter utilise un header `Idempotency-Key`. Un retry après
perte réseau reprend la même clé et la même transaction. La tâche Celery Beat
`reconcile_pending_mycoolpay_payments` récupère les callbacks perdus via
`checkStatus`; elle ne journalise que l'UUID local de corrélation.

## 4. Vérifications avant recette mobile

```powershell
$env:DJANGO_SETTINGS_MODULE='hivmeet_backend.test_settings'
python manage.py check
python manage.py test subscriptions.test_catalog_contract subscriptions.test_payment_gateway subscriptions.test_payment_reconciliation_tasks --noinput
```

Puis vérifier depuis Internet que le callback HTTPS est joignable, sans
contourner le filtrage IP pour un vrai callback. Les retours HTTPS peuvent être
testés dans un navigateur ; ils ne doivent modifier ni l'utilisateur, ni son
abonnement, ni une transaction.

Un test sandbox réel exige les deux clés de l'application marchande de test,
son tableau de bord configuré et un backend public HTTPS. Les doubles clics,
la perte du callback, l'annulation, l'échec, le démarrage à froid et la reprise
après fermeture doivent être rejoués avant validation de recette.

## 5. Matrice de recette actuelle

| Niveau | Preuve attendue | Résultat autorisé |
| --- | --- | --- |
| Tests locaux mockés | signatures, falsification, concurrence, callback perdu, succès/échec/annulation/attente | obligatoire en CI |
| Sandbox publique | Paylink réel, page hébergée, `checkStatus`, échec sans activation | test manuel séparé |
| Application de test dédiée | callback signé, retours HTTPS, `SUCCESS`, activation immédiate et réconciliation | obligatoire avant GO |
| Production | transaction réelle à faible montant après homologation | jamais utilisée comme substitut de sandbox |

Pour chaque scénario dédié, relever uniquement les UUID de corrélation locaux,
les deux références de transaction, le montant, la devise, le type et le
statut. Vérifier que le callback reçoit `OK`, que `checkStatus` concorde et que
la finalisation atomique n'accorde l'abonnement qu'une fois. Le retour navigateur
seul doit toujours laisser le paiement en attente.
