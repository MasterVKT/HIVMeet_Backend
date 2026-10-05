param(
  [Parameter(Mandatory = $true)][ValidateSet('prompt', 'stop')][string]$Event,
  [Parameter(Mandatory = $true)][string]$Scope,
  [Parameter(Mandatory = $true)][string]$HostName
)

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if ($null -eq $python) {
  Write-Output '{"decision":"approve","systemMessage":"Gouvernance HIVMeet indisponible : Python est requis pour le hook local."}'
  exit 0
}

$payload = ''
try {
    if ([Console]::IsInputRedirected) {
        $reader = [System.IO.StreamReader]::new([Console]::OpenStandardInput())
        $reader.ReadLineTimeout = 1000
        try {
            $payload = $reader.ReadToEnd()
        } catch [System.IO.IOException] {
            $payload = ''
        } finally {
            $reader.Dispose()
        }
    }
} catch {
    $payload = ''
}

if ([string]::IsNullOrWhiteSpace($payload)) {
    $payload = '{}'
}

$script = Join-Path $PSScriptRoot 'lifecycle_hook.py'
$map = Join-Path (Split-Path $PSScriptRoot -Parent) 'project-map.json'
if ($python.Name -eq 'py.exe' -or $python.Name -eq 'py') {
    $payload | & $python.Source -3 $script --event $Event --scope $Scope --host $HostName --map $map
} else {
    $payload | & $python.Source $script --event $Event --scope $Scope --host $HostName --map $map
}
exit $LASTEXITCODE
