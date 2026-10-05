# Plan de Test Utilisateur Complet — HIVMeet (Flutter + Django)

> **Document autonome.** Il est destiné à être fourni en pièce jointe à un agent IA qui n'a
> aucun contexte préalable sur ce projet. Tout ce qui est nécessaire à l'exécution figure ici :
> chemins, commandes, contrats d'API, critères d'acceptation, anomalies déjà repérées.

---

## Contexte

**HIVMeet** est une application de rencontre destinée aux personnes vivant avec le VIH. Elle
comporte deux dépôts :

| Composant | Chemin absolu | Stack |
|-----------|---------------|-------|
| Backend | `d:\Projets\HIVMeet\env\hivmeet_backend` | Django 4.2/5.2 + DRF + Channels + PostgreSQL + Redis + Celery + Firebase Admin |
| Frontend | `d:\Projets\HIVMeet\hivmeet` | Flutter (Clean Architecture : `domain` / `data` / `presentation`), BLoC, go_router, Dio, Firebase Auth |

Les deux moitiés ont été développées largement en parallèle, sur une longue période, avec de
nombreuses vagues de correctifs (des dizaines de rapports `BACKEND_*.md`, `AUDIT_*.md`,
`CORRECTION*.md` traînent à la racine des deux dépôts). Conséquence : **personne n'a jamais
validé l'application de bout en bout comme le ferait un utilisateur réel**, ni vérifié que la
totalité des appels émis par le client correspond à des routes réellement servies par le
serveur.

Une analyse statique préalable (dont les résultats sont consignés en §8) a déjà mis en évidence
plusieurs écarts de contrat certains et des incohérences de logique premium. Cela confirme le
besoin, mais ne le remplace pas : seul un parcours réel révèle les défauts de bout en bout.

**Objectif de ce plan** : faire exécuter, par un agent IA, une campagne de tests utilisateurs
réels sur émulateur Android et appareil physique, couvrant l'intégralité des fonctionnalités,
pour chaque couple de types de comptes (gratuit×gratuit, gratuit×premium, premium×premium), en
alternant systématiquement **action côté frontend → vérification côté backend**, et en
**corrigeant immédiatement** tout défaut rencontré avant de poursuivre.

**Résultat attendu** : une application dont chaque fonctionnalité présentée à l'utilisateur
fonctionne conformément aux spécifications, plus un rapport de campagne traçant chaque test,
chaque anomalie, chaque correction et chaque revalidation.

---

## 1. Mode d'emploi pour l'agent exécutant

### 1.1 Ton rôle

