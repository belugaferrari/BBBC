# Rodando no seu celular

Não dá para baixar da App Store ainda — o app não foi publicado. Para testar,
use o **Expo Go**, que roda o código direto do seu computador. Leva uns 10
minutos na primeira vez.

## O que você precisa

- Node.js 20+ e Docker no computador;
- o celular **na mesma rede Wi-Fi** que o computador;
- o app **Expo Go** (App Store / Play Store).

## Passo a passo

**1. Suba a API e o banco**

```bash
git clone https://github.com/belugaferrari/BBBC.git
cd BBBC
cp backend/.env.example backend/.env
docker compose up --build
```

Confira em `http://localhost:8000/docs` — deve abrir a documentação da API.

**2. Crie a família e o seu login**

Em outro terminal:

```bash
docker compose exec api python -m app.cli seed-family \
  --name "Familia BBBC" \
  --titular "Felipe"   --titular-email felipe@exemplo.com   --titular-password "escolha-uma-senha" \
  --conjuge "Clarissa" --conjuge-email clarissa@exemplo.com --conjuge-password "escolha-outra" \
  --dependente "Nome da filha mais velha" --dependente "Nome da filha mais nova"
```

**3. Rode o app**

```bash
cd mobile
npm install
npm start
```

Aparece um QR code no terminal. No **Android**, abra o Expo Go e escaneie por
ele. No **iPhone**, escaneie com a câmera nativa.

O app descobre sozinho o IP da sua máquina na rede (usa o mesmo host do QR
code), então não é preciso editar arquivo nenhum. Faça login com o e-mail e a
senha do passo 2.

## Se não conectar

| Sintoma | Causa quase sempre |
|---|---|
| QR abre mas o app trava carregando | Celular e computador em redes diferentes (uma no Wi-Fi de visitantes, outra na principal). |
| "Falha na requisição" no login | Firewall do computador bloqueando a porta 8000. Libere-a na rede local. |
| "Sessão expirada" logo ao entrar | A API não subiu; confira `docker compose ps`. |
| Quero fixar o endereço na mão | Edite `extra.apiBaseUrl` em `mobile/app.json` com `http://SEU_IP:8000/api/v1`. |

## E para virar app de verdade no celular

Quando quiser um app instalado, sem depender do computador ligado:

```bash
npm install -g eas-cli
eas build --platform android --profile preview   # gera um .apk para instalar direto
eas build --platform ios --profile preview       # exige conta de desenvolvedor Apple (US$ 99/ano)
```

Nesse ponto a API precisa estar hospedada em algum lugar com HTTPS — não mais
na sua máquina. Veja o checklist em `docs/seguranca.md`.
