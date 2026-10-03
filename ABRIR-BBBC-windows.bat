@echo off
REM BBBC - abre o sistema E o aplicativo, com um clique so.
REM Para usar no dia a dia. Os arquivos INICIAR-* continuam valendo para quem
REM quiser abrir um de cada vez.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\abrir-tudo.ps1"

REM Sem este pause, um erro que mate o PowerShell antes de o script chegar ao
REM proprio "aperte Enter" fecharia a janela levando a mensagem junto - e o que
REM se ve e so um piscar. A mensagem de erro e a unica coisa que explica o que
REM aconteceu; ela tem de ficar na tela.
pause
