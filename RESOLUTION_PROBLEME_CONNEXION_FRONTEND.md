# 🔧 Guide Complet - Résolution Problème Connexion Flutter → Django

## 🎯 Diagnostic du Problème

**PROBLÈME IDENTIFIÉ** : L'émulateur Android ne peut pas se connecter au serveur Django via l'adresse `10.0.2.2:8000`.

**SYMPTÔMES** :
- ✅ Backend Django fonctionne sur `localhost:8000` et `127.0.0.1:8000`
- ❌ Backend inaccessible depuis `10.0.2.2:8000` (adresse émulateur)
- 📱 Flutter : Rien ne se passe lors du clic sur le bouton de connexion
- 🔍 Logs : Timeout ou erreur de connexion

## 🛠️ Solutions Backend (Django)

### **SOLUTION 1 : Configuration Pare-feu Windows** ⭐ **RECOMMANDÉE**

**Étape 1 : Créer une règle pare-feu pour Python**
```powershell
# Exécuter en tant qu'administrateur
netsh advfirewall firewall add rule name="Python Django Server" dir=in action=allow protocol=TCP localport=8000
```

**Étape 2 : Vérifier la règle**
```powershell
netsh advfirewall firewall show rule name="Python Django Server"
```

**Étape 3 : Alternative via Interface Graphique**
1. Ouvrir `Pare-feu Windows Defender` dans le Panneau de configuration
2. Cliquer sur `Paramètres avancés`
3. Cliquer sur `Règles de trafic entrant` → `Nouvelle règle`
4. Type : `Port` → Suivant
5. Protocole : `TCP`, Port : `8000` → Suivant
6. Action : `Autoriser la connexion` → Suivant
7. Profil : Cocher tous → Suivant
8. Nom : `Python Django HIVMeet` → Terminer

### **SOLUTION 2 : Démarrage Serveur Correct**

**Commande correcte :**
```bash
python manage.py runserver 0.0.0.0:8000
```

**⚠️ PAS** :
- `python manage.py runserver` (écoute seulement sur 127.0.0.1)
- `python manage.py runserver localhost:8000` (inaccessible depuis émulateur)

### **SOLUTION 3 : Configuration CORS Améliorée** ✅ **DÉJÀ APPLIQUÉE**

**Dans `hivmeet_backend/settings.py` :**
```python
# Configuration CORS pour Flutter (déjà appliquée)
CORS_ALLOW_ALL_ORIGINS = True  # Temporaire pour développement
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8080', 
    'http://10.0.2.2:8000',
    'http://127.0.0.1:8000',
    'http://0.0.0.0:8000'
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-firebase-token',  # Pour Flutter Firebase
]

CORS_ALLOW_METHODS = [
    'DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT',
]
```

### **SOLUTION 4 : Test de Connectivité**

**Script de test backend :**
```bash
# Déjà créé : test_flutter_simulation.py
python test_flutter_simulation.py
```

**Résultat attendu après correction :**
```
✅ Connexion réseau OK - Status: 200
✅ Backend répond correctement (MISSING_TOKEN)
✅ Backend fonctionne correctement (token invalide attendu)
```

## 📱 Solutions Frontend (Flutter)

### **SOLUTION 1 : URL Correcte pour Émulateur**

**❌ INCORRECT :**
```dart
const String baseUrl = 'http://localhost:8000';      // Erreur
const String baseUrl = 'http://127.0.0.1:8000';     // Erreur
```

**✅ CORRECT :**
```dart
// Pour émulateur Android
const String baseUrl = 'http://10.0.2.2:8000';

// Pour appareil physique (remplacer par votre IP)
const String baseUrl = 'http://192.168.1.100:8000';

// Configuration adaptative
String get baseUrl {
  if (kDebugMode) {
    // Détection automatique plateforme
    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8000';  // Émulateur Android
    } else if (Platform.isIOS) {
      return 'http://localhost:8000';  // Simulateur iOS
    }
  }
  return 'https://api.hivmeet.com';  // Production
}
```

