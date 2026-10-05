# Guide uniforme d'intégration My CoolPay avec Flutter et Django

_Manuel de référence pour une intégration Paylink sûre en développement puis en production_

**Version vérifiée :** 8 septembre 2026

> Ce guide fusionne les deux guides source, retire les particularités des projets d'origine et tranche les détails fournisseur avec la documentation officielle My CoolPay.

Il est destiné à un agent IA ou à une équipe qui doit adapter l'intégration à n'importe quel projet Flutter et Django.

**Conclusion principale :** Flutter affiche le Paylink mais ne prouve jamais le paiement. Django calcule le prix, crée et conserve la transaction, confirme le résultat auprès de My CoolPay et accorde le produit une seule fois.

# Mode d'emploi

Suivre les sections dans l'ordre. Les exemples donnent une architecture de référence et doivent être adaptés aux modèles, aux règles de prix et au système d'authentification du projet cible. Aucun exemple ne doit être copié avant l'inventaire du projet et la vérification des URLs actives.

Pour un premier développement  utiliser les tests simulés, puis le bac à sable public dans ses limites documentées.

Pour une recette complète  utiliser une application marchande dédiée avec ses deux clés et des URLs HTTPS publiques.

Pour la production  changer la configuration et les clés sans modifier le coeur du flux de paiement.

# Sommaire

1 Décisions de conception

2 Contrat officiel My CoolPay

3 Bac a sable et environnements

4 Analyse obligatoire du projet cible

5 Architecture Django

6 Implementation Django

7 Implementation Flutter

8 Webhook vérification et réconciliation

9 Tests et recette

10 Passage en production

11 Depannage

12 Procedure autonome pour un agent IA

13 Critères d acceptation

Annexe A Arbitrages entre les guides

Annexe B Sources officielles

# 1 Décisions de conception

## 1 1 Règles obligatoires

Django est la seule frontiere entre le produit et My CoolPay. La clé privée ne quitte jamais le serveur.

Le client ne choisit jamais le montant, la devise, le motif final ni le bénéficiaire. Il choisit un produit ou un service et Django calcule le devis.

La référence applicative est créée et persistée avant l'appel Paylink. La référence My CoolPay est stockee dans un champ distinct.

Une redirection de navigateur ou un deep link ne constitue pas une preuve de paiement.

Seul un webhook authentifié ou un appel serveur checkStatus peut confirmer le paiement.

La finalisation métier est atomique et idempotente. Un même événement rejoué n'accorde jamais deux fois le produit.

Les paiements PENDING sont reconciliables car My CoolPay ne retente pas ses callbacks.

## 1 2 Flux cible

```
Flutter                       Django                         My CoolPay
| POST /payments/initiate/    |                                |
| produit et telephone        |                                |
|---------------------------->| valide produit et prix         |
|                             | cree app_transaction_ref       |
|                             | POST /api/public_key/paylink   |
|                             |------------------------------->|
|                             | transaction_ref payment_url    |
|                             |<-------------------------------|
| payment_id payment_url      | stocke PENDING                 |
|<----------------------------|                                |
| ouvre payment_url           |                                |
|------------------------------------------------------------->|
|                             | callback signe                 |
|                             |<-------------------------------|
|                             | verifie et finalise une fois   |
| GET /payments/id/           |                                |
|---------------------------->|                                |
| etat fiable et droit        |                                |
|<----------------------------|                                |
```

## 1 3 Séparation des responsabilités

| Composant | Responsabilités | Interdictions |
| --- | --- | --- |
| Flutter | Demander un Paylink ouvrir la page afficher et interroger l'état | Ne pas contenir la clé privée ne pas activer un droit |
| Django | Fixer le prix persister vérifier finaliser journaliser | Ne pas faire confiance au statut ou au montant du client |
| My CoolPay | Héberger la page traiter le paiement notifier et exposer checkStatus | La redirection utilisateur ne remplace pas le callback |

# 2 Contrat officiel My CoolPay

Les faits de cette section proviennent du workspace Postman officiel My CoolPay consulte le 8 septembre 2026. La collection indique une dernière édition générale au 28 juillet 2022 tandis que certaines pages sont toujours publiées et indexées. Vérifier ces pages au debut de chaque nouvelle intégration.

## 2 1 Prérequis marchands

1.  Obtenir un accès a l'espace marchand My CoolPay.

