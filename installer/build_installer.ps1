$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$iscc = 'C:\Users\JMARTIN\AppData\Local\Programs\Inno Setup 6\ISCC.exe'
$scriptPath = Join-Path $PSScriptRoot 'SeguimientoGO.iss'

if (-not (Test-Path $iscc)) {
    throw "No se encontro ISCC en: $iscc"
}

if (-not (Test-Path (Join-Path $projectRoot 'dist\SeguimientoGO_OneFile.exe'))) {
    throw 'No se encontro dist\SeguimientoGO_OneFile.exe. Genera primero el .exe con PyInstaller.'
}

& $iscc $scriptPath
Write-Host 'Instalador generado en installer_output\SeguimientoGOInstaller.exe'