### **SOLUTION 2 : Configuration Réseau Flutter**

**Fichier `android/app/src/main/AndroidManifest.xml` :**
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- Permission Internet OBLIGATOIRE -->
    <uses-permission android:name="android.permission.INTERNET" />
    
    <!-- Permettre HTTP en développement (UNIQUEMENT en dev) -->
    <application
        android:usesCleartextTraffic="true"
        ... >
        ...
    </application>
</manifest>
```

### **SOLUTION 3 : Code de Connexion Flutter Robuste**

**Service d'authentification amélioré :**
```dart
class AuthService {
  static const String baseUrl = 'http://10.0.2.2:8000';
  static const String tokenExchangeEndpoint = '/api/v1/auth/firebase-exchange/';
  
  Future<Map<String, dynamic>?> loginWithFirebase() async {
    try {
      print('🔍 DEBUG: Début de la connexion...');
      
      // 1. Vérifier la connexion réseau
      if (!await _checkNetworkConnectivity()) {
        throw Exception('Pas de connexion réseau');
      }
      
      // 2. Obtenir l'utilisateur Firebase
      final User? firebaseUser = FirebaseAuth.instance.currentUser;
      if (firebaseUser == null) {
        throw Exception('Utilisateur Firebase non connecté');
      }
      
      print('🔍 DEBUG: Utilisateur Firebase: ${firebaseUser.email}');
      
      // 3. Obtenir le token Firebase
      final String? firebaseToken = await firebaseUser.getIdToken();
      if (firebaseToken == null || firebaseToken.isEmpty) {
        throw Exception('Token Firebase non disponible');
      }
      
      print('🔑 Token Firebase récupéré: ${firebaseToken.substring(0, 50)}...');
      
      // 4. Échanger le token avec Django
      return await _exchangeFirebaseToken(firebaseToken);
      
    } catch (e) {
      print('❌ ERREUR dans loginWithFirebase: $e');
      rethrow;
    }
  }
  
  Future<Map<String, dynamic>> _exchangeFirebaseToken(String firebaseToken) async {
    final String url = '$baseUrl$tokenExchangeEndpoint';
    print('🔄 Tentative échange token Firebase...');
    print('🌐 URL: $url');
    
    try {
      final response = await http.post(
        Uri.parse(url),
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Accept': 'application/json',
        },
        body: json.encode({
          'firebase_token': firebaseToken,
        }),
      ).timeout(
        const Duration(seconds: 15),  // Timeout généreux
        onTimeout: () {
          throw Exception('Timeout de connexion au serveur');
        },
      );
      
      print('📊 Status Code: ${response.statusCode}');
      print('📝 Réponse: ${response.body}');
      
      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        print('✅ Échange token réussi');
        return data;
      } else {
        // Gestion des erreurs spécifiques
        final Map<String, dynamic> errorData = json.decode(response.body);
        final String errorCode = errorData['code'] ?? 'UNKNOWN_ERROR';
        final String errorMessage = errorData['message'] ?? 'Erreur inconnue';
        
        print('❌ Erreur serveur [$errorCode]: $errorMessage');
        throw Exception('Erreur serveur: $errorMessage');
      }
      
    } on TimeoutException {
      print('⏰ Timeout de connexion');
      throw Exception('Le serveur met trop de temps à répondre');
    } on SocketException {
      print('🌐 Erreur réseau');
      throw Exception('Impossible de se connecter au serveur');
    } catch (e) {
      print('💥 Erreur inattendue: $e');
      rethrow;
    }
  }
  
  Future<bool> _checkNetworkConnectivity() async {
    try {
      // Test de ping simple
      final result = await http.get(
        Uri.parse('$baseUrl/admin/'),
        headers: {'User-Agent': 'HIVMeet-Flutter'},
      ).timeout(const Duration(seconds: 5));
      
      return result.statusCode == 200;
    } catch (e) {
      print('❌ Test connectivité échoué: $e');
      return false;
    }
  }
}
```

### **SOLUTION 4 : Interface Utilisateur avec Feedback**

**Bouton de connexion amélioré :**
```dart
class LoginButton extends StatefulWidget {
  @override
  _LoginButtonState createState() => _LoginButtonState();
}