2.  Créer une application avec nom URL d'accueil logo URLs de redirection succès annulation échec URL de callback et email de notification.

3.  Faire valider l'application par My CoolPay. La documentation annonce une validation automatique sous vingt quatre heures.

4.  Récupérer la clé publique et la clé privée. La clé privée reste un secret serveur.

## 2 2 Création du Paylink

```
POST https://my-coolpay.com/api/{public_key}/paylink
Content-Type: application/json
Accept: application/json

{
"transaction_amount": 100,
"transaction_currency": "XAF",
"transaction_reason": "Commande ORD 123",
"app_transaction_ref": "pay_5f2c...",
"customer_phone_number": "699009900",
"customer_name": "Client Test",
"customer_email": "client@example.com",
"customer_lang": "fr"
}
```

La réponse d'exemple officielle est HTTP 201 et contient status success transaction_ref et payment_url. Le lien est à usage unique. Ne jamais remplacer une transaction_ref absente par app_transaction_ref.

| Champ | Règle d'intégration |
| --- | --- |
| transaction_amount | Nombre positif fixe par Django. Pour XAF préférer un entier sauf confirmation contraire du contrat marchand. |
| transaction_currency | XAF ou EUR selon la documentation publique. Utiliser seulement la devise activée pour le compte. |
| transaction_reason | Motif stable construit côté serveur. |
| app_transaction_ref | Référence unique de l'application créée avant l'appel. |
| customer_phone_number | Normaliser et valider sans inventer un format national universel. |
| customer_name customer_email | Données du compte authentifié ou données validees côté serveur. |
| customer_lang | fr ou en. |

La documentation permet d'ajouter des paramètres de requête au Paylink dans une longueur totale de 255 caracteres. Ils sont restitués dans la redirection finale et servent uniquement a l'expérience utilisateur.

## 2 3 Consultation du statut

```
GET https://my-coolpay.com/api/{public_key}/checkStatus/{transaction_ref}
Accept: application/json
```

Utiliser cette version GET. La version POST sur checkStatus existe encore mais est explicitement dépréciée. La réponse successful contient notamment app_transaction_ref transaction_ref transaction_type transaction_amount transaction_currency transaction_operator transaction_status et transaction_message.

Le statut peut être PENDING lors d'une consultation. Les statuts terminaux documentés dans le callback sont SUCCESS CANCELED et FAILED. Conserver ces valeurs fournisseur et les mapper explicitement vers les états du domaine local.

## 2 4 Callback et signature

My CoolPay envoie une requête POST a l'URL de callback configurée. Le corps documente contient application app_transaction_ref operator_transaction_ref transaction_ref transaction_type transaction_amount transaction_fees transaction_currency transaction_operator transaction_status transaction_reason transaction_message customer_phone_number et signature.

```
signature = md5(
transaction_ref
+ transaction_type
+ transaction_amount_sans_zeros_non_significatifs
+ transaction_currency
+ transaction_operator
+ private_key
)
```

La vérification officielle demande deux contrôles dans cet ordre  vérifier l'IP source My CoolPay puis recalculer la signature MD5. L'IP publiée le 8 septembre 2026 est 15.236.140.89. La vérifier à nouveau dans la documentation avant mise en service et configurer correctement le proxy inverse afin de ne pas faire confiance à un en-tête X Forwarded For fourni librement par Internet.

Après une vérification valide répondre en texte brut OK. En cas de rejet répondre KO avec un code adapté à la politique d'exploitation. Le callback est annonce comme émis une seule fois sans retry. La réconciliation par checkStatus est donc obligatoire.

## 2 5 URLs de redirection

Configurer trois URLs distinctes pour succès annulation et échec. Elles informent l'interface mais ne peuvent ni confirmer une transaction ni accorder un abonnement. Flutter doit ensuite interroger Django.

# 3 Bac à sable et environnements

## 3 1 Limite officielle

La documentation My CoolPay indique qu'il n'existe pas encore un environnement de test complet. Elle publie une application partagée My CoolPay Sandbox pour tester les API Web Mobile et Status avec la clé publique suivante 118a4852-7df8-46d9-834b-23b4ef25aaab. La clé privée est masquée pour des raisons de sécurité.

Cette clé publique peut changer. L'agent doit la relire dans la section Sandbox testing du workspace officiel avant de l utiliser. Comme la clé privée partagée est indisponible et que les URLs de cette application ne sont pas celles du projet cible le bac à sable public ne permet pas de valider seul un webhook signé de bout en bout.

