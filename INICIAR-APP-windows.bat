@echo off
REM BBBC - abre o aplicativo do celular (mostra um QR code para o Expo Go).
REM O trabalho de verdade esta em scripts\iniciar-app.ps1; este arquivo so o
REM chama com permissao de execucao, porque .ps1 nao abre com dois cliques.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-app.ps1"

REM Sem este pause, um erro que mate o PowerShell antes de o script chegar ao
REM proprio "aperte Enter" fecharia a janela levando a mensagem junto - e o que
REM se ve e so um piscar. A mensagem de erro e a unica coisa que explica o que
REM aconteceu; ela tem de ficar na tela.
pause
