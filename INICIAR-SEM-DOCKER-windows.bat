@echo off
REM BBBC - liga o sistema sem Docker, direto no Windows.
REM O trabalho de verdade esta em scripts\iniciar-nativo.ps1; este arquivo so o
REM chama com permissao de execucao, porque .ps1 nao abre com dois cliques.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-nativo.ps1"
