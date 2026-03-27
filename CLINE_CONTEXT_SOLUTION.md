
# 📋 Solution pour l'Erreur de Limite de Contexte Cline CLI

## ✅ Clarification Importante

Cette documentation concerne **Cline CLI** (installé via `npm install -g cline`) avec son interface Kanban intégrée, **PAS** l'extension VS Code.

---


## 🔍 Causes de l'Erreur

L'erreur "The request exceeds the maximum context window" se produit car :

1. **Fichiers de tâche trop volumineux** (> 50KB chacun)
2. **Historique de conversation trop long**
3. **Fichier de rules trop long** (`.clinerules/cline-rules.md`)

## ✅ Solutions Disponibles

### Solution 1 : Utiliser les Fichiers Condensés (RECOMMANDÉ)

J'ai créé deux fichiers condensés :

| Fichier | Taille | Utilisation |
|---------|--------|-------------|
| `TACHE_FILTRES_CONDENSEE.md` | ~2KB | Tâche filtres découverte |
| `TACHE_MESSAGES_CONDENSEE.md` | ~2KB | Tâche messages |

**Instructions :**
1. Dans Cline, copiez-collez le contenu d'un fichier `*_CONDENSEE.md`
2. OU donnez le chemin du fichier et demandez à Cline de le lire
3. Lancez l'exécution avec cette version condensée

### Solution 2 : Diviser en Sous-tâches

Au lieu d'une seule grande tâche, divisez en phases :

```
Phase 1: TACHE_FILTRES_PHASE1_AUDIT.md
  → Audit des fonctionnalités existantes

Phase 2: TACHE_FILTRES_PHASE2_IMPL.md  
  → Implémentation des manquants

Phase 3: TACHE_FILTRES_PHASE3_TESTS.md
  → Tests déterministes

Phase 4: TACHE_FILTRES_PHASE4_DOC.md
  → Documentation Frontend
```

### Solution 3 : Optimiser les Règles Cline

Réduire `.clinerules/cline-rules.md` de 300+ lignes à ~50 lignes essentielles :

```markdown
# HIVMeet Backend - Cline Rules (Condensed)

## Stack
Django 4.2 + DRF + PostgreSQL + Firebase Auth + Redis + Celery

## 8 Règles Critiques
1. Variables d'environnement → python-decouple
2. Validation serializer DRF stricte
3. Authentification Firebase obligatoire
4. Migrations Django systématiques
5. Respecter contrat API (docs/API_DOCUMENTATION.md)
6. Logging sans données sensibles
7. Transactions @transaction.atomic
8. Internationalisation gettext_lazy

## Endpoints Clés
- Discovery: /api/v1/discovery/profiles/
- Filters: PUT /api/v1/discovery/filters
- Messages: /api/v1/conversations/
- Premium: /api/v1/premium/

## Docs à Consulter
@docs/API_DOCUMENTATION.md
@docs/API_DISCOVERY_FILTERS.md
```

### Solution 4 : Utiliser le Mode "Per-Task" de Cline

1. Cliquez sur l'icône "Task" dans Cline
2. Créez une nouvelle tâche pour chaque phase
3. Chaque tâche aura son propre contexte

## 📝 Configuration Settings VS Code (Optionnels)

Bien qu'il n'y ait pas de paramètre Cline pour la compression, vous pouvez ajuster d'autres paramètres :

```json
{
    // Ces paramètres sont pour d'autres agents, pas Cline
    // "claudeCode.*" = Claude Code
    // "github.copilot.*" = GitHub Copilot
    
    // Limite de fichiers dans le contexte (tous agents)
    "chat.experimental.files.maximum": 20,
    
    // Taille maximale des fichiers pour l'indexation
    "search.maxFileSize": 5242880
}
```

## 🚀 Plan d'Action Recommandé

### Étape 1 : Condenser les Règles
```bash
# Sauvegarder l'original
cp .clinerules/cline-rules.md .clinerules/cline-rules-FULL.md

# Créer version condensée (instructions ci-dessus)
```

### Étape 2 : Utiliser les Tâches Condensées
```bash
# Lire le fichier condenseé
@TACHE_FILTRES_CONDENSEE.md
```

### Étape 3 : Exécuter en Phases
```bash
# Phase 1: Audit rapide
# Phase 2: Implémentation  
# Phase 3: Tests
# Phase 4: Documentation
```

## 📊 Comparaison des Tailles

| Approche | Taille Moyenne | Contexte Requis |
|----------|----------------|-----------------|
| Fichier Original | 50-100KB | ~150K tokens |
| Fichier Condensé | 2-5KB | ~10K tokens |
| Sous-tâches | 2KB x 4 | ~10K tokens chacune |

## ✅ Checklist de Validation

- [ ] Créer version condensée des règles Cline
- [ ] Utiliser `TACHE_FILTRES_CONDENSEE.md` 
- [ ] Utiliser `TACHE_MESSAGES_CONDENSEE.md`
- [ ] Diviser les grosses tâches en phases
- [ ] Réinitialiser le contexte si nécessaire (nouvelle conversation)

---

**Conclusion** : La solution principale est d'utiliser les **fichiers condensés** que j'ai créés. Il n'y a pas de plugin ou paramètre pour forcer la compression dans Cline.
