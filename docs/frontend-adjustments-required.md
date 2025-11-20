# Ajustements Frontend Requis - HIVMeet Backend Modifications

## Vue d'ensemble

Ce document détaille les ajustements nécessaires côté frontend suite aux modifications apportées au backend HIVMeet, notamment pour la gestion des données de test et l'amélioration de la robustesse du système.

## 1. Gestion des Photos de Profil

### 1.1 Source des Images
**Modification Backend :** Changement de la source des images de profil d'Unsplash vers Pexels pour une meilleure fiabilité.

**Ajustements Frontend Requis :**

#### A. Affichage des Photos
```dart
// Dans ProfilePhotoWidget ou équivalent
// Assurez-vous que l'URL des photos est correctement gérée
String getPhotoUrl(String photoPath) {
  // Les photos sont maintenant stockées localement avec des noms spécifiques
  // Format: profile_photos/{gender}_{index}_{timestamp}.jpg
  return photoPath.startsWith('http') 
    ? photoPath 
    : '$baseUrl/media/$photoPath';
}
```

#### B. Gestion des Erreurs de Chargement
```dart
// Ajoutez une gestion d'erreur robuste pour les photos
Widget buildProfilePhoto(String photoUrl) {
  return Image.network(
    photoUrl,
    errorBuilder: (context, error, stackTrace) {
      return Container(
        decoration: BoxDecoration(
          color: Colors.grey[300],
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(Icons.person, size: 50, color: Colors.grey[600]),
      );
    },
    loadingBuilder: (context, child, loadingProgress) {
      if (loadingProgress == null) return child;
      return Container(
        decoration: BoxDecoration(
          color: Colors.grey[200],
          borderRadius: BorderRadius.circular(8),
        ),
        child: Center(
          child: CircularProgressIndicator(
            value: loadingProgress.expectedTotalBytes != null
                ? loadingProgress.cumulativeBytesLoaded / 
                  loadingProgress.expectedTotalBytes!
                : null,
          ),
        ),
      );
    },
  );
}
```

### 1.2 Photos Multiples pour Utilisateurs Premium
**Modification Backend :** Les utilisateurs premium ont maintenant plusieurs photos de profil.

**Ajustements Frontend Requis :**

#### A. Carrousel de Photos
```dart
// Dans ProfileDetailScreen ou équivalent
class ProfilePhotoCarousel extends StatefulWidget {
  final List<String> photos;
  final bool isPremium;
  
  @override
  Widget build(BuildContext context) {
    if (photos.length <= 1) {
      return buildProfilePhoto(photos.first);
    }
    
    return PageView.builder(
      itemCount: photos.length,
      itemBuilder: (context, index) {
        return Stack(
          children: [
            buildProfilePhoto(photos[index]),
            if (isPremium && index > 0)
              Positioned(
                top: 8,
                right: 8,
                child: Container(
                  padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.amber,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${index + 1}/${photos.length}',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}
```

#### B. Indicateurs de Navigation
```dart
// Ajoutez des indicateurs de page pour les utilisateurs premium
Widget buildPhotoIndicators(int currentIndex, int totalPhotos) {
  if (totalPhotos <= 1) return SizedBox.shrink();
  
  return Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: List.generate(totalPhotos, (index) {
      return Container(
        margin: EdgeInsets.symmetric(horizontal: 2),
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: index == currentIndex 
            ? Theme.of(context).primaryColor 
            : Colors.grey[400],
        ),
      );
    }),
  );
}
```

## 2. Gestion des Statuts de Vérification

### 2.1 Nouveaux Statuts
**Modification Backend :** Ajout de nouveaux statuts de vérification : `pending`, `not_submitted`, `rejected`, `expired`.

**Ajustements Frontend Requis :**

#### A. Enum des Statuts
```dart
enum VerificationStatus {
  verified,
  pending,
  notSubmitted,
  rejected,
  expired,
}

extension VerificationStatusExtension on VerificationStatus {
  String get displayName {
    switch (this) {
      case VerificationStatus.verified:
        return 'Vérifié';
      case VerificationStatus.pending:
        return 'En attente';
      case VerificationStatus.notSubmitted:
        return 'Non soumis';
      case VerificationStatus.rejected:
        return 'Rejeté';
      case VerificationStatus.expired:
        return 'Expiré';
    }
  }
  
  Color get color {
    switch (this) {
      case VerificationStatus.verified:
        return Colors.green;
      case VerificationStatus.pending:
        return Colors.orange;
      case VerificationStatus.notSubmitted:
        return Colors.grey;
      case VerificationStatus.rejected:
        return Colors.red;
      case VerificationStatus.expired:
        return Colors.red[700]!;
    }
  }
  
  IconData get icon {
    switch (this) {
      case VerificationStatus.verified:
        return Icons.verified;
      case VerificationStatus.pending:
        return Icons.schedule;
      case VerificationStatus.notSubmitted:
        return Icons.pending;
      case VerificationStatus.rejected:
        return Icons.cancel;
      case VerificationStatus.expired:
        return Icons.timer_off;
    }
  }
}
```

