# Instalador en un paso de Fluo.
# Baja el último release de GitHub y lo instala para el usuario actual (sin administrador).
#
# Uso (PowerShell):
#   irm https://raw.githubusercontent.com/nicomine-dev/fluo/main/scripts/install.ps1 | iex
# O hacé doble clic en Instalar.bat, que corre esto mismo.

$ErrorActionPreference = "Stop"
$repo = "nicomine-dev/fluo"

if ($PSVersionTable.PSVersion.Major -lt 3) {
    Write-Host ""
    Write-Host "  Este Windows tiene un PowerShell viejo (Windows 7 sin actualizar) y no puede bajar de GitHub." -ForegroundColor Yellow
    Write-Host "  Baja el instalador desde el navegador: https://github.com/$repo/releases/latest"
    Start-Process "https://github.com/$repo/releases/latest"
    exit 2
}

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

Write-Host ""
Write-Host "  Fluo - instalador" -ForegroundColor Yellow
Write-Host "  Buscando la última versión en github.com/$repo ..."

$headers = @{ "User-Agent" = "Fluo-installer" }
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers $headers
} catch {
    Write-Host ""
    Write-Host "  No pude consultar GitHub. ¿Hay internet?" -ForegroundColor Red
    Write-Host "  Detalle: $($_.Exception.Message)"
    exit 1
}

$asset = $release.assets | Where-Object { $_.name -like "Fluo-Setup-*.exe" } | Select-Object -First 1
if (-not $asset) {
    Write-Host "  El release $($release.tag_name) no tiene instalador adjunto." -ForegroundColor Red
    exit 1
}

$sizeMb = [math]::Round($asset.size / 1MB, 1)
$out = Join-Path $env:TEMP $asset.name
Write-Host "  Descargando $($asset.name) ($sizeMb MB) ..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $out -UseBasicParsing -Headers $headers
# Saca la marca "descargado de internet" para que SmartScreen no bloquee la instalacion silenciosa.
Unblock-File -Path $out -ErrorAction SilentlyContinue

Write-Host "  Instalando ..."
# WaitForExit() espera solo al instalador: con -Wait, PowerShell esperaria tambien a la app que el instalador abre.
$proc = Start-Process -FilePath $out -ArgumentList "/SILENT", "/SP-", "/NORESTART" -PassThru
$proc.WaitForExit()
if ($proc.ExitCode -ne 0) {
    Write-Host "  El instalador terminó con código $($proc.ExitCode)." -ForegroundColor Red
    exit $proc.ExitCode
}

Write-Host ""
Write-Host "  Listo. Fluo $($release.tag_name) quedó instalado y ya se está abriendo." -ForegroundColor Green
Write-Host "  Tenés un acceso directo en el escritorio y en el menú Inicio."
Write-Host ""
