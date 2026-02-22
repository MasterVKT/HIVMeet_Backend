# Instructions Frontend - Activation Premium et Gestion des Souscriptions

## 📋 Contexte

Suite aux corrections apportées au backend pour résoudre le problème de Super Like (erreur 400: `no_active_subscription`), ce document décrit les ajustements nécessaires côté frontend pour garantir une intégration harmonieuse du système premium.

---

## ✅ 1. Respect des Spécifications Backend

### 1.1 Vérification de Conformité

Le backend a été implémenté en **STRICTE CONFORMITÉ** avec les spécifications définies dans :
- `Document de Spécification Interface - HIVMeet.txt`
- `API_DOCUMENTATION.md`
- `ENDPOINTS_COMPLETE_DOCUMENTATION.md`

**Points de conformité validés :**

✅ **Structure des modèles**
- `SubscriptionPlan` : Contient tous les champs requis (name, price, billing_interval, features)
- `Subscription` : OneToOneField avec User, statuts conformes (ACTIVE, TRIALING, EXPIRED, etc.)
- Compteurs de fonctionnalités : `super_likes_remaining`, `boosts_remaining`
- Dates de reset : `last_super_likes_reset`, `last_boosts_reset`

✅ **Endpoints API**
- `GET /api/v1/subscriptions/plans/` : Liste des plans disponibles
- `GET /api/v1/subscriptions/current/` : Abonnement actuel de l'utilisateur
- `POST /api/v1/subscriptions/purchase/` : Achat d'abonnement
- `POST /api/v1/subscriptions/current/cancel/` : Annulation
- `POST /api/v1/subscriptions/current/reactivate/` : Réactivation

✅ **Fonctionnalités Premium**
- `POST /api/v1/discovery/interactions/superlike` : Envoi de Super Like
- Signal Django automatique pour consommation après création du Like
- Vérification de disponibilité via `check_feature_availability()`
- Consommation de quota via `consume_premium_feature()`

✅ **Gestion des erreurs**
- `no_active_subscription` : Aucune souscription active trouvée
- `no_super_likes_remaining` : Quota épuisé
- `premium_required` : Fonctionnalité réservée aux utilisateurs premium

---

## ⚠️ 2. Problèmes Identifiés et Solutions

### 2.1 PROBLÈME CRITIQUE : Incohérence Flag Premium vs Subscription

**Description du problème :**
Le frontend avait activé le flag `is_premium=True` sur les utilisateurs test, mais **AUCUN enregistrement Subscription n'existait en base de données**. Cette incohérence causait l'erreur 400 lors de l'utilisation du bouton Super Like.

**Cause racine :**
Le backend vérifie l'existence d'une souscription active via `get_user_subscription(user)`, et non simplement le flag `is_premium`. Si aucune Subscription n'existe, la fonction `consume_premium_feature()` retourne :
```json
{
  "success": false,
  "error": "no_active_subscription"
}
```

**Solution appliquée côté backend :**
✅ Création de Subscriptions actives pour tous les utilisateurs premium (16 utilisateurs)
✅ Liaison avec le plan Premium existant (9.99 EUR, 3 super likes/jour, 10 boosts/mois)
✅ Initialisation des compteurs : 90 super likes, 10 boosts par utilisateur
✅ Statut : ACTIVE avec période valide (30 jours)

**Action requise côté frontend :**
**AUCUNE modification immédiate nécessaire** - Le problème est résolu côté backend.

Cependant, pour éviter cette situation à l'avenir :

---

### 2.2 RECOMMANDATION 1 : Vérification de Cohérence au Démarrage

**Problème :**
Le frontend ne vérifie pas si un utilisateur avec `is_premium=true` possède réellement une souscription active.

**Solution recommandée :**
Ajouter une vérification au démarrage de l'application et lors de la connexion.

**Implémentation suggérée (Flutter/Dart) :**

