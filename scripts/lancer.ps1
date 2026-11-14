# Lance le backend et l'interface dans deux fenêtres, puis ouvre le navigateur.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Backend non installé : lancer d'abord scripts\installer.bat" }
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) { throw "Interface non installée : lancer d'abord scripts\installer.bat" }

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
