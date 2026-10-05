# run_all_ollama_models.ps1
# Enregistre localement tous les modèles cloud Ollama (pull) pour qu'ils
# apparaissent dans `ollama list` et soient utilisables par des outils tiers
# (ex: GitHub Copilot via son provider Ollama).
#
# IMPORTANT: `ollama run <model>` sans prompt ouvre une session interactive (REPL)
# et bloque indéfiniment un script batch. On utilise donc `ollama pull` pour
# l'enregistrement, puis un test optionnel one-shot avec timeout.

$ErrorActionPreference = "Continue"

# Liste vérifiée par exécution réelle de `ollama pull` sur chaque entrée (pas seulement
# déduite de la doc, qui contenait plusieurs tags inexistants — voir modèles exclus
# en bas de fichier). Testé juillet 2026.
$models = @(
  "glm-5.2:cloud",
  "glm-5.1:cloud",
  "glm-5:cloud",
  "glm-4.7:cloud",
  "kimi-k2.7-code:cloud",
  "kimi-k2.6:cloud",
  "kimi-k2.5:cloud",
  "gemma4:cloud",
  "gemma4:31b-cloud",
  "qwen3.5:cloud",
  "qwen3.5:397b-cloud",
  "qwen3-coder:480b-cloud",
  "minimax-m2.1:cloud",
  "minimax-m2.5:cloud",
  "minimax-m2.7:cloud",
  "minimax-m3:cloud",
  "nemotron-3-super:cloud",
  "nemotron-3-nano:30b-cloud",
  "deepseek-v4-flash:cloud",
  "deepseek-v4-pro:cloud",
  "deepseek-v3.2:cloud",
  "gpt-oss:20b-cloud",
  "gpt-oss:120b-cloud",
  "gemini-3-flash-preview:cloud"
)

# Modèles testés et EXCLUS car le pull échoue réellement ("pull model manifest: file
# does not exist") — tags qui n'existent pas malgré ce que suggérait la doc/le fetch web :
#   gemma4:e2b-cloud, gemma4:e4b-cloud, gemma4:12b-cloud, gemma4:26b-cloud
#   qwen3.5:latest-cloud, 0.8b-cloud, 2b-cloud, 4b-cloud, 9b-cloud, 27b-cloud, 35b-cloud, 122b-cloud (et tous leurs variants quant/mlx-cloud)
#   qwen3-coder:30b-cloud, qwen3-coder:30b-a3b-cloud
#   nemotron-3-super:120b-cloud, nemotron-3-ultra:cloud, nemotron-3-nano:cloud, nemotron-3-nano:4b-cloud
#   deepseek-v3.1:671b-cloud
# Toute variante NON taguée "cloud" (ex: gemma4:31b, gpt-oss:120b, nemotron-3-super:120b-a12b-bf16)
# télécharge le modèle complet en local (potentiellement 10aines/100aines de Go) — exclue
# volontairement : ce script ne doit enregistrer QUE des modèles cloud légers.
# Si ollama.com publie ces tags plus tard, on pourra les rajouter après nouveau test.

# Timeout par modèle pour le test one-shot (secondes)
$testTimeoutSec = 120
# Passer à $true pour lancer un prompt de test après chaque pull (plus lent, vérifie l'inférence réelle)
$runSmokeTest = $false

# --- Pré-vérifications ---

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Error "CLI 'ollama' introuvable dans le PATH. Installez Ollama avant de continuer."
    exit 1
}

# NB: `ollama` n'a pas de sous-commande "whoami" — pas de moyen direct d'interroger
# le statut de connexion. On se contente d'avertir ; l'échec réel (si non connecté)
# sera détecté modèle par modèle via le code de sortie de `ollama pull`.
Write-Host "Rappel : les modèles cloud nécessitent un compte connecté. Si besoin : 'ollama signin'."

$logDir = Join-Path -Path (Get-Location) -ChildPath "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$results = @()

