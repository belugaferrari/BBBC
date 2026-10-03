@echo off
REM BBBC - liga o sistema sem Docker, direto no Windows.
REM O trabalho de verdade esta em scripts\iniciar-nativo.ps1; este arquivo so o
REM chama com permissao de execucao, porque .ps1 nao abre com dois cliques.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-nativo.ps1"

REM Sem este pause, um erro que mate o PowerShell antes de o script chegar ao
REM proprio "aperte Enter" fecharia a janela levando a mensagem junto - e o que
REM se ve e so um piscar. A mensagem de erro e a unica coisa que explica o que
REM aconteceu; ela tem de ficar na tela.
pause