## 3 2 Strategie de développement

| Niveau | But | Moyen |
| --- | --- | --- |
| Local simulé | Vérifier tous les cas et la sécurité | Mocks HTTP payloads de callback signes avec une clé de test locale et tests de concurrence |
| Sandbox public | Vérifier Paylink et checkStatus sans argent réel selon les capacités disponibles | Clé publique officielle partagée et aucun secret dans Flutter |
| Recette dédiée | Vérifier callbacks redirections et cycle complet | Application marchande de test ou dispositif fourni par le support avec clés dédiées et tunnel HTTPS |
| Production | Encaisser réellement | Application et clés de production gestionnaire de secrets domaines stables et supervision |

## 3 3 Configuration par environnement

```
# env.example sans valeur secrete
MYCOOLPAY_BASE_URL=https://my-coolpay.com/api
MYCOOLPAY_PUBLIC_KEY=<public_key_de_l_environnement>
MYCOOLPAY_PRIVATE_KEY=<private_key_seulement_si_disponible>
MYCOOLPAY_CURRENCY=XAF
MYCOOLPAY_CONNECT_TIMEOUT=5
MYCOOLPAY_READ_TIMEOUT=30
MYCOOLPAY_CALLBACK_SOURCE_IP=15.236.140.89
```

Ne pas inventer un domaine sandbox. La documentation officielle utilise la même base https my-coolpay com api. La séparation repose sur les applications les clés et les données de test disponibles pour le compte.

# 4 Analyse obligatoire du projet cible

Avant toute modification l'agent produit une cartographie courte du projet et confirme les décisions suivantes.

Emplacement des applications Django des URLs actives des settings et du système de taches asynchrones.

Models utilisateur commande produit abonnement et droits accordes après paiement.

Source de vérité de chaque prix devise durée et éligibilité.

Système d'authentification Flutter vers Django et mécanisme de renouvellement du token.

Écrans services réseau navigation et gestion du cycle de vie Flutter.

Routes existantes capables d activer un droit et code dupliqué ou non importé.

Règle de renouvellement annulation expiration remboursement et tentatives multiples.

L'agent doit arreter la conception et demander une décision métier si la durée le prix l'effet d'un renouvellement ou le produit a accorder ne peut pas être déterminé dans le code ou les spécifications.

# 5 Architecture Django

## 5 1 Structure conseillée

```
payments/
models.py            # transaction et evenements
serializers.py       # entree et sortie API
catalog.py           # resolution serveur du produit et du prix
mycoolpay.py          # client HTTP fournisseur
signatures.py        # verification du callback
finalization.py       # finaliseur atomique et idempotent
reconciliation.py    # verification des PENDING
views.py              # initiation statut callback
urls.py
tests/
```

## 5 2 Modèle de transaction

```
import uuid
from django.conf import settings
from django.db import models

class PaymentTransaction(models.Model):
class Status(models.TextChoices):
CREATED = "CREATED", "Created"
PENDING = "PENDING", "Pending"
SUCCESS = "SUCCESS", "Success"
CANCELED = "CANCELED", "Canceled"
FAILED = "FAILED", "Failed"

id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
app_transaction_ref = models.CharField(max_length=100, unique=True, db_index=True)
provider_transaction_ref = models.CharField(
max_length=150, unique=True, null=True, blank=True, db_index=True
)
purpose = models.CharField(max_length=50)
object_reference = models.CharField(max_length=150, blank=True)
amount = models.DecimalField(max_digits=12, decimal_places=2)
currency = models.CharField(max_length=3)
status = models.CharField(max_length=16, choices=Status.choices, default=Status.CREATED)
payment_url = models.URLField(max_length=1000, blank=True)
provider_message = models.TextField(blank=True)
paid_at = models.DateTimeField(null=True, blank=True)
finalized_at = models.DateTimeField(null=True, blank=True)
last_checked_at = models.DateTimeField(null=True, blank=True)
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

Ajouter selon les besoins une commande explicite une clé d'idempotence client un compteur de tentatives et un modèle PaymentEvent avec empreinte du payload. Eviter de conserver le payload brut en production si celui ci contient des données personnelles.

## 5 3 Transitions autorisées

| État courant | État suivant autorisé | Effet |
| --- | --- | --- |
| CREATED | PENDING FAILED | Conserver la trace même si l'appel externe échoue |
| PENDING | SUCCESS CANCELED FAILED | SUCCESS seul peut déclencher l'accomplissement |
| SUCCESS | Aucun | État terminal et accomplissement rejouable sans effet |
| CANCELED FAILED | Aucun ou règle explicite | Une nouvelle tentative crée une nouvelle transaction |

# 6 Implementation Django

## 6 1 Settings

```
import os

