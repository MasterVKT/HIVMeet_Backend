# Déploiement multi-agent de `code-review-graph`

> Guide reproductible pour isoler un graphe de code par dépôt et l'exposer à
> plusieurs agents AI dans un workspace VS Code.

- **Dernière vérification du guide :** 16 juillet 2026
- **Public visé :** agents AI d'implémentation, mainteneurs et administrateurs
  de workspaces de développement
- **Périmètre :** serveur MCP local `code-review-graph`, configurations projet,
  compatibilité Cline et validation de l'isolation

## 1. Objectif et résultat attendu

Ce guide résout un problème précis : un serveur MCP configuré globalement peut
être lancé depuis plusieurs workspaces tout en continuant à référencer le dépôt
qui a été codé en dur dans sa configuration. Dans ce cas, l'agent croit analyser
le projet actif alors que ses outils interrogent le graphe d'un autre projet.

Le résultat conforme possède les propriétés suivantes :

1. chaque dépôt dispose de sa propre base `.code-review-graph/graph.db` ;
2. chaque serveur reçoit explicitement la racine de son dépôt avec `--repo` ;
3. le processus démarre dans cette même racine avec `cwd` ;
4. `CRG_REPO_ROOT` et `CRG_DATA_DIR` confirment les mêmes chemins ;
5. les données du graphe sont ignorées par Git ;
6. chaque client MCP charge la configuration propre au workspace ;
7. toute résolution ambiguë échoue au lieu de choisir silencieusement un
   projet ;
8. les validations prouvent qu'aucun fichier indexé ne sort de la racine
   attendue.

Le graphe est local et persistant. Il ne doit pas être considéré comme un cache
global partageable entre dépôts, même lorsque les dépôts appartiennent au même
produit.

## 2. Sources de vérité et statut des informations

Les comportements génériques de ce guide s'appuient sur les documentations
officielles suivantes :

