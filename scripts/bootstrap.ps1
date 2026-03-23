[CmdletBinding()]
param(
    [switch]$IncludeMavsdk,
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

function Step([string]$Message) {
    Write-Host "[bootstrap] $Message" -ForegroundColor Cyan
}

function Ensure-Venv {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Step "Virtual environment olusturuluyor (.venv)"
        python -m venv .venv
    }
}

function Get-VenvPython {
    $venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment python bulunamadi: $venvPython"
    }
    return $venvPython
}

Ensure-Venv
$pythonExe = Get-VenvPython

Step "Pip guncelleniyor"
& $pythonExe -m pip install --upgrade pip

Step "Runtime bagimliliklari kuruluyor (requirements.txt)"
& $pythonExe -m pip install -r requirements.txt

Step "Gelistirme bagimliliklari kuruluyor (requirements-dev.txt)"
& $pythonExe -m pip install -r requirements-dev.txt

if ($IncludeMavsdk) {
    Step "MAVSDK kuruluyor"
    & $pythonExe -m pip install mavsdk
}

$env:PYTHONPATH = "src"

$uvicornArgs = @("-m", "uvicorn", "otonom.api:app", "--host", $Host, "--port", "$Port")
if (-not $NoReload) {
    $uvicornArgs += "--reload"
}

Step "Uygulama baslatiliyor: http://$Host`:$Port"
& $pythonExe @uvicornArgs