MYCOOLPAY = {
"BASE_URL": os.getenv("MYCOOLPAY_BASE_URL", "https://my-coolpay.com/api").rstrip("/"),
"PUBLIC_KEY": os.environ["MYCOOLPAY_PUBLIC_KEY"],
"PRIVATE_KEY": os.getenv("MYCOOLPAY_PRIVATE_KEY", ""),
"CURRENCY": os.getenv("MYCOOLPAY_CURRENCY", "XAF"),
"CONNECT_TIMEOUT": float(os.getenv("MYCOOLPAY_CONNECT_TIMEOUT", "5")),
"READ_TIMEOUT": float(os.getenv("MYCOOLPAY_READ_TIMEOUT", "30")),
"CALLBACK_SOURCE_IP": os.getenv("MYCOOLPAY_CALLBACK_SOURCE_IP", "15.236.140.89"),
}
```

Exiger PRIVATE_KEY au démarrage dans tout environnement qui accepte des callbacks. Le mode sandbox public peut la laisser vide mais doit alors refuser la finalisation par callback et utiliser seulement des tests simulés ou checkStatus.

## 6 2 Validation et catalogue

```
import re
from rest_framework import serializers

class InitiatePaymentSerializer(serializers.Serializer):
phone_number = serializers.CharField(max_length=20)
language = serializers.ChoiceField(choices=("fr", "en"), default="fr")
purpose = serializers.ChoiceField(choices=("premium", "coach_subscription"))
object_reference = serializers.CharField(required=False, allow_blank=True)
idempotency_key = serializers.UUIDField(required=False)

def validate_phone_number(self, value):
value = re.sub(r"[\s()-]", "", value)
if not re.fullmatch(r"\+?\d{8,15}", value):
raise serializers.ValidationError("Numero invalide")
return value
```

Le serializer ne reçoit ni montant ni devise. Une fonction resolve_product charge le produit ou le coach autorisé, vérifie l'éligibilité et renvoie amount currency reason et object_reference. Le prix affiché par Flutter peut venir d'un endpoint catalogue mais l initiation le recalcule toujours.

## 6 3 Client HTTP My CoolPay

```
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote, urlparse
import requests
from django.conf import settings

class MyCoolPayError(Exception):
pass

@dataclass(frozen=True)
class PaylinkResult:
transaction_ref: str
payment_url: str

class MyCoolPayClient:
def __init__(self, session=None):
self.cfg = settings.MYCOOLPAY
self.session = session or requests.Session()

def create_paylink(self, *, amount, reason, app_ref, phone, name, email, lang):
if Decimal(amount) <= 0:
raise MyCoolPayError("Montant invalide")
payload = {
"transaction_amount": int(amount),
"transaction_currency": self.cfg["CURRENCY"],
"transaction_reason": reason,
"app_transaction_ref": app_ref,
"customer_phone_number": phone,
"customer_name": name,
"customer_email": email,
"customer_lang": lang,
}
response = self.session.post(
f'{self.cfg["BASE_URL"]}/{self.cfg["PUBLIC_KEY"]}/paylink',
json=payload,
headers={"Accept": "application/json", "Content-Type": "application/json"},
timeout=(self.cfg["CONNECT_TIMEOUT"], self.cfg["READ_TIMEOUT"]),
)
response.raise_for_status()
data = response.json()
if data.get("status") != "success":
raise MyCoolPayError("Paylink refuse")
ref, url = data.get("transaction_ref"), data.get("payment_url")
parsed = urlparse(url or "")
if not ref or parsed.scheme != "https" or parsed.hostname != "my-coolpay.com":
raise MyCoolPayError("Reponse Paylink invalide")
return PaylinkResult(ref, url)

