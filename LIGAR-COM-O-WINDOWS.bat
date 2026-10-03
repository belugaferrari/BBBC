@echo off
REM BBBC - faz o sistema ligar junto com o Windows (ou desfaz isso).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\ligar-com-o-windows.ps1"

REM Sem este pause, um erro que mate o PowerShell antes de o script chegar ao
REM proprio "aperte Enter" fecharia a janela levando a mensagem junto - e o que
REM se ve e so um piscar. A mensagem de erro e a unica coisa que explica o que
REM aconteceu; ela tem de ficar na tela.
pause