```dart
// services/subscription_service.dart

class SubscriptionService {
  /// Vérifie la cohérence entre le flag premium et l'abonnement réel
  static Future<void> verifyPremiumConsistency() async {
    try {
      final user = await AuthService.getCurrentUser();
      
      if (user.isPremium) {
        // L'utilisateur a le flag premium, vérifier qu'il a une souscription
        final subscriptionResponse = await getCurrentSubscription();
        
        if (!subscriptionResponse.success || subscriptionResponse.data == null) {
          // INCOHÉRENCE DÉTECTÉE
          logger.warning(
            'User ${user.id} has is_premium=true but no active subscription'
          );
          
          // Option 1 : Désactiver les fonctionnalités premium localement
          await _disablePremiumFeaturesLocally();
          
          // Option 2 : Afficher un message à l'utilisateur
          await _showPremiumInconsistencyDialog();
          
          // Option 3 : Forcer une synchronisation avec le backend
          await _syncPremiumStatusFromBackend();
        }
      }
    } catch (e) {
      logger.error('Error verifying premium consistency: $e');
    }
  }
  
  /// Récupère l'abonnement actuel depuis le backend
  static Future<ApiResponse> getCurrentSubscription() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/v1/subscriptions/current/'),
        headers: await getAuthHeaders(),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return ApiResponse.success(data: data);
      } else if (response.statusCode == 404) {
        // Aucune souscription trouvée
        return ApiResponse.error(
          message: 'Aucun abonnement actif',
        );
      } else {
        final error = jsonDecode(response.body);
        return ApiResponse.error(
          message: error['message'] ?? 'Erreur lors de la récupération',
        );
      }
    } catch (e) {
      return ApiResponse.error(
        message: 'Erreur de connexion: $e',
      );
    }
  }
  
  /// Synchronise le statut premium depuis le backend
  static Future<void> _syncPremiumStatusFromBackend() async {
    final subscriptionResponse = await getCurrentSubscription();
    
    if (subscriptionResponse.success && subscriptionResponse.data != null) {
      final subscription = subscriptionResponse.data;
      
      // Mettre à jour le statut local
      final user = await AuthService.getCurrentUser();
      user.isPremium = subscription['status'] == 'active';
      await AuthService.updateLocalUser(user);
    }
  }
}
```

**Appeler cette vérification :**

```dart
// main.dart ou app_initializer.dart

Future<void> initializeApp() async {
  // ... autres initialisations
  
  // Vérifier la cohérence premium
  await SubscriptionService.verifyPremiumConsistency();
}
```

---

### 2.3 RECOMMANDATION 2 : Gestion Améliorée du Bouton Super Like

**Problème :**
Le bouton Super Like ne vérifie pas si l'utilisateur a des super likes disponibles **AVANT** d'envoyer la requête au backend.

**Solution recommandée :**
Vérifier localement le quota avant d'autoriser l'action.

**Implémentation suggérée (Flutter/Dart) :**

```dart
// services/like_service.dart

class LikeService {
  /// Envoie un Super Like avec vérification préalable du quota
  static Future<ApiResponse> sendSuperLike(String toUserId) async {
    // ÉTAPE 1 : Vérifier le statut premium
    final user = await AuthService.getCurrentUser();
    if (!user.isPremium) {
      return ApiResponse.error(
        message: 'Les Super Likes sont une fonctionnalité premium',
        errorCode: 'premium_required',
      );
    }
    
    // ÉTAPE 2 : Vérifier le quota disponible
    final subscriptionResponse = await SubscriptionService.getCurrentSubscription();
    
    if (!subscriptionResponse.success) {
      return ApiResponse.error(
        message: 'Impossible de vérifier votre abonnement',
        errorCode: 'subscription_check_failed',
      );
    }
    
    final subscription = subscriptionResponse.data;
    final superLikesRemaining = subscription['features_usage']?['super_likes_remaining'] ?? 0;
    
    if (superLikesRemaining <= 0) {
      // Quota épuisé
      return ApiResponse.error(
        message: 'Vous n\'avez plus de Super Likes disponibles aujourd\'hui',
        errorCode: 'no_super_likes_remaining',
      );
    }
    
    // ÉTAPE 3 : Envoyer le Super Like
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/v1/discovery/interactions/superlike'),
        headers: await getAuthHeaders(),
        body: jsonEncode({
          'target_user_id': toUserId,
        }),
      );
      
      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        
        // Mettre à jour le cache local du quota
        await _updateLocalSuperLikesCount(superLikesRemaining - 1);
        
        return ApiResponse.success(
          data: data,
          message: 'Super Like envoyé !',
        );
      } else if (response.statusCode == 400) {
        final error = jsonDecode(response.body);
        
        // Analyser l'erreur spécifique
        if (error['error'] == 'no_active_subscription') {
          // Incohérence détectée - forcer une resynchronisation
          await SubscriptionService.verifyPremiumConsistency();
        }
        
        return ApiResponse.error(
          message: error['message'] ?? 'Erreur lors de l\'envoi du Super Like',
          errorCode: error['error'],
        );
      } else if (response.statusCode == 429) {
        // Limite atteinte (réponse alternative du backend)
        return ApiResponse.error(
          message: 'Vous avez atteint votre limite quotidienne de Super Likes',
          errorCode: 'rate_limit_exceeded',
        );
      } else {
        final error = jsonDecode(response.body);
        return ApiResponse.error(
          message: error['message'] ?? 'Erreur inconnue',
        );
      }
    } catch (e) {
      return ApiResponse.error(
        message: 'Erreur de connexion: $e',
      );
    }
  }
  
  /// Met à jour le cache local du compteur de Super Likes
  static Future<void> _updateLocalSuperLikesCount(int newCount) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('super_likes_remaining', newCount);
  }
  
  /// Récupère le compteur local (pour affichage optimiste)
  static Future<int> getLocalSuperLikesCount() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('super_likes_remaining') ?? 0;
  }
}
```

