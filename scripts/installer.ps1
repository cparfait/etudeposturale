# Installation complète (backend + GPU + interface). À relancer sans risque : chaque étape est idempotente.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Green }
function Need($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd introuvable : $hint" }
}

Need python "installer Python 3.10 ou plus (python.org), cocher « Add to PATH »"
Need npm "installer Node.js 20 ou plus (nodejs.org)"
Need ffmpeg "installer ffmpeg (winget install Gyan.FFmpeg)"

$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Step "Environnement Python (backend\.venv)"
    python -m venv backend\.venv
    if ($LASTEXITCODE) { throw "Création de l'environnement Python impossible" }
}

Step "Dépendances du backend (avec le moteur de pose GPU)"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -e "backend[dev,gpu]"
if ($LASTEXITCODE) { throw "Installation du backend en échec" }

# rtmlib tire onnxruntime (CPU), qui masque la version GPU ; cuDNN doit rester en 9.10.
Step "ONNX Runtime GPU (retrait de la version CPU, cuDNN 9.10)"
& $py -m pip uninstall -y onnxruntime 2>$null | Out-Null
& $py -m pip install --force-reinstall --no-deps onnxruntime-gpu==1.23.2 nvidia-cudnn-cu12==9.10.2.21 --quiet
if ($LASTEXITCODE) { throw "Installation d'ONNX Runtime GPU en échec" }

Step "Interface (npm)"
npm --prefix frontend install
if ($LASTEXITCODE) { throw "Installation de l'interface en échec" }

Step "Vérification du moteur de pose"
& $py -c "from posturale.pose.engines import available_engines; print(available_engines())"

Write-Host "`nInstallation terminée. Lancer l'application : scripts\lancer.bat" -ForegroundColor Green