#### B. Widget d'Affichage du Statut
```dart
class VerificationStatusWidget extends StatelessWidget {
  final VerificationStatus status;
  
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: status.color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: status.color, width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(status.icon, size: 16, color: status.color),
          SizedBox(width: 4),
          Text(
            status.displayName,
            style: TextStyle(
              color: status.color,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
```

#### C. Gestion des Actions selon le Statut
```dart
class VerificationActionWidget extends StatelessWidget {
  final VerificationStatus status;
  final VoidCallback? onVerify;
  final VoidCallback? onResubmit;
  
  @override
  Widget build(BuildContext context) {
    switch (status) {
      case VerificationStatus.verified:
        return SizedBox.shrink(); // Aucune action nécessaire
        
      case VerificationStatus.notSubmitted:
        return ElevatedButton(
          onPressed: onVerify,
          child: Text('Vérifier mon profil'),
        );
        
      case VerificationStatus.pending:
        return Container(
          padding: EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.orange[50],
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              Icon(Icons.schedule, color: Colors.orange),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Votre vérification est en cours de traitement',
                  style: TextStyle(color: Colors.orange[800]),
                ),
              ),
            ],
          ),
        );
        
      case VerificationStatus.rejected:
        return Column(
          children: [
            Container(
              padding: EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.red[50],
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.error, color: Colors.red),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Votre vérification a été rejetée',
                      style: TextStyle(color: Colors.red[800]),
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(height: 8),
            ElevatedButton(
              onPressed: onResubmit,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
              ),
              child: Text('Resoumettre'),
            ),
          ],
        );
        
      case VerificationStatus.expired:
        return Column(
          children: [
            Container(
              padding: EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.red[50],
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.timer_off, color: Colors.red),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Votre vérification a expiré',
                      style: TextStyle(color: Colors.red[800]),
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(height: 8),
            ElevatedButton(
              onPressed: onVerify,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
              ),
              child: Text('Renouveler la vérification'),
            ),
          ],
        );
    }
  }
}
```

## 3. Gestion des Interactions (Likes, Matches, Messages)

### 3.1 Correction des Champs de Modèles
**Modification Backend :** Correction des noms de champs dans les modèles `Like`, `Match`, et `Message`.

**Ajustements Frontend Requis :**

#### A. Modèle Like
```dart
class Like {
  final String id;
  final String fromUserId; // Ancien: userId
  final String toUserId;   // Ancien: targetUserId
  final String likeType;   // 'regular' ou 'super'
  final DateTime createdAt;
  
  Like({
    required this.id,
    required this.fromUserId,
    required this.toUserId,
    required this.likeType,
    required this.createdAt,
  });
  
  factory Like.fromJson(Map<String, dynamic> json) {
    return Like(
      id: json['id'],
      fromUserId: json['from_user'], // Correction du nom de champ
      toUserId: json['to_user'],     // Correction du nom de champ
      likeType: json['like_type'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
  
  bool get isSuperLike => likeType == 'super';
}
```

#### B. Modèle Match
```dart
class Match {
  final String id;
  final String user1Id; // Ancien: users[0]
  final String user2Id; // Ancien: users[1]
  final String status;
  final DateTime createdAt;
  final DateTime? lastMessageAt;
  
  Match({
    required this.id,
    required this.user1Id,
    required this.user2Id,
    required this.status,
    required this.createdAt,
    this.lastMessageAt,
  });
  
  factory Match.fromJson(Map<String, dynamic> json) {
    return Match(
      id: json['id'],
      user1Id: json['user1'], // Correction du nom de champ
      user2Id: json['user2'], // Correction du nom de champ
      status: json['status'],
      createdAt: DateTime.parse(json['created_at']),
      lastMessageAt: json['last_message_at'] != null 
        ? DateTime.parse(json['last_message_at'])
        : null,
    );
  }
  
  List<String> get userIds => [user1Id, user2Id];
  
  String getOtherUserId(String currentUserId) {
    return user1Id == currentUserId ? user2Id : user1Id;
  }
}
```

#### C. Modèle Message
```dart
class Message {
  final String id;
  final String matchId;
  final String senderId;
  final String content;
  final String messageType;
  final String status; // Ancien: isRead (bool)
  final DateTime createdAt;
  
  Message({
    required this.id,
    required this.matchId,
    required this.senderId,
    required this.content,
    required this.messageType,
    required this.status,
    required this.createdAt,
  });
  
  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'],
      matchId: json['match'],
      senderId: json['sender'],
      content: json['content'],
      messageType: json['message_type'],
      status: json['status'], // Correction du nom de champ
      createdAt: DateTime.parse(json['created_at']),
    );
  }
  
  bool get isRead => status == 'read';
  bool get isSent => status == 'sent';
  bool get isDelivered => status == 'delivered';
}
```

