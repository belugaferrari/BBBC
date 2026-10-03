@echo off
REM BBBC - gera o aplicativo instalavel (.apk) do Android, para o celular abrir
REM com o PC desligado. O trabalho de verdade esta em scripts\gerar-apk.ps1;
REM este arquivo so o chama com permissao de execucao, porque .ps1 nao abre com
REM dois cliques.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\gerar-apk.ps1"

REM Sem este pause, um erro que mate o PowerShell antes de o script chegar ao
REM proprio "aperte Enter" fecharia a janela levando a mensagem junto - e o que
REM se ve e so um piscar. A mensagem de erro e a unica coisa que explica o que
REM aconteceu; ela tem de ficar na tela.
pause
