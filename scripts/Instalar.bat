@echo off
title Instalar Fluo
echo.
echo   Instalando Fluo: se baja la ultima version desde GitHub.
echo   No hace falta ser administrador.
echo.
powershell -NoProfile -Command "if ($PSVersionTable.PSVersion.Major -lt 3) { exit 2 }"
if errorlevel 2 goto viejo
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/nicomine-dev/fluo/main/scripts/install.ps1 | iex"
goto fin

:viejo
echo   Este Windows tiene un PowerShell viejo (Windows 7 sin actualizar) y no puede bajar de GitHub.
echo   Te abro la pagina de descarga: baja Fluo-Setup-x.y.z.exe y hace doble clic.
start https://github.com/nicomine-dev/fluo/releases/latest

:fin
echo.
pause