- [`code-review-graph`](https://github.com/tirth8205/code-review-graph) :
  installation, `build`, `status`, `serve`, `--repo`, Python 3.10+ et
  configuration Windows directe de l'exécutable ;
- [Codex MCP](https://developers.openai.com/codex/mcp/) :
  `.codex/config.toml`, serveurs STDIO, `command`, `args`, `env`, `cwd` et
  commandes `codex mcp` ;
- [Claude Code MCP](https://code.claude.com/docs/en/mcp) et
  [paramètres Claude Code](https://code.claude.com/docs/en/settings) :
  `.mcp.json`, portées, confiance et approbation des serveurs projet ;
- [VS Code MCP](https://code.visualstudio.com/docs/agent-customization/mcp-servers) ;
- [Cursor MCP](https://docs.cursor.com/context/model-context-protocol) ;
- [Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/) ;
- [Cline MCP](https://docs.cline.bot/mcp/mcp-overview) ;
- [Continue MCP](https://docs.continue.dev/customize/deep-dives/mcp) ;
- [Kiro MCP](https://kiro.dev/docs/mcp/configuration/) ;
- [Kilo Code MCP](https://kilo.ai/docs/automate/tools/use-mcp-tool) et
  [Kilo CLI MCP](https://kilo.ai/docs/automate/mcp/using-in-cli) ;
- [Qoder IDE MCP](https://docs.qoder.com/user-guide/chat/model-context-protocol)
  et [Qoder CLI MCP](https://docs.qoder.com/en/cli/mcp-servers).

Les sections intitulées **Cas XP SafeConnect** décrivent une exécution réelle
sur Windows. Les modèles macOS et Linux sont des adaptations portables fondées
sur les conventions des outils ; ils doivent être testés sur la machine cible.

## 3. Architecture et principes d'isolation

Tous les clients doivent exprimer le même contrat logique, même si leur format
de fichier varie :

```text
server name  = code-review-graph
transport    = stdio
command      = <CRG_EXECUTABLE>
args         = ["serve", "--repo", "<PROJECT_ROOT>"]
cwd          = <PROJECT_ROOT>
PYTHONUTF8   = 1
CRG_REPO_ROOT= <PROJECT_ROOT>
CRG_DATA_DIR = <PROJECT_ROOT>/.code-review-graph
```

### 3.1 Variables utilisées dans ce guide

| Variable | Signification | Exemple POSIX | Exemple Windows |
| --- | --- | --- | --- |
| `<PROJECT_ROOT>` | Racine Git absolue du dépôt | `/work/app` | `D:\work\app` |
| `<VENV_ROOT>` | Environnement Python du dépôt | `/work/app/.venv` | `D:\work\app\.venv` |
| `<PYTHON_EXECUTABLE>` | Interpréteur Python réel | `/work/app/.venv/bin/python` | `D:\work\app\.venv\Scripts\python.exe` |
| `<CRG_EXECUTABLE>` | Exécutable `code-review-graph` | `/work/app/.venv/bin/code-review-graph` | `D:\work\app\.venv\Scripts\code-review-graph.exe` |
| `<CRG_DATA_DIR>` | Répertoire de données isolé | `/work/app/.code-review-graph` | `D:\work\app\.code-review-graph` |
| `<CRG_VERSION>` | Version validée et figée | `2.3.3` | `2.3.3` |

Dans les fichiers JSON, les chemins Windows peuvent être écrits avec des `/`
ou avec des `\\` correctement échappés. Ne coller jamais un chemin contenant
des `\` simples dans une chaîne JSON.

### 3.2 Pourquoi les quatre garde-fous sont redondants

- `command` impose l'installation Python voulue ;
- `--repo` sélectionne explicitement le dépôt analysé ;
- `cwd` empêche l'auto-détection de partir d'un dossier arbitraire ;
- `CRG_REPO_ROOT` et `CRG_DATA_DIR` verrouillent la racine et le stockage pour
  les composants qui consultent l'environnement.

Cette redondance est volontaire. Une configuration qui ne dépend que du `cwd`
du processus hôte est fragile : plusieurs extensions VS Code démarrent depuis
le dossier d'installation de VS Code, et non depuis le workspace.

## 4. Formulaire préalable obligatoire

Avant toute mutation, l'agent exécutant remplit et confirme ce formulaire :

```yaml
project_root: <chemin absolu obtenu avec git rev-parse --show-toplevel>
operating_system: <windows|macos|linux>
vscode_distribution: <code|code-insiders|vscodium|autre>
python_version: <version, doit être >= 3.10>
python_executable: <chemin absolu>
virtual_environment: <chemin absolu ou none>
crg_version_requested: <version figée>
crg_executable: <chemin absolu>
crg_data_dir: <PROJECT_ROOT>/.code-review-graph
mcp_clients:
  - <client et version>
configuration_scope: <project|local-user|global-user>
global_config_backup: <chemin de sauvegarde ou not-applicable>
```

Règles avant modification :

1. préférer la portée **projet** pour tout serveur lié au contenu du dépôt ;
2. ne jamais remplacer un fichier global complet ; fusionner uniquement
   l'entrée `code-review-graph` ;
3. sauvegarder toute configuration globale avec une date UTC ;
4. inventorier les autres serveurs sans afficher leurs variables sensibles ;
5. ne jamais recopier une clé, un jeton ou un en-tête d'authentification dans
   un rapport ou une sortie de diagnostic ;
6. préserver les modifications non liées déjà présentes dans le dépôt.

### 4.1 Sauvegarder une configuration globale

PowerShell :

```powershell
$GlobalConfig = "<ABSOLUTE_GLOBAL_CONFIG_PATH>"
$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Backup = "$GlobalConfig.$Timestamp.bak"
Copy-Item -LiteralPath $GlobalConfig -Destination $Backup -ErrorAction Stop
Write-Output "Backup=$Backup"
```

macOS/Linux :

```bash
set -euo pipefail
GLOBAL_CONFIG="<ABSOLUTE_GLOBAL_CONFIG_PATH>"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$GLOBAL_CONFIG.$TIMESTAMP.bak"
cp "$GLOBAL_CONFIG" "$BACKUP"
printf 'Backup=%s\n' "$BACKUP"
```

Après la copie, parser le fichier de sauvegarde avec le même validateur que
l'original. Pour fusionner une entrée, utiliser un parseur JSON/TOML ou
l'interface du client ; éviter les remplacements textuels globaux. Comparer
enfin la liste des noms de serveurs avant et après, sans afficher leurs valeurs
`env`, `headers` ou arguments potentiellement sensibles.

## 5. Installation portable et idempotente

### 5.1 Choisir le mode d'installation

| Mode | Usage recommandé | Avantage | Risque à gérer |
| --- | --- | --- | --- |
| Environnement virtuel du dépôt | Reproductibilité maximale | Exécutable et version isolés | Chemin propre à l'OS |
| `pipx` | Outil utilisateur partagé | Installation propre et simple | Même version pour plusieurs projets |
| `uvx` | Exécution outillée récente | Résolution rapide et isolée | Dépendance à `uv` |
| `pip` global | À éviter sauf environnement jetable | Simple | Conflits de versions et permissions |

Pour plusieurs projets indépendants, l'environnement virtuel local est le
choix le plus explicite. Si `pipx` ou `uvx` est retenu, chaque configuration
doit tout de même fournir son propre `--repo` et son propre `CRG_DATA_DIR`.

Le CLI officiel propose aussi `code-review-graph install`, qui détecte plusieurs
plateformes, ou `code-review-graph install --platform <name>`. Dans un contexte
multi-projet audité, exécuter cette commande séparément depuis chaque racine,
puis contrôler les fichiers générés avec le contrat de la section 3. Les
modèles manuels ci-dessous restent utiles lorsque le client n'est pas détecté
ou lorsque l'isolation doit être démontrée champ par champ.

La version validée dans le cas XP SafeConnect est `2.3.3`. Au 16 juillet 2026,
la page officielle des releases signalait une version plus récente (`2.3.6`).
Ne pas mettre à niveau silencieusement : installer la version demandée, puis
qualifier séparément toute nouvelle version.

### 5.2 Windows PowerShell

```powershell
$ProjectRoot = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $ProjectRoot) {
  throw "La commande doit être exécutée dans un dépôt Git."
}

Set-Location -LiteralPath $ProjectRoot
$VenvRoot = Join-Path $ProjectRoot ".venv"
$PythonExecutable = Join-Path $VenvRoot "Scripts\python.exe"
$CrgExecutable = Join-Path $VenvRoot "Scripts\code-review-graph.exe"
$CrgDataDir = Join-Path $ProjectRoot ".code-review-graph"
$CrgVersion = "<CRG_VERSION>"

if (-not (Test-Path -LiteralPath $PythonExecutable)) {
  python -m venv $VenvRoot
}

& $PythonExecutable -m pip install --upgrade pip
& $PythonExecutable -m pip install "code-review-graph==$CrgVersion"
& $CrgExecutable --version
& $CrgExecutable build --repo $ProjectRoot --data-dir $CrgDataDir
& $CrgExecutable status --repo $ProjectRoot --data-dir $CrgDataDir
```

Sur Windows, lancer directement `code-review-graph.exe`. Le projet officiel
signale que les wrappers `cmd /c` peuvent provoquer des erreurs JSON/EOF. Pour
le routeur Cline décrit plus loin, lancer également l'interpréteur
`python.exe` réel plutôt que `py.exe`.

### 5.3 macOS et Linux avec Bash

```bash
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
VENV_ROOT="$PROJECT_ROOT/.venv"
PYTHON_EXECUTABLE="$VENV_ROOT/bin/python"
CRG_EXECUTABLE="$VENV_ROOT/bin/code-review-graph"
CRG_DATA_DIR="$PROJECT_ROOT/.code-review-graph"
CRG_VERSION="<CRG_VERSION>"

cd "$PROJECT_ROOT"

if [[ ! -x "$PYTHON_EXECUTABLE" ]]; then
  python3 -m venv "$VENV_ROOT"
fi

"$PYTHON_EXECUTABLE" -m pip install --upgrade pip
"$PYTHON_EXECUTABLE" -m pip install "code-review-graph==$CRG_VERSION"
"$CRG_EXECUTABLE" --version
"$CRG_EXECUTABLE" build --repo "$PROJECT_ROOT" --data-dir "$CRG_DATA_DIR"
"$CRG_EXECUTABLE" status --repo "$PROJECT_ROOT" --data-dir "$CRG_DATA_DIR"
```

Sous macOS, les commandes sont identiques. Seuls les chemins des données des
applications VS Code changent dans le cas du routeur Cline.

### 5.4 Installation avec `pipx` ou `uvx`

```bash
# Installation utilisateur figée.
pipx install "code-review-graph==<CRG_VERSION>"
pipx runpip code-review-graph show code-review-graph

# Ou exécution ponctuelle avec uvx.
uvx --from "code-review-graph==<CRG_VERSION>" code-review-graph --version
```

Avec `uvx`, la valeur `command` du client peut être `uvx` et les arguments
doivent inclure `--from`, la version, puis `code-review-graph serve --repo ...`.
Tester cette commande complète dans un terminal avant de la placer dans MCP.

### 5.5 Ignorer la base locale

Ajouter une seule règle au `.gitignore` du dépôt si elle n'existe pas :

```gitignore
.code-review-graph/
```

Vérifier ensuite :

```bash
git check-ignore -v .code-review-graph/graph.db
git status --short -- .code-review-graph
```

La première commande doit afficher la règle d'exclusion. La seconde ne doit
retourner aucun fichier.

## 6. Matrice des clients MCP

| Client | Configuration projet recommandée | Configuration utilisateur/globale | `cwd` / `env` | Activation et preuve | Statut du cas réel |
| --- | --- | --- | --- | --- | --- |
| [Codex CLI/IDE](https://developers.openai.com/codex/mcp/) | `.codex/config.toml` | `~/.codex/config.toml` | Oui / oui | `codex mcp get code-review-graph` | Testé en exécution |
| [Claude Code](https://code.claude.com/docs/en/mcp) | `.mcp.json` | `~/.claude.json` selon la portée | Oui / oui | confiance + `claude mcp get code-review-graph` | Testé en exécution |
| [VS Code / Copilot](https://code.visualstudio.com/docs/agent-customization/mcp-servers) | `.vscode/mcp.json` | profil utilisateur VS Code | Oui / oui | panneau MCP / commande palette | Validé structurellement |
| [Cursor](https://docs.cursor.com/context/model-context-protocol) | `.cursor/mcp.json` | `~/.cursor/mcp.json` | Oui / oui | panneau MCP de Cursor | Validé structurellement |
| [Qoder IDE](https://docs.qoder.com/user-guide/chat/model-context-protocol) | éditeur MCP de Qoder ; adaptateur projet selon version | paramètres Qoder | Oui / oui | indicateur connecté | Validé structurellement |
| [Qoder CLI](https://docs.qoder.com/en/cli/mcp-servers) | `.mcp.json` en portée projet | `~/.qoder/settings.json` | Selon schéma | `qodercli mcp list` | Validé structurellement |
| [Gemini CLI](https://geminicli.com/docs/tools/mcp-server/) | `.gemini/settings.json` | `~/.gemini/settings.json` | Oui / oui | `gemini mcp list` ou `/mcp` | Validé structurellement |
| [Cline avec portée workspace](https://docs.cline.bot/mcp/mcp-overview) | emplacement annoncé par la version ; `.cline/mcp.json` seulement si prouvé | `~/.cline/mcp.json` pour le CLI ou fichier ouvert par l'IDE | Selon version / oui | `cline mcp` ou panneau IDE | Modèle conditionnel validé |
| [Cline VS Code 4.0.8](https://docs.cline.bot/mcp/mcp-overview) | fichier ouvert par **Configure MCP Servers** | fichier global de l'extension | Pas de `cwd` workspace fiable | logs + arbre de processus | Testé avec routeur |
| [Kilo Code](https://kilo.ai/docs/automate/tools/use-mcp-tool) | `.kilocode/mcp.json` | paramètres de l'extension | Oui / oui | panneau MCP | Validé structurellement |
| [Kilo CLI](https://kilo.ai/docs/automate/mcp/using-in-cli) | `.kilo/kilo.json` ou `.kilo/kilo.jsonc` | `~/.config/kilo/kilo.json` | commande tableau / environnement | `kilo mcp list` ou `/mcps` | Validé structurellement |
| [Kiro](https://kiro.dev/docs/mcp/configuration/) | `.kiro/settings/mcp.json` | `~/.kiro/settings/mcp.json` | Oui / oui | `/mcp` | Validé structurellement |
| [Continue](https://docs.continue.dev/customize/deep-dives/mcp) | `.continue/mcpServers/*.yaml` | configuration Continue | Oui / oui | mode Agent, liste des outils | Validé structurellement |

Les versions évoluent. Avant d'écrire un fichier, l'agent doit confirmer
l'emplacement réellement lu par la version installée. Une configuration
présente sur disque mais ignorée par le client n'est pas une activation.

## 7. Modèles de configuration

Remplacer tous les marqueurs `<...>`. Ne pas conserver les chevrons dans une
configuration finale.

### 7.1 JSON MCP commun

Ce modèle convient à `.mcp.json`, `.cursor/mcp.json`, `.gemini/settings.json`,
`.kiro/settings/mcp.json` et aux clients acceptant `mcpServers`. Certains
clients ignorent `type` ou `cwd`, mais leur présence est généralement tolérée ;
valider le schéma de la version cible.

```json
{
  "mcpServers": {
    "code-review-graph": {
      "type": "stdio",
      "command": "<CRG_EXECUTABLE>",
      "args": ["serve", "--repo", "<PROJECT_ROOT>"],
      "cwd": "<PROJECT_ROOT>",
      "env": {
        "PYTHONUTF8": "1",
        "CRG_REPO_ROOT": "<PROJECT_ROOT>",
        "CRG_DATA_DIR": "<PROJECT_ROOT>/.code-review-graph"
      }
    }
  }
}
```

Pour Gemini CLI, conserver le serveur sous la clé de premier niveau
`mcpServers`. Le dossier doit être approuvé/trusted pour que les serveurs STDIO
projet soient lancés.

Pour Qoder CLI, la documentation actuelle recommande `.mcp.json` pour la
portée projet partagée. Une ancienne configuration `.qoder/mcp.json` ne doit
être conservée que si la version installée prouve qu'elle la lit.

### 7.2 VS Code et GitHub Copilot

VS Code utilise la clé `servers` :

```json
{
  "servers": {
    "code-review-graph": {
      "type": "stdio",
      "command": "<CRG_EXECUTABLE>",
      "args": ["serve", "--repo", "<PROJECT_ROOT>"],
      "cwd": "<PROJECT_ROOT>",
      "env": {
        "PYTHONUTF8": "1",
        "CRG_REPO_ROOT": "<PROJECT_ROOT>",
        "CRG_DATA_DIR": "<PROJECT_ROOT>/.code-review-graph"
      }
    }
  }
}
```

Fusionner cette clé avec les autres serveurs déjà présents ; ne jamais
remplacer le fichier complet.

### 7.3 Codex TOML

```toml
[mcp_servers.code-review-graph]
enabled = true
command = "<CRG_EXECUTABLE>"
args = ["serve", "--repo", "<PROJECT_ROOT>"]
cwd = "<PROJECT_ROOT>"
startup_timeout_sec = 60
tool_timeout_sec = 120

[mcp_servers.code-review-graph.env]
PYTHONUTF8 = "1"
CRG_REPO_ROOT = "<PROJECT_ROOT>"
CRG_DATA_DIR = "<PROJECT_ROOT>/.code-review-graph"

[mcp_servers.code-review-graph.tools.get_minimal_context_tool]
approval_mode = "approve"

[mcp_servers.code-review-graph.tools.query_graph_tool]
approval_mode = "approve"

[mcp_servers.code-review-graph.tools.detect_changes_tool]
approval_mode = "approve"

[mcp_servers.code-review-graph.tools.get_impact_radius_tool]
approval_mode = "approve"
```

Limiter les approbations automatiques aux outils de lecture nécessaires. Les
outils qui construisent le graphe, produisent des fichiers ou appliquent un
refactoring doivent conserver la politique d'approbation du projet.

### 7.4 Continue YAML

Créer `.continue/mcpServers/code-review-graph.yaml` :

```yaml
name: Code Review Graph
version: 1.0.0
schema: v1
mcpServers:
  - name: code-review-graph
    type: stdio
    command: <CRG_EXECUTABLE>
    args:
      - serve
      - --repo
      - <PROJECT_ROOT>
    cwd: <PROJECT_ROOT>
    env:
      PYTHONUTF8: "1"
      CRG_REPO_ROOT: <PROJECT_ROOT>
      CRG_DATA_DIR: <PROJECT_ROOT>/.code-review-graph
    connectionTimeout: 120000
```

Continue n'expose les serveurs MCP qu'en mode Agent. Son dossier est
`.continue/mcpServers` avec un `S` final.

### 7.5 Kilo CLI JSONC

Créer `.kilo/kilo.jsonc` ou `.kilo/kilo.json` selon la version :

```jsonc
{
  "$schema": "https://app.kilo.ai/config.json",
  "mcp": {
    "code-review-graph": {
      "type": "local",
      "command": [
        "<CRG_EXECUTABLE>",
        "serve",
        "--repo",
        "<PROJECT_ROOT>"
      ],
      "environment": {
        "PYTHONUTF8": "1",
        "CRG_REPO_ROOT": "<PROJECT_ROOT>",
        "CRG_DATA_DIR": "<PROJECT_ROOT>/.code-review-graph"
      },
      "enabled": true,
      "timeout": 120000
    }
  }
}
```

Ici, `command` est un tableau contenant l'exécutable et ses arguments, et
`environment` remplace la clé `env` du JSON MCP commun.

### 7.6 Kilo Code

Créer `.kilocode/mcp.json` avec le modèle JSON MCP commun. La configuration
projet prend le pas sur un serveur global de même nom. Utiliser le panneau MCP
pour confirmer la connexion après sauvegarde.

### 7.7 Cline en configuration projet, uniquement si la version la documente

La documentation Cline actuelle garantit `~/.cline/mcp.json` pour le CLI et
demande d'ouvrir le fichier réellement utilisé depuis le panneau de
l'extension IDE. Elle ne garantit pas qu'un `.cline/mcp.json` placé dans chaque
workspace soit lu par toutes les versions. Le modèle suivant est donc un
adaptateur conditionnel : ne l'utiliser que si la version installée documente
ou démontre cette portée projet.

```json
{
  "mcpServers": {
    "code-review-graph": {
      "disabled": false,
      "timeout": 120,
      "type": "stdio",
      "command": "<CRG_EXECUTABLE>",
      "args": ["serve", "--repo", "<PROJECT_ROOT>"],
      "cwd": "<PROJECT_ROOT>",
      "env": {
        "PYTHONUTF8": "1",
        "CRG_REPO_ROOT": "<PROJECT_ROOT>",
        "CRG_DATA_DIR": "<PROJECT_ROOT>/.code-review-graph"
      },
      "autoApprove": [
        "get_minimal_context_tool",
        "query_graph_tool",
        "get_impact_radius_tool",
        "get_review_context_tool",
        "semantic_search_nodes_tool",
        "list_graph_stats_tool",
        "detect_changes_tool"
      ]
    }
  }
}
```

Ne présumer jamais que l'extension IDE lit le fichier du CLI. Ouvrir **Cline →
MCP Servers → Configure → Configure MCP Servers**, puis comparer le fichier
ouvert avec la configuration projet.

### 7.8 Approbation Claude Code

Le serveur projet est déclaré dans `.mcp.json`. L'approbation personnelle doit
rester dans `.claude/settings.local.json` :

```json
{
  "enabledMcpjsonServers": ["code-review-graph"]
}
```

Si le fichier contient déjà d'autres paramètres, fusionner uniquement la clé
ou ajouter le nom à la liste. Ne pas utiliser `enableAllProjectMcpServers` pour
contourner un choix ciblé. Le workspace doit d'abord être marqué comme fiable.

Vérification :

```bash
claude mcp get code-review-graph
```

Le résultat attendu contient `Status: Connected`, le bon exécutable et le bon
`--repo`.

## 8. Cline : traitement de la configuration globale

### 8.1 Quand le routeur est nécessaire

Utiliser le routeur uniquement si les trois conditions sont réunies :

1. la version installée de Cline utilise un unique fichier global pour tous les
   workspaces ;
2. la configuration globale ne permet pas d'injecter la racine du workspace ;
3. plusieurs workspaces doivent utiliser des graphes locaux différents.

Sinon, préférer une configuration projet native. Le routeur dépend de détails
de l'hôte VS Code et doit donc rester un mécanisme de compatibilité testé.

### 8.2 Constat Windows avec Cline VS Code 4.0.8

Dans le cas observé :

- l'extension ne contenait aucune référence à `.cline/mcp.json` ;
- elle ouvrait le fichier global `cline_mcp_settings.json` ;
- le processus d'extension host avait pour `cwd` le dossier d'installation de
  VS Code, pas le dépôt ;
- Cline ne déclarait pas la capacité MCP `roots`, donc le serveur ne pouvait
  pas demander la racine active avec `roots/list` ;
- `py.exe` créait un processus intermédiaire : dans le script Python,
  `os.getppid()` renvoyait le lanceur Python et non l'extension host ;
- appeler directement le véritable `python.exe` rétablissait la filiation
  `extension host → routeur Python → code-review-graph`.

### 8.3 Résolution de la fenêtre VS Code

Le routeur applique cet ordre :

1. tester `Path.cwd()` ;
2. obtenir le PID parent ;
3. rechercher `Extension host with pid <PID> started` dans les journaux VS
   Code ;
4. associer ce journal à son dossier `windowN` ;
5. extraire l'identifiant `workspaceStorage/<id>` ;
6. lire `<user-data>/User/workspaceStorage/<id>/workspace.json` ;
7. convertir l'URI `file://` en chemin ;
8. comparer le chemin à l'allowlist des dépôts ;
9. démarrer le seul serveur correspondant ;
10. sortir avec un code non nul si l'identification n'est pas unique.

### 8.4 Emplacements des données VS Code

| Distribution | Windows | macOS | Linux |
| --- | --- | --- | --- |
| VS Code | `%APPDATA%\Code` | `~/Library/Application Support/Code` | `${XDG_CONFIG_HOME:-~/.config}/Code` |
| VS Code Insiders | `%APPDATA%\Code - Insiders` | `~/Library/Application Support/Code - Insiders` | `${XDG_CONFIG_HOME:-~/.config}/Code - Insiders` |
| VSCodium | `%APPDATA%\VSCodium` | `~/Library/Application Support/VSCodium` | `${XDG_CONFIG_HOME:-~/.config}/VSCodium` |

Le routeur doit parcourir uniquement les distributions réellement autorisées.
Toute variante portable ou profil lancé avec `--user-data-dir` nécessite
d'ajouter explicitement son dossier de données.

### 8.5 Routeur neutralisé de référence

Le modèle suivant ne contient aucun chemin personnel. Remplacer l'allowlist et
tester chaque projet avant de l'utiliser globalement.

```python
"""Route un serveur code-review-graph global vers un workspace autorisé."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


PROJECTS = (
    (Path("<PROJECT_A_ROOT>"), Path("<PROJECT_A_CRG_EXECUTABLE>")),
    (Path("<PROJECT_B_ROOT>"), Path("<PROJECT_B_CRG_EXECUTABLE>")),
)


def is_within(candidate: Path, root: Path) -> bool:
    candidate_norm = os.path.normcase(str(candidate.resolve()))
    root_norm = os.path.normcase(str(root.resolve()))
    try:
        return os.path.commonpath((candidate_norm, root_norm)) == root_norm
    except ValueError:
        return False


def file_uri_to_path(value: str) -> Path | None:
    parsed = urlparse(value)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    decoded = unquote(parsed.path)
    if os.name == "nt" and re.match(r"^/[A-Za-z]:/", decoded):
        decoded = decoded[1:]
    return Path(decoded.replace("/", os.sep))


def vscode_data_roots() -> tuple[Path, ...]:
    home = Path.home()
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return ()
        base = Path(appdata)
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return tuple(base / name for name in ("Code", "Code - Insiders", "VSCodium"))


def workspace_from_extension_host(parent_pid: int) -> Path | None:
    pid_pattern = re.compile(
        rf"Extension host with pid\s+{re.escape(str(parent_pid))}\s+started",
        re.IGNORECASE,
    )
    storage_pattern = re.compile(
        r"workspaceStorage[\\/]([0-9a-f]{32})(?:[\\/.]|$)",
        re.IGNORECASE,
    )

    candidates: list[tuple[float, Path, Path]] = []
    for code_root in vscode_data_roots():
        logs_root = code_root / "logs"
        storage_root = code_root / "User" / "workspaceStorage"
        if not logs_root.is_dir() or not storage_root.is_dir():
            continue
        for log_path in logs_root.glob("*/window*/exthost/exthost.log"):
            candidates.append((log_path.stat().st_mtime, log_path, storage_root))

    for _, log_path, storage_root in sorted(candidates, reverse=True):
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not pid_pattern.search(text):
            continue
        storage_ids = storage_pattern.findall(text)
        if not storage_ids:
            return None
        metadata_path = storage_root / storage_ids[-1] / "workspace.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        folder_uri = metadata.get("folder")
        if not isinstance(folder_uri, str):
            return None
        return file_uri_to_path(folder_uri)
    return None


def identify_project() -> tuple[Path, Path] | None:
    for candidate in (Path.cwd(), workspace_from_extension_host(os.getppid())):
        if candidate is None:
            continue
        matches = [entry for entry in PROJECTS if is_within(candidate, entry[0])]
        if len(matches) == 1:
            return matches[0]
    return None


def main() -> int:
    project = identify_project()
    if project is None:
        print(
            "Routeur refusé : aucun workspace autorisé unique n'a été identifié.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    root, executable = project
    if not executable.is_file():
        print(f"Exécutable introuvable : {executable}", file=sys.stderr, flush=True)
        return 3

    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONUTF8": "1",
            "CRG_REPO_ROOT": str(root),
            "CRG_DATA_DIR": str(root / ".code-review-graph"),
        }
    )
    process = subprocess.Popen(
        (str(executable), "serve", "--repo", str(root)),
        cwd=root,
        env=environment,
    )
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
```

Limites explicites de ce modèle :

- il gère les workspaces ouverts sur un dossier unique ;
- un fichier `.code-workspace` multi-racines exige une politique de sélection
  supplémentaire et doit échouer tant qu'elle n'est pas définie ;
- le format des journaux VS Code peut changer ;
- les chemins réseau et environnements distants doivent être testés séparément ;
- si Cline ajoute une configuration workspace fiable, supprimer ce routeur au
  profit de la fonctionnalité native.

### 8.6 Entrée globale Cline neutralisée

Sauvegarder le fichier global, puis fusionner uniquement cette entrée :

```json
{
  "mcpServers": {
    "code-review-graph": {
      "disabled": false,
      "timeout": 120,
      "type": "stdio",
      "command": "<PYTHON_EXECUTABLE>",
      "args": ["<ABSOLUTE_PATH_TO_ROUTER>/code-review-graph-project-router.py"],
      "autoApprove": [
        "get_minimal_context_tool",
        "query_graph_tool",
        "get_impact_radius_tool",
        "get_review_context_tool",
        "semantic_search_nodes_tool",
        "list_graph_stats_tool",
        "detect_changes_tool"
      ]
    }
  }
}
```

Ne jamais remplacer l'objet `mcpServers` complet : les serveurs globaux sans
rapport avec ce guide doivent rester inchangés.

## 9. Activation et rechargement

Après modification :

1. valider la syntaxe du fichier ;
2. fermer les anciens processus MCP si le client ne les remplace pas ;
3. recharger la fenêtre ou utiliser la commande de reload du client ;
4. vérifier le statut avant d'appeler un outil ;
5. lancer `get_minimal_context_tool` comme premier test de lecture.

Commandes disponibles selon le client :

```bash
codex mcp get code-review-graph
claude mcp get code-review-graph
gemini mcp list
qodercli mcp list
kilo mcp list
```

Dans Cline, Kiro, Kilo Code, Cursor, Continue et VS Code, utiliser également le
panneau MCP ou la commande `/mcp` prévue par la version installée.

## 10. Validation technique complète

### 10.1 Version et commande réelle

```bash
"<CRG_EXECUTABLE>" --version
"<CRG_EXECUTABLE>" status --repo "<PROJECT_ROOT>" --data-dir "<CRG_DATA_DIR>"
```

La version doit correspondre à `<CRG_VERSION>`. En cas de différence, ne pas
continuer avant d'avoir qualifié la compatibilité ou corrigé l'exécutable.

### 10.2 Test direct du protocole MCP

Ce script envoie `initialize`, `notifications/initialized`, puis `tools/list`.
Il doit afficher le nom du serveur et le nombre d'outils :

```python
import json
import subprocess

command = [
    "<CRG_EXECUTABLE>",
    "serve",
    "--repo",
    "<PROJECT_ROOT>",
]

process = subprocess.Popen(
    command,
    cwd="<PROJECT_ROOT>",
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

initialize = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "crg-smoke-test", "version": "1"},
    },
}
process.stdin.write(json.dumps(initialize) + "\n")
process.stdin.flush()
initialize_reply = json.loads(process.stdout.readline())

process.stdin.write(
    json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    )
    + "\n"
)
process.stdin.write(
    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    + "\n"
)
process.stdin.flush()
tools_reply = json.loads(process.stdout.readline())

process.stdin.close()
process.wait(timeout=30)

server = initialize_reply["result"]["serverInfo"]["name"]
tools = tools_reply["result"]["tools"]
print(f"server={server} tools={len(tools)} exit={process.returncode}")
```

La version validée dans le cas réel exposait 30 outils. Une version ultérieure
peut en exposer un nombre différent ; comparer le résultat à la documentation
de la version installée plutôt que d'imposer éternellement le nombre 30.

### 10.3 Isolation SQLite en lecture seule

```python
import os
import sqlite3
from pathlib import Path

root = Path("<PROJECT_ROOT>").resolve()
database = root / ".code-review-graph" / "graph.db"
uri = database.as_uri() + "?mode=ro"

with sqlite3.connect(uri, uri=True) as connection:
    nodes = connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    paths = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT file_path FROM nodes "
            "WHERE file_path IS NOT NULL AND file_path != ''"
        )
    ]

outside = []
for value in paths:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        inside = os.path.commonpath(
            (os.path.normcase(str(candidate.resolve())), os.path.normcase(str(root)))
        ) == os.path.normcase(str(root))
    except ValueError:
        inside = False
    if not inside:
        outside.append(value)

print(f"nodes={nodes} files={len(paths)} outside={len(outside)}")
if outside:
    raise SystemExit(f"Fichiers extérieurs détectés : {outside[:10]}")
```

Le critère d'acceptation est `outside=0` pour chaque dépôt.

### 10.4 Arbre des processus Cline

Windows PowerShell :

```powershell
$Processes = Get-CimInstance Win32_Process
$Routers = @(
  $Processes | Where-Object {
    $_.Name -eq "python.exe" -and
    $_.CommandLine -like "*code-review-graph-project-router.py*"
  }
)
$RouterIds = @($Routers | Select-Object -ExpandProperty ProcessId)
$Servers = @(
  $Processes | Where-Object {
    $_.Name -eq "code-review-graph.exe" -and
    $_.CommandLine -like "* serve --repo *"
  }
)

$Routers | Select-Object ProcessId, ParentProcessId, CommandLine
$Servers | Select-Object ProcessId, ParentProcessId, CommandLine
```

macOS/Linux :

```bash
ps -eo pid,ppid,args | grep -E \
  'code-review-graph-project-router.py|code-review-graph serve --repo' | \
  grep -v grep
```

Pour chaque workspace, il doit exister une chaîne cohérente :

```text
extension host du workspace
└── routeur Python
    └── <CRG_EXECUTABLE> serve --repo <PROJECT_ROOT>
```

### 10.5 Validation des formats

```bash
# JSON standard.
python -m json.tool .mcp.json >/dev/null
python -m json.tool .vscode/mcp.json >/dev/null
python -m json.tool .cursor/mcp.json >/dev/null
python -m json.tool .gemini/settings.json >/dev/null
python -m json.tool .kiro/settings/mcp.json >/dev/null

# TOML avec Python 3.11+.
python -c "import tomllib,pathlib; tomllib.loads(pathlib.Path('.codex/config.toml').read_text())"

# YAML et JSONC/Markdown avec Prettier si le projet l'utilise.
npx --yes prettier --check \
  .continue/mcpServers/code-review-graph.yaml \
  .kilo/kilo.jsonc \
  docs/technical/CODE_REVIEW_GRAPH_MULTI_AGENT_SETUP.md
```

Adapter `python` à `<PYTHON_EXECUTABLE>` sous Windows. Ne pas installer un
formateur global uniquement pour cette vérification si le projet possède déjà
son propre hook.

### 10.6 Contrôles Git

```bash
git diff --check
git check-ignore -v .code-review-graph/graph.db
git status --short -- .code-review-graph
```

### 10.7 Test d'échec fermé du routeur

Lancer le routeur depuis un dossier qui n'est ni un projet autorisé ni une
fenêtre VS Code associée :

```bash
cd "<UNRELATED_DIRECTORY>"
"<PYTHON_EXECUTABLE>" "<ABSOLUTE_PATH_TO_ROUTER>/code-review-graph-project-router.py"
```

Résultat attendu : code de sortie `2`, message sur `stderr`, aucun serveur
`code-review-graph` enfant.

## 11. Audit automatisé minimal

Un agent peut appliquer cette logique à chaque projet :

1. parser chaque fichier de configuration ;
2. aplatir toutes les valeurs texte ;
3. confirmer la présence de `<PROJECT_ROOT>`, `<CRG_EXECUTABLE>`, `serve`,
   `--repo`, `CRG_REPO_ROOT` et `CRG_DATA_DIR` ;
4. confirmer que l'exécutable existe ;
5. confirmer que la base existe ;
6. exécuter le test SQLite ;
7. exécuter le handshake MCP ;
8. vérifier les statuts des clients installés.

Le rapport d'audit doit distinguer :

- **testé en exécution** : le client a lancé le serveur et listé les outils ;
- **connecté selon le client** : la commande ou l'UI annonce la connexion ;
- **validé structurellement** : le fichier est syntaxiquement correct et
  contient les bons chemins, mais le client n'a pas été exécuté ;
- **non vérifié** : aucune preuve suffisante.

Ne jamais transformer « validé structurellement » en « activé » dans un compte
rendu.

## 12. Tableau de dépannage

| Symptôme | Cause probable | Diagnostic | Correction sûre |
| --- | --- | --- | --- |
| Exécutable introuvable | Mauvais environnement virtuel ou chemin relatif | Exécuter `<CRG_EXECUTABLE> --version` | Retrouver l'exécutable absolu et mettre à jour uniquement l'entrée concernée |
| Le mauvais dépôt apparaît | `--repo` ou `CRG_DATA_DIR` pointe ailleurs | Inspecter commande, environnement et SQLite | Aligner les quatre garde-fous, reconstruire le graphe local |
| Cline partage le graphe entre fenêtres | Configuration IDE globale avec chemin codé en dur | Ouvrir le fichier réellement utilisé par Cline | Utiliser la configuration projet native ou le routeur fail-closed |
| Cline ne lance pas le routeur | PID parent masqué par `py.exe` sous Windows | Inspecter l'arbre des processus | Appeler directement le vrai `python.exe` |
| Claude reste en attente | Workspace non fiable ou serveur projet non approuvé | `claude mcp get code-review-graph` et panneau `/mcp` | Approuver dans `settings.local.json`, puis accepter la confiance du dossier |
| `Invalid JSON: EOF` ou connexion fermée sous Windows | Wrapper shell ou encodage | Lancer l'exécutable directement | Utiliser `.exe` + `PYTHONUTF8=1`, éviter `cmd /c` |
| JSON invalide | Antislash Windows non échappé ou virgule manquante | `python -m json.tool` | Utiliser `/` ou `\\`, puis reformater |
| Démarrage trop lent | Graphe initial ou timeout client trop court | Lancer `status` et mesurer le handshake | Porter le startup/connection timeout à 60–120 s |
| Aucun outil visible | Serveur non initialisé, filtrage ou mauvais mode | Test `tools/list`, vérifier `CRG_TOOLS` | Retirer le filtre involontaire ; utiliser le mode Agent si requis |
| Nombre d'outils inférieur | Version différente ou allowlist | `--version`, `CRG_TOOLS`, config client | Comparer à la version installée et documenter le filtrage |
| Base partagée | `CRG_DATA_DIR` global | Lire la ligne de commande et l'environnement | Utiliser `<PROJECT_ROOT>/.code-review-graph` par dépôt |
| Processus orphelin | Reload incomplet du client | Inspecter PID/PPID et commande | Fermer uniquement le processus identifié, puis reconnecter le client |
| Routeur refuse un workspace valide | Journal ou `workspaceStorage` non trouvé | Vérifier le dossier de données VS Code | Ajouter explicitement la distribution/profil ou abandonner le routeur pour la config native |
| Workspace multi-root non supporté | `workspace.json` référence un `.code-workspace` | Lire les métadonnées sans les modifier | Définir une politique explicite ou échouer fermé |

## 13. Sécurité et maintenance

- Ne jamais committer de secrets dans un fichier MCP.
- Utiliser les expansions d'environnement prévues par chaque client pour les
  serveurs qui exigent des identifiants ; `code-review-graph` local n'en exige
  normalement aucun.
- Limiter `autoApprove` aux outils de lecture jugés sûrs par le projet.
- Réévaluer le routeur après toute mise à jour de Cline ou VS Code.
- Figer la version de `code-review-graph` dans les environnements reproductibles.
- Qualifier une mise à jour dans un seul dépôt pilote avant de l'étendre.
- Refaire le handshake MCP, l'audit SQLite et les statuts clients après une
  mise à jour.
- Ne pas inscrire `.code-review-graph` dans un registre multi-dépôts si
  l'objectif est une isolation stricte par workspace.
- Documenter la date, la version du client et la preuve de connexion.

## 14. Checklist de livraison à un autre agent AI

L'agent chargé de l'implémentation doit rendre les preuves suivantes :

- [ ] formulaire préalable complété ;
- [ ] racine Git obtenue par commande, non supposée ;
- [ ] Python >= 3.10 confirmé ;
- [ ] version CRG choisie et figée ;
- [ ] exécutable absolu testé ;
- [ ] graphe construit dans le dépôt ;
- [ ] `.code-review-graph/` ignoré par Git ;
- [ ] configuration projet créée pour chaque client installé ;
- [ ] configurations globales sauvegardées et fusionnées sans perte ;
- [ ] Cline natif utilisé si possible ;
- [ ] routeur utilisé uniquement si nécessaire ;
- [ ] routeur testé positivement dans chaque workspace ;
- [ ] routeur testé négativement hors allowlist ;
- [ ] handshake MCP réussi ;
- [ ] outils listés ;
- [ ] `outside=0` dans chaque base ;
- [ ] statuts Codex/Claude/autres clients enregistrés ;
- [ ] formats parsés ou vérifiés ;
- [ ] `git diff --check` réussi ;
- [ ] aucun secret présent dans le diff ou le rapport ;
- [ ] première conclusion rejetée et seconde passe effectuée.

## 15. Cas XP SafeConnect — preuves observées

Cette annexe est factuelle. Elle ne doit pas servir de modèle de chemins pour
une autre machine.

### 15.1 Projets et bases

| Projet logique | Fichiers indexés | Nœuds | Fichiers extérieurs | Base |
| --- | ---: | ---: | ---: | --- |
| `monitor_app` | 306 | 5 526 | 0 | `<MONITOR_APP_ROOT>/.code-review-graph/graph.db` |
| `monitored_app` | 188 | 3 395 | 0 | `<MONITORED_APP_ROOT>/.code-review-graph/graph.db` |
| backend | 331 | 3 744 | 0 | `<BACKEND_ROOT>/.code-review-graph/graph.db` |

Les trois environnements exécutaient `code-review-graph 2.3.3`. Les trois bases
étaient ignorées par Git et absentes de `git status`.

### 15.2 Clients configurés

Onze familles de formats projet ont été contrôlées pour chaque dépôt :

1. Codex TOML ;
2. VS Code MCP JSON ;
3. `.mcp.json` partagé ;
4. Cursor ;
5. Qoder ;
6. Gemini ;
7. Cline projet ;
8. Kilo Code ;
9. Kilo CLI ;
10. Kiro ;
11. Continue.

L'audit final a exécuté 38 contrôles de présence, syntaxe et cohérence sans
échec. Codex et Claude Code ont été interrogés depuis chacun des trois dépôts et
ont retourné un serveur activé/connecté avec le bon exécutable et le bon
`--repo`.

### 15.3 Cline en exécution réelle

La version installée était Cline VS Code `4.0.8`. Après remplacement de la
commande globale par le routeur :

- trois processus routeurs Python distincts étaient actifs ;
- chacun était enfant de l'extension host de sa fenêtre VS Code ;
- chaque routeur possédait un enfant `code-review-graph` distinct ;
- les commandes enfants contenaient respectivement les racines de
  `monitor_app`, `monitored_app` et du backend ;
- les trois journaux se terminaient par une reconnexion réussie du serveur ;
- le serveur exposait 30 outils dans chaque test MCP ;
- un lancement hors des workspaces autorisés retournait le code `2` sans
  démarrer de serveur.

Les autres serveurs globaux Cline ont été préservés. Leur contenu, leurs
variables et leurs éventuels secrets ne font pas partie de ce rapport.

## 16. Critères d'acceptation finaux

Le déploiement n'est terminé que si toutes ces affirmations sont vraies :

1. un agent inconnu du projet peut déterminer tous les chemins sans les
   deviner ;
2. chaque projet utilise une base distincte ;
3. chaque client installé pointe vers le même contrat d'isolation ;
4. chaque configuration globale a été fusionnée sans supprimer d'autres
   serveurs ;
5. chaque client annoncé comme « activé » possède une preuve d'exécution ;
6. les clients non lancés sont décrits comme « validés structurellement » ;
7. le routeur Cline échoue fermé ;
8. le test SQLite retourne `outside=0` ;
9. aucun secret ni chemin personnel n'est présent dans les modèles génériques ;
10. les données du cas réel restent confinées à l'annexe ;
11. le formatage et les contrôles Git réussissent ;
12. une seconde revue contre la demande originale a été réalisée.
