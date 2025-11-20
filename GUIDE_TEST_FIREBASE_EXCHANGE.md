# 🧪 Guide de Test - Échange de Tokens Firebase ↔ Django JWT

## ✅ Solution Implémentée

L'endpoint d'échange de tokens Firebase a été **implémenté avec succès** selon l'architecture prévue du projet HIVMeet.

### 🔗 Endpoint Disponible
```
POST /api/v1/auth/firebase-exchange
```

### 📋 Format de Requête
```json
{
  "firebase_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."
}
```

### 📋 Réponses Possibles

#### ✅ Succès (200 OK)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "John Doe",
    "is_verified": false,
    "is_premium": false,
    "email_verified": true
  }
}
```

#### ❌ Token Firebase manquant (400)
```json
{
  "error": true,
  "message": "Firebase token is required."
}
```

#### ❌ Token Firebase invalide (401)
```json
{
  "error": true,
  "message": "Invalid Firebase token."
}
```

#### ❌ Utilisateur non trouvé (404)
```json
{
  "error": true,
  "message": "User not found. Please complete your registration.",
  "code": "USER_NOT_FOUND"
}
```

## 🧪 Tests à Effectuer Côté Frontend

### Test 1: Vérification de l'endpoint
```bash
curl -X POST http://10.0.2.2:8000/api/v1/auth/firebase-exchange \
  -H "Content-Type: application/json" \
  -d "{}"
```
**Résultat attendu :** Erreur 400 "Firebase token is required."

### Test 2: Token invalide
```bash
curl -X POST http://10.0.2.2:8000/api/v1/auth/firebase-exchange \
  -H "Content-Type: application/json" \
  -d '{"firebase_token": "invalid_token"}'
```
**Résultat attendu :** Erreur 401 "Invalid Firebase token."

### Test 3: Intégration Flutter (Code d'exemple)

```dart
Future<void> testFirebaseExchange() async {
  try {
    // 1. Récupérer le token Firebase Auth
    User? user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      print("❌ Utilisateur non connecté à Firebase");
      return;
    }
    
    String firebaseToken = await user.getIdToken();
    print("🔑 Token Firebase récupéré: ${firebaseToken.substring(0, 50)}...");
    
    // 2. Tenter l'échange de token
    final response = await http.post(
      Uri.parse('http://10.0.2.2:8000/api/v1/auth/firebase-exchange'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: json.encode({
        'firebase_token': firebaseToken,
      }),
    );
    
    print("📊 Status Code: ${response.statusCode}");
    print("📋 Response: ${response.body}");
    
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      String accessToken = data['access_token'];
      String refreshToken = data['refresh_token'];
      
      print("✅ Échange réussi !");
      print("🎯 Access Token: ${accessToken.substring(0, 50)}...");
      
      // 3. Tester l'endpoint discovery avec le token Django JWT
      final discoveryResponse = await http.get(
        Uri.parse('http://10.0.2.2:8000/api/v1/discovery/?page=1&per_page=20'),
        headers: {
          'Authorization': 'Bearer $accessToken',
          'Content-Type': 'application/json',
        },
      );
      
      print("🔍 Discovery Status: ${discoveryResponse.statusCode}");
      if (discoveryResponse.statusCode == 200) {
        print("🎉 SUCCESS: Discovery fonctionne avec JWT Django !");
      } else {
        print("❌ Erreur Discovery: ${discoveryResponse.body}");
      }
      
    } else if (response.statusCode == 404) {
      print("⚠️ Utilisateur non trouvé - Inscription requise");
    } else {
      print("❌ Erreur d'échange: ${response.body}");
    }
    
  } catch (e) {
    print("💥 Exception: $e");
  }
}
```

## 🎯 Workflow Complet Attendu

### 1. Connexion Firebase
```
🔐 Utilisateur se connecte via Firebase Auth
🔑 Token Firebase ID récupéré
```

### 2. Échange de Token
```
🔄 POST /api/v1/auth/firebase-exchange
✅ Réception tokens JWT Django (access + refresh)
💾 Stockage sécurisé des tokens JWT
```

### 3. Utilisation API
```
📱 Toutes les requêtes API utilisent le JWT Django
📋 Header: Authorization: Bearer <access_token>
🔄 Refresh automatique quand token expire (15 min)
```

## 📊 Codes de Statut et Actions

| Code | Signification | Action Frontend |
|------|---------------|-----------------|
| 200 | ✅ Échange réussi | Stocker tokens JWT, rediriger vers app |
| 400 | ❌ Token manquant | Vérifier code d'envoi du token |
| 401 | ❌ Token invalide | Re-authentifier Firebase Auth |
| 404 | ⚠️ Utilisateur inexistant | Rediriger vers inscription complète |
| 500 | 💥 Erreur serveur | Réessayer plus tard |

## 🔧 Debugging

### Logs Backend Attendus
```
🔄 Firebase token verified for UID: abc123, email: user@domain.com
👤 Existing user found: user@domain.com
🎯 JWT tokens generated for user: user@domain.com
```

### Logs Frontend Attendus
```
🔑 Token Firebase récupéré: eyJhbGciOiJSUzI1NiIs...
🔄 Tentative échange token Firebase...
✅ Échange token réussi
🎯 Token Django JWT utilisé: eyJ0eXAiOiJKV1QiLCJhbGc...
```

## 🚀 Test de Production

1. **Connexion réelle** avec un compte Firebase existant
2. **Vérification** que l'utilisateur existe en base Django  
3. **Échange** de token réussi (200 OK)
4. **Navigation** dans l'app avec JWT Django
5. **Toutes les pages** se chargent sans erreur 401

---

## 🎉 Résultat Attendu

**L'application HIVMeet devrait maintenant fonctionner parfaitement !**

- ✅ Authentification Firebase → Django JWT
- ✅ Toutes les APIs accessibles avec JWT
- ✅ Page Discovery fonctionnelle
- ✅ Navigation complète dans l'application

**Cette solution respecte parfaitement l'architecture prévue du projet HIVMeet.** 🎯 