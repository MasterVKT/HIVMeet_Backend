# 📋 TÂCHE KANBAN : Implémentation Complète de la Page Messages Backend

## 🎯 Titre de la Tâche

**"Audit, Implémentation et Tests Déterministes de l'Intégralité des Fonctionnalités de la Page Messages - Backend 100% Opérationnel + Documentation Frontend Complète"**

---

## 📝 Description Détaillée

### Objectif Principal

Cette tâche consiste à :

1. **Audit Complet** : Vérifier que **TOUTES** les fonctionnalités de la page Messages sont **implémentées et 100% fonctionnelles** côté backend
2. **Implémentation des Manquants** : Identifier et implémenter chaque fonctionnalité qui n'est pas encore développée
3. **Tests Déterministes** : Créer des tests approfondis, efficaces et **totalement déterministes** pour chaque fonctionnalité individuelle et leurs combinaisons
4. **Automatisation des Corrections** : Correction automatique des erreurs avec vérification systématique à chaque niveau
5. **Régression Testing** : Tests systématiques à chaque étape pour garantir **100% de certitude** de non-régression
6. **Documentation Frontend** : Génération de fichiers markdown détaillés et structurés contenant **l'intégralité des éléments backend** nécessaires au frontend

---

## 🔍 PHASE 1 : ANALYSE ET AUDIT (Étapes Préliminaires)

### 1.1 Inventaire COMPLET des Fonctionnalités Attendues

Selon les spécifications détaillées (`docs/FRONTEND_MESSAGING_API.md`, `docs/Document de Spécification Interface - HIVMeet.txt`, `docs/backend-specs.md`), les fonctionnalités suivantes doivent exister :

#### A. Conversations (Liste)

| # | Fonctionnalité | Description | Endpoint Backend | Statut |
|---|----------------|-------------|------------------|--------|
| 1 | **Liste Conversations** | Liste des conversations actives | `GET /api/v1/conversations/` | ❓ |
| 2 | **Tri par Date** | Conversations triées par dernier message | Inhérent | ❓ |
| 3 | **Filtre Statut** | Filtrer par actif/archivé | `?status=active\|archived` | ❓ |
| 4 | **Pagination** | Pagination des conversations | `page`, `page_size` | ❓ |
| 5 | **Compteur Non-Lus** | Afficher nombre de messages non lus | `unread_count_for_me` | ❓ |
| 6 | **Info Dernier Message** | Aperçu du dernier message | `last_message` | ❓ |
| 7 | **Info Autre Utilisateur** | Photo, nom, statut en ligne | `other_user` | ❓ |

#### B. Messages (Conversation)

