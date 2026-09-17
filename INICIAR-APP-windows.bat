@echo off
REM BBBC - abre o aplicativo do celular (mostra um QR code para o Expo Go).
REM O trabalho de verdade esta em scripts\iniciar-app.ps1; este arquivo so o
REM chama com permissao de execucao, porque .ps1 nao abre com dois cliques.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-app.ps1"
