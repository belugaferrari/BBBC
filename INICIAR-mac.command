#!/usr/bin/env bash
#
# BBBC - inicia o sistema com dois cliques.
#
# Faz tudo o que o passo a passo pedia para digitar: confere o Docker, sobe o
# banco e a API, cria a familia na primeira vez e abre o navegador.
# Pode ser executado quantas vezes quiser - nao duplica nada.

set -uo pipefail
cd "$(dirname "$0")"

VERMELHO=$'\033[31m'; VERDE=$'\033[32m'; NEGRITO=$'\033[1m'; NORMAL=$'\033[0m'

titulo()  { printf "\n%s%s%s\n" "$NEGRITO" "$1" "$NORMAL"; }
ok()      { printf "  %s✓%s %s\n" "$VERDE" "$NORMAL" "$1"; }
erro()    { printf "\n%s✗ %s%s\n" "$VERMELHO" "$1" "$NORMAL"; }

fim() {
  printf "\n%sPode fechar esta janela.%s\n" "$NEGRITO" "$NORMAL"
  read -r -n 1 -p "Aperte qualquer tecla para sair..."
  exit "${1:-0}"
}

printf "%s\n" "════════════════════════════════════════════"
printf "%s  BBBC - Financas da familia%s\n" "$NEGRITO" "$NORMAL"
printf "%s\n" "════════════════════════════════════════════"

# ---------------------------------------------------------------- Docker ---
titulo "1. Conferindo o Docker"

if ! command -v docker >/dev/null 2>&1; then
  erro "O Docker nao esta instalado."
  echo "  Baixe em https://www.docker.com/products/docker-desktop/"
  echo "  Instale, abra o Docker Desktop e rode este arquivo de novo."
  command -v open >/dev/null && open "https://www.docker.com/products/docker-desktop/"
  fim 1
fi
ok "Docker instalado"

if ! docker info >/dev/null 2>&1; then
  erro "O Docker esta instalado, mas nao esta em execucao."
  echo "  Abra o aplicativo 'Docker Desktop', espere o icone da baleia parar"
  echo "  de se mexer, e rode este arquivo de novo."
  command -v open >/dev/null && open -a Docker 2>/dev/null
  fim 1
fi
ok "Docker em execucao"

# ------------------------------------------------------------- Subir tudo ---
titulo "2. Ligando o sistema"
echo "  (na primeira vez demora alguns minutos - esta baixando o necessario)"
echo

if ! docker compose up -d --build; then
  erro "Nao consegui subir o sistema."
  echo "  A causa mais comum e ja existir outro programa usando a porta 5432"
  echo "  ou a 8000. Feche-o e tente de novo."
  fim 1
fi
ok "Banco de dados e API no ar"

# ------------------------------------------------------------- Esperar API ---
titulo "3. Esperando a API responder"
pronto=0
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then pronto=1; break; fi
  printf "."
  sleep 2
done
echo
if [ "$pronto" -ne 1 ]; then
  erro "A API nao respondeu a tempo."
  echo "  Veja o que aconteceu com: docker compose logs api"
  fim 1
fi
ok "API respondendo em http://localhost:8000"

# ----------------------------------------------------------------- Familia ---
titulo "4. Conferindo o seu cadastro"

# Codigo de saida em vez de ler texto: uma falha de conexao lida como "ja
# existe" pularia o cadastro justamente quando ele e necessario.
docker compose exec -T api python -m app.cli needs-setup >/dev/null 2>&1
PRECISA_CADASTRO=$?

if [ "$PRECISA_CADASTRO" -eq 2 ]; then
  erro "A API subiu, mas nao esta falando com o banco de dados."
  echo "  Veja o que aconteceu com: docker compose logs"
  fim 1
fi

if [ "$PRECISA_CADASTRO" -eq 0 ]; then
  echo
  echo "  Primeira vez por aqui. Vou criar o seu acesso."
  echo "  (e so apertar Enter para aceitar o que esta entre colchetes)"
  echo

  # E-mail e a chave do login: se for digitado errado, nao ha como adivinhar
  # depois. Por isso a conferencia do '@'.
  perguntar_email() {
    local rotulo="$1" padrao="$2" resposta=""
    while true; do
      read -r -p "  $rotulo [$padrao]: " resposta
      resposta=${resposta:-$padrao}
      case "$resposta" in
        *@*.*) printf '%s' "$resposta"; return 0 ;;
        *) echo "  Isso nao parece um e-mail. Tente de novo." >&2 ;;
      esac
    done
  }

  # A senha e digitada as cegas: sem conferencia, um dedo errado tranca o
  # usuario para fora do proprio sistema.
  perguntar_senha() {
    local rotulo="$1" senha="" confirmacao=""
    while true; do
      read -r -s -p "  $rotulo (minimo 8 caracteres): " senha; echo >&2
      if [ ${#senha} -lt 8 ]; then
        echo "  Muito curta. Tente outra." >&2
        continue
      fi
      read -r -s -p "  Digite a mesma senha de novo: " confirmacao; echo >&2
      if [ "$senha" != "$confirmacao" ]; then
        echo "  As duas nao bateram. Vamos de novo." >&2
        continue
      fi
      printf '%s' "$senha"
      return 0
    done
  }

  EMAIL_TITULAR=$(perguntar_email "Seu e-mail" "felipe@exemplo.com")
  SENHA=$(perguntar_senha "Escolha uma senha")

  EMAIL_CONJUGE=$(perguntar_email "E-mail da Clarissa" "clarissa@exemplo.com")
  SENHA_CONJUGE=$(perguntar_senha "Senha da Clarissa")

  read -r -p "  Nome da filha mais velha [Filha 1]: " FILHA1
  read -r -p "  Nome da filha mais nova  [Filha 2]: " FILHA2

  # As senhas vao pela entrada padrao, e nao como argumento: senha com aspas,
  # acento ou cifrao quebraria ao passar pela linha de comando.
  if printf '%s\n%s\n' "$SENHA" "$SENHA_CONJUGE" \
     | docker compose exec -T api python -m app.cli seed-family \
        --skip-if-exists --passwords-from-stdin \
        --name "Familia BBBC" \
        --titular "Felipe"   --titular-email "$EMAIL_TITULAR" \
        --conjuge "Clarissa" --conjuge-email "$EMAIL_CONJUGE" \
        --dependente "${FILHA1:-Filha 1}" --dependente "${FILHA2:-Filha 2}" >/dev/null; then
    ok "Cadastro criado"
  else
    erro "Nao consegui criar o cadastro."
    fim 1
  fi
else
  ok "Cadastro ja existe (nada foi alterado)"
fi

# -------------------------------------------------------------------- Fim ---
titulo "Pronto!"
docker compose exec -T api python -m app.cli status 2>/dev/null | sed 's/^/  /'

cat <<'FIM'

  O sistema esta rodando. Duas maneiras de usar:

  1. NO NAVEGADOR (ja vou abrir)
     http://localhost:8000/docs
     Clique em "Authorize", entre com o seu e-mail e senha.

  2. NO CELULAR
     Abra o arquivo INICIAR-APP-mac.command e escaneie o QR code
     com o aplicativo Expo Go.

  Para desligar tudo depois, abra o arquivo PARAR-mac.command.
FIM

sleep 1
command -v open >/dev/null && open "http://localhost:8000/docs"
fim 0
