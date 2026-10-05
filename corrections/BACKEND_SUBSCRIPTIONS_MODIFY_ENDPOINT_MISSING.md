# BACKEND_SUBSCRIPTIONS_MODIFY_ENDPOINT_MISSING.md

**Date** : 2026-07-31
**Auteur** : Agent AI frontend (session messagerie temps réel)
**Destinataire** : Agent AI en charge du développement backend HIVMeet
**Priorité** : P1 (fonctionnalité attendue côté frontend, actuellement inutilisable)
**Statut** : Anomalie backend confirmée par lecture du code

---

## 1. Résumé

Le frontend HIVMeet expose une méthode `PremiumRepository.modifySubscription()` qui permet à un utilisateur premium de changer de plan d'abonnement (upgrade/downgrade) avec calcul de proration. Cette méthode appelle `PUT /api/v1/subscriptions/current` avec un payload `{ "new_plan_id": "...", "proration": true }`.

**L'endpoint n'existe pas côté backend.** Aucune route, aucune vue, aucun serializer ne gère la modification d'un abonnement existant. La requête renverra une erreur 404 (ou 405 Method Not Allowed selon la configuration DRF).

Ce n'est pas un bug introduit par les travaux récents sur la messagerie temps réel — c'est un gap préexistant découvert en auditant la cohérence du contrat `subscriptions` pendant la correction du `PremiumRepositoryImpl` (voir `FRONTEND_REALTIME_MESSAGING_ACTION_REPORT.md` §7).

---

## 2. Contexte de découverte

### 2.1 Pourquoi cette anomalie a été trouvée maintenant

Le rapport `FRONTEND_REALTIME_MESSAGING_ACTION_REPORT.md` §7 demandait de corriger `PremiumRepositoryImpl.getCurrentSubscription()` et `cancelSubscription()` qui lisaient un wrapper `payload['subscription']` inexistant. En réécrivant le mapping `_mapJsonToUserSubscription()`, l'audit a vérifié **toutes** les méthodes de `PremiumRepositoryImpl` qui consomment des réponses backend — et `modifySubscription()` est apparue comme consommant elle aussi un wrapper `data['subscription']` sur un endpoint qui n'existe même pas.

### 2.2 Pourquoi c'est bloquant pour le flux premium

Le rapport backend `BACKEND_REALTIME_MESSAGING_IMPLEMENTATION_REPORT.md` §6 documente que le gate premium (`check_feature_availability`) est désormais fonctionnel et invalidé en temps réel à l'annulation/expiration. Si l'utilisateur veut :

1. **Vérifier visuellement que son achat a été pris en compte** → corrigé par le fix `getCurrentSubscription()` (§7 du rapport frontend)
2. **Changer de plan** (mensuel → annuel, ou inverse) → **bloqué par cette anomalie**
3. **Annuler** → fonctionne (`POST /current/cancel/`)
4. **Réactiver** → fonctionne (`POST /current/reactivate/`)

Le changement de plan est une fonctionnalité standard des apps SaaS de dating (Tinder, Bumble, Hinge proposent tous le upgrade/downgrade mid-cycle avec proration).

---

## 3. Analyse détaillée de l'écart frontend ↔ backend

### 3.1 Côté frontend (code actuel)

**Fichier** : `lib/data/datasources/remote/subscriptions_api.dart` (l.84-93)
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

**Fichier** : `lib/data/repositories/premium_repository_impl.dart` (l.330-345)
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

**Fichier** : `lib/domain/repositories/premium_repository.dart` (interface)
```dart
Future<Either<Failure, UserSubscription>> modifySubscription({
  required String newPlanId,
  bool proration = true,
});
```

### 3.2 Côté backend (code actuel)

**Fichier** : `d:\Projets\HIVMeet\env\hivmeet_backend\subscriptions\urls.py`

Toutes les routes enregistrées :

