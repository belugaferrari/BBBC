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
echo   Como o celular vai se conectar a este computador?
echo.
echo     [1] Pelo Wi-Fi da casa - mais rapido. Comece por esta.
echo     [2] Pela internet      - mais lenta, mas atravessa firewall e
echo                              roteador que separa os aparelhos.
echo.
echo   Se voce ja tentou a 1 e o celular disse
echo   "Failed to download remote update", use a 2.
echo.

REM Enter aceita a opcao 1: o caminho normal nao deve exigir escolha.
set "MODO="
set /p "MODO=  Digite 1 ou 2 e aperte Enter [1]: "
if not defined MODO set "MODO=1"

echo.
echo   Vai aparecer um QR code aqui embaixo.
echo.
echo   ANDROID: abra o aplicativo Expo Go e escaneie por dentro dele.
echo   IPHONE:  escaneie com a camera normal do celular.
echo.
echo   Para parar, aperte Ctrl+C nesta janela.
echo.

if "%MODO%"=="2" (
  echo   Modo internet: a primeira vez demora mais, esta abrindo o caminho.
  echo.
  call npm run start:tunnel
) else (
  echo   Modo Wi-Fi: o celular precisa estar no MESMO Wi-Fi que este computador.
  echo.
  echo   Se o Windows perguntar se libera o acesso do Node.js a rede,
  echo   responda PERMITIR - sem isso o celular nao alcanca o computador.
  echo.
  call npm start
)
