@echo off
REM BBBC - abre o aplicativo do celular (mostra um QR code para o Expo Go).
cd /d "%~dp0mobile"

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo [x] O Node.js nao esta instalado.
  echo     Baixe a versao LTS em https://nodejs.org e rode este arquivo de novo.
  start https://nodejs.org
  pause
  exit /b 1
)

if not exist node_modules (
  echo.
  echo Preparando o aplicativo ^(so na primeira vez, ~2 minutos^)...
  echo.
  call npm install
  if errorlevel 1 (
    echo [x] Falha ao preparar o aplicativo.
    pause
    exit /b 1
  )
)

echo.
echo   Vai aparecer um QR code aqui embaixo.
echo.
echo   ANDROID: abra o aplicativo Expo Go e escaneie por dentro dele.
echo   IPHONE:  escaneie com a camera normal do celular.
echo.
echo   O celular precisa estar no MESMO Wi-Fi que este computador.
echo   Para parar, aperte Ctrl+C nesta janela.
echo.
call npm start