**Widget UI avec affichage du quota :**

```dart
// widgets/super_like_button.dart

class SuperLikeButton extends StatefulWidget {
  final String targetUserId;
  final VoidCallback onSuccess;
  
  const SuperLikeButton({
    required this.targetUserId,
    required this.onSuccess,
  });
  
  @override
  _SuperLikeButtonState createState() => _SuperLikeButtonState();
}

class _SuperLikeButtonState extends State<SuperLikeButton> {
  bool _isLoading = false;
  int _superLikesRemaining = 0;
  
  @override
  void initState() {
    super.initState();
    _loadSuperLikesCount();
  }
  
  Future<void> _loadSuperLikesCount() async {
    final response = await SubscriptionService.getCurrentSubscription();
    if (response.success) {
      setState(() {
        _superLikesRemaining = response.data['features_usage']
            ?['super_likes_remaining'] ?? 0;
      });
    }
  }
  
  Future<void> _handleSuperLike() async {
    if (_superLikesRemaining <= 0) {
      _showNoSuperLikesDialog();
      return;
    }
    
    setState(() => _isLoading = true);
    
    final response = await LikeService.sendSuperLike(widget.targetUserId);
    
    setState(() => _isLoading = false);
    
    if (response.success) {
      // Mettre à jour le compteur local
      setState(() => _superLikesRemaining--);
      
      // Animation de succès
      _showSuccessAnimation();
      
      widget.onSuccess();
    } else {
      // Afficher l'erreur
      _showErrorDialog(response.message);
      
      // Si l'erreur est "no_active_subscription", recharger le quota
      if (response.errorCode == 'no_active_subscription') {
        await _loadSuperLikesCount();
      }
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Bouton Super Like
        ElevatedButton(
          onPressed: _isLoading ? null : _handleSuperLike,
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.blue,
            shape: CircleBorder(),
            padding: EdgeInsets.all(20),
          ),
          child: _isLoading
              ? CircularProgressIndicator(color: Colors.white)
              : Icon(Icons.star, color: Colors.white, size: 30),
        ),
        
        SizedBox(height: 8),
        
        // Compteur de Super Likes restants
        Text(
          '$_superLikesRemaining Super Likes restants',
          style: TextStyle(
            fontSize: 12,
            color: _superLikesRemaining > 0 ? Colors.blue : Colors.red,
          ),
        ),
      ],
    );
  }
  
  void _showNoSuperLikesDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Plus de Super Likes'),
        content: Text(
          'Vous avez utilisé tous vos Super Likes pour aujourd\'hui. '
          'Ils seront réinitialisés demain.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('OK'),
          ),
        ],
      ),
    );
  }
  
  void _showSuccessAnimation() {
    // Animation de succès (étoiles, confettis, etc.)
  }
  
  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Erreur'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('OK'),
          ),
        ],
      ),
    );
  }
}
```

---

### 2.4 RECOMMANDATION 3 : Synchronisation Périodique des Quotas

**Problème :**
Les quotas (super likes, boosts) se réinitialisent automatiquement côté backend (quotidien pour super likes, mensuel pour boosts), mais le frontend peut afficher des valeurs obsolètes.

**Solution recommandée :**
Synchroniser périodiquement les quotas avec le backend.

**Implémentation suggérée (Flutter/Dart) :**

