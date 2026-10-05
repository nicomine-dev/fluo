@echo off
title Instalar Fluo
echo.
echo   Instalando Fluo: se baja la ultima version desde GitHub.
echo   No hace falta ser administrador.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/nicomine-dev/fluo/main/scripts/install.ps1 | iex"
echo.
pause