| Méthode | Chemin | Vue | Sert à |
|---------|--------|-----|--------|
| GET | `/plans/` | `SubscriptionPlanListView` | Lister les plans |
| GET | `/current/` | `CurrentSubscriptionView` | Abonnement courant |
| POST | `/purchase/` | `PurchaseSubscriptionView` | Acheter |
| POST | `/current/cancel/` | `cancel_subscription` (FBV) | Annuler |
| POST | `/current/reactivate/` | `reactivate_subscription` (FBV) | Réactiver |
| POST | `/webhooks/payments/mycoolpay/` | `mycoolpay_webhook` | Webhook paiement |

**Il n'y a aucune route pour modifier/changer un plan existant.** Pas de `PUT /current/`, pas de `POST /current/modify/`, pas de `POST /current/change-plan/`.

**Fichier** : `d:\Projets\HIVMeet\env\hivmeet_backend\subscriptions\views.py`

`CurrentSubscriptionView` est un `RetrieveAPIView` — il ne gère que `GET`. Un `PUT` sur `/current/` renverrait 405 Method Not Allowed (DRF bloque automatiquement les méthodes non supportées par un `RetrieveAPIView`).

### 3.3 Contrainte métier identifiée

`PurchaseSubscriptionView.create` (views.py ~107-165) rejette explicitement les utilisateurs ayant déjà un abonnement actif :
```python
existing_sub = request.user.subscription
if existing_sub.is_active:
    return Response(
        {"error": _("You already have an active subscription")},
        status=status.HTTP_400_BAD_REQUEST
    )
```

Cela signifie qu'il n'y a **aucun chemin** pour changer de plan : l'achat est bloqué (déjà abonné), et la modification n'existe pas. L'utilisateur est coincé dans son plan jusqu'à expiration/annulation.

---

## 4. Spécification de l'endpoint à implémenter

### 4.1 Route proposée

```
POST /api/v1/subscriptions/current/modify/
```

**Justification du choix** :
- `POST` plutôt que `PUT` car l'opération n'est pas idempotente (elle déclenche un paiement de proration côté fournisseur)
- Chemin `/current/modify/` cohérent avec les actions existantes `/current/cancel/` et `/current/reactivate/`
- FBV (function-based view) pour rester cohérent avec `cancel_subscription` et `reactivate_subscription`

### 4.2 Requête

**Headers** :
- `Authorization: Bearer {jwt_token}` (utilisateur authentifié)
- `Content-Type: application/json`
- `Accept-Language: fr` ou `en` (pour la localisation du `plan_name` dans la réponse)