def check_status(self, transaction_ref):
ref = quote(transaction_ref, safe="")
response = self.session.get(
f'{self.cfg["BASE_URL"]}/{self.cfg["PUBLIC_KEY"]}/checkStatus/{ref}',
headers={"Accept": "application/json"},
timeout=(self.cfg["CONNECT_TIMEOUT"], self.cfg["READ_TIMEOUT"]),
)
response.raise_for_status()
data = response.json()
if data.get("status") != "success":
raise MyCoolPayError("Consultation de statut refusee")
return data
```

Valider l hôte par parsing et comparaison exacte. Si My CoolPay documente plus tard un autre sous domaine de paiement, l'ajouter à une liste fermée de configuration. Ne pas accepter une simple chaîne qui commence par une URL attendue.

## 6 4 Initiation

1.  Authentifier l'utilisateur.

2.  Valider la demande puis résoudre le produit et le prix côté serveur.

3.  Créer une référence applicative unique et une ligne CREATED avant l'appel réseau.

4.  Appeler Paylink sans transaction SQL longue.

5.  En cas d'erreur certaine marquer FAILED. En cas de timeout ambigu conserver un état réconciliable et ne pas rejouer aveuglement.

6.  Stocker transaction_ref et payment_url puis passer a PENDING.

7.  Retourner payment_id payment_url et status. Ne pas retourner la clé privée ni un mécanisme d'activation.

```
{
"payment_id": "UUID local",
"payment_url": "https://my-coolpay.com/payment/checkout/...",
"status": "PENDING"
}
```

## 6 5 Endpoint de statut

```
GET /api/payments/{payment_id}/
Authorization: Bearer <token Django>

{
"payment_id": "...",
"status": "PENDING|SUCCESS|CANCELED|FAILED",
"purpose": "premium",
"fulfilled": false
}
```

La requête filtre par id et user request user. Elle ne revele pas les données d'un autre utilisateur. Elle peut déclencher une vérification checkStatus limitée par un délai minimum ou laisser cette vérification à une tâche périodique.

# 7 Implementation Flutter

## 7 1 Configuration et dépendances

Conserver la base URL Django dans une configuration par environnement. Utiliser le client HTTP déjà présent dans le projet et centraliser l'ajout du Bearer token. Une WebView ou un navigateur externe peut ouvrir le Paylink. Le choix dépend de l'expérience produit et des moyens de paiement testés.

```
dependencies:
dio: <version compatible avec le projet>
webview_flutter: <version compatible avec le projet>
```

Ne pas recopier les versions des guides historiques. Exécuter flutter pub outdated puis choisir des versions compatibles avec le SDK du projet.

## 7 2 DTO et initiation

```
class PaymentAttemptDto {
final String paymentId;
final Uri paymentUrl;
final String status;

PaymentAttemptDto.fromJson(Map<String, dynamic> json)
: paymentId = json['payment_id'] as String,
paymentUrl = Uri.parse(json['payment_url'] as String),
status = json['status'] as String {
if (paymentUrl.scheme != 'https' || paymentUrl.host != 'my-coolpay.com') {
throw const FormatException('Paylink invalide');
}
}
}

Future<PaymentAttemptDto> initiatePayment({
required String phoneNumber,
required String language,
required String purpose,
String? objectReference,
}) async {
final response = await dio.post<Map<String, dynamic>>(
'/payments/initiate/',
data: {
'phone_number': phoneNumber.trim(),
'language': language,
'purpose': purpose,
if (objectReference != null) 'object_reference': objectReference,
},
);
return PaymentAttemptDto.fromJson(response.data!);
}
```

## 7 3 Navigation et retour

Conserver payment_id pendant tout le parcours. Si la WebView intercepte une URL terminale vérifier exactement le schemà l'hôte et le chemin de la redirection configurée. Bloquer les doubles traitements locaux mais ne compter sur ce verrou que pour l'expérience utilisateur.

Après succès annulation échec fermeture timeout ou reprise de l'application interroger Django.

Afficher vérification en cours tant que Django renvoie PENDING.

Mettre a jour l'interface et les droits locaux uniquement après SUCCESS et fulfilled true renvoyés par Django.

Une URL qui contient le mot success sur un autre domaine ne doit produire aucun effet.

Ne pas journaliser le token le numéro complet ou une URL de paiement contenant des paramètres sensibles.

## 7 4 Configuration mobile

```
<uses-permission android:name="android.permission.INTERNET" />
```

| Client | URL Django locale typique |
| --- | --- |
| Flutter desktop ou navigateur local | http://127.0.0.1:8000/api |
| Émulateur Android standard | http://10.0.2.2:8000/api |
| Appareil physique | http://adresse LAN du poste:8000/api |
| Production | https://api.example.com/api |

Placer usesCleartextTraffic true uniquement dans le manifeste debug si le développement local l exige. Préférer les Android App Links et iOS Universal Links à un schéma personnalisé lorsque le produit peut publier un domaine HTTPS vérifié.

# 8 Webhook vérification et réconciliation

## 8 1 Vérification de signature

```
import hashlib
import hmac
from decimal import Decimal, InvalidOperation