### 3.2 Gestion des Erreurs de Signal
**Modification Backend :** Correction des erreurs dans les signaux Django pour la gestion des super likes.

**Ajustements Frontend Requis :**

#### A. Gestion des Erreurs de Super Like
```dart
class LikeService {
  static Future<ApiResponse> sendLike(String toUserId, String likeType) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/likes/'),
        headers: await getAuthHeaders(),
        body: jsonEncode({
          'to_user': toUserId,
          'like_type': likeType,
        }),
      );
      
      if (response.statusCode == 201) {
        return ApiResponse.success(
          data: jsonDecode(response.body),
          message: likeType == 'super' 
            ? 'Super like envoyé !' 
            : 'Like envoyé !',
        );
      } else {
        final error = jsonDecode(response.body);
        return ApiResponse.error(
          message: error['message'] ?? 'Erreur lors de l\'envoi du like',
        );
      }
    } catch (e) {
      return ApiResponse.error(
        message: 'Erreur de connexion: $e',
      );
    }
  }
  
  static Future<ApiResponse> sendSuperLike(String toUserId) async {
    // Vérifier d'abord si l'utilisateur a des super likes disponibles
    final subscriptionResponse = await SubscriptionService.getCurrentSubscription();
    
    if (!subscriptionResponse.success) {
      return ApiResponse.error(
        message: 'Impossible de vérifier votre abonnement',
      );
    }
    
    final subscription = subscriptionResponse.data;
    if (subscription['super_likes_remaining'] <= 0) {
      return ApiResponse.error(
        message: 'Vous n\'avez plus de super likes disponibles',
      );
    }
    
    return await sendLike(toUserId, 'super');
  }
}
```

#### B. Widget de Gestion des Super Likes
```dart
class SuperLikeButton extends StatelessWidget {
  final String targetUserId;
  final int superLikesRemaining;
  final VoidCallback? onSuperLikeSent;
  
  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: superLikesRemaining > 0 ? () async {
        final response = await LikeService.sendSuperLike(targetUserId);
        
        if (response.success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Super like envoyé !'),
              backgroundColor: Colors.green,
            ),
          );
          onSuperLikeSent?.call();
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(response.message),
              backgroundColor: Colors.red,
            ),
          );
        }
      } : null,
      icon: Icon(Icons.favorite, color: Colors.pink),
      label: Text('Super Like'),
      style: ElevatedButton.styleFrom(
        backgroundColor: Colors.pink[100],
        foregroundColor: Colors.pink[800],
      ),
    );
  }
}
```

## 4. Gestion des Données de Test

### 4.1 Affichage des Informations de Test
**Modification Backend :** Ajout d'utilisateurs de test avec des données variées.

**Ajustements Frontend Requis :**

#### A. Indicateur de Compte de Test
```dart
class TestAccountIndicator extends StatelessWidget {
  final String email;
  
  bool get isTestAccount => email.endsWith('@test.com');
  
  @override
  Widget build(BuildContext context) {
    if (!isTestAccount) return SizedBox.shrink();
    
    return Container(
      margin: EdgeInsets.only(bottom: 8),
      padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.blue[50],
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.blue[200]!),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.science, size: 16, color: Colors.blue[700]),
          SizedBox(width: 4),
          Text(
            'Compte de test',
            style: TextStyle(
              color: Colors.blue[700],
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
```

#### B. Informations de Connexion de Test
```dart
class TestLoginInfo extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      title: Text('Informations de test'),
      children: [
        Padding(
          padding: EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Comptes de test disponibles:',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              SizedBox(height: 8),
              Text('• Admin: admin@hivmeet.com / adminpass123'),
              Text('• Utilisateurs: [email]@test.com / testpass123'),
              SizedBox(height: 8),
              Text(
                'Utilisateurs premium:',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              Text('• Thomas, Alex, Samuel, Sophie, Emma, Camille, Jordan, Antoine, Marcus, Sarah, David, Lucas, Max, Elena'),
              SizedBox(height: 8),
              Text(
                'Utilisateurs vérifiés:',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              Text('• 22 utilisateurs sur 28 sont vérifiés'),
            ],
          ),
        ),
      ],
    );
  }
}
```

## 5. Améliorations de l'Interface Utilisateur