**Body** :
```json
{
  "new_plan_id": "hivmeet_yearly",
  "proration": true
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `new_plan_id` | `string` | ✅ | `plan_id` du nouveau plan (ex: `hivmeet_monthly`, `hivmeet_yearly`) |
| `proration` | `boolean` | ❌ (default: `true`) | Si `true`, calcule un avoir/proration au prorata de la période restante. Si `false`, le changement prend effet au prochain cycle de facturation. |

### 4.3 Réponse — Succès (200 OK)

Utiliser le serializer existant `CurrentSubscriptionSerializer` (déjà utilisé par `GET /current/`), avec un block `proration` additionnel pour informer le frontend du montant crédité/débité :

```json
{
  "subscription_id": "sub_external_id_from_provider",
  "plan_id": "hivmeet_yearly",
  "plan_name": "HIVMeet Premium Annuel (fr label)",
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

| Champ | Type | Description |
|-------|------|-------------|
| `subscription_id` | `string` | ID externe du provider de paiement |
| `plan_id` | `string` | `plan_id` du nouveau plan |
| `plan_name` | `string` | Nom localisé via `Accept-Language` |
| `status` | `string` | `active` ou `trialing` |
| `current_period_start` | `string` (ISO-8601) | Début de la nouvelle période |
| `current_period_end` | `string` (ISO-8601) | Fin de la nouvelle période |
| `auto_renew` | `boolean` | Renouvellement auto |
| `cancel_at_period_end` | `boolean` | Annulation en attente en fin de période |
| `features_summary` | `object` | Flags/limites du nouveau plan (même structure que `CurrentSubscriptionSerializer`) |
| `proration.credit_amount` | `number\|null` | Montant crédité au prorata de l'ancienne période restante |
| `proration.charge_amount` | `number\|null` | Montant débité pour la nouvelle période |
| `proration.currency` | `string\|null` | Devise (`EUR`) |
| `proration.prorated_period_start` | `string\|null` (ISO-8601) | Début de la période proratisée |
| `proration.prorated_period_end` | `string\|null` (ISO-8601) | Fin de la période proratisée |

**Note** : Le block `proration` peut être `null` si `proration: false` a été demandé (changement effectif au prochain cycle).

### 4.4 Réponse — Erreurs

| Status | Cas | Body |
|--------|-----|------|
| 400 | `new_plan_id` manquant ou invalide | `{"error": "invalid_plan", "message": "Plan introuvable ou inactif."}` |
| 400 | L'utilisateur n'a pas d'abonnement actif | `{"error": "no_active_subscription", "message": "Aucun abonnement actif à modifier."}` |
| 400 | Le nouveau plan est identique au plan courant | `{"error": "same_plan", "message": "Le nouveau plan est identique au plan actuel."}` |
| 402 | Proration nécessite un paiement et le moyen de paiement est invalide/expiré | `{"error": "payment_required", "message": "Un paiement est requis pour ce changement."}` |
| 403 | L'utilisateur n'est pas premium | `{"error": "not_premium", "message": "Fonctionnalité réservée aux membres premium."}` |
| 429 | Rate limiting | Standard DRF throttle response |

### 4.5 Logique métier à implémenter

```
1. Vérifier que request.user.subscription existe et is_active=True
   → sinon : 400 {"error": "no_active_subscription"}

2. Charger SubscriptionPlan via new_plan_id
   → si introuvable ou inactif : 400 {"error": "invalid_plan"}

3. Vérifier que new_plan != current_plan
   → si identique : 400 {"error": "same_plan"}

4. Si proration=True :
   a. Calculer le crédit au prorata de la période restante de l'ancien plan
      credit = (ancien_prix / anciens_jours_total) * jours_restants
   b. Calculer le débit pour la nouvelle période au prorata
      charge = (nouveau_prix / nouveaux_jours_total) * jours_restants
   c. Si charge > credit : un paiement est nécessaire (vérifier le moyen de paiement)
   d. Appeler le provider de paiement (MyCoolPay) pour le changement de plan avec proration
   e. Mettre à jour Subscription :
      - plan = new_plan
      - current_period_start = now (ou période proratisée)
      - current_period_end = recalculée selon le nouveau billing_interval
      - external_id = nouvel ID si le provider en crée un nouveau
   f. Invalider le cache premium (comme pour cancel/reactivate — voir BACKEND_REALTIME_MESSAGING_IMPLEMENTATION_REPORT.md §6)

5. Si proration=False :
   a. Programmer le changement pour le prochain cycle de facturation
      (annuler l'ancien, créer un nouveau au prochain billing_date)
   b. Marquer Subscription avec un flag pending_plan_change
   c. Le webhook de renouvellement appliquera le changement

6. Retourner CurrentSubscriptionSerializer(subscription) + block proration
```

### 4.6 URL à ajouter

**Fichier** : `subscriptions/urls.py`
```python
path('current/modify/', views.modify_subscription, name='subscription-modify'),
```

### 4.7 Vue proposée (FBV, cohérent avec cancel/reactivate)

**Fichier** : `subscriptions/views.py`
```python
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def modify_subscription(request):
    """
    Change l'abonnement actuel vers un nouveau plan.
    Calcule la proration si demandé.
    """
    user = request.user

    # 1. Vérifier qu'un abonnement actif existe
    subscription = getattr(user, 'subscription', None)
    if subscription is None or not subscription.is_active:
        return Response(
            {"error": "no_active_subscription",
             "message": _("Aucun abonnement actif à modifier.")},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 2. Valider le nouveau plan
    new_plan_id = request.data.get('new_plan_id')
    if not new_plan_id:
        return Response(
            {"error": "invalid_plan",
             "message": _("new_plan_id est requis.")},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        new_plan = SubscriptionPlan.objects.get(
            plan_id=new_plan_id, is_active=True
        )
    except SubscriptionPlan.DoesNotExist:
        return Response(
            {"error": "invalid_plan",
             "message": _("Plan introuvable ou inactif.")},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 3. Vérifier que ce n'est pas le même plan
    if subscription.plan == new_plan:
        return Response(
            {"error": "same_plan",
             "message": _("Le nouveau plan est identique au plan actuel.")},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 4. Gérer la proration
    proration_requested = request.data.get('proration', True)

    try:
        result = SubscriptionService.modify_subscription(
            subscription=subscription,
            new_plan=new_plan,
            proration=proration_requested,
        )
    except PaymentRequiredError:
        return Response(
            {"error": "payment_required",
             "message": _("Un paiement est requis pour ce changement.")},
            status=status.HTTP_402_PAYMENT_REQUIRED
        )
    except Exception as e:
        logger.error(f"modify_subscription failed: {e}")
        return Response(
            {"error": "modification_failed",
             "message": _("Erreur lors de la modification.")},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # 5. Invalider le cache premium
    invalidate_premium_cache(user)

    # 6. Retourner l'abonnement mis à jour
    serializer = CurrentSubscriptionSerializer(
        subscription, context={'request': request, 'language': get_language()}
    )
    data = serializer.data
    data['proration'] = result.get('proration_info', None)
    return Response(data, status=status.HTTP_200_OK)
```

### 4.8 Service à implémenter

**Fichier** : `subscriptions/services.py` (ajouter à l'existant)

```python
class SubscriptionService:
    @staticmethod
    def modify_subscription(subscription, new_plan, proration=True):
        """
        Modifie un abonnement existant vers un nouveau plan.
        Gère la proration côté provider de paiement (MyCoolPay).
        """
        # ... implémentation dépendante du provider ...
        # Calculer le crédit/débit
        # Appeler l'API provider pour le changement
        # Mettre à jour l'objet Subscription
        # Retourner {"proration_info": {...}}
        pass
```

---

## 5. Impact frontend après implémentation backend

### 5.1 Aucun changement frontend requis pour l'endpoint lui-même

Le frontend a déjà :
- `SubscriptionsApi.modifySubscription()` qui appelle `PUT /subscriptions/current` → **à corriger** en `POST /subscriptions/current/modify/` (voir §5.2 ci-dessous)
- `PremiumRepository.modifySubscription()` qui lit la réponse → **à corriger** le wrapper `data['subscription']` (voir §5.3 ci-dessous)
- `PremiumRepository.modifySubscription()` dans l'interface → déjà conforme

### 5.2 Correction frontend requise après implémentation

Une fois l'endpoint backend implémenté, le frontend devra ajuster deux choses :

**a) `subscriptions_api.dart`** — changer la méthode et le chemin HTTP :
```dart
// AVANT (actuel — ne correspond à rien côté backend)
Future<Response<Map<String, dynamic>>> modifySubscription({
  required String newPlanId,
  bool proration = true,
}) async {
  return await _apiClient.put('/subscriptions/current', data: {
    'new_plan_id': newPlanId,
    'proration': proration,
  });
}

// APRÈS (aligné avec le nouvel endpoint)
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

**b) `premium_repository_impl.dart`** — supprimer le wrapper `data['subscription']` (même bug que celui corrigé pour `getCurrentSubscription` en §7) :
```dart
// AVANT (actuel — lit data['subscription'] qui n'existe pas)
final data = response.data!;
final subscriptionData = data['subscription'] as Map<String, dynamic>;
final result = _mapJsonToUserSubscription(subscriptionData);

// APRÈS (champs à plat, aligné avec CurrentSubscriptionSerializer)
final data = response.data ?? const <String, dynamic>{};
final result = _mapJsonToUserSubscription(data);
```

Ces corrections frontend seront appliquées par l'agent frontend dès que l'endpoint backend sera confirmé comme implémenté et fonctionnel.

### 5.3 Impact sur le cache premium

Le backend doit invalider le cache premium après un changement de plan, de la même manière que pour `cancel` et `reactivate` (voir `BACKEND_REALTIME_MESSAGING_IMPLEMENTATION_REPORT.md` §6). Le rapport backend documente déjà `invalidate_premium_cache(user)` pour ces opérations — il suffit d'appeler la même fonction après la modification.

---

## 6. Tests backend suggérés

```python
# subscriptions/tests/test_modify.py

class ModifySubscriptionTest(TestCase):
    def test_modify_to_higher_plan_with_proration(self):
        """Upgrade monthly → yearly avec proration : crédit + nouveau cycle."""

    def test_modify_to_lower_plan_with_proration(self):
        """Downgrade yearly → monthly avec proration : crédit > charge."""

    def test_modify_without_active_subscription_returns_400(self):
        """Pas d'abonnement actif → 400 no_active_subscription."""

    def test_modify_to_same_plan_returns_400(self):
        """Même plan → 400 same_plan."""

    def test_modify_to_invalid_plan_returns_400(self):
        """plan_id inexistant → 400 invalid_plan."""

    def test_modify_invalidates_premium_cache(self):
        """Le cache premium doit être invalidé après modification."""

    def test_modify_with_proration_false_schedules_for_next_cycle(self):
        """proration=False : le changement est programmé pour le prochain cycle."""
```

---

## 7. Checklist de validation

- [ ] Route `POST /api/v1/subscriptions/current/modify/` ajoutée à `subscriptions/urls.py`
- [ ] Vue `modify_subscription` implémentée dans `subscriptions/views.py`
- [ ] `SubscriptionService.modify_subscription()` implémenté dans `subscriptions/services.py`
- [ ] Proration calculée correctement (crédit au prorata de l'ancienne période)
- [ ] Appel au provider de paiement (MyCoolPay) pour le changement
- [ ] Cache premium invalidé après modification (`invalidate_premium_cache(user)`)
- [ ] Réponse conforme à `CurrentSubscriptionSerializer` + block `proration`
- [ ] Gestion des erreurs : 400 (no_active_subscription, invalid_plan, same_plan), 402 (payment_required)
- [ ] Tests unitaires passent
- [ ] `Accept-Language` respecté pour `plan_name`
- [ ] Documentation endpoint mise à jour dans `API_DOCUMENTATION.md`

---

## 8. Anomalies connexes signalées (informatif)

Pendant cet audit, d'autres écarts ont été identifiés entre le frontend et le backend `subscriptions` :

### 8.1 `PurchaseSubscriptionView` bloque les utilisateurs existants

`PurchaseSubscriptionView.create` rejette tout utilisateur ayant déjà un abonnement actif. Une fois l'endpoint `modify` implémenté, ce rejet reste légitime (un upgrade se fait via `modify`, pas via `purchase`). Mais la documentation frontend (`subscriptions_api.dart`) devrait clarifier que `purchase` est réservé au premier achat, et `modify` au changement de plan.

### 8.2 `features_usage` absent de `CurrentSubscriptionSerializer`

Le frontend a une méthode `getFeaturesUsage()` qui appelle `GET /subscriptions/features-usage` — cet endpoint existe côté backend et retourne `boosts_remaining` / `super_likes_remaining`. Cependant, le frontend `_mapJsonToUserSubscription` (ancienne version, maintenant corrigée) tentait de lire `features_usage` dans la réponse de `GET /current/` — ce qui n'existe pas. Le fix frontend sépare désormais correctement les deux : `getCurrentSubscription()` retourne `features_summary` (flags du plan), et `getFeaturesUsage()` retourne les compteurs runtime séparément. **Aucune action backend requise pour ceci** — juste à savoir pour ne pas fusionner les deux dans une seule réponse.

### 8.3 `validatePayment` — endpoint à vérifier

Le frontend appelle `GET /subscriptions/validate-payment/{session_id}`. Vérifier que cet endpoint existe et fonctionne côté backend — il n'a pas été audité dans cette session.

---

## 9. Décision attendue

1. **Implémenter l'endpoint `POST /current/modify/`** selon la spécification §4
2. **Confirmer au frontend** que l'endpoint est prêt pour que l'agent frontend applique les corrections §5.2
3. **Mettre à jour `API_DOCUMENTATION.md`** avec le nouvel endpoint

Si l'endpoint ne doit pas être implémenté (décision produit de ne pas supporter le changement de plan mid-cycle), alors :
- Supprimer `modifySubscription()` du frontend (interface, impl, API, BLoC si présent)
- Documenter la décision dans `API_DOCUMENTATION.md`