Tu es à la fois **testeur** (tu utilises l'application comme un utilisateur), **diagnosticien**
(tu localises la cause d'un dysfonctionnement) et **développeur** (tu corriges, des deux côtés).

### 1.2 La boucle d'exécution — à appliquer à chaque test, sans exception

```
┌─ 1. LIRE  la fiche de test (préconditions, étapes, critères)
├─ 2. AGIR  sur l'appareil, exactement comme un utilisateur (UI uniquement)
├─ 3. OBSERVER simultanément :
│      • l'écran (capture d'écran systématique)
│      • les logs Flutter (`flutter run` / `flutter logs`)
│      • les logs Django (console du serveur ASGI)
│      • l'état de la base si le test le demande
├─ 4. COMPARER aux critères d'acceptation
│
├─ SI CONFORME ──► journaliser ✅ et passer IMMÉDIATEMENT au test suivant
│
└─ SI NON CONFORME ──► entrer en boucle de correction :
       a. Reproduire une seconde fois pour écarter l'aléa (réseau, timing)
       b. LOCALISER la couche fautive :
            – requête jamais émise .............. → frontend (BLoC / repository / UI)
            – requête émise, 4xx/5xx ............ → lire le corps de réponse + traceback Django
            – 404 sur la route .................. → écart de contrat (§8) : comparer routes FE/BE
            – 200 mais affichage faux ........... → mapping de modèle Dart (`fromJson`)
            – rien ne bouge en temps réel ....... → WebSocket (connexion, token, channel layer)
       c. REMONTER LA TRACE jusqu'au code source (fichier:ligne des deux côtés)
       d. COMPRENDRE l'intention : à quoi sert cette fonctionnalité pour l'utilisateur ?
          Quelle est la spécification (§7, `docs/API_DOCUMENTATION.md`) ?
       e. CORRIGER à la source — jamais un contournement dans l'UI pour masquer un
          défaut serveur, jamais un assouplissement de validation pour faire passer un test
       f. REDÉMARRER ce qui doit l'être (hot reload Flutter, redémarrage Django si modèle/URL)
       g. REJOUER le test intégralement depuis l'étape 1
       h. Ne passer au suivant QUE si le test passe
       i. Journaliser 🔧 avec : symptôme, cause racine, fichiers modifiés, preuve de résolution
```

### 1.3 Règles impératives

- **Ne jamais sauter un test échoué.** Si un défaut est vraiment bloquant et hors de portée
  (dépendance externe indisponible, par exemple), le marquer ⛔ **BLOQUÉ**, documenter
  précisément le blocage, et poursuivre — mais uniquement dans ce cas.
- **Toute action utilisateur passe par l'interface.** Les appels `curl`/HTTPie servent
  exclusivement au *diagnostic* et à la *vérification*, jamais à simuler l'utilisateur.
- **Après chaque correction backend touchant un modèle** : `makemigrations` + `migrate`,
  et commiter la migration avec le modèle.
- **Après chaque correction touchant un texte visible** : le passer par l'i18n
  (`gettext_lazy` côté Django, `assets/translations/{fr,en}.json` côté Flutter).
- **Ne jamais journaliser de donnée sensible** (statut VIH, token complet, mot de passe) dans
  les logs ou le rapport.
- **Une correction = un commit atomique** avec un message explicite. Ne pas empiler.
- **Ne pas modifier ce plan.** Le rapport est un fichier séparé.
- **Vérifier avant de corriger un « endpoint manquant »** : certaines méthodes du frontend
  peuvent être du code mort jamais appelé depuis l'UI. Chercher les appelants avant de
  décider s'il faut créer la route backend ou supprimer le code client (§8.1).

### 1.4 Journal de campagne

Créer et tenir à jour `d:\Projets\HIVMeet\RAPPORT_TESTS_E2E.md` :

```markdown
# Rapport de campagne de tests E2E — HIVMeet
Démarré le : <date>   |   Agent : <modèle>   |   Backend : <commit>   |   Frontend : <commit>

## Tableau de bord
| Bloc | Total | ✅ | 🔧 | ⛔ | ⏭ |
|------|-------|----|----|----|----|

## Journal détaillé

### [B3-07] Like sur un profil — compte gratuit
- **Statut** : 🔧 Corrigé
- **Appareil** : emulator-5554
- **Comptes** : free_a → free_b
- **Symptôme observé** : compteur de likes restants figé à 10 après 3 likes
- **Diagnostic** : `GET /api/v1/discovery/profiles` renvoie bien `daily_likes_remaining: 7`
  (vérifié dans les logs Django), mais `DiscoveryBloc` ne relit pas le champ après un like.
- **Cause racine** : `lib/presentation/blocs/discovery/discovery_bloc.dart:<ligne>` — l'état
  n'est pas reconstruit avec la valeur renvoyée par la réponse du like.
- **Correction** : <description + fichiers>
- **Revalidation** : rejoué intégralement → compteur 10→9→8→7. ✅
- **Captures** : `screenshots/B3-07-avant.png`, `screenshots/B3-07-apres.png`
```

Légende : ✅ conforme du premier coup · 🔧 défaut trouvé puis corrigé et revalidé ·
⛔ bloqué · ⏭ non applicable (justifier).

---

## 2. Mise en place de l'environnement

### 2.1 État constaté de la machine

Vérifié au moment de la rédaction — à reconfirmer au démarrage :

- Flutter installé et fonctionnel ; `adb` en `platform-tools` version 35.0.1
- PostgreSQL **écoute déjà** sur `127.0.0.1:5432`
- Redis **écoute déjà** sur `127.0.0.1:6379`
- Python 3.12.3, virtualenv du backend en `.venv\Scripts\python.exe`
- Docker 29.6.1 disponible (`docker-compose.yml` présent : `db`, `redis`, `web`, `celery`,
  `celery-beat`, `flower`) — **non requis** puisque PG et Redis tournent en natif
- Appareils vus par `adb devices` :
  - `emulator-5554` — `sdk_gphone64_x86_64`
  - `192.168.1.155:43669` — **TECNO KF7j** (appareil physique, connecté en Wi-Fi/adb-tls)
- AVD disponibles : `Pixel_3a_API_32_extension_level_7_x86_64`, `Pixel_3a_API_34`,
  `Pixel_6a_API_32`, `flutter_emulator`, `flutter_emulator_2`

### 2.2 Démarrage du backend

```bash
cd /d/Projets/HIVMeet/env/hivmeet_backend
source .venv/Scripts/activate      # PowerShell : .\.venv\Scripts\Activate.ps1

# Vérifier que PG et Redis répondent
python -c "import socket;[print(p,'OK') if socket.create_connection(('127.0.0.1',p),2) else 0 for p in (5432,6379)]"

python manage.py migrate
python manage.py collectstatic --noinput   # si nécessaire
```

**Serveur ASGI.** `channels` est dans `INSTALLED_APPS` et `ASGI_APPLICATION` pointe sur
`hivmeet_backend.asgi.application` : la commande `runserver` est alors remplacée par le
serveur ASGI de Channels, qui sert **HTTP et WebSocket**. Ni `daphne` ni `uvicorn` ne sont
installés dans le venv — inutile de les ajouter.

```bash
# 0.0.0.0 est indispensable pour que l'appareil physique atteigne le serveur
python manage.py runserver 0.0.0.0:8000
```

Au démarrage, **confirmer dans la console** que Channels prend la main (message mentionnant
ASGI/Daphne, pas le serveur WSGI de développement). Sinon, les WebSockets ne fonctionneront
pas et tout le bloc temps réel (B7) échouera pour une raison d'infrastructure, pas de code.

Vérification de vie :
```bash
curl -s http://127.0.0.1:8000/health/simple/
curl -s http://127.0.0.1:8000/health/ready/
```

**Celery.** `CELERY_TASK_ALWAYS_EAGER` vaut `True` quand `DEBUG=True` : les tâches s'exécutent
en synchrone dans le process Django. Aucun worker n'est nécessaire pour les tests de parcours.
Un worker + beat ne sont requis que pour le bloc B10 (expiration d'abonnement, compteurs
quotidiens) :
```bash
celery -A hivmeet_backend worker -l info      # terminal séparé
celery -A hivmeet_backend beat   -l info      # terminal séparé
```

**Variables d'environnement.** Il n'existe **pas** de `.env` à la racine du backend, seulement
`env.example`. Les valeurs par défaut de `settings.py` s'appliquent donc :
`DEBUG=True`, `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hivmeet_db`,
`REDIS_URL=redis://127.0.0.1:6379/0`, `ALLOWED_HOSTS` incluant `10.0.2.2` et `*`.
Vérifier que `credentials/hivmeet_firebase_credentials.json` existe — l'authentification en
dépend entièrement. Si absent, c'est un blocage à traiter avant tout autre chose.

### 2.3 Adresse du backend vue par l'application

`lib/core/config/app_config.dart` (lignes 73-105) choisit l'URL ainsi :

| Cible | URL par défaut |
|-------|----------------|
| Émulateur Android (debug) | `http://10.0.2.2:8000` |
| **Appareil physique (debug)** | **`http://192.168.1.118:8000`** |
| Web (debug) | `http://localhost:8000` |
| Release | `https://api.hivmeet.com` |

L'URL des WebSockets en dérive automatiquement (`http`→`ws`), et `ApiClient` y ajoute
`/api/v1/`.

> ⚠️ **Point de vigilance majeur.** L'IP codée en dur pour l'appareil physique est
> `192.168.1.118`, alors que le TECNO observé est sur `192.168.1.155`. L'IP de la **machine
> hôte** sur le LAN doit être déterminée au démarrage (`ipconfig`) et, si elle diffère de
> `192.168.1.118`, il faut **impérativement** utiliser la surcharge prévue :
>
> ```bash
> flutter run -d 192.168.1.155:43669 --dart-define=API_URL=http://<IP_HOTE_LAN>:8000
> ```
>
> Sans cela, tous les tests sur appareil physique échoueront en timeout réseau et le
> diagnostic partira dans une mauvaise direction. Le pare-feu Windows doit également
> autoriser les connexions entrantes sur le port 8000.

### 2.4 Lancement de l'application

```bash
cd /d/Projets/HIVMeet/hivmeet
flutter pub get
flutter devices                     # confirmer les identifiants exacts

# Émulateur (l'IP 10.0.2.2 est gérée automatiquement)
flutter run -d emulator-5554

# Appareil physique — surcharge d'URL obligatoire (cf. §2.3)
flutter run -d 192.168.1.155:43669 --dart-define=API_URL=http://<IP_HOTE_LAN>:8000
```

Pour tester une paire de comptes, faire tourner **deux instances simultanément** — deux
émulateurs (`flutter_emulator` et `flutter_emulator_2`, ou deux AVD Pixel) — chacune dans son
terminal `flutter run`. C'est indispensable pour tout ce qui est réciproque : match, chat
temps réel, notifications, indicateurs de présence et de saisie.

```bash
emulator -avd Pixel_3a_API_34 &
emulator -avd Pixel_6a_API_32 &
adb devices          # récupérer les deux identifiants emulator-55XX
```

### 2.5 Outillage d'observation

```bash
flutter logs -d emulator-5554                       # logs applicatifs
adb -s emulator-5554 logcat | grep -i hivmeet       # logs système / Firebase / FCM
adb -s emulator-5554 exec-out screencap -p > screenshots/<ID_TEST>.png
adb -s emulator-5554 shell dumpsys battery          # état batterie (tests physiques)

# Console Django : garder le terminal `runserver` visible en permanence.
# Inspection base :
python manage.py shell
python manage.py dbshell
```

Créer un dossier `d:\Projets\HIVMeet\screenshots\` pour les captures référencées dans le
rapport.

---

## 3. Comptes de test et matrice des paires

### 3.1 Jeux de données existants

Le backend fournit des scripts de peuplement à sa racine :

| Script | Rôle |
|--------|------|
| `populate_test_users.py` | Crée des utilisateurs variés avec profils complets (Thomas, etc.), genres, âges, villes, préférences |
| `populate_male_profiles_for_marie.py` | Peuple des profils masculins ciblés |
| `populate_test_interactions.py` | Crée des likes/dislikes de test |
| `populate_without_signals.py` / `force_populate.py` | Variantes contournant les signaux |
| `matching/management/commands/reset_test_interactions.py` | Remet les interactions à zéro |
| `subscriptions/management/commands/init_subscription_plans.py` | **Obligatoire** : crée les plans d'abonnement |
| `resources/management/commands/populate_resources.py` | Peuple le contenu éducatif |

**À exécuter avant toute chose** (l'écran Premium et l'écran Ressources sont vides sinon) :
```bash
python manage.py init_subscription_plans
python manage.py populate_resources
```

> Lire l'en-tête de chaque script de peuplement avant exécution. Certains créent les
> utilisateurs directement en base sans passer par Firebase : ils servent de **profils cibles
> à découvrir**, mais on ne peut pas s'y connecter depuis l'application. Ils sont parfaits
> pour remplir le deck de découverte, mais ne remplacent pas les comptes acteurs.

### 3.2 Les comptes acteurs

L'inscription réelle passe par le SDK Firebase côté client
(`createUserWithEmailAndPassword`, `lib/core/services/authentication_service.dart:634`), puis
par `POST /api/v1/auth/firebase-exchange/` qui crée/synchronise l'utilisateur Django et rend
un JWT. **Les comptes acteurs doivent donc être créés depuis l'application elle-même**, via
l'écran d'inscription (test B1-01). Ne pas les fabriquer en base.

Créer quatre comptes acteurs :

| Alias | Rôle | Genre / recherche | Créé par |
|-------|------|-------------------|----------|
| **ALICE** | Gratuite | femme, cherche hommes | Inscription UI (B1-01) |
| **BOB** | Gratuit | homme, cherche femmes | Inscription UI (B1-01 bis) |
| **CARLA** | Premium | femme, cherche hommes | Inscription UI puis élévation (§3.3) |
| **DAVID** | Premium | homme, cherche femmes | Inscription UI puis élévation (§3.3) |

Les préférences (tranche d'âge, distance, genres recherchés) doivent être **réciproquement
compatibles** entre les membres d'une paire, sinon les profils ne s'affichent pas et le
diagnostic est trompeur. Le script `test_with_compatible_ages.py`, à la racine du backend,
documente cette contrainte.

Enregistrer les identifiants (email + mot de passe) dans un fichier **local et non commité**,
p. ex. `d:\Projets\HIVMeet\.test-accounts.local.md`. Vérifier qu'il est bien couvert par le
`.gitignore` avant d'écrire dedans.

### 3.3 Élévation en Premium — passe 1 (octroi direct)

Le statut premium est déterminé par plusieurs chemins de code **qui ne concordent pas**
(cf. anomalie A-05, §8.2). Pour que l'état soit cohérent quel que soit le chemin emprunté, il
faut positionner **à la fois** les champs de `User` **et** une `Subscription` active :

```python
# python manage.py shell
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.cache import cache
from subscriptions.models import Subscription, SubscriptionPlan
from subscriptions.utils import premium_status_cache_key

U = get_user_model()
u = U.objects.get(email="carla@test.local")

# 1) Champs portés par le modèle User
u.is_premium = True
u.premium_until = timezone.now() + timedelta(days=30)
u.save(update_fields=["is_premium", "premium_until"])

# 2) Abonnement actif correspondant
plan = SubscriptionPlan.objects.get(plan_id="hivmeet_monthly")
Subscription.objects.update_or_create(
    user=u,
    defaults=dict(
        plan=plan,
        status=Subscription.STATUS_ACTIVE,
        current_period_end=timezone.now() + timedelta(days=30),
    ),
)

# 3) Purger le cache de statut premium (TTL 5 min, sinon l'ancien état persiste)
cache.delete(premium_status_cache_key(u.id))
```

Vérification depuis l'application : `GET /api/v1/user-profiles/premium-status/` doit refléter
le premium **immédiatement**. Si ce n'est pas le cas, c'est le cache (voir A-06, §8.2).

Pour retrouver l'état gratuit : remettre `is_premium=False`, `premium_until=None`, passer la
souscription en `STATUS_EXPIRED`, purger le cache.

### 3.4 Matrice des paires

Chaque bloc relationnel (B4 à B8) se rejoue pour les trois combinaisons :

| # | Paire | Acteurs | Ce que la combinaison révèle spécifiquement |
|---|-------|---------|---------------------------------------------|
| **P1** | gratuit × gratuit | ALICE ↔ BOB | Quotas des deux côtés, limite de 10 likes/jour, absence de « qui m'a liké », rewind refusé, filtres restreints |
| **P2** | gratuit × premium | ALICE ↔ DAVID | Asymétrie : ce que le premium voit et que le gratuit ne voit pas ; réception d'un super-like par un gratuit ; accusés de lecture asymétriques ; le premium voit le gratuit dans « qui m'a liké » mais pas l'inverse |
| **P3** | premium × premium | CARLA ↔ DAVID | Fonctionnalités premium simultanées : boost croisé, super-likes, rewind, appels, filtres avancés des deux côtés |

**Discipline d'isolation.** Avant de changer de paire, remettre les interactions à zéro pour
que le deck de découverte se recharge et que les compteurs quotidiens ne polluent pas la
combinaison suivante :
```bash
python manage.py reset_test_interactions
```
Vérifier ce que la commande couvre exactement (`Like`, `Dislike`, `Match`,
`InteractionHistory`, `DailyLikeLimit`) et compléter à la main si elle laisse des résidus.

---

## 4. Ordre de parcours et graphe de dépendances

L'ordre n'est pas arbitraire : il suit le graphe de dépendances fonctionnelles. Chaque bloc ne
peut être testé que si les précédents passent, car il consomme leurs sorties.

```
                    ┌──────────────────────────────────┐
                    │ B0  Infrastructure & connectivité │
                    └────────────────┬─────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │ B1  Authentification              │  ← produit : JWT, User Django
                    └────────────────┬─────────────────┘
                                     ▼
                    ┌──────────────────────────────────┐
                    │ B2  Profil, photos, vérification  │  ← produit : profil éligible
                    └────────────────┬─────────────────┘     à la découverte
                                     ▼
                    ┌──────────────────────────────────┐
                    │ B3  Découverte, filtres, quotas   │  ← produit : likes
                    └────────────────┬─────────────────┘
                        ┌────────────┴────────────┐
                        ▼                         ▼
        ┌───────────────────────────┐  ┌──────────────────────────┐
        │ B4  Matching (réciprocité)│  │ B5  Historique & premium │
        └───────────┬───────────────┘  │     découverte           │
                    ▼                  └──────────────────────────┘
        ┌───────────────────────────┐
        │ B6  Messagerie (REST)     │  ← nécessite un match
        └───────────┬───────────────┘
                    ▼
        ┌───────────────────────────┐
        │ B7  Temps réel (WebSocket)│  ← nécessite une conversation
        └───────────┬───────────────┘
                    ▼
        ┌───────────────────────────┐
        │ B8  Notifications & FCM   │  ← consomme les événements de B4/B6/B7
        └───────────────────────────┘

  Blocs transverses, testables dès que B1 passe :
        B9  Ressources & feed communautaire
        B10 Abonnements & premium (passes 1 et 2)
        B11 Paramètres, confidentialité, blocage, modération, RGPD
        B12 Robustesse : réseau, cycle de vie, i18n, accessibilité, perfs
```

**Justification.** Rien ne fonctionne sans JWT (B1). Un profil incomplet ou non vérifié
n'apparaît pas dans le deck des autres : `matching/services.py` filtre sur `is_active`,
`email_verified`, `is_hidden` et `allow_profile_in_discovery` — d'où B2 avant B3. Un match
(B4) n'existe que par un like réciproque (B3). Une conversation (B6) n'existe que par un
match. Le temps réel (B7) opère sur une conversation existante. Les notifications (B8) sont
produites par les événements des blocs précédents. Les blocs transverses n'ont pour
dépendance qu'une session authentifiée.

**Ordre effectif recommandé** : B0 → B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8, puis B9 → B10 →
B11 → B12. Rejouer B3→B8 pour chacune des trois paires P1/P2/P3.

---

## 5. Contrat d'API de référence

Routes **réellement servies** par le backend, relevées dans les modules `urls.py`. Préfixe
commun : `/api/v1/`. C'est la référence pour arbitrer tout écart FE/BE.

### Authentification — `authentication/urls.py`
> Chaque route est déclarée en double, avec et sans slash final.

| Méthode | Chemin | Vue |
|---------|--------|-----|
| POST | `auth/register` | `register_view` |
| GET | `auth/verify-email/<verification_token>` | `verify_email_view` |
| POST | `auth/login` | `login_view` |
| POST | `auth/logout` | `logout_view` |
| POST | `auth/firebase-login/` · `auth/firebase-exchange/` | `FirebaseLoginView` |
| POST | `auth/forgot-password` | `forgot_password_view` |
| POST | `auth/reset-password` | `reset_password_view` |
| POST | `auth/refresh-token/` | `refresh_token_view` |
| POST | `auth/fcm-token` | `RegisterFCMTokenView` |
| POST | `auth/report-user` | `report_user_view` |
| GET | `auth/reports` | `my_reports_view` |
| POST | `auth/reports/<report_id>/resolve` | `resolve_report_view` |

### Profils — `profiles/urls.py` (préfixe `user-profiles/`)
`me/` · `<user_id>/` · `me/photos/` · `me/photos/<photo_id>/set-main/` ·
`me/photos/<photo_id>/` · `likes-received/` · `super-likes-received/` · `premium-status/` ·
`me/verification/` · `me/verification/generate-upload-url/` ·
`me/verification/submit-documents/`

### Découverte — `matching/urls/discovery.py` (préfixe `discovery/`)
`` (racine) · `profiles` · `filters` (PUT) · `filters/get` (GET) ·
`interactions/like` · `interactions/dislike` · `interactions/superlike` ·
`interactions/super-like` · `interactions/rewind` · `interactions/liked-me` ·
`interactions/status` · `interactions/my-likes` · `interactions/my-passes` ·
`interactions/<interaction_id>/revoke` · `interactions/stats` · `boost/activate`

### Matches — `matching/urls/matches.py` (préfixe `matches/`)
`` (liste) · `<match_id>` (unmatch)

### Messagerie — `messaging/urls.py` (préfixe `conversations/`)
`` · `unread-count/` · `<conversation_id>/messages/` ·
`<conversation_id>/messages/media/` · `<conversation_id>/messages/mark-as-read/` ·
`<conversation_id>/messages/<message_id>/` · `<conversation_id>/messages/<message_id>/read/` ·
`<conversation_id>/typing/` · `<conversation_id>/presence/` ·
`calls/initiate-premium/` · `<conversation_id>/` (suppression)

### Appels — `messaging/urls_calls.py` (préfixe `calls/`)
`initiate` · `<call_id>/answer` · `<call_id>/ice-candidate` · `<call_id>/terminate`

### Contenu — `resources/urls.py` (préfixe `content/`)
`resource-categories` · `resources` · `resources/<resource_id>` ·
`resources/<resource_id>/favorite` (POST+DELETE) · `favorites`

### Feed — `resources/urls_feed.py` (préfixe `feed/`)
`posts` (×2, cf. A-01) · `posts/<post_id>/like` · `posts/<post_id>/comments` (×2, cf. A-01)

### Abonnements — `subscriptions/urls.py` (préfixe `subscriptions/`)
`plans/` · `current/` · `purchase/` · `current/cancel/` · `current/reactivate/` ·
`current/modify/` — plus le webhook `webhooks/payments/mycoolpay/`

### Notifications — `notifications/urls.py` (préfixe `notifications/`)
`` · `unread-count/` · `read-all/` · `delete-all/` · `<pk>/read/` · `<pk>/delete/`

### Paramètres — `profiles/urls_settings.py` (préfixe `user-settings/`)
> Sans slash final.

`notification-preferences` · `privacy-preferences` · `blocks` · `blocks/<user_id>` ·
`delete-account` · `export-data`

### WebSockets — `hivmeet_backend/asgi.py`

| URL | Consumer |
|-----|----------|
| `ws/conversations/<conversation_id>/` | `messaging.consumers.ConversationConsumer` |
| `ws/notifications/` | `notifications.consumers.UserNotificationConsumer` |

Authentification : en-tête `Authorization: Bearer <jwt>` ou, en repli, `?token=<jwt>` — c'est
la voie qu'emploie le client Flutter (`chat_websocket_service.dart:107`,
`notification_websocket_service.dart:82`). Codes de fermeture : `4000` token invalide,
`4001` conversation introuvable/accès refusé, `4999` erreur interne.

**Messages client → serveur** (chat) : `message.send`, `typing.start`, `typing.stop`, `ping`,
`offer`, `answer`, `ice.candidate`.
**Événements serveur → client** : `message.created`, `message.read`, `message.delivered`,
`typing.indicator`, `presence.update`, `webrtc.offer`, `webrtc.answer`, `ice.candidate`,
`incoming_call`, `call_update`, `pong`, `error`.

### Hors `/api/v1/`
`health/` · `health/simple/` · `health/ready/` · `metrics/` · `swagger/` · `redoc/` ·
`admin/` · `rosetta/`

> `swagger/` est un excellent outil de diagnostic pendant la campagne : il donne les schémas
> de sérialiseurs réels sans lire le code.

---

## 6. Règles métier de référence — gratuit vs premium

Valeurs relevées dans le code source (à considérer comme la vérité d'implémentation ; en cas
de divergence avec un document de spécification, la trancher explicitement et journaliser
la décision).

`matching/daily_likes_service.py:32-36` :

| Constante | Valeur |
|-----------|--------|
| `FREE_DAILY_LIKES_LIMIT` | **10** |
| `FREE_DAILY_SUPER_LIKES_LIMIT` | **1** |
| `PREMIUM_DAILY_SUPER_LIKES_LIMIT` | **5** |
| `UNLIMITED` | `-1` (likes premium) |

Plans d'abonnement, `subscriptions/management/commands/init_subscription_plans.py` :

| Plan | Prix | Devise | Période | Essai | Boosts/mois | Super-likes/jour |
|------|------|--------|---------|-------|-------------|------------------|
| `hivmeet_monthly` | 7,99 | EUR | mensuel | 7 j | 1 | 5 |
| `hivmeet_annual` | 57,99 | EUR | annuel | 14 j | 1 | 5 |

Les deux plans activent `unlimited_likes`, `can_see_likers`, `can_rewind`.

Matrice attendue :

| Fonctionnalité | Gratuit | Premium | Application côté backend |
|----------------|---------|---------|--------------------------|
| Likes/jour | 10 | illimité | `daily_likes_service.py` → **429** au dépassement |
| Super-likes/jour | 1 | 5 | idem → **429** |
| Rewind (annuler un swipe) | ❌ | ✅ | `views_discovery.py:413` → **403** |
| Voir qui m'a liké | ❌ | ✅ | `views_discovery.py:441` → **403** |
| Boost de profil | ❌ | ✅ | `views_discovery.py:473` → **403** |
| Filtres avancés (vérifiés seulement, en ligne seulement) | à déterminer par test | ✅ | `matching/services.py` |
| Messagerie après match | ✅ | ✅ | — |
| Appels premium | ❌ | ✅ | `conversations/calls/initiate-premium/` |
| Ressources marquées premium | ❌ | ✅ | `resource_detail_page.dart:70` |

Statuts de souscription : `pending`, `active`, `trialing`, `past_due`, `canceled`, `expired`.
`is_active` ⇔ `status ∈ {active, trialing}` (`subscriptions/models.py:339`).

---

## 7. Les blocs de test

Format d'une fiche : **ID** · objectif · préconditions · étapes (interface uniquement) ·
appel backend attendu · critères d'acceptation · vérification serveur.

---

### B0 — Infrastructure et connectivité

| ID | Test | Critères d'acceptation |
|----|------|------------------------|
| B0-01 | Backend joignable depuis l'hôte | `GET /health/simple/` → 200 ; `/health/ready/` → 200 avec DB et Redis à `ok` |
| B0-02 | Backend joignable depuis l'émulateur | `adb -s emulator-5554 shell curl -s http://10.0.2.2:8000/health/simple/` → 200 |
| B0-03 | Backend joignable depuis l'appareil physique | Depuis le TECNO, `http://<IP_HOTE>:8000/health/simple/` → 200. Si échec : pare-feu Windows, ou `runserver` non lié à `0.0.0.0`, ou IP hôte erronée |
| B0-04 | Serveur ASGI actif | La console de démarrage confirme Channels/Daphne. Un handshake WS sur `ws://127.0.0.1:8000/ws/notifications/?token=<jwt>` n'est pas refusé au niveau protocole |
| B0-05 | Channel layer opérationnel | `python manage.py shell` : `from channels.layers import get_channel_layer; get_channel_layer()` retourne bien un `RedisChannelLayer` (et non le fallback en mémoire) |
| B0-06 | Données de référence présentes | `SubscriptionPlan.objects.count() >= 2` et au moins une ressource éducative |
| B0-07 | Compilation du frontend | `flutter analyze` sans erreur bloquante ; `flutter run` installe et lance sur les deux cibles |
| B0-08 | Credentials Firebase | `credentials/hivmeet_firebase_credentials.json` présent et lisible ; `google-services.json` présent côté Android |

> ⛔ Un échec sur B0-01 à B0-05 arrête la campagne : il faut réparer l'environnement avant
> d'attribuer quoi que ce soit au code applicatif.

---

### B1 — Authentification

Le parcours réel : le client crée le compte via le SDK **Firebase Auth**, récupère un ID token,
puis appelle `POST /api/v1/auth/firebase-exchange/` qui crée/retrouve l'utilisateur Django et
retourne un JWT. Le JWT est ensuite injecté par l'intercepteur Dio
(`lib/core/network/api_client.dart:55-114`). Les chemins exclus d'authentification y sont
listés lignes 58-67.

| ID | Test | Étapes | Attendu |
|----|------|--------|---------|
| B1-01 | Inscription ALICE | Onboarding → « S'inscrire » → email/mot de passe/date de naissance/pseudo → valider | Compte créé côté Firebase ; `firebase-exchange` → 200 avec JWT ; `User` Django créé avec le bon `firebase_uid` |
| B1-01b | Inscription BOB, CARLA, DAVID | idem | idem, ×3 |
| B1-02 | Refus des moins de 18 ans | Saisir une date donnant < 18 ans | Message d'erreur clair et localisé, aucun compte créé ni côté Firebase ni côté Django |
| B1-03 | Validation du mot de passe | Mot de passe court / uniquement numérique / trop courant | Refus explicite (min. 8 caractères, cf. `AUTH_PASSWORD_VALIDATORS`) |
| B1-04 | Email déjà utilisé | Réinscription avec l'email d'ALICE | Erreur intelligible, pas de doublon en base |
| B1-05 | Après inscription | Observer la navigation | `register_page.dart:52,358` renvoie vers `/login`. **Vérifier que l'utilisateur comprend qu'il doit vérifier son email** — voir A-07 (§8.2) |
| B1-06 | Connexion nominale | Écran de connexion, identifiants d'ALICE | Redirection vers `/discovery`, JWT stocké, profil chargé |
| B1-07 | Mauvais mot de passe | | Message d'erreur localisé, pas de fuite d'information (« utilisateur inexistant » vs « mot de passe invalide ») |
| B1-08 | Persistance de session | Tuer l'application, relancer | Reconnexion automatique via le token stocké, sans ressaisie |
| B1-09 | Rafraîchissement de token | Laisser la session ouverte jusqu'à expiration de l'access token, ou forcer via `TokenManager` | Refresh transparent, aucune déconnexion visible. Vérifier `POST auth/refresh-token/` dans les logs |
| B1-10 | Rejeu après 401 | Invalider le token stocké, déclencher un appel | L'intercepteur (`_authRetryMarker`) refresh puis rejoue une seule fois ; pas de boucle infinie |
| B1-11 | Déconnexion | Profil → Déconnexion | Retour à `/login`, tokens purgés, une route protégée redirige vers `/login` |
| B1-12 | Garde de route | Déconnecté, tenter d'atteindre `/discovery`, `/matches`, `/premium` | Redirection vers `/login` (`routes.dart:97-129`) |
| B1-13 | Mot de passe oublié | Chercher le lien depuis l'écran de connexion | ⚠️ Le backend expose `auth/forgot-password` et `auth/reset-password`, mais **aucune page Flutter correspondante n'est routée**. Voir A-08 (§8.2) |
| B1-14 | Vérification d'email | Suivre le lien reçu | `GET auth/verify-email/<token>`. En dev, `EMAIL_BACKEND` est probablement console : récupérer le lien dans les logs Django. **Décisif** : sans `email_verified`, le profil n'apparaît dans aucun deck (§4) |
| B1-15 | Enregistrement du token FCM | Après connexion | `POST auth/fcm-token` émis, `FCMToken` créé en base |

---

### B2 — Profil, photos, vérification

| ID | Test | Attendu |
|----|------|---------|
| B2-01 | Consultation de mon profil | `GET user-profiles/me/` → 200 ; tous les champs affichés correspondent à la réponse |
| B2-02 | Édition du profil | `/profile/edit` : bio, ville, centres d'intérêt, types de relation recherchés → enregistrer | `PATCH user-profiles/me/` → 200, persistance après rechargement |
| B2-03 | Validation de la bio | Bio trop longue, bio avec balises HTML/script | Refus ou nettoyage ; aucune injection stockée |
| B2-04 | Préférences de découverte | Tranche d'âge, distance max, genres recherchés, types de relation | Persistées et rechargées à l'identique |
| B2-05 | Ajout de photo (galerie) | `/profile/photos` → ajouter | `POST user-profiles/me/photos/` → 201, photo affichée, fichier présent côté serveur |
| B2-06 | Ajout de photo (caméra) | idem, source caméra | **Réservé à l'appareil physique** (§9). Sur émulateur, la caméra virtuelle est acceptable en secours |
| B2-07 | Photo principale | Sélectionner une photo → « définir comme principale » | `PUT .../set-main/` → 200 ; c'est bien cette photo qui apparaît dans le deck des autres |
| B2-08 | Suppression de photo | | `DELETE .../photos/<id>/` → 204 ; le profil reste cohérent |
| B2-09 | Limite de photos | Dépasser le maximum autorisé | Message clair, pas d'erreur 500. Relever la limite réelle dans `profiles/models.py` et la consigner |
| B2-10 | Profil sans photo | Supprimer toutes les photos | L'application ne plante pas ; comportement dans le deck des autres à vérifier et documenter |
| B2-11 | Statut de vérification | `/verification` | `GET user-profiles/me/verification/` → statut cohérent |
| B2-12 | Soumission de vérification | Suivre le parcours complet | `POST .../generate-upload-url/` puis `.../submit-documents/` → statut passe en attente |
| B2-13 | Profil public d'un tiers | Ouvrir le profil de BOB depuis le deck | `GET user-profiles/<user_id>/` → **aucune donnée sensible non autorisée** (email, statut VIH si privé). Comparer méticuleusement la réponse à ce qui est affiché |
| B2-14 | Visibilité en découverte | Basculer `allow_profile_in_discovery` / `is_hidden` depuis les paramètres | Le profil disparaît puis réapparaît dans le deck de l'autre compte |

---

### B3 — Découverte, filtres et quotas

Cœur fonctionnel. Filtres appliqués côté serveur (`matching/services.py`, ~lignes 150-260) :
exclusion de soi-même, des profils déjà vus, des comptes inactifs ou à email non vérifié, des
profils masqués ou hors découverte ; puis âge, genre (réciproque), type de relation, distance,
« vérifiés seulement », « en ligne seulement » (5 dernières minutes) ; puis priorisation des
profils boostés.

| ID | Test | Attendu |
|----|------|---------|
| B3-01 | Chargement du deck | `GET discovery/profiles` → 200 ; les cartes affichées correspondent aux profils retournés |
| B3-02 | Deck vide | Épuiser le deck | État vide explicite et localisé, pas d'écran blanc ni de spinner infini |
| B3-03 | Contenu de la carte | | Photo, prénom, âge, distance, badges. Comparer champ à champ avec la réponse serveur (`matching/serializers.py`) |
| B3-04 | Détail d'un profil | Tap sur une carte | Ouverture de `/profile-detail`, toutes les données présentes |
| B3-05 | Swipe droite = like | Geste de swipe | `POST discovery/interactions/like` → 201 ; `InteractionHistory` créé |
| B3-06 | Swipe gauche = dislike | | `POST discovery/interactions/dislike` ; le profil ne réapparaît plus |
| B3-07 | Compteur de likes (gratuit) | ALICE, 3 likes | Compteur 10 → 9 → 8 → 7, cohérent avec `daily_likes_remaining` de la réponse |
| B3-08 | **Quota atteint (gratuit)** | ALICE, 11ᵉ like | **429**, message clair proposant le premium, pas de crash. Vérifier que le 11ᵉ like n'est **pas** enregistré en base |
| B3-09 | Likes illimités (premium) | CARLA, > 15 likes | Aucun blocage ; `daily_likes_limit` à `null`/illimité |
| B3-10 | Super-like (gratuit) | ALICE, 1 super-like puis un 2ᵉ | Le 1ᵉʳ passe ; le 2ᵉ → **429** avec message explicite |
| B3-11 | Super-like (premium) | CARLA, 5 puis un 6ᵉ | Les 5 passent, le 6ᵉ → 429 |
| B3-12 | **Rewind (gratuit)** | ALICE, après un swipe | ⚠️ `discovery_page.dart:199` affiche le bouton dès que `canRewind` (= `_currentIndex > 0`), **sans vérifier le premium**, alors que le backend répond **403**. Voir A-04 (§8.2). Attendu après correction : bouton absent ou paywall, jamais une erreur brute |
| B3-13 | Rewind (premium) | CARLA | `POST discovery/interactions/rewind` → 200 ; le profil précédent revient ; l'interaction est bien annulée en base |
| B3-14 | Filtre d'âge | `/discovery/filters` : 30-35 | `PUT discovery/filters` → 200 ; aucun profil hors bornes dans le deck rechargé |
| B3-15 | Filtre de genre | Changer les genres recherchés | Deck cohérent **dans les deux sens** : la réciprocité est appliquée serveur (`genders_sought`) |
| B3-16 | Filtre de distance | Réduire à 5 km | Deck réduit en conséquence ; vérifier avec des profils de villes différentes du script de peuplement |
| B3-17 | Filtres avancés (gratuit) | « Vérifiés seulement », « En ligne seulement » | Comportement attendu selon la spec : paywall ou filtre ignoré. **Documenter le comportement réel** et trancher |
| B3-18 | Filtres avancés (premium) | idem avec CARLA | Filtres réellement appliqués (vérifiable dans les logs `matching/services.py`, très verbeux) |
| B3-19 | Persistance des filtres | Régler, quitter, revenir | `GET discovery/filters/get` restitue les mêmes valeurs |
| B3-20 | Boost (gratuit) | ALICE tente un boost | **403** avec paywall, pas d'erreur brute |
| B3-21 | Boost (premium) | CARLA active un boost | `POST discovery/boost/activate` → 200 ; le profil de CARLA remonte en tête du deck de DAVID ; le quota mensuel décroît |
| B3-22 | Pas d'auto-affichage | | ALICE ne se voit jamais elle-même |
| B3-23 | Pas de répétition | Recharger plusieurs fois | Aucun profil déjà swipé ne revient (sauf après rewind) |
| B3-24 | Pagination / cyclage | Parcourir un deck long | Chargement continu sans doublon ni saut |
| B3-25 | Réinitialisation quotidienne | Reculer `DailyLikeLimit` d'un jour en base, ou attendre minuit UTC | Le quota d'ALICE repasse à 10 |

---

### B4 — Matching

| ID | Test | Attendu |
|----|------|---------|
| B4-01 | Like non réciproque | ALICE like BOB, BOB n'a rien fait | Pas de match ; réponse `is_match: false` |
| B4-02 | **Match réciproque** | BOB like ALICE en retour (2 appareils) | Match créé **une seule fois** ; animation « C'est un match ! » sur les **deux** appareils ; conversation créée |
| B4-03 | Concurrence | Les deux likes émis quasi simultanément | Un seul `Match` en base. La spec (`CLAUDE.md`) impose `get_or_create` sous transaction — vérifier |
| B4-04 | Liste des matches | `/matches` | `GET matches/` → 200 ; ALICE et BOB s'y voient mutuellement |
| B4-05 | Match par super-like | ALICE super-like DAVID, DAVID like ALICE | Match créé ; le super-like est distingué visuellement |
| B4-06 | Unmatch | Depuis la fiche du match | `DELETE matches/<match_id>` → 204 ; disparition **des deux côtés** ; sort du deck ; conversation traitée conformément à la spec |
| B4-07 | Aucun match | Compte neuf | État vide explicite et localisé |
| B4-08 | Notification de match | | Notification produite pour les deux (vérifiée en B8) |
| B4-09 | Matrice des paires | Rejouer B4-02 pour P1, P2, P3 | Comportement identique quel que soit le type de compte |

---

### B5 — Historique d'interactions et découverte premium

| ID | Test | Attendu |
|----|------|---------|
| B5-01 | Mes likes | `/interaction-history/likes` | `GET discovery/interactions/my-likes` → liste exacte des profils likés |
| B5-02 | Mes passes | `/interaction-history/passes` | `GET .../my-passes` → liste des profils rejetés |
| B5-03 | Statistiques | `/interaction-history/stats` | `GET .../stats` → chiffres cohérents avec les compteurs réels en base |
| B5-04 | Révocation d'une interaction | Annuler un like depuis l'historique | `POST .../<interaction_id>/revoke` → l'interaction disparaît ; le profil redevient éligible au deck ; **le quota quotidien est-il recrédité ?** Trancher et documenter |
| B5-05 | **Qui m'a liké (gratuit)** | ALICE ouvre `/likes-received` | Paywall (`likes_received_page.dart:56-136` gère `premium-required`) ; **403** côté serveur ; aucune identité divulguée, même partiellement, même floutée dans la charge JSON |
| B5-06 | Qui m'a liké (premium) | CARLA, après qu'ALICE l'ait likée | `GET user-profiles/likes-received/` → 200 ; ALICE visible |
| B5-07 | Super-likes reçus | | `GET user-profiles/super-likes-received/` → cohérent |
| B5-08 | Statut premium | | `GET user-profiles/premium-status/` reflète l'état exact et **immédiatement** après changement (cf. A-06) |

---

### B6 — Messagerie (REST)

| ID | Test | Attendu |
|----|------|---------|
| B6-01 | Liste des conversations | `/conversations` | `GET conversations/` → 200 ; une entrée par match |
| B6-02 | Ouverture d'une conversation | | `GET conversations/<id>/messages/` → historique, pagination correcte |
| B6-03 | Envoi d'un message texte | Saisir, envoyer | `POST conversations/<id>/messages/` → 201 ; affiché immédiatement côté émetteur ; reçu côté destinataire |
| B6-04 | Message vide / espaces | | Envoi refusé côté client, sans appel serveur |
| B6-05 | Message très long | | Limite appliquée avec message clair, jamais de 500 |
| B6-06 | Sanitisation | Envoyer `<script>alert(1)</script>` | Stocké et rendu comme texte inerte des deux côtés |
| B6-07 | Message média | Joindre une image | `POST .../messages/media/` → 201 ; image affichée chez le destinataire |
| B6-08 | Média et premium | Tester avec ALICE (gratuite) | Le modèle `User` expose `can_send_media` : vérifier si la restriction est appliquée, et la cohérence entre UI et serveur |
| B6-09 | Marquer comme lu | Ouvrir une conversation non lue | `POST .../mark-as-read/` ; le compteur non-lus retombe à 0 |
| B6-10 | Compteur global | | `GET conversations/unread-count/` cohérent avec la pastille de l'onglet Messages |
| B6-11 | Accusé de lecture unitaire | | `POST .../messages/<id>/read/` ; indicateur visible chez l'émetteur |
| B6-12 | Accusés et premium | Paire P2 (gratuit × premium) | Vérifier l'asymétrie éventuelle et sa cohérence avec la spec |
| B6-13 | Suppression d'un message | Appui long → supprimer | `DELETE .../messages/<id>/` → disparaît ; comportement chez l'autre conforme à la spec |
| B6-14 | Suppression d'une conversation | | `DELETE conversations/<id>/` → 204 ; effet côté interlocuteur conforme à la spec |
| B6-15 | Messagerie hors match | Forger une requête vers la conversation d'un tiers | **403/404** — jamais 200. Test de sécurité, autorisé ici en direct via curl |
| B6-16 | Après unmatch | | La conversation devient inaccessible conformément à la spec |
| B6-17 | Matrice des paires | Rejouer B6-03/07/09 pour P1, P2, P3 | Cohérence |

---

### B7 — Temps réel (WebSocket)

**Prérequis** : deux appareils actifs simultanément sur la même conversation, et B0-04/B0-05
au vert.

| ID | Test | Attendu |
|----|------|---------|
| B7-01 | Connexion WS chat | Ouvrir une conversation | Connexion à `ws/conversations/<id>/?token=<jwt>` acceptée ; visible dans les logs Django |
| B7-02 | Connexion WS notifications | Après connexion | `ws/notifications/?token=<jwt>` acceptée |
| B7-03 | WS sans token | Retirer le token (diagnostic direct) | Fermeture **4000** |
| B7-04 | WS sur conversation d'un tiers | | Fermeture **4001**. Test de sécurité |
| B7-05 | **Livraison temps réel** | ALICE envoie, BOB a la conversation ouverte | Message affiché chez BOB **sans rafraîchissement** ; événement `message.created` |
| B7-06 | Indicateur de saisie | ALICE tape | « en train d'écrire… » chez BOB ; `typing.start` / `typing.stop` ; extinction après arrêt |
| B7-07 | Présence | BOB ouvre puis quitte la conversation | `presence.update` reçu ; statut en ligne/hors ligne correct |
| B7-08 | Accusé de lecture temps réel | BOB lit | `message.read` reçu par ALICE, coche mise à jour instantanément |
| B7-09 | Keep-alive | Laisser ouvert plusieurs minutes | `ping` → `pong` ; la connexion tient |
| B7-10 | Reconnexion | Couper le Wi-Fi 30 s puis rétablir | Reconnexion automatique ; les messages manqués sont récupérés ; **aucun doublon** |
| B7-11 | Token expiré en WS | Attendre l'expiration | Reconnexion avec un token frais, conformément à la documentation du consumer |
| B7-12 | Appel — initiation | Depuis le chat, lancer un appel | `POST calls/initiate` ; `incoming_call` reçu par le destinataire |
| B7-13 | Appel — signalisation WebRTC | Accepter | `offer` / `answer` / `ice.candidate` échangés ; `POST calls/<id>/answer` |
| B7-14 | Appel — fin | Raccrocher | `POST calls/<id>/terminate` ; `call_update` reçu ; les deux UI reviennent à l'état normal |
| B7-15 | Appel premium | ALICE (gratuite) tente un appel | Paywall ou 403 cohérent ; `conversations/calls/initiate-premium/` |
| B7-16 | Deux appareils, même compte | Connecter ALICE sur émulateur **et** TECNO | Comportement conforme à la spec (diffusion sur les deux ? éviction ?). Documenter |

---

### B8 — Notifications

| ID | Test | Attendu |
|----|------|---------|
| B8-01 | Liste | `/notifications` | `GET notifications/` → 200, pagination gérée (`notification_api.dart` accepte liste **ou** objet paginé) |
| B8-02 | Compteur non lus | | `GET notifications/unread-count/` cohérent avec la pastille |
| B8-03 | Notification de match | Provoquer un match | Notification créée pour les deux, avec le bon libellé |
| B8-04 | Notification de message | Envoyer un message à un destinataire hors de la conversation | Notification produite |
| B8-05 | Notification de like reçu | | Conforme à la spec (peut être réservée au premium) |
| B8-06 | Marquer une notification lue | Tap | `PUT notifications/<id>/read/` ; compteur décrémenté |
| B8-07 | Tout marquer lu | | `PUT notifications/read-all/` ; compteur à 0 |
| B8-08 | Supprimer une notification | | `DELETE notifications/<id>/delete/` |
| B8-09 | Tout supprimer | | `DELETE notifications/delete-all/` ; liste vide |
| B8-10 | Navigation depuis la notification | Tap sur « nouveau message » | Ouvre la bonne conversation |
| B8-11 | Préférences | `/profile/notifications` | `GET`/`PUT user-settings/notification-preferences` ; désactiver un type le supprime effectivement |
| B8-12 | **Push FCM, app en arrière-plan** | Mettre en arrière-plan, provoquer un match | Notification système affichée. **Appareil physique privilégié** (§9) |
| B8-13 | **Push FCM, app fermée** | Tuer l'application | Notification système reçue ; le tap ouvre l'application au bon endroit |
| B8-14 | Pas de doublon | App au premier plan avec WS actif **et** FCM | `realtime_event_bus.dart` déduplique : une seule notification visible |

---

### B9 — Ressources et feed communautaire

| ID | Test | Attendu |
|----|------|---------|
| B9-01 | Liste des ressources | `/resources` | `GET content/resources` → 200 ; contenu affiché |
| B9-02 | Catégories | | `GET content/resource-categories` → filtrage fonctionnel |
| B9-03 | Détail d'une ressource | | `GET content/resources/<id>` → contenu complet |
| B9-04 | Favori | Bouton favori | `POST content/resources/<id>/favorite` ; retrouvé dans `GET content/favorites` |
| B9-05 | Retrait de favori | | `DELETE content/resources/<id>/favorite` (la vue accepte POST et DELETE) |
| B9-06 | Ressource premium (gratuit) | ALICE ouvre une ressource premium | Paywall (`resource_detail_page.dart:70`) |
| B9-07 | Ressource premium (premium) | CARLA | Accès complet |
| B9-08 | **Feed — liste** | `/feed` | ⚠️ **A-01** : `GET feed/posts` est masqué par la route de création. Attendu **actuel** : 405. Attendu **après correction** : 200 avec la liste |
| B9-09 | Feed — création | Publier un post | `POST feed/posts` → 201 ; visible chez l'autre compte |
| B9-10 | Feed — like | | `POST feed/posts/<id>/like` |
| B9-11 | Feed — retrait de like | | ⚠️ Le client émet un `DELETE` mais la vue n'accepte que POST (bascule). Voir A-02 |
| B9-12 | **Feed — commentaires (lecture)** | Ouvrir les commentaires | ⚠️ **A-01** : `GET feed/posts/<id>/comments` masqué. Actuel : 405. Après correction : 200 |
| B9-13 | Feed — ajout de commentaire | | `POST feed/posts/<id>/comments` → 201 |
| B9-14 | Feed — signalement de post | | ⚠️ Route absente côté backend. Voir A-03 |
| B9-15 | Recherche de contenu | Barre de recherche, si présente dans l'UI | ⚠️ `GET content/search` n'existe pas côté backend. Voir A-03 |

---

### B10 — Abonnements et premium

#### Passe 1 — fonctionnalités, avec octroi direct (§3.3)

| ID | Test | Attendu |
|----|------|---------|
| B10-01 | Écran Premium | `/premium` | `GET subscriptions/plans/` → les deux plans affichés avec prix (7,99 €/mois, 57,99 €/an), essai et avantages corrects |
| B10-02 | Abonnement courant (gratuit) | | `GET subscriptions/current/` → absence d'abonnement gérée proprement |
| B10-03 | Abonnement courant (premium) | CARLA | Plan, statut et date d'échéance corrects |
| B10-04 | Bascule gratuit → premium | Élever ALICE pendant que l'app tourne, puis rafraîchir | Toutes les fonctionnalités premium s'ouvrent (rewind, qui m'a liké, boost, likes illimités). **Mesurer le délai** : cache de 5 min possible (A-06) |
| B10-05 | Bascule premium → gratuit | Rétrograder CARLA | Les fonctionnalités se referment proprement ; **aucun crash**, aucune donnée premium résiduelle affichée |
| B10-06 | Annulation | | `POST subscriptions/current/cancel/` → statut `canceled` ; accès maintenu jusqu'à l'échéance (à confirmer par la spec) |
| B10-07 | Réactivation | | `POST subscriptions/current/reactivate/` → retour en `active` |
| B10-08 | Changement de plan | Mensuel → annuel | `POST subscriptions/current/modify/` |
| B10-09 | Expiration | Reculer `premium_until` et `current_period_end` dans le passé, purger le cache, lancer `check_subscription_expirations` | Retour à l'état gratuit, sans brutalité côté UI |
| B10-10 | Période d'essai | Souscription en `trialing` | Traitée comme premium (`is_active` inclut `trialing`) |

#### Passe 2 — parcours d'achat réel

| ID | Test | Attendu |
|----|------|---------|
| B10-20 | Achat depuis l'application | ALICE → Premium → choisir un plan → payer | `POST subscriptions/purchase/` ; le client passe par `payment_service.dart` (`https://api.mycoolpay.com/v1`) |
| B10-21 | Webhook de paiement | Paiement confirmé | `POST /api/v1/webhooks/payments/mycoolpay/` reçu et traité ; souscription passée en `active` ; `Payment` créé en `succeeded` |
| B10-22 | Idempotence du webhook | Rejouer le même webhook | Aucun double crédit, aucune double souscription |
| B10-23 | Paiement échoué | Simuler un échec | Statut `failed` ; l'utilisateur reste gratuit ; message clair |
| B10-24 | Retour dans l'application | Après paiement | L'UI reflète le premium sans nécessiter une reconnexion manuelle |
| B10-25 | Sécurité du webhook | Poster un webhook non signé ou falsifié | Rejeté. Test de sécurité |

> Si le sandbox MyCoolPay ou ses credentials sont indisponibles, marquer B10-20 à B10-24 ⛔ en
> le documentant précisément, mais **exécuter tout de même B10-21/22/25** en postant
> directement des charges utiles au webhook — c'est la partie backend, testable isolément.

---

### B11 — Paramètres, confidentialité, modération, RGPD

| ID | Test | Attendu |
|----|------|---------|
| B11-01 | Préférences de confidentialité | `/profile/privacy` | `GET user-settings/privacy-preferences` ; les modifications persistent (vérifier la présence d'un PUT côté client) |
| B11-02 | Bloquer un utilisateur | Depuis un profil ou un chat | `POST user-settings/blocks/<user_id>` ; disparaît du deck, des matches et des conversations, **des deux côtés** |
| B11-03 | Liste des bloqués | `/profile/blocked-users` | `GET user-settings/blocks` |
| B11-04 | Débloquer | | `DELETE user-settings/blocks/<user_id>` ; le profil redevient visible |
| B11-05 | Blocage et découverte | Après blocage | Le bloqué n'apparaît plus jamais dans le deck, dans aucun des deux sens |
| B11-06 | Signaler un utilisateur | Choisir un motif | `POST auth/report-user` → 201 ; `Report` créé |
| B11-07 | Mes signalements | | `GET auth/reports` |
| B11-08 | Export de données (RGPD) | `/profile/data` | `GET user-settings/export-data` → export complet et lisible ; contrôler qu'il ne contient **que** les données de l'utilisateur |
| B11-09 | Suppression de compte | Parcours complet avec confirmation | `POST user-settings/delete-account` ; l'utilisateur disparaît du deck des autres ; ses conversations sont traitées conformément à la spec ; **aucune donnée sensible orpheline** |
| B11-10 | Après suppression | Tenter de se reconnecter | Refus propre |
| B11-11 | Pages légales | `/privacy`, `/terms`, `/about` | S'affichent, contenu localisé |

---

### B12 — Robustesse, i18n, accessibilité, performance

| ID | Test | Attendu |
|----|------|---------|
| B12-01 | Backend arrêté | Couper `runserver`, utiliser l'app | Message d'erreur intelligible partout, jamais d'écran blanc ni de trace technique brute |
| B12-02 | Réseau coupé | Mode avion | Message hors ligne ; reprise correcte au retour du réseau |
| B12-03 | Réseau lent | `adb shell settings put global ...` ou throttling de l'émulateur | Indicateurs de chargement présents ; pas de double soumission |
| B12-04 | Timeout | Suspendre le serveur pendant une requête | Le timeout Dio (30 s) est atteint et traité proprement |
| B12-05 | Rotation d'écran | Sur chaque écran principal | Aucun état perdu, aucun crash |
| B12-06 | Arrière-plan / retour | Sur chaque écran principal | État restauré, WS reconnecté |
| B12-07 | Bouton retour Android | Depuis chaque écran | Navigation cohérente ; pas de sortie inattendue de l'application |
| B12-08 | Bascule FR → EN | Changer la langue système ou l'option in-app | Toute l'interface bascule. Les traductions vivent dans `assets/translations/{fr,en}.json` ; l'en-tête `Accept-Language` est envoyé par `ApiClient` et Django a `LocaleMiddleware` : **les messages d'erreur serveur doivent aussi basculer** |
| B12-09 | Chaînes en dur | Parcourir toute l'application en anglais | ⚠️ Départ connu : `hiv_bottom_navigation.dart:152-177` contient « Découverte », « Matches », « Messages », « Ressources », « Profil » en dur. Relever toutes les occurrences |
| B12-10 | Route inexistante | Naviguer vers `/home` (constante `AppRoutes.home` déclarée mais **aucune `GoRoute` correspondante**) | Page d'erreur propre. Vérifier qu'aucun code de l'app ne navigue vers `/home` — sinon c'est un défaut |
| B12-11 | Pages non routées | `create_profile.dart`, `resource_detail_page.dart`, `simple_splash_page.dart` n'ont pas de `GoRoute` | Déterminer si elles sont atteintes par navigation directe ou si c'est du code mort. Documenter |
| B12-12 | Fluidité du deck | Swiper rapidement 20 profils | Pas de saccade ni de fuite mémoire visible |
| B12-13 | Longue conversation | 100+ messages | Défilement fluide, pagination correcte |
| B12-14 | Accessibilité | Activer TalkBack | Éléments interactifs annoncés ; contrastes suffisants |
| B12-15 | Double-tap rapide | Sur les boutons d'envoi, de like, d'achat | Pas de double soumission |
| B12-16 | Limitation de débit | Enchaîner très rapidement les appels | **429** géré proprement côté client. Voir `BACKEND_RATE_LIMITING_PROBLEME.md` |

---

## 8. Zone rouge — anomalies identifiées avant exécution

Issues d'une analyse statique du code, **non encore confirmées à l'exécution**. À traiter en
priorité : elles expliqueront probablement une bonne partie des échecs.

### 8.1 Écarts de contrat : appels client sans route serveur

Le client Flutter émet des requêtes vers des chemins absents des `urls.py`. Ils produiront
**404** (ou 405) s'ils sont réellement déclenchés par l'interface.

| Appel client | Fichier client | Route backend |
|--------------|----------------|---------------|
| `GET/PUT /auth/me` | `auth_api.dart:563,581` | absente |
| `POST /auth/change-password` | `auth_api.dart:595` | absente |
| `DELETE /auth/delete-account` | `auth_api.dart:614` | absente (l'équivalent est `user-settings/delete-account`) |
| `POST/DELETE /auth/block-user`, `GET /auth/blocked-users` | `auth_api.dart:659,667,678` | absentes (équivalent : `user-settings/blocks`) |
| `POST /auth/verify-email` | `auth_api.dart:551` | seul `GET auth/verify-email/<token>` existe |
| `POST /auth/resend-verification` | `auth_api.dart:557` | absente |
| `GET /discovery/boost/status` | `matching_api.dart:179` | absente (seul `boost/activate`) |
| `POST /subscriptions/use-boost`, `use-super-like` | `subscriptions_api.dart:50,58` | absentes |
| `GET /subscriptions/premium-stats`, `features-usage`, `available-features` | `subscriptions_api.dart:66,72,78` | absentes |
| `GET /subscriptions/validate-payment/<id>` | `subscriptions_api.dart:97` | absente |
| `GET /content/categories`, `/content/search`, `/content/recently-viewed`, `/content/reading-stats` | `resources_api.dart:160,267,193,244` | absentes |
| `POST /content/resources/<id>/read`, `/like`, `/bookmark`, `/share` | `resources_api.dart:167,214,222,237` | absentes |
| `POST /feed/posts/<id>/report` | `resources_api.dart:140` | absente |

**Méthode de traitement.** Pour chacun, dans cet ordre :
1. Chercher les appelants (`grep` du nom de méthode dans `lib/presentation` et
   `lib/data/repositories`).
2. **Aucun appelant** → code mort. Le supprimer, ou le marquer `@Deprecated` avec un
   commentaire. Ne pas créer d'endpoint backend « au cas où ».
3. **Appelant existant et fonctionnalité présentée à l'utilisateur** → défaut réel. Décider :
   - un équivalent backend existe (`/auth/block-user` → `user-settings/blocks/<id>`) → **corriger
     le client** pour viser la bonne route ;
   - aucun équivalent et la fonctionnalité est au contrat → **implémenter la route backend**
     conformément à `docs/API_DOCUMENTATION.md` et aux conventions du projet ;
   - la fonctionnalité n'est pas au contrat → **retirer l'élément d'interface** plutôt que de
     laisser un bouton qui échoue.

### 8.2 Anomalies de logique

| Réf | Anomalie | Localisation | Impact attendu |
|-----|----------|--------------|----------------|
| **A-01** | Routes masquées dans le feed : `path('posts', create_feed_post)` est déclaré **avant** `path('posts', get_feed_posts)`, et `path('posts/<uuid>/comments', add_comment)` avant `get_post_comments`. Django résolvant sur le chemin seul, la première déclaration l'emporte. Or `create_feed_post` et `add_comment` sont `@api_view(['POST'])` | `resources/urls_feed.py:11-17`, `resources/views.py:217,256,320,356` | **`GET /feed/posts` et `GET /feed/posts/<id>/comments` renvoient 405.** Le feed communautaire est inutilisable en lecture. Correction : fusionner en une route par chemin acceptant `['GET','POST']`, ou distinguer les chemins |
| **A-02** | `DELETE /feed/posts/<id>/like` émis par le client, mais `toggle_post_like` est `@api_view(['POST'])` | `resources_api.dart:208` / `resources/views.py:294` | 405 au retrait de like. Corriger d'un côté ou de l'autre selon la sémantique voulue (bascule vs verbes explicites) |
| **A-03** | Signalement de post et recherche de contenu appelés côté client, sans route serveur | cf. §8.1 | 404 si l'UI les expose |
| **A-04** | Le bouton Rewind s'affiche sur la seule condition `canRewind = _currentIndex > 0`, sans vérification du premium, alors que le serveur répond 403 aux non-premium | `discovery_page.dart:199`, `discovery_bloc.dart:532` vs `matching/views_discovery.py:413` | Un utilisateur gratuit voit un bouton qui échoue. Attendu : masquer, ou afficher un paywall explicite |
| **A-05** | **Trois définitions concurrentes du statut premium** : (a) `subscriptions/utils.is_premium_user()` exige `user.is_premium` **et** `premium_until > now` ; (b) `DailyLikesService.is_premium_user()` accepte `user.is_premium` seul **ou** une souscription active ; (c) `views_discovery.py` teste `request.user.is_premium` brut | `subscriptions/utils.py`, `matching/daily_likes_service.py:39-63`, `matching/views_discovery.py:413,441,473` | États incohérents : un utilisateur avec `is_premium=True` et `premium_until=None` est premium pour les quotas de likes mais pas ailleurs. Converger vers **une seule** source de vérité |
| **A-06** | Le statut premium est mis en cache 5 minutes (`PREMIUM_STATUS_CACHE_TTL`) sans invalidation évidente à l'achat | `subscriptions/utils.py` | Après un achat réussi, les fonctionnalités peuvent rester fermées jusqu'à 5 minutes. Invalider le cache à chaque transition d'abonnement |
| **A-07** | Après inscription, le client renvoie vers `/login` sans écran de vérification d'email, alors que la découverte filtre sur `email_verified` | `register_page.dart:52,358` vs `matching/services.py` | Un nouvel utilisateur peut se connecter, ne rien comprendre à son absence du deck des autres, et n'être jamais invité à vérifier son email |
| **A-08** | Le backend expose `auth/forgot-password` et `auth/reset-password`, mais aucune page Flutter n'est routée pour le mot de passe oublié | `authentication/urls.py:28-31` vs `lib/core/config/routes.dart` | Fonctionnalité de récupération de compte inaccessible |
| **A-09** | `AppRoutes.home = '/home'` déclarée sans `GoRoute` correspondante | `routes.dart:51` | Toute navigation vers `/home` tombe sur la page d'erreur |
| **A-10** | Libellés de la barre de navigation en dur, en français | `hiv_bottom_navigation.dart:152-177` | La navigation ne se traduit pas en anglais |
| **A-11** | `AppConfig.profiles` vaut `/profiles/` alors que le backend sert `/user-profiles/` | `app_config.dart:167` | Piège si cette constante est utilisée ; vérifier ses appelants |
| **A-12** | IP de l'appareil physique codée en dur à `192.168.1.118` | `app_config.dart:90` | Échec réseau systématique sur appareil physique si l'hôte a une autre IP. Contournable par `--dart-define` (§2.3), mais la valeur en dur mérite d'être remplacée par une configuration explicite |
| **A-13** | `CORS_ALLOW_ALL_ORIGINS = True` et `ALLOWED_HOSTS` contenant `*` | `settings.py:212,20` | Acceptable en développement, **inacceptable en production**. À consigner comme dette de sécurité, sans modifier le comportement de développement pendant la campagne |

### 8.3 Rapports antérieurs à consulter au besoin

Les deux dépôts contiennent des dizaines de rapports de correction. **Ne pas les lire par
avance** — c'est un puits sans fond de contexte et beaucoup décrivent des problèmes déjà
résolus. En revanche, **quand un test échoue**, chercher un rapport correspondant : il
contient souvent le diagnostic déjà fait.

```bash
ls /d/Projets/HIVMeet/env/hivmeet_backend/*.md | grep -iE "discovery|likes|filter|messag|premium|notification"
grep -ril "<mot-clé du symptôme>" /d/Projets/HIVMeet/env/hivmeet_backend/*.md /d/Projets/HIVMeet/hivmeet/*.md
```

Documents structurants, à consulter en priorité pour arbitrer une spécification :
`docs/API_DOCUMENTATION.md` (référence de contrat), `docs/backend-specs.md`,
`docs/Document de Spécification Interface - HIVMeet.txt`, `docs/FRONTEND_*_API.md`,
`ENDPOINTS_COMPLETE_DOCUMENTATION.md`.

---

## 9. Sous-ensemble réservé à l'appareil physique

L'ensemble des blocs s'exécute sur émulateur. Le TECNO KF7j rejoue le sous-ensemble suivant,
qui ne peut pas être validé fidèlement sur émulateur :

| Test physique | Origine | Pourquoi l'émulateur ne suffit pas |
|---------------|---------|-----------------------------------|
| PH-01 | B2-06 | Caméra réelle : capture, orientation EXIF, poids du fichier, permissions Android |
| PH-02 | B2-05 | Galerie réelle, photos volumineuses, permissions de stockage |
| PH-03 | B8-12/13 | Push FCM réel avec l'application en arrière-plan puis fermée — l'émulateur sans Play Services ne le reproduit pas |
| PH-04 | B7-05..11 | WebSocket sur Wi-Fi réel : latence, coupures, transitions réseau |
| PH-05 | B12-02 | Bascule Wi-Fi ↔ données mobiles en cours de session |
| PH-06 | B3-14/16 | Géolocalisation réelle et filtre de distance |
| PH-07 | B7-12..15 | Appels : microphone, haut-parleur, permissions, comportement en appel entrant système |
| PH-08 | B12-12/13 | Performance réelle sur matériel modeste |
| PH-09 | B12-14 | TalkBack sur appareil réel |
| PH-10 | B12-05/06 | Cycle de vie réel : appel entrant, notification système, verrouillage d'écran |
| PH-11 | — | Consommation batterie sur une session de 15 min (`adb shell dumpsys batterystats`) |

**Rappel** : lancer avec `--dart-define=API_URL=http://<IP_HOTE_LAN>:8000` (§2.3).

---

## 10. Séquence d'exécution recommandée

| Étape | Contenu | Configuration |
|-------|---------|---------------|
| 1 | B0 complet | Hôte seul |
| 2 | B1, B2 pour ALICE et BOB | Émulateur A |
| 3 | B1, B2 pour CARLA et DAVID | Émulateur A |
| 4 | Élévation premium de CARLA et DAVID (§3.3) | Shell Django |
| 5 | B3 avec ALICE (gratuit) puis CARLA (premium) | Émulateur A |
| 6 | **Paire P1** — B4 à B8, ALICE ↔ BOB | Émulateurs A + B |
| 7 | `reset_test_interactions` | Shell Django |
| 8 | **Paire P2** — B4 à B8, ALICE ↔ DAVID | Émulateurs A + B |
| 9 | `reset_test_interactions` | Shell Django |
| 10 | **Paire P3** — B4 à B8, CARLA ↔ DAVID | Émulateurs A + B |
| 11 | B5 (historique et découverte premium) | Émulateur A |
| 12 | B9 (ressources et feed) | Émulateurs A + B |
| 13 | B10 passe 1 (octroi direct) | Émulateur A + shell |
| 14 | B10 passe 2 (achat réel + webhook) | Émulateur A + shell |
| 15 | B11 (paramètres, RGPD, modération) | Émulateurs A + B |
| 16 | B12 (robustesse, i18n, perfs) | Émulateur A |
| 17 | PH-01 à PH-11 | TECNO physique |
| 18 | Rejeu de régression : tous les tests marqués 🔧 | Émulateur A (+ B si nécessaire) |
| 19 | Rapport final | — |

> L'étape 18 n'est pas optionnelle. Une correction tardive peut réintroduire un défaut réparé
> plus tôt. Rejouer l'intégralité des tests corrigés, dans l'ordre, à la fin de la campagne.

---

## 11. Critères de sortie

La campagne est terminée quand **tous** les points suivants sont vrais :

1. Chaque test de B0 à B12 porte un statut ✅, 🔧 (corrigé **et** revalidé) ou ⛔ (bloqué,
   avec justification technique explicite).
2. Chaque test PH-01 à PH-11 a été exécuté sur l'appareil physique.
3. Chacune des trois paires P1, P2, P3 a parcouru B4 à B8 intégralement.
4. Chaque anomalie A-01 à A-13 est **résolue** ou **explicitement documentée** avec la
   décision prise et sa justification.
5. Chaque appel client de §8.1 est tranché : route créée, client corrigé, ou code mort
   supprimé.
6. Le rapport `RAPPORT_TESTS_E2E.md` est complet, avec captures d'écran pour tout test 🔧.
7. Aucune régression : la suite de tests automatisés du backend passe toujours.
   ```bash
   cd /d/Projets/HIVMeet/env/hivmeet_backend
   python -m pytest tests/ authentication/ matching/ messaging/ profiles/ subscriptions/ notifications/ resources/ -v
   ```
   > Il n'existe ni `pytest.ini`, ni `pyproject.toml`, ni `conftest.py` racine. Si pytest ne
   > se configure pas seul, se replier sur `python manage.py test`, et **créer la
   > configuration pytest manquante** — c'est en soi une amélioration légitime.
   >
   > Attention : la racine du backend contient une trentaine de scripts `test_*.py` qui sont
   > des scripts de diagnostic manuels, pas des tests pytest. Trois d'entre eux ont déjà été
   > renommés `manual_check_*.py`. Si la collecte pytest se casse sur ces fichiers, appliquer
   > le même renommage plutôt que de les supprimer.
8. `flutter analyze` ne remonte aucune erreur bloquante.
9. Les migrations sont générées, appliquées et commitées avec leurs modèles.
10. Le rapport se conclut par une synthèse : nombre de défauts par couche (frontend /
    backend / contrat), par sévérité, et la liste ordonnée de ce qui reste à traiter.

---

## 12. Fichiers de référence

**Backend** — `d:\Projets\HIVMeet\env\hivmeet_backend`

| Fichier | Rôle |
|---------|------|
| `hivmeet_backend/settings.py` | Configuration complète |
| `hivmeet_backend/api_urls.py`, `hivmeet_backend/urls.py` | Routage racine |
| `hivmeet_backend/asgi.py` | Routage WebSocket |
| `authentication/models.py`, `views.py`, `urls.py` | Utilisateur, auth, signalements |
| `profiles/models.py`, `views.py`, `views_premium.py`, `views_settings.py` | Profils, photos, vérification, paramètres |
| `matching/services.py` | **Algorithme de découverte** (logs très verbeux, précieux pour le diagnostic) |
| `matching/daily_likes_service.py` | **Quotas de likes** |
| `matching/views_discovery.py`, `views_history.py`, `views_matches.py` | Vues de découverte et matching |
| `messaging/consumers.py` | **Consumer WebSocket du chat** |
| `notifications/consumers.py` | Consumer WebSocket des notifications |
| `subscriptions/utils.py`, `services.py`, `views.py` | **Logique premium**, paiements |
| `resources/views.py`, `urls_feed.py` | Contenu et feed (siège de A-01) |
| `docs/API_DOCUMENTATION.md` | **Contrat d'API de référence** |

**Frontend** — `d:\Projets\HIVMeet\hivmeet`

| Fichier | Rôle |
|---------|------|
| `lib/core/config/app_config.dart` | **URLs backend et WebSocket** |
| `lib/core/config/routes.dart` | **Toutes les routes et la garde d'authentification** |
| `lib/core/network/api_client.dart` | Client Dio, intercepteurs, refresh de token |
| `lib/core/services/authentication_service.dart` | Firebase Auth |
| `lib/core/services/chat_websocket_service.dart` | WebSocket du chat |
| `lib/core/services/notification_websocket_service.dart` | WebSocket des notifications |
| `lib/core/realtime/realtime_event_bus.dart` | Déduplication WS / FCM |
| `lib/data/datasources/remote/*.dart` | **Tous les appels HTTP** (8 fichiers) |
| `lib/presentation/blocs/**` | 15 BLoC : auth, chat, conversations, discovery, feed, interaction_history, matches, notifications, premium, profile, register, resource_detail, resources, unread |
| `lib/presentation/pages/**` | 34 pages |
| `assets/translations/{fr,en}.json` | Traductions |
