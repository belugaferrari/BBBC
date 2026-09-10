@echo off
REM BBBC - inicia o sistema com dois cliques.
REM O trabalho de verdade esta em scripts\iniciar.ps1; este arquivo so o chama
REM com permissao de execucao, porque .ps1 nao abre com dois cliques no Windows.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar.ps1"
