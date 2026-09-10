#!/usr/bin/env bash
# BBBC - desliga o sistema. Os dados ficam guardados para a proxima vez.
set -uo pipefail
cd "$(dirname "$0")"

echo "Desligando o BBBC..."
if docker compose down; then
  echo
  echo "Pronto. Seus dados continuam salvos."
  echo "Para ligar de novo, abra o INICIAR-mac.command."
else
  echo
  echo "Nao consegui desligar. O Docker esta em execucao?"
fi
echo
read -r -n 1 -p "Aperte qualquer tecla para sair..."