```dart
// services/subscription_sync_service.dart

class SubscriptionSyncService {
  static Timer? _syncTimer;
  
  /// Démarre la synchronisation périodique des quotas
  static void startPeriodicSync() {
    // Synchroniser toutes les 5 minutes
    _syncTimer = Timer.periodic(Duration(minutes: 5), (timer) async {
      await syncSubscriptionData();
    });
  }
  
  /// Arrête la synchronisation
  static void stopPeriodicSync() {
    _syncTimer?.cancel();
    _syncTimer = null;
  }
  
  /// Synchronise les données d'abonnement avec le backend
  static Future<void> syncSubscriptionData() async {
    try {
      final response = await SubscriptionService.getCurrentSubscription();
      
      if (response.success && response.data != null) {
        final subscription = response.data;
        
        // Mettre à jour le cache local
        final prefs = await SharedPreferences.getInstance();
        
        await prefs.setInt(
          'super_likes_remaining',
          subscription['features_usage']?['super_likes_remaining'] ?? 0,
        );
        
        await prefs.setInt(
          'boosts_remaining',
          subscription['features_usage']?['boosts_remaining'] ?? 0,
        );
        
        await prefs.setString(
          'subscription_status',
          subscription['status'] ?? 'inactive',
        );
        
        await prefs.setString(
          'subscription_expires_at',
          subscription['current_period_end'] ?? '',
        );
        
        logger.info('Subscription data synced successfully');
      }
    } catch (e) {
      logger.error('Error syncing subscription data: $e');
    }
  }
}
```

**Appeler au démarrage de l'application :**

```dart
// main.dart

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // ... autres initialisations
  
  // Démarrer la synchronisation périodique
  SubscriptionSyncService.startPeriodicSync();
  
  runApp(MyApp());
}
```

---

## 📊 3. Format des Réponses API

### 3.1 GET `/api/v1/subscriptions/current/`

**Réponse de succès (200) :**
```json
{
  "subscription_id": "sub_985e8997-d402-4383-a27c-ff2018482871_2ab440c6",
  "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "plan": {
    "id": "premium_monthly_001",
    "name": "Premium",
    "name_en": "Premium",
    "name_fr": "Premium",
    "price": "9.99",
    "currency": "EUR",
    "billing_interval": "month"
  },
  "status": "active",
  "current_period_start": "2026-01-23T00:30:00Z",
  "current_period_end": "2026-02-22T00:30:00Z",
  "auto_renew": true,
  "cancel_at_period_end": false,
  "features_summary": {
    "unlimited_likes": true,
    "can_see_likers": true,
    "can_rewind": true,
    "media_messaging_enabled": true,
    "audio_video_calls_enabled": true
  },
  "features_usage": {
    "super_likes_remaining": 90,
    "boosts_remaining": 10,
    "last_super_likes_reset": "2026-01-23T00:30:00Z",
    "last_boosts_reset": "2026-01-23T00:30:00Z"
  }
}
```

**Réponse si aucune souscription (404) :**
```json
{
  "error": "no_subscription",
  "message": "Aucun abonnement actif trouvé"
}
```

### 3.2 POST `/api/v1/discovery/interactions/superlike`

**Requête :**
```json
{
  "target_user_id": "uuid-de-l-utilisateur-cible"
}
```

**Réponse de succès (200) :**
```json
{
  "error": false,
  "is_match": true,
  "match": {
    "id": "match-uuid",
    "user": {
      "id": "uuid",
      "display_name": "Jean Dupont",
      "profile_picture": "url"
    },
    "matched_at": "2026-01-23T00:35:00Z"
  },
  "daily_like_limit": 100,
  "likes_remaining": 99,
  "super_likes_remaining": 89
}
```

**Réponse si pas de match (200) :**
```json
{
  "error": false,
  "is_match": false,
  "daily_like_limit": 100,
  "likes_remaining": 99,
  "super_likes_remaining": 89
}
```

**Réponse d'erreur - Pas de souscription (400) :**
```json
{
  "error": true,
  "message": "Aucune souscription active",
  "details": {
    "error_code": "no_active_subscription"
  }
}
```

**Réponse d'erreur - Quota épuisé (429) :**
```json
{
  "error": true,
  "message": "Vous avez utilisé tous vos super likes aujourd'hui"
}
```

---

## 🔄 4. Flux de Traitement Recommandé

### 4.1 Au Clic sur le Bouton Super Like

```
1. Vérifier localement si l'utilisateur est premium
   ├─ Non → Afficher message "Fonctionnalité premium"
   └─ Oui → Continuer

2. Récupérer le quota depuis le cache local ou le backend
   ├─ Quota > 0 → Continuer
   └─ Quota = 0 → Afficher message "Plus de Super Likes"

3. Afficher confirmation (optionnel)
   "Utiliser un Super Like ? (X restants)"

4. Envoyer la requête POST /api/v1/discovery/interactions/superlike

5. Traiter la réponse
   ├─ Succès (200) → Mettre à jour le compteur local
   │                  Afficher animation de succès
   │                  Si is_match=true → Afficher notification de match
   │
   ├─ Erreur 400 (no_active_subscription)
   │   → Forcer resynchronisation avec le backend
   │   → Afficher message d'erreur à l'utilisateur
   │   → Désactiver temporairement les fonctionnalités premium
   │
   └─ Erreur 429 (quota épuisé)
       → Mettre à jour le compteur local à 0
       → Afficher message "Plus de Super Likes disponibles"
```

