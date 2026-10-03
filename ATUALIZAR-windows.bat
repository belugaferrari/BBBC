@echo off
REM BBBC - traz a versao nova sem reinstalar tudo nem mexer nos seus dados.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\atualizar.ps1"
