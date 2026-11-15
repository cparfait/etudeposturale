# Lance le backend et l'interface dans deux fenêtres, puis ouvre le navigateur.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Backend non installé : lancer d'abord scripts\installer.bat" }
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) { throw "Interface non installée : lancer d'abord scripts\installer.bat" }

# Une instance précédente encore ouverte garderait les ports 8000 / 5173 (et resterait en HTTP) : on l'arrête.
$old = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq "python.exe" -and $_.CommandLine -match "uvicorn posturale\.api\.main") -or
    ($_.Name -eq "node.exe" -and $_.CommandLine -match [regex]::Escape((Join-Path $root "frontend\node_modules")))
}
foreach ($p in $old) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if ($old) { Write-Host "Ancienne instance arrêtée."; Start-Sleep -Seconds 1 }

# Certificat HTTPS local : renouvelé si l'adresse Wi-Fi du PC a changé (le QR code du téléphone l'utilise)
if (Test-Path (Join-Path $root "data\https\ca.key")) { & $py (Join-Path $root "scripts\https_local.py") | Out-Null }

Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", `
    "`$Host.UI.RawUI.WindowTitle = 'Posturale - backend'; & '$py' -m uvicorn posturale.api.main:app --port 8000 --app-dir backend/src"
Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", `
    "`$Host.UI.RawUI.WindowTitle = 'Posturale - interface'; npm --prefix frontend run dev"

$https = (Test-Path (Join-Path $root "frontend\certs\cert.pem")) -and (Test-Path (Join-Path $root "frontend\certs\key.pem"))
$url = if ($https) { "https://localhost:5173" } else { "http://localhost:5173" }

Write-Host "Démarrage…"
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-WebRequest "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 1 | Out-Null
        break
    } catch { Start-Sleep -Milliseconds 500 }
}
Start-Sleep -Seconds 2
Start-Process $url
Write-Host "Application ouverte sur $url (fermer les deux fenêtres pour l'arrêter)."