### 5.1 Gestion des États de Chargement
```dart
class LoadingStateWidget extends StatelessWidget {
  final bool isLoading;
  final Widget child;
  final String? loadingMessage;
  
  @override
  Widget build(BuildContext context) {
    if (!isLoading) return child;
    
    return Stack(
      children: [
        child,
        Container(
          color: Colors.black54,
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(),
                if (loadingMessage != null) ...[
                  SizedBox(height: 16),
                  Text(
                    loadingMessage!,
                    style: TextStyle(color: Colors.white),
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}
```

### 5.2 Gestion des Erreurs
```dart
class ErrorWidget extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: Colors.grey[400],
          ),
          SizedBox(height: 16),
          Text(
            message,
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[600],
            ),
            textAlign: TextAlign.center,
          ),
          if (onRetry != null) ...[
            SizedBox(height: 16),
            ElevatedButton(
              onPressed: onRetry,
              child: Text('Réessayer'),
            ),
          ],
        ],
      ),
    );
  }
}
```

## 6. Tests et Validation

### 6.1 Tests des Fonctionnalités Premium
```dart
class PremiumFeatureTest {
  static Future<void> testSuperLikes() async {
    // Test d'envoi de super like
    final response = await LikeService.sendSuperLike('test_user_id');
    assert(response.success || response.message.contains('super likes'));
  }
  
  static Future<void> testMultiplePhotos() async {
    // Test d'affichage des photos multiples
    final user = await UserService.getUserProfile('premium_user_id');
    assert(user.photos.length > 1);
  }
  
  static Future<void> testVerificationStatus() async {
    // Test des différents statuts de vérification
    final users = await UserService.getUsers();
    final statuses = users.map((u) => u.verificationStatus).toSet();
    assert(statuses.length >= 3); // Au moins 3 statuts différents
  }
}
```

### 6.2 Validation des Données
```dart
class DataValidation {
  static bool validateUserData(User user) {
    // Vérifier que les données utilisateur sont cohérentes
    if (user.isPremium && user.premiumUntil == null) {
      return false;
    }
    
    if (user.isVerified && user.verificationStatus != VerificationStatus.verified) {
      return false;
    }
    
    return true;
  }
  
  static bool validateMatchData(Match match) {
    // Vérifier que les données de match sont cohérentes
    if (match.user1Id == match.user2Id) {
      return false;
    }
    
    return true;
  }
}
```

## 7. Configuration et Déploiement

### 7.1 Variables d'Environnement
```dart
// Assurez-vous que ces variables sont configurées
class Environment {
  static const String baseUrl = String.fromEnvironment(
    'HIVMEET_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
  
  static const bool isTestMode = bool.fromEnvironment(
    'HIVMEET_TEST_MODE',
    defaultValue: false,
  );
}
```

### 7.2 Gestion des Environnements
```dart
class EnvironmentService {
  static bool get isDevelopment => Environment.baseUrl.contains('localhost');
  static bool get isTestMode => Environment.isTestMode;
  
  static String get apiBaseUrl {
    if (isDevelopment) {
      return 'http://10.0.2.2:8000'; // Pour l'émulateur Android
    }
    return Environment.baseUrl;
  }
}
```

## 8. Résumé des Modifications

### 8.1 Modifications Critiques
1. **Photos de profil** : Gestion des photos multiples pour les utilisateurs premium
2. **Statuts de vérification** : Support des nouveaux statuts (pending, rejected, expired)
3. **Modèles de données** : Correction des noms de champs (from_user/to_user, user1/user2)
4. **Gestion des erreurs** : Amélioration de la gestion des erreurs de super likes

### 8.2 Modifications Recommandées
1. **Interface utilisateur** : Ajout d'indicateurs visuels pour les comptes de test
2. **Validation** : Amélioration de la validation des données
3. **Tests** : Ajout de tests pour les nouvelles fonctionnalités

### 8.3 Points d'Attention
1. **Compatibilité** : Assurez-vous que les anciennes versions de l'API sont toujours supportées
2. **Performance** : Les photos multiples peuvent impacter les performances de chargement
3. **Sécurité** : Vérifiez que les données de test ne sont pas exposées en production

## 9. Checklist de Déploiement

- [ ] Mettre à jour les modèles de données (Like, Match, Message)
- [ ] Implémenter la gestion des photos multiples
- [ ] Ajouter les nouveaux statuts de vérification
- [ ] Tester les fonctionnalités premium
- [ ] Valider la gestion des erreurs
- [ ] Ajouter les indicateurs de compte de test
- [ ] Tester avec les données de test
- [ ] Vérifier la compatibilité avec l'API backend
- [ ] Déployer en environnement de test
- [ ] Valider en production

## 10. Support et Maintenance

Pour toute question concernant ces modifications, consultez :
- La documentation de l'API backend
- Les logs d'erreur pour identifier les problèmes
- Les tests automatisés pour valider les fonctionnalités

---

**Note :** Ce document doit être mis à jour à chaque modification significative du backend pour maintenir la cohérence entre les deux systèmes. 