def canonical_number(value):
try:
text = format(Decimal(str(value)), "f")
except InvalidOperation as exc:
raise ValueError("Montant invalide") from exc
return (text.rstrip("0").rstrip(".") if "." in text else text) or "0"

def valid_signature(payload, private_key):
raw = "".join([
str(payload["transaction_ref"]),
str(payload["transaction_type"]),
canonical_number(payload["transaction_amount"]),
str(payload["transaction_currency"]),
str(payload["transaction_operator"]),
private_key,
])
expected = hashlib.md5(raw.encode("utf-8")).hexdigest()
received = str(payload.get("signature", ""))
return hmac.compare_digest(received.lower(), expected.lower())
```

MD5 est utilise ici uniquement parce que le protocole fournisseur l impose. La signature ne dispense pas de comparer application app_transaction_ref transaction_ref montant devise type PAYIN et produit local. Pour une défense supplémentaire le finaliseur peut relire checkStatus avant d accorder un droit.

## 8 2 Traitement du callback

1.  Lire l'IP source résolue par le proxy de confiance et la comparer à la valeur officielle configurée.

2.  Vérifier la présence des champs puis la signature en temps constant.

3.  Vérifier application contre la clé publique attendue.

4.  Charger la transaction par app_transaction_ref et verrouiller la ligne.

5.  Comparer les deux références le montant la devise et transaction_type PAYIN.

6.  Accepter seulement SUCCESS CANCELED ou FAILED dans un callback.

7.  Appeler l'unique finaliseur atomique et idempotent.

8.  Répondre rapidement OK en texte brut pour un callback valide y compris un replay sans effet.

## 8 3 Finaliseur atomique

```
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

@transaction.atomic
def apply_provider_status(payment_id, provider_data):
payment = PaymentTransaction.objects.select_for_update().get(pk=payment_id)
assert_provider_matches_local(payment, provider_data)

if payment.finalized_at is not None:
return payment

new_status = provider_data["transaction_status"]
if new_status == "SUCCESS":
grant_product_once(payment)  # adapte au domaine et idempotent
payment.paid_at = timezone.now()

