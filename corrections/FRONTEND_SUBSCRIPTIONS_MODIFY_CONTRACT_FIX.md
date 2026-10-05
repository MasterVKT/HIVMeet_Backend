# FRONTEND_SUBSCRIPTIONS_MODIFY_CONTRACT_FIX.md

**Date** : 2026-07-31
**Auteur** : Agent AI backend (session implémentation endpoint `POST /current/modify/`)
**Destinataire** : Agent AI en charge du développement frontend HIVMeet (Flutter/Dart)
**Priorité** : P1 (l'endpoint backend est implémenté et testé ; le frontend ne peut pas l'utiliser tant que les corrections ci-dessous ne sont pas appliquées)
**Statut** : Anomalie frontend confirmée par lecture du code + vérification croisée backend

---

## 1. Résumé exécutif

Le backend vient d'implémenter l'endpoint **`POST /api/v1/subscriptions/current/modify/`** permettant à un utilisateur premium de changer de plan (upgrade/downgrade) avec calcul de proration. L'endpoint est fonctionnel, testé (19 tests backend, 41 tests subscriptions au total — tous au vert) et documenté.

Côté frontend, la méthode `modifySubscription()` existe déjà dans **trois fichiers** (API, interface repository, implémentation repository) mais souffre de **quatre anomalies** qui l'empêchent de fonctionner avec l'endpoint backend réel :

1. **Méthode HTTP et chemin incorrects** — le frontend appelle `PUT /subscriptions/current` alors que le backend expose `POST /subscriptions/current/modify/`.
2. **Wrapper de réponse inexistant** — le frontend lit `data['subscription']` alors que le backend retourne les champs à plat (même structure que `GET /current/`).
3. **Absence de gestion des nouveaux codes d'erreur** — le backend peut retourner `402 payment_required` et des codes d'erreur structurés (`no_active_subscription`, `same_plan`, `invalid_plan`, `payment_required`, `modification_failed`) que le frontend n'interprète pas.
4. **Absence d'événement BLoC** — `modifySubscription` n'est câblé à aucun event/state du `PremiumBloc` et n'est appelé par aucune page/widget. La fonctionnalité est donc invisible côté UI.

Ce rapport détaille chaque anomalie, fournit le code de correction exact et liste les tests à écrire.

---

## 2. État actuel du backend (référence de vérité)

### 2.1 Endpoint implémenté

```
POST /api/v1/subscriptions/current/modify/
```

- **Authentification** : Bearer JWT (requis)
- **Headers** : `Accept-Language: fr|en` (pour la localisation de `plan_name`)
- **Content-Type** : `application/json`

### 2.2 Requête (body JSON)

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `new_plan_id` | `string` | ✅ | `plan_id` du nouveau plan (ex: `hivmeet_monthly`, `hivmeet_yearly`) |
| `proration` | `boolean` | ❌ (default: `true`) | Si `true`, applique le changement immédiatement avec avoir au prorata. Si `false`, programme le changement au prochain cycle de facturation. |

Exemple :
```json
{
  "new_plan_id": "hivmeet_yearly",
  "proration": true
}
```

### 2.3 Réponse — Succès (200 OK)

La réponse utilise le **même sérialiseur** que `GET /current/` (`CurrentSubscriptionSerializer`), avec un block additionnel `proration`. Les champs sont **à plat** (pas de wrapper `subscription`) :

```json
{
  "subscription_id": "sub_external_id_from_provider",
  "plan_id": "hivmeet_yearly",
  "plan_name": "HIVMeet Premium Annuel",
  "status": "active",
  "current_period_start": "2026-07-31T16:00:00Z",
  "current_period_end": "2027-07-31T16:00:00Z",
  "auto_renew": true,
  "cancel_at_period_end": false,
  "features_summary": {
    "unlimited_likes": true,
    "can_see_likers": true,
    "can_rewind": true,
    "monthly_boosts_count": 5,
    "daily_super_likes_count": 5,
    "media_messaging_enabled": true,
    "audio_video_calls_enabled": true
  },
  "proration": {
    "credit_amount": 3.50,
    "charge_amount": 0.00,
    "currency": "EUR",
    "prorated_period_start": "2026-07-31T16:00:00Z",
    "prorated_period_end": "2027-07-31T16:00:00Z"
  }
}
```