| # | Fonctionnalité | Description | Endpoint Backend | Statut |
|---|----------------|-------------|------------------|--------|
| 8 | **Récupérer Messages** | Liste des messages d'une conversation | `GET /conversations/{conversation_id}/messages/` | ❓ |
| 9 | **Envoyer Message Texte** | Créer un message texte | `POST /conversations/{conversation_id}/messages/` | ❓ |
| 10 | **Envoyer Message Média** | Image/Vidéo/Audio (Premium) | `POST /conversations/{conversation_id}/messages/media/` | ❓ |
| 11 | **Pagination Infinie** | Chargement de plus de messages | `before_message_id` | ❓ |
| 12 | **Supprimer Message** | Soft-delete d'un message | `DELETE /conversations/{conversation_id}/messages/{message_id}/` | ❓ |
| 13 | **Marquer Lu (Batch)** | Marquer messages comme lus (jusqu'à un point) | `PUT /conversations/{conversation_id}/messages/mark-as-read/` | ❓ |
| 14 | **Marquer LU (Single)** | Marquer un seul message comme lu | `PUT /conversations/{conversation_id}/messages/{message_id}/read` | ❓ |
| 15 | **Indicateur Frappe** | "Xx est en train d'écrire..." | `POST /conversations/{conversation_id}/typing` | ❓ |
| 16 | **Statut Présence** | Vérifier si l'autre est en ligne | `GET /conversations/{conversation_id}/presence` | ❓ |
| 17 | **Marquage Auto Lu** | Backend marque auto comme lu à la récupération | `MessageService.get_conversation_messages()` | ❓ |

#### C. Appels Audio/Vidéo

| # | Fonctionnalité | Description | Endpoint Backend | Statut |
|---|----------------|-------------|------------------|--------|
| 18 | **Initier Appel** | Démarrer un appel audio/vidéo | `POST /api/v1/calls/initiate` | ❓ |
| 19 | **Répondre Appel** | Accepter un appel entrant | `POST /api/v1/calls/{call_id}/answer` | ❓ |
| 20 | **ICE Candidates** | Échange WebRTC | `POST /api/v1/calls/{call_id}/ice-candidate` | ❓ |
| 21 | **Terminer Appel** | Fin d'appel | `POST /api/v1/calls/{call_id}/terminate` | ❓ |
| 22 | **Journal Appels** | Historique des appels dans messages | Automatique | ❓ |
| 23 | **Limite Durée** | 30 min/jour pour Premium | `Call.check_call_limit` | ❓ |
| 24 | **Signalement Appel** | Notification FCM appel entrant | FCM Push | ❓ |

#### D. Fonctionnalités Premium

| # | Fonctionnalité | Description | Vérification | Statut |
|---|----------------|-------------|--------------|--------|
| 25 | **Appels Premium** | Audio/vidéo pour Premium | `is_premium` | ❓ |
| 26 | **Médias Premium** | Images/vidéos pour Premium | `is_premium` | ❓ |
| 27 | **Historique Illimité** | Tous les messages (pas de limite 50) | Premium check | ❓ |
| 28 | **Chiffrement E2E** | Chiffrement bout-en-bout optionnel | Premium | ❓ |
| 29 | **WebSocket Premium** | Temps réel pour Premium | WebSocket | ❓ |

#### E. Notifications & Temps Réel

| # | Fonctionnalité | Description | Implémentation | Statut |
|---|----------------|-------------|----------------|--------|
| 30 | **Push Notifications FCM** | Notifications nouveaux messages | Firebase Cloud Messaging | ❓ |
| 31 | **Notification Message Lu** | Push quand message est lu | FCM | ❓ |
| 32 | **Notification Appel Entrant** | Push appel entrant | FCM | ❓ |
| 33 | **Polling Gratuit** | Polling 30s pour gratuits | HTTP Polling | ❓ |

#### F. Modération & Sécurité

| # | Fonctionnalité | Description | Implémentation | Statut |
|---|----------------|-------------|----------------|--------|
| 34 | **Filtrage Contenu** | Détection contenu inapproprié | IA/Regex | ❓ |
| 35 | **Modération Images** | Scan de modération images | AI Service | ❓ |
| 36 | **Signalement** | Signaler utilisateur/message | `POST /reports` | ❓ |

### 1.2 Analyse du Code Existant

#### Fichiers à Examiner

```
messaging/
├── models.py              # Message, Call, TypingIndicator
├── views.py               # Endpoints HTTP
├── services.py            # MessageService, CallService
├── serializers.py         # Validation et sérialisation
├── urls.py               # Routing conversations
├── urls_calls.py          # Routing appels
└── tasks.py              # Tâches asynchrones (notifications)

matching/
├── models.py              # Match avec unread counts
└── ...
```

#### Points d'Audit Spécifiques

1. **ConversationListView** :
   - ❏ Retourne toutes les conversations actives
   - ❏ Inclut les informations other_user (photo, nom, en ligne)
   - ❏ Inclut unread_count_for_me
   - ❏ Inclut last_message preview
   - ❏ Tri par last_message_at

2. **MessageService.get_conversation_messages()** :
   - ❏ Filtre les messages supprimés
   - ❏ Pagination avec before_message_id
   - ❏ Limite 50 pour non-premium
   - ❏ Marque les messages comme lus automatiquement

3. **MessageService.send_message()** :
   - ❏ Vérifie l'utilisateur fait partie du match
   - ❏ Vérifie le match est actif
   - ❏ Dédoublonnage par client_message_id
   - ❏ Vérifie premium pour médias
   - ❏ Met à jour last_message_at
   - ❏ Incrémente unread count

4. **CallService** :
   - ❏ Vérifie limite premium
   - ❏ Vérifie pas d'appel en cours
   - ❏ Crée journal d'appel dans messages

### 1.3 Fonctionnalités SPÉCIFIQUEMENT identifiées dans les spécifications (À VÉRIFIER)

Selon `docs/Document de Spécification Interface - HIVMeet.txt` et `docs/FRONTEND_MESSAGING_API.md` :

#### Endpoints Temps Réel (À IMPLÉMENTER)
- `POST /conversations/{conversation_id}/typing` - Indicateur de frappe
- `GET /conversations/{conversation_id}/presence` - Statut de présence

#### Flux de Téléversement Média
1. Frontend appelle `POST /conversations/generate-media-upload-url`
2. Backend retourne `upload_url` et `file_path_on_storage`
3. Frontend upload sur Firebase Storage
4. Frontend appelle `POST /conversations/{id}/messages` avec `media_file_path_on_storage`

#### Notifications FCM attendues
- `NEW_MATCH` - Nouveau match
- `NEW_MESSAGE` - Nouveau message
- `PROFILE_LIKED` - Like reçu (Premium)
- `message_read` - Message lu

---

## 🔧 PHASE 2 : IMPLÉMENTATION DES FONCTIONNALITÉS MANQUANTES

### 2.1 Checklist d'Implémentation

Pour chaque fonctionnalité manquante identifiée :

- [ ] **Implémenter la fonctionnalité**
- [ ] **Vérifier compilation sans erreur**
- [ ] **Créer test unitaire déterministe**
- [ ] **Exécuter test et vérifier succès**
- [ ] **Documenter l'implémentation**

### 2.2 Points Critiques à Vérifier

#### A. Gestion des Non-Lus

```python
# Le match DOIT avoir les compteurs mis à jour
match.user1_unread_count += 1  # Incrémenter pour le destinataire
match.save()

# Reset quand l'utilisateur lit
match.reset_unread(request.user)  # Remet à 0 pour l'utilisateur
```

#### B. Soft Delete des Messages

```python
# Chaque utilisateur peut supprimer pour lui-même
message.delete_for_user(user)
# is_deleted_by_sender = True (si expéditeur)
# is_deleted_by_recipient = True (si destinataire)
```

#### C. Indicateur de Frappe (À IMPLÉMENTER)

```python
# Mise à jour Redis avec TTL 10 secondes
cache.set(f"typing_{match.id}_{user.id}", True, timeout=10)

# Lecture des indicateurs
is_typing = cache.get(f"typing_{match.id}_{other_user.id}")
```

### 2.3 Format des Réponses API (CONFORME aux spécifications)

#### GET /api/v1/conversations/

```json
{
  "count": 5,
  "next": "?page=2",
  "previous": null,
  "results": [
    {
      "conversation_id": "uuid",
      "other_user": {
        "user_id": "uuid",
        "display_name": "Marie",
        "main_photo_url": "https://...",
        "is_online": true,
        "last_active": "2026-03-27T03:00:00Z"
      },
      "last_message": {
        "message_id": "uuid",
        "content_preview": "Salut, ça va ?",
        "sender_id": "uuid",
        "sent_at": "2026-03-27T03:00:00Z",
        "is_read_by_me": false
      },
      "unread_count_for_me": 3,
      "created_at": "2026-03-20T10:00:00Z",
      "last_activity_at": "2026-03-27T03:00:00Z"
    }
  ]
}
```

#### GET /api/v1/conversations/{conversation_id}/messages/

```json
{
  "count": 150,
  "next": "?before_message_id=xxx",
  "previous": null,
  "results": [
    {
      "message_id": "uuid",
      "conversation_id": "uuid",
      "sender_id": "uuid",
      "content": "Salut!",
      "message_type": "text",
      "media_url": null,
      "media_type": null,
      "sent_at": "2026-03-27T03:00:00Z",
      "read_at_by_recipient": "2026-03-27T03:00:05Z",
      "is_sending": false
    }
  ],
  "has_more": true,
  "show_premium_prompt": false
}
```

#### POST /api/v1/conversations/{conversation_id}/messages/

```json
// Requête
{
  "client_message_id": "client-123",
  "content": "Bonjour!",
  "type": "text",
  "media_file_path_on_storage": null
}

// Réponse 201
{
  "message_id": "uuid",
  "client_message_id": "client-123",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "content": "Bonjour!",
  "message_type": "text",
  "sent_at": "2026-03-27T03:00:00Z",
  "is_read_by_recipient": null
}
```

---

## 🧪 PHASE 3 : CRÉATION DES TESTS DÉTERMINISTES

### 3.1 Principes des Tests Déterministes

✅ **GARANTIES ABSOLUES** :
- Si le test **passe** → La fonctionnalité **fonctionne à 100%**
- Si le test **échoue** → La fonctionnalité **ne fonctionne pas**
- **ZÉRO faux positifs**
- **ZÉRO faux négatifs**

### 3.2 Structure des Tests

#### A. Tests de Conversations

```python
# tests/test_messaging_conversations.py

class TestConversationList:
    """Tests déterministes pour la liste des conversations."""
    
    def test_returns_only_active_matches_with_messages(self):
        """
        GIVEN: 
          - Utilisateur A avec 3 matches (2 actifs, 1 supprimé)
          - Match 1 avec messages, Match 2 avec messages, Match 3 sans messages
        WHEN: A appelle GET /api/v1/conversations/
        THEN: 
          - Exactement 2 conversations retournées
          - Match supprimé NON inclus
          - Match sans messages NON inclus
        """
        
    def test_includes_unread_count_per_conversation(self):
        """
        GIVEN: Match avec unread_count=5 pour user A
        WHEN: A appelle GET /api/v1/conversations/
        THEN: unread_count_for_me = 5
        """
        
    def test_orders_by_last_message_at_descending(self):
        """
        GIVEN: Conv1 last_message=10h, Conv2 last_message=12h, Conv3 last_message=11h
        WHEN: A appelle GET /api/v1/conversations/
        THEN: Ordre = [Conv2, Conv3, Conv1]
        """
```

#### B. Tests de Messages

```python
class TestMessageRetrieval:
    """Tests pour la récupération des messages."""
    
    def test_returns_messages_in_descending_order(self):
        """
        GIVEN: Messages M1 (8h), M2 (9h), M3 (10h)
        WHEN: GET /conversations/{conversation_id}/messages/
        THEN: [M3, M2, M1] (plus récent en premier)
        """
        
    def test_marks_retrieved_messages_as_read(self):
        """
        GIVEN: 
          - Message M1 de B vers A, status=SENT
          - Message M2 de B vers A, status=SENT
        WHEN: A appelle GET /conversations/{conversation_id}/messages/
        THEN: 
          - M1.status = READ
          - M2.status = READ
        """
        
    def test_filters_deleted_messages_for_sender(self):
        """
        GIVEN: 
          - Message M1 envoyé par A, supprimé par A (is_deleted_by_sender=True)
          - Message M2 envoyé par A, non supprimé
        WHEN: A appelle GET /conversations/{conversation_id}/messages/
        THEN: M1 NON visible, M2 visible
        """
        
    def test_non_premium_limited_to_50_messages(self):
        """
        GIVEN: Utilisateur gratuit avec 100 messages
        WHEN: GET /conversations/{conversation_id}/messages/
        THEN: Max 50 messages retournés
        """
```

#### C. Tests d'Envoi de Messages

```python
class TestSendMessage:
    """Tests pour l'envoi de messages."""
    
    def test_creates_message_successfully(self):
        """
        GIVEN: Match actif entre A et B
        WHEN: A envoie un message "Salut!"
        THEN: 
          - Message créé avec content="Salut!"
          - Message.sender = A
          - Message.status = SENT
        """
        
    def test_updates_match_last_message(self):
        """
        GIVEN: Match avec last_message_at=10h
        WHEN: A envoie un message à 12h
        THEN: Match.last_message_at = 12h
        """
        
    def test_increments_unread_for_recipient(self):
        """
        GIVEN: Match avec user1_unread_count=0, user2_unread_count=0
        WHEN: A (user1) envoie un message à B (user2)
        THEN: user2_unread_count = 1
        """
        
    def test_rejects_media_for_non_premium(self):
        """
        GIVEN: Utilisateur gratuit essayant d'envoyer une image
        WHEN: POST /conversations/{conversation_id}/messages/ avec type=image
        THEN: Erreur 403 Forbidden
        """
        
    def test_deduplicates_by_client_message_id(self):
        """
        GIVEN: Message avec client_message_id="abc-123" existe déjà
        WHEN: Envoie message avec même client_message_id
        THEN: Retourne le message existant (pas de doublon)
        """
```

#### D. Tests d'Indicateur de Frappe (NOUVEAU)

```python
class TestTypingIndicator:
    """Tests pour l'indicateur de frappe."""
    
    def test_set_typing_indicator(self):
        """
        GIVEN: Aucun indicateur de frappe
        WHEN: A tape dans la conversation avec B
        THEN: Indicateur "A est en train d'écrire" visible pour B
        """
        
    def test_typing_expires_after_timeout(self):
        """
        GIVEN: A a envoyé indicateur de frappe
        WHEN: 10 secondes passent
        THEN: Indicateur expire automatiquement
        """
        
    def test_stop_typing_indicator(self):
        """
        GIVEN: A est en train d'écrire
        WHEN: A appuie sur "Envoyer"
        THEN: Indicateur disparaît
        """
```

#### E. Tests de Suppression

```python
class TestMessageDeletion:
    """Tests pour la suppression de messages."""
    
    def test_sender_can_delete_own_message(self):
        """
        GIVEN: Message M1 envoyé par A
        WHEN: A supprime M1
        THEN: M1.is_deleted_by_sender = True
        """
        
    def test_cannot_delete_others_message(self):
        """
        GIVEN: Message M1 envoyé par A à B
        WHEN: C (hors conversation) essaie de supprimer M1
        THEN: Erreur 403 Forbidden
        """
```

#### F. Tests d'Appels

```python
class TestCallInitiation:
    """Tests pour l'initiation d'appels."""
    
    def test_premium_user_can_initiate_call(self):
        """
        GIVEN: Utilisateur Premium
        WHEN: Initie un appel
        THEN: Appel créé avec status=RINGING
        """
        
    def test_non_premium_cannot_initiate_call(self):
        """
        GIVEN: Utilisateur gratuit
        WHEN: Initie un appel
        THEN: Erreur 403 Forbidden
        """
        
    def test_call_duration_limit_enforced(self):
        """
        GIVEN: Utilisateur Premium avec 30min d'appels aujourd'hui
        WHEN: Initie un nouvel appel
        THEN: Erreur 403 (limite atteinte)
        """
```

### 3.3 Scénarios de Test Complets

#### Scénario 1 : Cycle de Vie Complet d'une Conversation

| # | Test | Action | Résultat Attendu | Déterministe ? |
|---|------|--------|------------------|----------------|
| 1 | Création match | A like B → Match | Match créé | ✅ |
| 2 | Premier message | A envoie "Salut" | Message créé, unread=1 | ✅ |
| 3 | Marquage auto | B récupère les messages | Messages automatiquement marqués READ | ✅ |
| 4 | Réponse | B envoie "Bonjour" | Message créé, unread=1 pour A | ✅ |
| 5 | Supprimer message | A supprime son message | is_deleted_by_sender=True | ✅ |
| 6 | Indicateur frappe | A tape | B voit "... est en train d'écrire" | ✅ |

#### Scénario 2 : Limites Premium

| # | Test | Utilisateur | Résultat Attendu | Déterministe ? |
|---|------|-------------|------------------|----------------|
| 1 | Limite 50 messages | Gratuit | Max 50 messages | ✅ |
| 2 | Messages illimités | Premium | 100+ messages si existants | ✅ |
| 3 | Médias texto | Gratuit | Erreur 403 | ✅ |
| 4 | Médias premium | Premium | Succès | ✅ |
| 5 | Appel audio | Gratuit | Erreur 403 | ✅ |
| 6 | Appel premium | Premium | Appel créé | ✅ |
| 7 | Limite 30min/appel | Premium (30min atteint) | Erreur 403 | ✅ |

---

## 📚 PHASE 4 : DOCUMENTATION FRONTEND

### 4.1 Fichiers à Générer

À la fin de cette tâche, créer **DEUX fichiers markdown** :

#### Fichier 1 : `MESSAGES_BACKEND_SPECIFICATION_FRONTEND.md`

Structure complète avec :
1. Vue d'Ensemble
2. Endpoints API Conversations
3. Endpoints API Messages
4. Endpoints API Appels
5. Endpoints Temps Réel (Typing, Presence)
6. Modèles de Données (Flutter)
7. Scénarios d'Utilisation
8. Codes d'Erreur
9. Exemples de Code Dart
10. Notes Importantes

#### Fichier 2 : `MESSAGES_BACKEND_CONTRACT_FRONTEND.md`

Contrats JSON par endpoint avec types exacts, valeurs enum, cas limites.

### 4.2 Contenu Obligatoire selon Spécifications

#### Structure Message (CONFORME)

```dart
class Message {
  final String messageId;
  final String conversationId;
  final String senderId;
  final String content;
  final MessageType type; // text, image, video, audio, call_log
  final String? mediaUrl;
  final String? mediaType;
  final DateTime sentAt;
  final DateTime? readAtByRecipient;
  final bool isSending;
}
```

#### Structure Conversation (CONFORME)

```dart
class Conversation {
  final String conversationId;
  final UserInfo otherUser;
  final LastMessage? lastMessage;
  final int unreadCountForMe;
  final DateTime createdAt;
  final DateTime? lastActivityAt;
  final bool isArchived;
}
```

---

## ✅ PHASE 5 : CHECKLIST FINALE DE VALIDATION

### 5.1 Validation de l'Implémentation (33 fonctionnalités)

- [ ] **Conversations** (7 fonctionnalités)
  - [ ] Liste des conversations
  - [ ] Compteur non-lus
  - [ ] Tri par date
  - [ ] Info autre utilisateur
  - [ ] Filtre statut

- [ ] **Messages** (10 fonctionnalités)
  - [ ] Envoi texte
  - [ ] Envoi média (Premium)
  - [ ] Suppression soft
  - [ ] Marquage lu (batch)
  - [ ] Marquage lu (single)
  - [ ] Indicateur frappe
  - [ ] Statut présence
  - [ ] Marquage auto à la récupération
  - [ ] Dédoublonnage client_message_id

- [ ] **Appels** (7 fonctionnalités)
  - [ ] Initiation
  - [ ] Réponse
  - [ ] ICE candidates
  - [ ] Terminaison
  - [ ] Journal d'appel
  - [ ] Limite durée 30min
  - [ ] Notification FCM appel entrant

- [ ] **Premium** (5 fonctionnalités)
  - [ ] Appels Premium
  - [ ] Médias Premium
  - [ ] Historique Illimité
  - [ ] Chiffrement E2E
  - [ ] WebSocket Premium

- [ ] **Notifications** (4 fonctionnalités)
  - [ ] Push FCM nouveaux messages
  - [ ] Notification message lu
  - [ ] Notification appel entrant
  - [ ] Polling pour gratuits

### 5.2 Validation des Tests

- [ ] **Tests déterministes créés** (chaque fonctionnalité)
- [ ] **Couverture ≥ 80%**
- [ ] **ZÉRO erreur dans les tests**

### 5.3 Validation de la Documentation

- [ ] **Fichier 1 créé** : Specification complète
- [ ] **Fichier 2 créé** : contrat JSON
- [ ] **Types conformes aux spécifications**

---

## 🚀 INSTRUCTIONS D'EXÉCUTION

### Question : Lancer en Mode Plan ?

**RÉPONSE RECOMMANDÉE** : **NON** ❌

**JUSTIFICATION** :
1. ✅ Analyse préliminaire déjà effectuée
2. ✅ Spécifications documentées (FRONTEND_MESSAGING_API.md, Document Interface)
3. ✅ Code existant analysé
4. ✅ Tests à créer clairement définis
5. ✅ Structure documentation proposée

### Action Recommandée

**Lancer directement en MODE ACTION (ACT MODE)**

---

## 🎯 RÉSULTAT FINAL ATTENDU

### Livrables

1. ✅ **Backend Messagerie 100% Opérationnel**
   - 33 fonctionnalités implémentées/testées
   - Tous les tests passent

2. ✅ **Tests Déterministes Complets**
   - Tests pour chaque fonctionnalité
   - Couverture ≥ 80%

3. ✅ **Documentation Frontend**
   - `MESSAGES_BACKEND_SPECIFICATION_FRONTEND.md`
   - `MESSAGES_BACKEND_CONTRACT_FRONTEND.md`

4. ✅ **ZÉRO Régression**
   - Aucune fonctionnalité existante cassée

---

**Version** : 2.0 (mise à jour avec spécifications complètes)  
**Date de création** : 27 mars 2026  
**Statut** : Prêt pour exécution  
**Recommandation** : Lancer directement en MODE ACTION