payment.status = new_status
if new_status in {"SUCCESS", "CANCELED", "FAILED"}:
payment.finalized_at = timezone.now()
payment.save()
return payment
```

grant_product_once doit utiliser une contrainte unique ou un verrou sur l'objet métier. Un compteur de followers ne doit être incrémenté que lors d'une vraie transition d'inactif vers actif. Un paiement SUCCESS déjà finalisé est un no op.

## 8 4 Réconciliation

Planifier une tâche qui sélectionne les PENDING âgés de quelques minutes puis appelle checkStatus avec backoff limite de concurrence et age maximal. Le même finaliseur traite la réponse. Conserver last_checked_at et une erreur expurgée. Cette tâche couvre les callbacks perdus car My CoolPay ne les retente pas.

# 9 Tests et recette

## 9 1 Tests Django

Création Paylink réponse 201 et éventuelle réponse 200 tolérée seulement si observée et testée.

status error JSON invalide champ manquant domaine inattendu timeout et erreurs 4xx ou 5xx.

GET checkStatus et mapping PENDING SUCCESS CANCELED FAILED.

Signature valide invalide montant canonique champs absents et mauvaise IP source.

Mauvaise application référence fournisseur référence application montant devise ou type.

Prix toujours resolu côté serveur et montant injecté par le client ignoré ou refusé.

Deux callbacks SUCCESS et concurrence callback réconciliation accordent un seul droit.

Un utilisateur ne peut consulter que ses propres transactions.

## 9 2 Tests Flutter

Parsing du DTO et rejet d'une URL non HTTPS ou d'un domaine hostile.

Absence ou expiration du token et erreurs 400 401 409 422 et 5xx.

Retour succès avant le webhook avec affichage PENDING puis actualisation.

Fermeture de WebView abandon reprise de l'application et timeout de polling.

Double clic et retry réseau avec une clé d'idempotence lorsque le backend la prend en charge.

## 9 3 Recette sandbox publique

1.  Relire la section officielle Sandbox testing et copier la clé publique courante dans les secrets locaux.

2.  Créer une transaction de test avec données fictives et vérifier la réponse Paylink.

3.  Ouvrir le lien et exécuter uniquement les scénarios permis par le bac à sable au moment du test.

4.  Interroger checkStatus et comparer les deux références le montant la devise et le type.

5.  Consigner les fonctions non testables notamment le callback signé si la clé privée reste indisponible.

## 9 4 Recette complète dédiée

URLs HTTPS publiques succès annulation échec et callback configurées dans l'application marchande.

Succès réel ou scénario de test officiel avec callback valide et réponse OK.

Rejeu du callback sans double droit.

Simulation d'un callback perdu puis récupération par checkStatus.

Échec annulation abandon timeout et perte réseau après création du Paylink.

Vérification sur Android et iOS pour chaque moyen de paiement disponible au compte.

Les appels sandbox réels ne font pas partie de la suite CI standard. La CI utilise des mocks déterministes et des jeux de callbacks fixes.

# 10 Passage en production

[ ] Application marchande de production créée et validée.

[ ] Clés stockées dans un gestionnaire de secrets et rotation prévue.

[ ] Clé privée absente de Flutter de Git et des logs.

[ ] URLs stables HTTPS certificat DNS slash final et proxy de confiance vérifiés.

[ ] IP callback officielle revalidée et configurable sans redéploiement de code.

[ ] Vérification signature application références montant devise et type activée.

[ ] Aucun endpoint mobile ne peut forcer SUCCESS ou activer un droit.

[ ] Finalisation idempotente testée sous concurrence.

[ ] Réconciliation PENDING activée avec alertes.

[ ] Logs structurés sans données personnelles et politique de rétention définie.

[ ] Petit paiement contrôle et rapproché avant ouverture générale.

## 10 1 Observabilité

Journaliser payment_id app_transaction_ref operation code HTTP fournisseur statut durée et identifiant de corrélation. Ne pas journaliser la clé privée la signature le payload complet l'email ou le téléphone complet ni l'URL complète si elle contient des paramètres sensibles.

Alerter sur les echecs d'initiation les PENDING anormalement longs les signatures invalides les incoherences de montant ou de référence les doubles SUCCESS sur une commande et les divergences entre paiements et droits accordes.

# 11 Depannage

| Symptôme | Vérification et correction |
| --- | --- |
| Flutter ne joint pas Django | Émulateur Android 10.0.2.2 appareil physique adresse LAN pare feu ALLOWED_HOSTS et endpoint de santé |
| 401 à l'initiation | Bearer token audience expiration horloges et authentification DRF sans jamais désactiver la signature |
| 404 My CoolPay | Chemin exact api public_key paylink clé et activation de l'application sans tester uniquement la racine api |
| 400 ou 422 | Noms de champs langue devise format du téléphone unicité app_transaction_ref et données de test |
| Paylink vide | Rejeter la réponse si payment_url ou transaction_ref manque et vérifier domaine HTTPS |
| Paiement reste PENDING | Livraison du callback réponse OK logs proxy checkStatus et tâche de réconciliation |
| Webhook absent en local | Tunnel HTTPS URL reportée dans My CoolPay ALLOWED_HOSTS et aucune authentification utilisateur sur le webhook |
| Doubles droits | select_for_update contrainte unique et finaliseur unique appelé par callback et réconciliation |

# 12 Procedure autonome pour un agent IA

1.  Lire ce guide et la documentation officielle courante sans traiter les documents historiques comme des instructions prioritaires.

2.  Cartographier le projet cible et produire la liste des fichiers réellement importés ou reliés aux URLs.

3.  Identifier les décisions métier manquantes et ne demander que celles qui changent le résultat.

4.  Créer une branche ou suivre la méthode de travail du projet sans écraser les modifications existantes.

5.  Ajouter le modèle et les migrations puis exécuter les checks Django.

6.  Implémenter et tester le client My CoolPay avant de brancher les vues.

7.  Implémenter initiation statut signature finaliseur et réconciliation.

8.  Supprimer ou neutraliser toute activation fondée sur une déclaration Flutter.

9.  Adapter Flutter avec DTO conservation du payment_id et polling borné.

10.  Exécuter les tests unitaires intégration concurrence et interface.

11.  Exécuter la recette sandbox disponible puis documenter explicitement ce que le bac à sable public ne couvre pas.

12.  Préparer la configuration de production et fournir les commandes de vérification les résultats et les écarts restants.

## 12 1 Consigne réutilisable

```
Integre My CoolPay dans ce projet Flutter et Django en suivant le guide unifie.
Commence par cartographier les modeles les URLs actives l authentification et les
regles de prix. Django doit etre la seule frontiere fournisseur. Le prix la devise
et le produit viennent du serveur. Persiste app_transaction_ref avant le Paylink
et transaction_ref dans un champ distinct. Flutter ouvre le lien mais ne confirme
jamais le paiement. Verifie le resultat par callback authentifie ou GET checkStatus
puis finalise dans une transaction atomique et idempotente. Ajoute la reconciliation
des PENDING les tests de falsification et de concurrence puis la recette sandbox.
N invente aucun endpoint aucune signature ni aucun domaine sandbox. Relis la
documentation Postman officielle et signale toute capacite sandbox indisponible.
```

# 13 Critères d acceptation

[ ] Un utilisateur authentifié obtient un Paylink pour un produit éligible.

[ ] Le client ne contrôle pas le montant la devise le motif ni le bénéficiaire.

[ ] Les références application et fournisseur sont stockées séparément.

[ ] Une redirection falsifiée ne change aucun droit.

[ ] Un callback avec mauvaise IP signature application référence montant devise ou type est rejeté.

[ ] SUCCESS accorde exactement le bon produit une seule fois.

[ ] CANCELED et FAILED n'accordent aucun droit.

[ ] Un callback perdu est récupéré par checkStatus.

[ ] Aucune clé privée ni donnée personnelle sensible ne figure dans le client le dépôt ou les logs.

[ ] Les tests unitaires intégration concurrence Flutter et recette applicable passent.

[ ] Le passage en production est un changement contrôle de configuration et non une réécriture du métier.

# Annexe A Arbitrages entre les guides

| Sujet | Décision retenue | Fondement |
| --- | --- | --- |
| Vérification de statut | GET checkStatus référence est la version courante | La version POST est marquée Legacy et deprecated |
| Confirmation | Callback vérifié plus réconciliation checkStatus | Callback émis une seule fois sans retry |
| Signature | Formule MD5 exacte du fournisseur avec montant canonique | Documentation callback officielle |
| Réponse callback | Texte brut OK ou KO | Section Security officielle |
| IP callback | Vérifier 15.236.140.89 via une configuration revalidable | Section Security officielle consultée le 8 septembre 2026 |
| Sandbox | Pas de domaine sandbox invente et bac public incomplet | Section Sandbox testing officielle |
| Clé privée sandbox | Ne pas supposer qu elle est disponible | La documentation publique la masque |
| Montant XAF | Entier positif par défaut comme validation prudente | L API exige un number mais ne publie pas une règle générale sur les décimales |
| HTTP Paylink | Attendre 201 et traiter toute autre réponse seulement si le contrat réel la confirme | Exemple officiel 201 Created |
| URL navigateur | Signal UX seulement | Principe de sécurité et séparation redirection callback |

# Annexe B Sources officielles

Workspace et collection My CoolPay API Docs

https://www.postman.com/my-coolpay/my-coolpay-workspace/documentation/q45oyma/my-coolpay-api-docs

Paylink

https://www.postman.com/my-coolpay/my-coolpay-workspace/request/nno1qn9/paylink

Check status

https://www.postman.com/my-coolpay/my-coolpay-workspace/request/915ytc4/check-status

Callback handling webhook

https://www.postman.com/my-coolpay/my-coolpay-workspace/folder/uj9qj2n/6-callback-handling-webhook

Security

https://www.postman.com/my-coolpay/my-coolpay-workspace/folder/kn9v2gi/7-security

Sandbox testing

https://www.postman.com/my-coolpay/my-coolpay-workspace/folder/84yotbg/8-sandbox-testing

La documentation française PDF de 2021 est signalée par My CoolPay comme potentiellement obsolète. Elle ne doit pas primer sur le workspace Postman courant.