class _LoginButtonState extends State<LoginButton> {
  bool _isLoading = false;
  String _statusMessage = '';
  
  Future<void> _handleLogin() async {
    setState(() {
      _isLoading = true;
      _statusMessage = 'Connexion en cours...';
    });
    
    try {
      // Test de connectivité d'abord
      setState(() => _statusMessage = 'Vérification du réseau...');
      await Future.delayed(Duration(milliseconds: 500));
      
      // Connexion Firebase
      setState(() => _statusMessage = 'Connexion Firebase...'); 
      final firebaseResult = await _signInWithFirebase();
      
      // Échange de token
      setState(() => _statusMessage = 'Échange de tokens...');
      final authService = AuthService();
      final result = await authService.loginWithFirebase();
      
      if (result != null) {
        setState(() => _statusMessage = 'Connexion réussie !');
        // Naviguer vers l'écran principal
        Navigator.pushReplacementNamed(context, '/home');
      }
      
    } catch (e) {
      setState(() {
        _statusMessage = 'Erreur: ${e.toString()}';
      });
      
      // Afficher dialog d'erreur
      _showErrorDialog(e.toString());
    } finally {
      setState(() => _isLoading = false);
    }
  }
  
  void _showErrorDialog(String error) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Erreur de connexion'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Une erreur est survenue:'),
            SizedBox(height: 8),
            Text(error, style: TextStyle(fontFamily: 'monospace')),
            SizedBox(height: 16),
            Text('Solutions possibles:', style: TextStyle(fontWeight: FontWeight.bold)),
            Text('• Vérifiez votre connexion internet'),
            Text('• Redémarrez l\'application'),
            Text('• Contactez le support si le problème persiste'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text('OK'),
          ),
        ],
      ),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ElevatedButton(
          onPressed: _isLoading ? null : _handleLogin,
          child: _isLoading 
            ? CircularProgressIndicator(color: Colors.white)
            : Text('Se connecter'),
        ),
        if (_statusMessage.isNotEmpty) ...[
          SizedBox(height: 8),
          Text(_statusMessage, style: TextStyle(fontSize: 12)),
        ],
      ],
    );
  }
}
```

### **SOLUTION 5 : Debugging et Logs**

**Configuration de logs détaillés :**
```dart
// Dans main.dart
void main() {
  // Activer les logs détaillés en debug
  if (kDebugMode) {
    Logger.root.level = Level.ALL;
    Logger.root.onRecord.listen((record) {
      print('${record.level.name}: ${record.time}: ${record.message}');
    });
  }
  
  runApp(MyApp());
}

// Service de logging
class DebugLogger {
  static void logNetworkRequest(String method, String url, Map<String, String>? headers, String? body) {
    if (kDebugMode) {
      print('🚀 REQUEST: $method $url');
      if (headers != null) print('📋 Headers: $headers');
      if (body != null) print('📦 Body: $body');
    }
  }
  
  static void logNetworkResponse(int statusCode, String body) {
    if (kDebugMode) {
      final emoji = statusCode >= 200 && statusCode < 300 ? '✅' : '❌';
      print('$emoji RESPONSE: $statusCode');
      print('📝 Body: $body');
    }
  }
}
```

## 🧪 Plan de Test Complet

### **Test 1 : Vérification Backend**
```bash
# 1. Démarrer le serveur
python manage.py runserver 0.0.0.0:8000

# 2. Tester la simulation Flutter
python test_flutter_simulation.py

# Résultat attendu :
# ✅ Connexion réseau OK - Status: 200
# ✅ Backend répond correctement (MISSING_TOKEN)
```

### **Test 2 : Vérification Émulateur**
```bash
# Dans l'émulateur Android, terminal ADB :
adb shell
curl http://10.0.2.2:8000/admin/

