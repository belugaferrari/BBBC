@echo off
REM BBBC - traz a versao nova sem reinstalar tudo nem mexer nos seus dados.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\atualizar.ps1"

REM Sem este pause, um erro que mate o PowerShell antes de o script chegar ao
REM proprio "aperte Enter" fecharia a janela levando a mensagem junto - e o que
REM se ve e so um piscar. A mensagem de erro e a unica coisa que explica o que
REM aconteceu; ela tem de ficar na tela.
pause
