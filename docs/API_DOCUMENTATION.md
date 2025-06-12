# Documentation de l’API HIVMeet

## Authentification & Utilisateurs

### POST `/auth/login`
- **Description** : Authentifie un utilisateur avec email et mot de passe.
- **Requête** :
  ```json
  {
    "email": "string",
    "password": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "token": "jwt_token",
    "user": { ...userObject }
  }
  ```
- **Erreurs** :
  - 401 : Identifiants invalides

---

### POST `/auth/register`
- **Description** : Crée un nouveau compte utilisateur.
- **Requête** :
  ```json
  {
    "email": "string",
    "password": "string",
    "username": "string",
    "birthdate": "YYYY-MM-DD",
    "gender": "string"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "user": { ...userObject },
    "token": "jwt_token"
  }
  ```
- **Erreurs** :
  - 400 : Email déjà utilisé, données invalides

---

### POST `/auth/verification`
- **Description** : Vérifie le compte utilisateur (email, code SMS, etc.).
- **Requête** :
  ```json
  {
    "userId": "string",
    "code": "string"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "verified": true
  }
  ```
- **Erreurs** :
  - 400 : Code invalide

---

## Profils

### GET `/profiles/me`
- **Description** : Récupère le profil de l’utilisateur connecté.
- **Réponse** (200) :
  ```json
  {
    "profile": { ...profileObject }
  }
  ```

---

### POST `/profiles`
- **Description** : Crée ou met à jour le profil de l’utilisateur.
- **Requête** :
  ```json
  {
    "bio": "string",
    "gender": "string",
    "birthdate": "YYYY-MM-DD",
    "photos": ["url1", "url2", ...],
    "preferences": { ... }
  }
  ```
- **Réponse** (201/200) :
  ```json
  {
    "profile": { ...profileObject }
  }
  ```

---

### GET `/profiles/:id`
- **Description** : Récupère le profil d’un utilisateur par son ID.
- **Réponse** (200) :
  ```json
  {
    "profile": { ...profileObject }
  }
  ```
- **Erreurs** :
  - 404 : Profil non trouvé

---

## Découverte & Filtres

### GET `/discovery`
- **Description** : Liste les profils à découvrir selon les préférences de l’utilisateur.
- **Query params** :
  - `age_min`, `age_max`, `gender`, `distance_max`, etc.
- **Réponse** (200) :
  ```json
  {
    "profiles": [{ ...profileObject }, ...]
  }
  ```

---

### POST `/discovery/filters`
- **Description** : Définit ou met à jour les filtres de découverte de l’utilisateur.
- **Requête** :
  ```json
  {
    "age_min": 18,
    "age_max": 35,
    "gender": "string",
    "distance_max": 50
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "filters": { ... }
  }
  ```

---

## Matchs

### POST `/matches`
- **Description** : Like ou dislike un profil.
- **Requête** :
  ```json
  {
    "targetProfileId": "string",
    "action": "like" | "dislike"
  }
  ```
- **Réponse** (200) :
  ```json
  {
    "match": true | false
  }
  ```

---

### GET `/matches`
- **Description** : Liste les profils avec lesquels il y a un match.
- **Réponse** (200) :
  ```json
  {
    "matches": [{ ...profileObject }, ...]
  }
  ```

---

## Messagerie

### GET `/conversations`
- **Description** : Liste les conversations de l’utilisateur.
- **Réponse** (200) :
  ```json
  {
    "conversations": [
      {
        "id": "string",
        "participants": [{ ...userObject }],
        "lastMessage": { ...messageObject }
      }
    ]
  }
  ```

---

### GET `/conversations/:id/messages`
- **Description** : Récupère les messages d’une conversation.
- **Réponse** (200) :
  ```json
  {
    "messages": [{ ...messageObject }, ...]
  }
  ```

---

### POST `/conversations/:id/messages`
- **Description** : Envoie un message dans une conversation.
- **Requête** :
  ```json
  {
    "content": "string"
  }
  ```
- **Réponse** (201) :
  ```json
  {
    "message": { ...messageObject }
  }
  ```

---

## Objets de données

### userObject
```json
{
  "id": "string",
  "email": "string",
  "username": "string",
  "createdAt": "datetime"
}
```

### profileObject
```json
{
  "id": "string",
  "userId": "string",
  "bio": "string",
  "gender": "string",
  "birthdate": "YYYY-MM-DD",
  "photos": ["url1", "url2", ...],
  "preferences": { ... }
}
```

### messageObject
```json
{
  "id": "string",
  "senderId": "string",
  "content": "string",
  "sentAt": "datetime"
}
```

---

## Sécurité & Authentification

- Toutes les routes (sauf `/auth/*`) nécessitent un header `Authorization: Bearer <token>`.
- Les réponses d’erreur doivent être structurées :
  ```json
  {
    "error": "message"
  }
  ```

---

## Autres recommandations

- Les dates doivent être au format ISO 8601.
- Les listes paginées peuvent utiliser les query params `page` et `limit`.
- Les endpoints doivent retourner des statuts HTTP appropriés (200, 201, 400, 401, 404, etc.).

---

Cette documentation peut être enrichie selon les besoins spécifiques du frontend ou de nouvelles fonctionnalités.