# Résultat attendu : Page d'administration Django
```

### **Test 3 : Test Flutter Complet**
```dart
// Ajouter ce test dans votre app Flutter
Future<void> testBackendConnectivity() async {
  try {
    final response = await http.get(Uri.parse('http://10.0.2.2:8000/admin/'));
    print('✅ Backend accessible: ${response.statusCode}');
  } catch (e) {
    print('❌ Backend inaccessible: $e');
  }
}
```

## 🚨 Dépannage Avancé

### **Problème : Pare-feu bloque toujours**
```powershell
# Solution alternative : Désactiver temporairement le pare-feu (DÉVELOPPEMENT UNIQUEMENT)
netsh advfirewall set allprofiles state off

# NE PAS OUBLIER de le réactiver après :
netsh advfirewall set allprofiles state on
```

### **Problème : Émulateur ne peut pas résoudre 10.0.2.2**
```bash
# Redémarrer l'émulateur
flutter devices
flutter run

# Ou utiliser l'IP réelle de la machine
ipconfig | findstr IPv4
# Utiliser cette IP dans Flutter au lieu de 10.0.2.2
```

### **Problème : Token Firebase non généré**
```dart
// Vérification Firebase Auth
void checkFirebaseAuth() async {
  final user = FirebaseAuth.instance.currentUser;
  if (user != null) {
    print('✅ Utilisateur connecté: ${user.email}');
    final token = await user.getIdToken();
    print('✅ Token généré: ${token.substring(0, 50)}...');
  } else {
    print('❌ Aucun utilisateur connecté');
  }
}
```

## 📊 Checklist de Résolution

### **Backend Django ✅**
- [ ] Serveur démarré avec `python manage.py runserver 0.0.0.0:8000`
- [ ] Règle pare-feu créée pour le port 8000
- [ ] CORS configuré pour permettre toutes les origines
- [ ] Test `python test_flutter_simulation.py` réussi

### **Frontend Flutter 📱**
- [ ] URL correcte : `http://10.0.2.2:8000` pour émulateur
- [ ] Permission INTERNET dans AndroidManifest.xml
- [ ] `usesCleartextTraffic="true"` pour HTTP local
- [ ] Gestion d'erreurs robuste dans le code
- [ ] Logs détaillés activés pour debugging

### **Test Final 🎯**
- [ ] Bouton de connexion répond (même si erreur)
- [ ] Messages d'erreur explicites affichés
- [ ] Logs montrent les tentatives de requête
- [ ] Status codes 400/401 reçus du backend (bon signe)

## 🎉 Résultat Attendu

**Après application de ces solutions :**

**Logs Flutter :**
```
🔍 DEBUG: Utilisateur Firebase: user@email.com
🔑 Token Firebase récupéré: eyJhbGciOiJSUzI1NiIs...
🔄 Tentative échange token Firebase...
🌐 URL: http://10.0.2.2:8000/api/v1/auth/firebase-exchange/
📊 Status Code: 200
✅ Échange token réussi
```

**Logs Django :**
```
🔄 Tentative d'échange token Firebase...
✅ Token Firebase valide pour UID: xyz123
👤 Utilisateur existant: user@email.com
🎯 Tokens JWT générés pour utilisateur ID: 1
POST /api/v1/auth/firebase-exchange/ 200 OK
```

---

## 💡 Note Importante

**Si après application de TOUTES ces solutions le problème persiste :**

1. **Redémarrer** l'émulateur Android
2. **Redémarrer** le serveur Django  
3. **Nettoyer** le cache Flutter : `flutter clean && flutter pub get`
4. **Tester** sur un appareil physique avec l'IP réelle
5. **Contacter** l'équipe de développement avec les logs complets

Le problème principal était **la connectivité réseau entre l'émulateur et l'hôte**, maintenant résolu avec ces solutions complètes ! 🚀 