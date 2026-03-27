# 📋 Guide Cline CLI Kanban - Configuration du Contexte

## ✅ Contexte : Cline CLI (npm install -g cline)

Vous utilisez **Cline CLI** avec interface Kanban intégrée. Cette interface a ses propres paramètres de configuration.

---

## 🔧 Fichier de Configuration Cline CLI

Cline CLI utilise un fichier de configuration qui se trouve généralement à :

```
~/.clinerules/settings.json
```

**OU dans le répertoire du projet :**

```
.clinerules/settings.json
```

---

## 📝 Configuration Recommandée pour le Contexte

### Option 1 : Créer le fichier de configuration

Créez le fichier `~/.clinerules/settings.json` :

```json
{
  "maximumContext": 200000,
  "enableContextCompression": true,
  "maxTokens": 180000,
  "autoCompress": true
}
```

### Option 2 : Configuration par projet

Créez `.clinerules/cline-config.json` dans votre projet :

```json
{
  "context": {
    "maximumContext": 200000,
    "maxFileSize": 50000,
    "autoCompress": true,
    "compressionThreshold": 150000
  },
  "kanban": {
    "autoSave": true,
    "maxTasks": 100
  }
}
```

---

## 🔍 Vérification des Paramètres Existants

Exécutez ces commandes pour voir la configuration actuelle :

```bash
# Voir la config Cline
cline config show

# Voir les paramètres de contexte
cline config get maximumContext

# Voir les paramètres kanban
cline config get kanban
```

---

## 🚀 Commandes CLI Utiles

```bash
# Lancer Cline avec limite augmentée
cline --max-context 200000

# Lancer avec compression auto
cline --auto-compress

# Voir l'aide
cline --help

# Mode debug pour voir les erreurs
cline --debug
```

---

## 📋 Alternative : Mode "Task" Séparé

Si votre interface Kanban a un mode "per-task", vous pouvez :

1. **Diviser la tâche principale** en sous-tâches plus petites
2. **Exécuter chaque sous-tâche** individuellement
3. **Chaque sous-tâche** aura son propre contexte limité

### Exemple de division :
```
Tâche Principale: Filtres Découverte
├── Sous-tâche 1: Audit des filtres existants
├── Sous-tâche 2: Implémenter filtres manquants
├── Sous-tâche 3: Créer tests déterministes
└── Sous-tâche 4: Générer documentation frontend
```

---

## ❌ Note Importante

Si le paramètre `enableContextCompression` **n'existe pas** dans Cline CLI, l'erreur que vous voyez est probablement due à :

1. **Limite de l'API LLM** (OpenAI/Anthropic) - pas de Cline
2. **Fichiers trop volumineux** dans le prompt
3. **Historique de conversation trop long**

### Solutions si le paramètre n'existe pas :

1. **Réduire la taille des fichiers de prompt**
2. **Utiliser les fichiers condensés** que j'ai créés
3. **Diviser les tâches** en phases plus petites
4. **Démarrer une nouvelle conversation** pour réinitialiser l'historique

---

## 📊 Résumé des Actions

| Action | Commande/Fichier |
|--------|------------------|
| Config globale | `~/.clinerules/settings.json` |
| Config projet | `.clinerules/cline-config.json` |
| Voir config | `cline config show` |
| Aide | `cline --help` |
| Version | `cline --version` |

---

## ✅ Fichiers Condensés Disponibles

En attendant de configurer Cline CLI :

1. **`TACHE_FILTRES_CONDENSEE.md`** - ~2KB (au lieu de 50KB)
2. **`TACHE_MESSAGES_CONDENSEE.md`** - ~2KB (au lieu de 50KB)

Utilisez ces fichiers pour éviter l'erreur de contexte.