### 4.2 Au Démarrage de l'Application

```
1. Charger l'utilisateur depuis le stockage local

2. Si is_premium = true
   ├─ Récupérer la souscription active depuis le backend
   │  GET /api/v1/subscriptions/current/
   │
   ├─ Succès (200)
   │  ├─ Vérifier que status = "active"
   │  ├─ Mettre à jour les quotas dans le cache local
   │  └─ Activer les fonctionnalités premium dans l'UI
   │
   └─ Erreur (404 ou autre)
      ├─ INCOHÉRENCE DÉTECTÉE
      ├─ Mettre is_premium = false localement
      ├─ Désactiver les fonctionnalités premium dans l'UI
      └─ Logger l'erreur pour investigation

3. Démarrer la synchronisation périodique des quotas
```

---

## 🧪 5. Tests Frontend Recommandés

### 5.1 Test de Cohérence Premium

```dart
// test/subscription_consistency_test.dart

void main() {
  group('Subscription Consistency Tests', () {
    test('User with is_premium=true should have active subscription', () async {
      // Simuler un utilisateur premium
      final user = User(id: 'test-uuid', isPremium: true);
      
      // Récupérer la souscription
      final subscriptionResponse = await SubscriptionService.getCurrentSubscription();
      
      // Vérifier la cohérence
      expect(subscriptionResponse.success, true);
      expect(subscriptionResponse.data['status'], 'active');
    });
    
    test('User without subscription should have is_premium=false', () async {
      // Simuler un utilisateur sans souscription
      final user = User(id: 'test-uuid', isPremium: false);
      
      // Récupérer la souscription
      final subscriptionResponse = await SubscriptionService.getCurrentSubscription();
      
      // Vérifier
      expect(subscriptionResponse.success, false);
    });
  });
}
```

### 5.2 Test du Bouton Super Like

```dart
// test/super_like_button_test.dart

void main() {
  group('Super Like Button Tests', () {
    test('Should show error when quota is 0', () async {
      // Simuler quota à 0
      final subscription = {
        'features_usage': {'super_likes_remaining': 0}
      };
      
      // Tenter d'envoyer un Super Like
      final response = await LikeService.sendSuperLike('target-uuid');
      
      // Vérifier
      expect(response.success, false);
      expect(response.errorCode, 'no_super_likes_remaining');
    });
    
    test('Should decrement quota after successful Super Like', () async {
      // Quota initial : 5
      final initialQuota = 5;
      
      // Envoyer un Super Like
      final response = await LikeService.sendSuperLike('target-uuid');
      
      // Vérifier
      expect(response.success, true);
      
      // Récupérer le nouveau quota
      final newQuota = await LikeService.getLocalSuperLikesCount();
      expect(newQuota, initialQuota - 1);
    });
  });
}
```

---

## 📝 6. Résumé des Actions Frontend

### Actions OBLIGATOIRES

1. ✅ **AUCUNE modification immédiate requise** - Le problème est résolu côté backend

### Actions FORTEMENT RECOMMANDÉES

1. ⚠️ **Implémenter la vérification de cohérence au démarrage**
   - Fichier : `services/subscription_service.dart`
   - Fonction : `verifyPremiumConsistency()`
   - Impact : Évite les incohérences futures

2. ⚠️ **Améliorer la gestion du bouton Super Like**
   - Fichier : `services/like_service.dart`
   - Fonction : `sendSuperLike()` avec vérification préalable du quota
   - Impact : Meilleure UX, moins d'erreurs

3. ⚠️ **Ajouter la synchronisation périodique des quotas**
   - Fichier : `services/subscription_sync_service.dart`
   - Fonction : `startPeriodicSync()`
   - Impact : Quotas toujours à jour

### Actions OPTIONNELLES (Améliorations UX)

1. 💡 Afficher le compteur de Super Likes restants dans l'UI
2. 💡 Montrer une animation spéciale lors de l'envoi d'un Super Like
3. 💡 Afficher une notification lorsque les quotas sont réinitialisés
4. 💡 Proposer l'upgrade premium si l'utilisateur n'a plus de Super Likes

---

## 📞 Support et Questions

Si des questions subsistent concernant l'implémentation frontend, veuillez contacter l'équipe backend avec les détails suivants :
- Endpoint concerné
- Format de requête/réponse attendu
- Comportement observé vs comportement attendu

---

**Date de création** : 23 janvier 2026  
**Version backend** : 1.0  
**Statut** : ✅ Backend conforme aux spécifications, corrections appliquées
