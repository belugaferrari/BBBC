@echo off
REM BBBC - abre o sistema E o aplicativo, com um clique so.
REM Para usar no dia a dia. Os arquivos INICIAR-* continuam valendo para quem
REM quiser abrir um de cada vez.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\abrir-tudo.ps1"