**Important** : le block `proration` est `null` si `proration: false` a été demandé (changement programmé au prochain cycle).

### 2.4 Réponse — Erreurs

Toutes les erreurs suivent le format standard du projet :

| Status HTTP | `error` (code) | `message` | Cas |
|-------------|-----------------|----------|-----|
| 400 | `invalid_plan` | « Plan introuvable ou inactif. » / « new_plan_id est requis. » | `new_plan_id` manquant, introuvable ou inactif |
| 400 | `no_active_subscription` | « Aucun abonnement actif à modifier. » | L'utilisateur n'a pas d'abonnement actif |
| 400 | `same_plan` | « Le nouveau plan est identique au plan actuel. » | Le nouveau plan est le même que le courant |
| 402 | `payment_required` | « Un paiement est requis pour ce changement. » | Proration nécessite un paiement et le moyen de paiement est invalide/expiré |
| 500 | `modification_failed` | « Erreur lors de la modification. » | Erreur serveur inattendue |
| 401 | — (DRF standard) | « Informations d'authentification non fournies. » | Non authentifié |

Exemple de réponse d'erreur :
```json
{
  "error": "same_plan",
  "message": "Le nouveau plan est identique au plan actuel."
}
```

> **Note** : Le serializer `ModifySubscriptionSerializer` effectue aussi une validation DRF. Si `new_plan_id` est absent, la réponse sera une 400 avec le format DRF standard `{"new_plan_id": ["Ce champ est obligatoire."]}` (via le `custom_exception_handler` du projet).

### 2.5 Fichiers backend de référence (pour consultation)

| Fichier | Rôle |
|---------|------|
| `subscriptions/urls.py` | Route `path('current/modify/', views.modify_subscription, name='modify')` |
| `subscriptions/views.py` | FBV `modify_subscription` |
| `subscriptions/services.py` | `SubscriptionService.modify_subscription()` + `PaymentRequiredError` + `_calculate_proration()` |
| `subscriptions/serializers.py` | `ModifySubscriptionSerializer`, `ProrationInfoSerializer` |
| `subscriptions/models.py` | `Transaction.TYPE_MODIFICATION` |
| `subscriptions/migrations/0002_add_modification_transaction_type.py` | Migration |
| `subscriptions/tests.py` | `ModifySubscriptionAPITest`, `ModifySubscriptionServiceTest` (19 tests) |
| `docs/API_DOCUMENTATION.md` | Documentation endpoint |
| `ENDPOINTS_COMPLETE_DOCUMENTATION.md` | Documentation endpoint (version complète) |

---

## 3. Anomalies détectées côté frontend — Analyse détaillée

### 3.1 Anomalie #1 — Méthode HTTP et chemin incorrects

**Fichier** : `lib/data/datasources/remote/subscriptions_api.dart` (l.84-93)

**Code actuel (incorrect)** :
```dart
/// Modifier l'abonnement actuel
/// PUT /api/v1/subscriptions/current
Future<Response<Map<String, dynamic>>> modifySubscription({
  required String newPlanId,
  bool proration = true,
}) async {
  return await _apiClient.put('/subscriptions/current', data: {
    'new_plan_id': newPlanId,
    'proration': proration,
  });
}
```

