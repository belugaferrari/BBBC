@echo off
REM BBBC - troca a senha de quem entra no aplicativo.
REM So vale neste computador, o que guarda o banco de dados.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\trocar-senha.ps1"

REM Sem este pause, um erro que mate o PowerShell antes do proprio "aperte
REM Enter" fecharia a janela levando a mensagem junto.
pause
