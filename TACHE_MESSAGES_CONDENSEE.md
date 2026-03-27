# 📋 TÂCHE KANBAN : Messages Backend (Version Condensée)

## 🎯 Objectif
Audit + Tests + Documentation Frontend de la page Messages.

## 🔍 Checklist Fonctionnalités (33 au total)

### A. Conversations (7)
- [ ] Liste conversations
- [ ] Compteur non-lus
- [ ] Tri par date
- [ ] Info autre utilisateur
- [ ] Pagination
- [ ] Filtre statut (actif/archivé)

### B. Messages (10)
- [ ] Envoi texte
- [ ] Envoi média (Premium)
- [ ] Suppression soft
- [ ] Marquage lu (batch)
- [ ] Marquage lu (single)
- [ ] Indicateur frappe (`POST /conversations/{id}/typing`)
- [ ] Statut présence (`GET /conversations/{id}/presence`)
- [ ] Marquage auto à récupération
- [ ] Dédoublonnage `client_message_id`

### C. Appels Audio/Vidéo (7)
- [ ] Initiation appel
- [ ] Réponse appel
- [ ] ICE candidates
- [ ] Terminaison
- [ ] Journal d'appel
- [ ] Limite 30min (Premium)
- [ ] Notification FCM appel

### D. Premium (5)
- [ ] Appels Premium
- [ ] Médias Premium
- [ ] Historique Illimité (50 → ∞)
- [ ] Chiffrement E2E
- [ ] WebSocket Premium

### E. Notifications (4)
- [ ] Push FCM nouveaux messages
- [ ] Notification message lu
- [ ] Notification appel entrant
- [ ] Polling 30s (gratuits)

## 📁 Fichiers à Examiner
```
messaging/{models,views,services,serializers,urls}.py
matching/models.py (Match avec unread counts)
```

## 🧪 Tests Déterministes

```python
# Structure : GIVEN/WHEN/THEN
class TestConversationList:
    def test_returns_only_active_matches(self): ...
    def test_unread_count_accurate(self): ...

class TestMessageRetrieval:
    def test_marks_as_read_on_fetch(self): ...
    def test_non_premium_limited_to_50(self): ...

class TestSendMessage:
    def test_increments_unread_for_recipient(self): ...
    def test_rejects_media_for_non_premium(self): ...

class TestTypingIndicator:
    def test_typing_expires_after_10s(self): ...

class TestCalls:
    def test_premium_required_for_call(self): ...
    def test_30min_limit_enforced(self): ...
```

## 📚 Documentation à Générer
1. `MESSAGES_BACKEND_SPECIFICATION_FRONTEND.md`
2. `MESSAGES_BACKEND_CONTRACT_FRONTEND.md`

## ✅ Résultat
- 33 fonctionnalités testées
- Couverture ≥80%
- ZÉRO régression
- Documentation Frontend complète

## 🚀 Lancer en ACT MODE