**Problèmes** :
1. **Méthode HTTP** : utilise `PUT` alors que le backend expose `POST` (l'opération n'est pas idempotente — elle déclenche un paiement de proration côté provider).
2. **Chemin** : utilise `/subscriptions/current` (sans trailing slash, sans segment d'action) alors que le backend expose `/subscriptions/current/modify/`.
3. **Conséquence** : une requête `PUT /api/v1/subscriptions/current` serait redirigée par `APPEND_SLASH` vers `GET /api/v1/subscriptions/current/` (la vue `CurrentSubscriptionView` est un `RetrieveAPIView` qui ne gère que `GET`). La requête retournerait une **405 Method Not Allowed** ou serait silencieusement transformée en GET par le redirect.

**Code corrigé** :
```dart
/// Modifier l'abonnement actuel (changement de plan / upgrade / downgrade)
/// POST /api/v1/subscriptions/current/modify/
Future<Response<Map<String, dynamic>>> modifySubscription({
  required String newPlanId,
  bool proration = true,
}) async {
  return await _apiClient.post('/subscriptions/current/modify/', data: {
    'new_plan_id': newPlanId,
    'proration': proration,
  });
}
```

**Diff** : `put` → `post`, `/subscriptions/current` → `/subscriptions/current/modify/`, commentaire mis à jour.

---

### 3.2 Anomalie #2 — Wrapper de réponse inexistant

**Fichier** : `lib/data/repositories/premium_repository_impl.dart` (l.327-344)

**Code actuel (incorrect)** :
```dart
@override
Future<Either<Failure, UserSubscription>> modifySubscription({
  required String newPlanId,
  bool proration = true,
}) async {
  try {
    final response = await _subscriptionsApi.modifySubscription(
      newPlanId: newPlanId,
      proration: proration,
    );
    final data = response.data!;
    final subscriptionData = data['subscription'] as Map<String, dynamic>;

    final result = _mapJsonToUserSubscription(subscriptionData);
    return Right(result);
  } on DioException catch (e) {
    return Left(ServerFailure(message: e.message ?? 'Erreur de serveur'));
  } catch (e) {
    return Left(ServerFailure(message: 'Erreur lors de la modification: $e'));
  }
}
```

**Problème** :
- Ligne 336 : `final subscriptionData = data['subscription'] as Map<String, dynamic>;`
- Le backend retourne les champs **à plat** (même structure que `GET /current/` via `CurrentSubscriptionSerializer`). Il n'y a **pas** de clé `subscription` dans la réponse.
- Conséquence : `data['subscription']` vaut `null`, le cast `as Map<String, dynamic>` lève une `TypeError` (`type 'Null' is not a subtype of type 'Map<String, dynamic>'`), interceptée par le `catch (e)` qui retourne un `ServerFailure` générique. L'utilisateur verra « Erreur lors de la modification: type 'Null' is not a subtype... » même si la requête a réussi côté backend.

**C'est exactement le même bug** que celui déjà corrigé pour `getCurrentSubscription()` (cf. commentaire dans `_mapJsonToUserSubscription` l.355-362 qui documente explicitement que les champs sont à plat). La méthode `modifySubscription` n'a pas bénéficié de cette correction.

**Code corrigé** :
```dart
@override
Future<Either<Failure, UserSubscription>> modifySubscription({
  required String newPlanId,
  bool proration = true,
}) async {
  try {
    final response = await _subscriptionsApi.modifySubscription(
      newPlanId: newPlanId,
      proration: proration,
    );
    final data = response.data ?? const <String, dynamic>{};

    // Le backend retourne les champs à plat (CurrentSubscriptionSerializer),
    // identique à GET /current/. Pas de wrapper `subscription`.
    final result = _mapJsonToUserSubscription(data);
    return Right(result);
  } on DioException catch (e) {
    return Left(ServerFailure(message: e.message ?? 'Erreur de serveur'));
  } catch (e) {
    return Left(ServerFailure(message: 'Erreur lors de la modification: $e'));
  }
}
```

**Diff** : suppression de la ligne `data['subscription']`, passage direct de `data` à `_mapJsonToUserSubscription`.

---

### 3.3 Anomalie #3 — Absence de gestion des codes d'erreur backend

**Problème** : Le backend peut retourner des erreurs métier structurées (400/402) avec un champ `error` contenant un code (`invalid_plan`, `no_active_subscription`, `same_plan`, `payment_required`, `modification_failed`). Le frontend actuel intercepte uniquement les `DioException` et les exceptions génériques, sans interpréter ces codes.

**Impact** :
- L'utilisateur verra un message générique (« Erreur de serveur ») au lieu d'un message localisé et précis.
- Le cas `402 payment_required` est particulièrement important : il indique qu'un paiement 3D Secure est requis et devrait déclencher un flux de vérification côté frontend (comme pour `purchaseSubscription`).

**Solution proposée** : Ajouter une méthode helper `_parseModifyError` qui inspecte le corps de la réponse d'erreur Dio et mappe les codes backend vers des `Failure` explicites.

**Code à ajouter** dans `premium_repository_impl.dart` (avant la méthode `modifySubscription`) :

```dart
/// Extrait un message d'erreur lisible depuis une réponse d'erreur Dio.
String _extractServerErrorMessage(DioException e) {
  final data = e.response?.data;
  if (data is Map<String, dynamic>) {
    // Format d'erreur standard du backend : {"error": "...", "message": "..."}
    final message = data['message'] as String?;
    if (message != null && message.isNotEmpty) {
      return message;
    }
    final error = data['error'] as String?;
    if (error != null) {
      return error;
    }
  }
  return e.message ?? 'Erreur de serveur';
}
```

**Code corrigé de `modifySubscription` (version complète avec gestion d'erreurs)** :

```dart
@override
Future<Either<Failure, UserSubscription>> modifySubscription({
  required String newPlanId,
  bool proration = true,
}) async {
  try {
    final response = await _subscriptionsApi.modifySubscription(
      newPlanId: newPlanId,
      proration: proration,
    );
    final data = response.data ?? const <String, dynamic>{};

    // Le backend retourne les champs à plat (CurrentSubscriptionSerializer),
    // identique à GET /current/. Pas de wrapper `subscription`.
    final result = _mapJsonToUserSubscription(data);
    return Right(result);
  } on DioException catch (e) {
    final statusCode = e.response?.statusCode;
    final message = _extractServerErrorMessage(e);

    // 402 → un paiement est requis (proration avec nouveau débit)
    if (statusCode == 402) {
      return Left(ServerFailure(
        message: message,
        // Optionnel : si le backend retourne un client_secret pour 3DS,
        // l'extraire ici et déclencher le flux de vérification.
      ));
    }

    // 400 → erreur de validation métier (invalid_plan, same_plan, etc.)
    if (statusCode == 400) {
      return Left(ServerFailure(message: message));
    }

    return Left(ServerFailure(message: message));
  } catch (e) {
    return Left(ServerFailure(message: 'Erreur lors de la modification: $e'));
  }
}
```

> **Note** : si la classe `ServerFailure` ne supporte pas de champ `code`, il est acceptable de garder uniquement le `message`. L'important est que l'utilisateur voie le message backend localisé plutôt qu'un message générique.

---

### 3.4 Anomalie #4 — Absence d'événement BLoC et de câblage UI

**Fichiers concernés** :
- `lib/presentation/blocs/premium/premium_event.dart` — aucun event `ModifySubscription`
- `lib/presentation/blocs/premium/premium_state.dart` — aucun state `PremiumModifySuccess` / `PremiumModifyError`
- `lib/presentation/blocs/premium/premium_bloc.dart` — aucun handler `_onModifySubscription`

**Problème** : Même après correction des anomalies #1, #2 et #3, la méthode `modifySubscription` n'est appelée par **aucun** BLoC, UseCase, page ou widget. La fonctionnalité de changement de plan est totalement invisible côté UI.

**Preuve** : une recherche `modifySubscription` dans tout le dossier `lib/presentation/` retourne **zéro résultat**. Le `PremiumBloc` enregistre des handlers pour `LoadPremiumPlans`, `PurchasePremium`, `CancelPremium`, `UpdateAutoRenew`, `UseBoost`, `UseSuperLike`, `LoadPremiumStats`, `LoadPaymentHistory`, `RetryPayment` — mais **pas** pour `ModifySubscription`.

**Solution** : Ajouter l'event, le state et le handler au `PremiumBloc`.

#### 4a. Ajouter l'événement dans `premium_event.dart`

```dart
class ModifySubscription extends PremiumEvent {
  final String newPlanId;
  final bool proration;

  const ModifySubscription({
    required this.newPlanId,
    this.pration = true,
  });

  @override
  List<Object> get props => [newPlanId, proration];
}
```

#### 4b. Ajouter les states dans `premium_state.dart`

```dart
class PremiumModifySuccess extends PremiumState {
  final UserSubscription subscription;

  const PremiumModifySuccess({required this.subscription});

  @override
  List<Object> get props => [subscription];
}

class PremiumModifyError extends PremiumState {
  final String message;

  const PremiumModifyError({required this.message});

  @override
  List<Object> get props => [message];
}
```

> **Alternative** : réutiliser `PremiumPurchaseSuccess` et `PremiumPurchaseError` pour éviter de multiplier les states. Cependant, des states distincts permettent à l'UI de différencier un achat initial d'un changement de plan (ex: afficher « Plan mis à jour » au lieu de « Abonnement activé »).

#### 4c. Ajouter le handler dans `premium_bloc.dart`

```dart
// Dans le constructeur, après les autres `on<...>` :
on<ModifySubscription>(_onModifySubscription);
```

```dart
Future<void> _onModifySubscription(
  ModifySubscription event,
  Emitter<PremiumState> emit,
) async {
  emit(PremiumProcessing());
  final result = await _premiumRepository.modifySubscription(
    newPlanId: event.newPlanId,
    proration: event.pration,
  );
  result.fold(
    (failure) => emit(PremiumModifyError(message: failure.message)),
    (subscription) => emit(PremiumModifySuccess(subscription: subscription)),
  );
}
```

#### 4d. Câblage UI (recommandation)

Dans la page de gestion d'abonnement (ex: `PremiumPage` ou une nouvelle `ManageSubscriptionPage`), ajouter un bouton ou un sélecteur de plan qui déclenche :

```dart
context.read<PremiumBloc>().add(
  ModifySubscription(
    newPlanId: selectedPlanId,
    proration: true, // ou false selon le toggle utilisateur
  ),
);
```

Et réagir aux states :

```dart
BlocListener<PremiumBloc, PremiumState>(
  listener: (context, state) {
    if (state is PremiumModifySuccess) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Plan mis à jour : ${state.subscription.plan.name}')),
      );
      context.read<PremiumBloc>().add(LoadCurrentSubscription());
    } else if (state is PremiumModifyError) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(state.message)),
      );
    }
  },
);
```

---

## 4. Tableau récapitulatif des corrections

| # | Fichier | Ligne(s) | Anomalie | Correction | Priorité |
|---|---------|----------|----------|------------|----------|
| 1 | `lib/data/datasources/remote/subscriptions_api.dart` | 84-93 | `PUT /subscriptions/current` | → `POST /subscriptions/current/modify/` | **Bloquante** |
| 2 | `lib/data/repositories/premium_repository_impl.dart` | 336 | `data['subscription']` wrapper inexistant | → `data` direct (champs à plat) | **Bloquante** |
| 3 | `lib/data/repositories/premium_repository_impl.dart` | 327-344 | Pas de gestion des codes d'erreur backend | → `_extractServerErrorMessage` + switch sur statusCode | **Recommandée** |
| 4a | `lib/presentation/blocs/premium/premium_event.dart` | — | Pas d'event `ModifySubscription` | → Ajouter `class ModifySubscription` | **Recommandée** |
| 4b | `lib/presentation/blocs/premium/premium_state.dart` | — | Pas de states modify | → Ajouter `PremiumModifySuccess` / `PremiumModifyError` | **Recommandée** |
| 4c | `lib/presentation/blocs/premium/premium_bloc.dart` | 18-29 | Pas de handler | → Ajouter `on<ModifySubscription>(_onModifySubscription)` | **Recommandée** |
| 4d | `lib/presentation/pages/premium/` | — | Pas de UI | → Ajouter sélecteur de plan + `BlocListener` | **Recommandée** |

> Les anomalies #1 et #2 sont **bloquantes** : sans elles, la méthode `modifySubscription` lèvera une exception à chaque appel. Les anomalies #3 et #4 sont **recommandées** pour une expérience utilisateur complète, mais la fonctionnalité peut fonctionner techniquement avec seulement #1 et #2.

---

## 5. Vérification du mapping `_mapJsonToUserSubscription`

La méthode `_mapJsonToUserSubscription` (l.355-432 de `premium_repository_impl.dart`) lit les champs à plat suivants :

| Champ lu par le frontend | Champ retourné par le backend | Compatible ? |
|--------------------------|------------------------------|--------------|
| `json['subscription_id']` | `subscription_id` | ✅ |
| `json['plan_id']` | `plan_id` | ✅ |
| `json['plan_name']` | `plan_name` | ✅ |
| `json['status']` | `status` | ✅ |
| `json['current_period_start']` | `current_period_start` | ✅ |
| `json['current_period_end']` | `current_period_end` | ✅ |
| `json['auto_renew']` | `auto_renew` | ✅ |
| `json['cancel_at_period_end']` | `cancel_at_period_end` | ✅ |
| `json['features_summary']` | `features_summary` | ✅ |

**Conclusion** : le mapping est **déjà compatible** avec la réponse backend. Aucune modification de `_mapJsonToUserSubscription` n'est nécessaire.

**Point d'attention** : le backend retourne un block `proration` additionnel (non présent dans `GET /current/`). Le `_mapJsonToUserSubscription` actuel ignore silencieusement les champs qu'il ne connaît pas — ce qui est acceptable. Si le frontend souhaite afficher les informations de proration (montant crédité/débité), il faudra étendre `UserSubscription` avec un champ optionnel `prorationInfo`. Cela n'est pas bloquant pour la correction immédiate.

---

## 6. Tests frontend à écrire

Aucun test n'existe actuellement pour `modifySubscription` (le dossier `test/` ne contient aucun fichier `*premium*` ou `*subscription*`). Voici les tests minimum recommandés :

### 6.1 Test du repository (mock `SubscriptionsApi`)

```dart
// test/data/repositories/premium_repository_modify_test.dart

import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:dartz/dartz.dart';
import 'package:hivmeet/data/repositories/premium_repository_impl.dart';
import 'package:hivmeet/data/datasources/remote/subscriptions_api.dart';
import 'package:hivmeet/data/services/payment_service.dart' as ps;
import 'package:hivmeet/core/error/failures.dart';

// Générer les mocks avec build_runner si pas déjà fait
class MockSubscriptionsApi extends Mock implements SubscriptionsApi {}
class MockPaymentService extends Mock implements ps.PaymentService {}

void main() {
  late PremiumRepositoryImpl repository;
  late MockSubscriptionsApi mockApi;

  setUp(() {
    mockApi = MockSubscriptionsApi();
    final mockPayment = MockPaymentService();
    repository = PremiumRepositoryImpl(mockApi, mockPayment);
  });

  test('modifySubscription should return UserSubscription on success', () async {
    // Arrange — réponse à plat (pas de wrapper `subscription`)
    when(mockApi.modifySubscription(
      newPlanId: 'hivmeet_yearly',
      proration: true,
    )).thenAnswer((_) async => Response(
      data: {
        'subscription_id': 'sub_123',
        'plan_id': 'hivmeet_yearly',
        'plan_name': 'HIVMeet Premium Annuel',
        'status': 'active',
        'current_period_start': '2026-07-31T16:00:00Z',
        'current_period_end': '2027-07-31T16:00:00Z',
        'auto_renew': true,
        'cancel_at_period_end': false,
        'features_summary': {
          'unlimited_likes': true,
          'can_see_likers': true,
          'can_rewind': true,
          'monthly_boosts_count': 5,
          'daily_super_likes_count': 5,
          'media_messaging_enabled': true,
          'audio_video_calls_enabled': true,
        },
        'proration': {
          'credit_amount': 3.50,
          'charge_amount': 0.00,
          'currency': 'EUR',
        },
      },
      statusCode: 200,
      requestOptions: RequestOptions(path: '/subscriptions/current/modify/'),
    ));

    // Act
    final result = await repository.modifySubscription(
      newPlanId: 'hivmeet_yearly',
      proration: true,
    );

    // Assert
    expect(result.isRight(), true);
    result.fold(
      (_) => fail('Should be Right'),
      (subscription) {
        expect(subscription.id, 'sub_123');
        expect(subscription.plan.planId, 'hivmeet_yearly');
        expect(subscription.isActive, true);
      },
    );
  });

  test('modifySubscription should return Failure on 402 payment_required', () async {
    // Arrange
    when(mockApi.modifySubscription(
      newPlanId: 'hivmeet_yearly',
      proration: true,
    )).thenThrow(DioException(
      response: Response(
        data: {
          'error': 'payment_required',
          'message': 'Un paiement est requis pour ce changement.',
        },
        statusCode: 402,
        requestOptions: RequestOptions(path: '/subscriptions/current/modify/'),
      ),
      type: DioExceptionType.badResponse,
      requestOptions: RequestOptions(path: '/subscriptions/current/modify/'),
    ));

    // Act
    final result = await repository.modifySubscription(
      newPlanId: 'hivmeet_yearly',
    );

    // Assert
    expect(result.isLeft(), true);
    result.fold(
      (failure) => expect(failure.message, contains('paiement')),
      (_) => fail('Should be Left'),
    );
  });

  test('modifySubscription should return Failure on 400 same_plan', () async {
    when(mockApi.modifySubscription(
      newPlanId: 'hivmeet_monthly',
      proration: true,
    )).thenThrow(DioException(
      response: Response(
        data: {
          'error': 'same_plan',
          'message': 'Le nouveau plan est identique au plan actuel.',
        },
        statusCode: 400,
        requestOptions: RequestOptions(path: '/subscriptions/current/modify/'),
      ),
      type: DioExceptionType.badResponse,
      requestOptions: RequestOptions(path: '/subscriptions/current/modify/'),
    ));

    final result = await repository.modifySubscription(
      newPlanId: 'hivmeet_monthly',
    );

    expect(result.isLeft(), true);
    result.fold(
      (failure) => expect(failure.message, contains('identique')),
      (_) => fail('Should be Left'),
    );
  });
}
```

### 6.2 Test du BLoC (recommandé)

```dart
// test/presentation/blocs/premium/premium_bloc_modify_test.dart

test('should emit [PremiumProcessing, PremiumModifySuccess] on successful modify', () async {
  when(mockRepository.modifySubscription(
    newPlanId: 'hivmeet_yearly',
    proration: true,
  )).thenAnswer((_) async => Right(testSubscription));

  bloc.add(ModifySubscription(newPlanId: 'hivmeet_yearly', proration: true));

  await expectLater(
    bloc.stream,
    emitsInOrder([
      PremiumProcessing(),
      PremiumModifySuccess(subscription: testSubscription),
    ]),
  );
});
```

---

## 7. Points d'attention et edge cases

### 7.1 Trailing slash

Le backend utilise Django avec `APPEND_SLASH=True` (défaut). L'endpoint attend un trailing slash : `/subscriptions/current/modify/`. Le frontend doit inclure le `/` final dans le chemin, sinon Dio/Django fera une redirection 301→GET qui perdra le body POST.

**✅ La correction proposée en §3.1 inclut déjà le trailing slash.**

### 7.2 Block `proration` dans la réponse

Le backend retourne un block `proration` qui peut être `null` (si `proration: false`) ou un objet avec `credit_amount`, `charge_amount`, `currency`, `prorated_period_start`, `prorated_period_end`.

Le `_mapJsonToUserSubscription` actuel ignore ce champ. Si l'UI doit afficher le détail de la proration (« Vous recevez un avoir de 3,50 € »), il faudra :
1. Ajouter un champ `ProrationInfo? proration` à l'entité `UserSubscription` dans `lib/domain/entities/premium.dart`.
2. Mapper ce champ dans `_mapJsonToUserSubscription`.

Cela n'est **pas bloquant** pour la correction immédiate — l'abonnement mis à jour est retourné correctement sans le détail de proration.

### 7.3 Statut `trialing` côté backend

Le backend peut retourner `status: "trialing"` (période d'essai). Le `_parseSubscriptionStatus` du frontend (l.430-441) ne gère pas cette valeur et tombe dans le `default: return SubscriptionStatus.expired`. Ce n'est pas spécifique à `modifySubscription` (c'est un bug préexistant du mapping), mais il faut le corriger :

```dart
SubscriptionStatus _parseSubscriptionStatus(String status) {
  switch (status) {
    case 'active':
      return SubscriptionStatus.active;
    case 'trialing':  // ← AJOUTER (le backend utilise "trialing", pas "trial")
    case 'trial':
      return SubscriptionStatus.trial;
    case 'expired':
      return SubscriptionStatus.expired;
    case 'canceled':  // ← le backend utilise "canceled", pas "cancelled"
      return SubscriptionStatus.cancelled;
    case 'pending':
      return SubscriptionStatus.pending;
    default:
      return SubscriptionStatus.expired;
  }
}
```

> **Attention** : le backend utilise `"canceled"` (un L, orthographe américaine) alors que le frontend attend `"cancelled"` (deux L, orthographe britannique) via le `default`. Vérifier et harmoniser — c'est un bug potentiel sur `getCurrentSubscription` et `cancelSubscription` aussi.

### 7.4 `features_summary` — clés manquantes

Le backend `CurrentSubscriptionSerializer` retourne 7 clés dans `features_summary` :
`unlimited_likes`, `can_see_likers`, `can_rewind`, `monthly_boosts_count`, `daily_super_likes_count`, `media_messaging_enabled`, `audio_video_calls_enabled`.

Le frontend `_mapJsonToUserSubscription` (via `PremiumFeatures`) attend aussi `priority_support`, `advanced_filters`, `incognito_mode` (présents dans `_mapJsonToPremiumPlan` mais **pas** dans le mapping `_mapJsonToUserSubscription`). Le mapping actuel gère cela avec `?? false` — acceptable mais à surveiller.

### 7.5 Idempotence et double-clic

Le changement de plan n'est pas idempotent côté backend si `proration=true` (il déclenche un paiement). Le BLoC devrait désactiver le bouton de confirmation pendant `PremiumProcessing` pour éviter les double-clics.

---

## 8. Checklist de validation frontend

- [ ] **#1** `subscriptions_api.dart` : `put` → `post`, chemin → `/subscriptions/current/modify/`
- [ ] **#2** `premium_repository_impl.dart` : supprimer `data['subscription']`, passer `data` directement à `_mapJsonToUserSubscription`
- [ ] **#3** `premium_repository_impl.dart` : ajouter `_extractServerErrorMessage` et gérer les status codes 400/402
- [ ] **#4a** `premium_event.dart` : ajouter `class ModifySubscription`
- [ ] **#4b** `premium_state.dart` : ajouter `PremiumModifySuccess` et `PremiumModifyError`
- [ ] **#4c** `premium_bloc.dart` : enregistrer `on<ModifySubscription>` + implémenter `_onModifySubscription`
- [ ] **#4d** UI : ajouter un sélecteur de plan / bouton de changement dans la page de gestion d'abonnement
- [ ] **#5** `_parseSubscriptionStatus` : gérer `trialing` et `canceled` (orthographe backend)
- [ ] **#6** Tests : écrire `premium_repository_modify_test.dart` + `premium_bloc_modify_test.dart`
- [ ] **#7** Vérifier que `flutter analyze` ne rapporte aucune erreur
- [ ] **#8** Vérifier que `flutter test` passe
- [ ] **#9** Tester manuellement : upgrade monthly → yearly avec `proration=true`, vérifier le retour et l'invalidation du cache premium

---

## 9. Références croisées

- **Rapport backend source** : `corrections/BACKEND_SUBSCRIPTIONS_MODIFY_ENDPOINT_MISSING.md` (spécification initiale de l'endpoint)
- **Rapport de messagerie temps réel** : `FRONTEND_REALTIME_MESSAGING_ACTION_REPORT.md` §7 (correction similaire du wrapper `data['subscription']` pour `getCurrentSubscription` et `cancelSubscription`)
- **Documentation API** : `docs/API_DOCUMENTATION.md` § Subscriptions → `POST /current/modify/`
- **Documentation complète** : `ENDPOINTS_COMPLETE_DOCUMENTATION.md` § Subscriptions → `POST /current/modify/`
- **Tests backend** : `subscriptions/tests.py` → `ModifySubscriptionAPITest`, `ModifySubscriptionServiceTest` (19 tests, tous au vert)

---

## 10. Décision attendue

1. **Appliquer les corrections #1 et #2 immédiatement** (bloquantes) — ce sont des changements de 2 lignes chacun.
2. **Appliquer la correction #3** (gestion d'erreurs) pour une UX correcte.
3. **Implémenter le câblage BLoC #4** pour rendre la fonctionnalité accessible depuis l'UI.
4. **Corriger `_parseSubscriptionStatus`** (#5) pour gérer `trialing` et `canceled`.
5. **Écrire les tests** (#6) pour éviter toute régression future.
6. **Confirmer au backend** que les corrections frontend sont appliquées et que l'endpoint `POST /current/modify/` fonctionne end-to-end.

Si la décision produit est de **ne pas supporter** le changement de plan mid-cycle pour le moment, alors :
- Supprimer `modifySubscription()` du frontend (interface, impl, API)
- Supprimer l'event/state BLoC s'il a été ajouté
- Documenter la décision dans `API_DOCUMENTATION.md`
- Le backend conservera l'endpoint (il est testé et non bloquant) mais le marquera comme « non utilisé côté frontend » dans la documentation

---

**Signature** : Agent AI backend — HIVMeet
**Date** : 2026-07-31
**Version** : 1.0