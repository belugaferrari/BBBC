#!/usr/bin/env bash
#
# BBBC - abre o aplicativo do celular.
# Mostra um QR code para ser escaneado com o Expo Go.

set -uo pipefail
cd "$(dirname "$0")/mobile"

NEGRITO=$'\033[1m'; NORMAL=$'\033[0m'; VERMELHO=$'\033[31m'

if ! command -v node >/dev/null 2>&1; then
  printf "%s✗ O Node.js nao esta instalado.%s\n" "$VERMELHO" "$NORMAL"
  echo "  Baixe a versao LTS em https://nodejs.org e rode este arquivo de novo."
  command -v open >/dev/null && open "https://nodejs.org"
  read -r -n 1 -p "Aperte qualquer tecla para sair..."
  exit 1
fi

if [ ! -d node_modules ]; then
  printf "\n%sPreparando o aplicativo (so na primeira vez, ~2 minutos)...%s\n\n" \
    "$NEGRITO" "$NORMAL"
  npm install || {
    printf "%s✗ Falha ao preparar o aplicativo.%s\n" "$VERMELHO" "$NORMAL"
    read -r -n 1 -p "Aperte qualquer tecla para sair..."
    exit 1
  }
fi

cat <<'FIM'

  Como o celular vai se conectar a este computador?

    [1] Pelo Wi-Fi da casa - mais rapido. Comece por esta.
    [2] Pela internet      - mais lenta, mas atravessa firewall e
                             roteador que separa os aparelhos.

  Se voce ja tentou a 1 e o celular disse
  "Failed to download remote update", use a 2.

FIM

# Enter aceita a opcao 1: o caminho normal nao deve exigir escolha.
read -r -p "  Digite 1 ou 2 e aperte Enter [1]: " MODO
MODO="${MODO:-1}"

cat <<'FIM'

  Vai aparecer um QR code aqui embaixo.

  ANDROID: abra o aplicativo Expo Go e escaneie por dentro dele.
  IPHONE:  escaneie com a camera normal do celular.

  Para parar, aperte Ctrl+C nesta janela.

FIM

if [ "$MODO" = "2" ]; then
  echo "  Modo internet: a primeira vez demora mais, esta abrindo o caminho."
  echo
  npm run start:tunnel
else
  echo "  Modo Wi-Fi: o celular precisa estar no MESMO Wi-Fi que este computador."
  echo
  npm start
fi