foreach ($m in $models) {
    $safeName = $m -replace '[\\/:*?"<>|]', '_'
    $logFile = Join-Path $logDir "$safeName.log"
    Write-Host "=== Pull : $m ==="

    try {
        # NB: rediriger le flux natif via PowerShell (*>&1, *>) fait que PowerShell 5.1
        # enveloppe chaque ligne stderr dans un NativeCommandError, même si l'exit code
        # final est 0. On passe donc par `cmd /c` pour une redirection niveau OS, propre.
        $escapedLog = $logFile -replace '"', '""'
        $maxRetries = 3
        $attempt = 0
        do {
            $attempt++
            cmd /c "ollama pull `"$m`" > `"$escapedLog`" 2>&1"
            $pullExit = $LASTEXITCODE

            $rawLog = if (Test-Path $logFile) { Get-Content -Path $logFile -Raw } else { "" }
            # Erreurs transitoires côté serveur Ollama (rate-limit / timeout upstream) : on retente.
            $isTransient = $rawLog -match "503|upstream connect error|connection timeout"

            if ($pullExit -ne 0 -and $isTransient -and $attempt -lt $maxRetries) {
                $backoff = 5 * $attempt
                Write-Host "Erreur transitoire pour $m (tentative $attempt/$maxRetries). Nouvel essai dans ${backoff}s..." -ForegroundColor Yellow
                Start-Sleep -Seconds $backoff
            }
        } while ($pullExit -ne 0 -and $isTransient -and $attempt -lt $maxRetries)

        # Ollama émet des séquences ANSI (spinner) même en sortie redirigée : on les
        # retire du fichier de log pour qu'il reste lisible en texte brut.
        if (Test-Path $logFile) {
            $rawLog = Get-Content -Path $logFile -Raw
            if ($rawLog) {
                $cleanLog = $rawLog -replace '\x1b\[[0-9;?]*[a-zA-Z]', ''
                Set-Content -Path $logFile -Value $cleanLog -Encoding UTF8
            }
        }

        if ($pullExit -ne 0) {
            Write-Host "Échec du pull pour $m (exit $pullExit). Voir $logFile" -ForegroundColor Red
            $results += [PSCustomObject]@{ Model = $m; Pull = "ÉCHEC"; Test = "N/A" }
            Start-Sleep -Seconds 1
            continue
        }

        Write-Host "Pull réussi pour $m." -ForegroundColor Green
        $testStatus = "Ignoré"

        if ($runSmokeTest) {
            Write-Host "Test one-shot (timeout ${testTimeoutSec}s)..."
            $job = Start-Job -ScriptBlock {
                param($model)
                & ollama run $model "Réponds uniquement par: OK" 2>&1
            } -ArgumentList $m

            if (Wait-Job $job -Timeout $testTimeoutSec) {
                $testOutput = Receive-Job $job
                Add-Content -Path $logFile -Value "`n--- Smoke test ---`n$testOutput"
                $testStatus = "OK"
                Write-Host "Test réussi pour $m." -ForegroundColor Green
            } else {
                Stop-Job $job | Out-Null
                Add-Content -Path $logFile -Value "`n--- Smoke test : TIMEOUT après ${testTimeoutSec}s ---"
                $testStatus = "TIMEOUT"
                Write-Host "Timeout du test pour $m." -ForegroundColor Yellow
            }
            Remove-Job $job -Force | Out-Null
        }

        $results += [PSCustomObject]@{ Model = $m; Pull = "OK"; Test = $testStatus }
    } catch {
        $_ | Out-String | Add-Content -Path $logFile
        Write-Host "Exception pour $m : $_" -ForegroundColor Red
        $results += [PSCustomObject]@{ Model = $m; Pull = "EXCEPTION"; Test = "N/A" }
    }

    Start-Sleep -Seconds 1
}

Write-Host "`n=== Résumé ==="
$results | Format-Table -AutoSize
Write-Host "Batch terminé. Logs dans $logDir"

$failed = $results | Where-Object { $_.Pull -ne "OK" }
if ($failed) {
    Write-Warning "$($failed.Count) modèle(s) en échec. Consultez les logs correspondants."
}
