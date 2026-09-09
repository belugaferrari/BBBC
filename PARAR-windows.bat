@echo off
REM BBBC - desliga o sistema. Os dados ficam guardados para a proxima vez.
cd /d "%~dp0"
echo Desligando o BBBC...
docker compose down
echo.
echo Pronto. Seus dados continuam salvos.
echo Para ligar de novo, abra o INICIAR-windows.bat.
echo.
pause
