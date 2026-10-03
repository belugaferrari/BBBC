@echo off
REM BBBC - faz o sistema ligar junto com o Windows (ou desfaz isso).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\ligar-com-o-windows.ps1"
