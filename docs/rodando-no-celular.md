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

A saida quase universal e o **modo tunel**, que serve o app pela internet em vez
da rede local:

```bash
npm run start:tunnel
```

E mais lento, mas atravessa firewall, roteador que isola aparelhos e celular na
rede errada - as tres causas da tabela de uma vez. Os arquivos INICIAR-APP
oferecem isso como opcao 2.

| Sintoma | Causa quase sempre |
|---|---|
| "Failed to download remote update" | O celular nao alcanca o computador. Firewall do Windows bloqueando o Node, ou redes diferentes. Use o modo tunel. |
| QR abre mas o app trava carregando | Celular e computador em redes diferentes (uma no Wi-Fi de visitantes, outra na principal). |
| "Something went wrong" logo ao abrir | Expo Go mais novo que o SDK do projeto. Toque em "View error log" para ver qual dos dois e. |
| "Falha na requisição" no login | Firewall do computador bloqueando a porta 8000. Libere-a na rede local. |
| "Sessão expirada" logo ao entrar | A API não subiu; confira `docker compose ps`. |
| Quero fixar o endereço na mão | Edite `extra.apiBaseUrl` em `mobile/app.json` com `http://SEU_IP:8000/api/v1`. |

## Caminho 2: um APK instalado no aparelho

Se você quiser o app instalado, sem o Expo Go e sem o terminal aberto, o build
sai pelo **EAS Build** (serviço da própria Expo). O perfil já está pronto em
`eas.json`:

```bash
npm install -g eas-cli
eas login                                        # conta gratuita
eas build --platform android --profile preview   # devolve um link de .apk
```

O build roda na nuvem da Expo e leva uns 15 minutos. No fim, sai uma URL: abra
no celular, baixe e instale (o Android vai pedir para permitir "instalar de
fonte desconhecida"). O plano gratuito tem fila e um número limitado de builds
por mês — suficiente para uso pessoal.

**Antes de instalar, decida onde a API vai rodar.** Um app instalado não tem
servidor do Expo de onde deduzir o endereço. Por isso a tela de login tem o
campo **"Configurar servidor"**: digite ali `192.168.0.10:8000` (o IP da sua
máquina) e o app guarda no Keychain/Keystore. Enquanto o Docker estiver rodando
em casa e o celular no mesmo Wi-Fi, funciona. Fora de casa, só com a API
hospedada — veja o checklist em `docs/seguranca.md`.

### iPhone

Não existe caminho gratuito para instalar um app fora da App Store: a Apple
exige conta de desenvolvedor (US$ 99/ano) mesmo para uso próprio. Sem ela, no
iPhone o caminho é o Expo Go do Caminho 1, que é gratuito e funciona igual.

## O que custa dinheiro, afinal

| Item | Custo |
|---|---|
| Expo Go (testar hoje, Android e iPhone) | grátis |
| EAS Build gerando APK Android | grátis no plano free (com fila) |
| Build local com Android Studio | grátis, exige ~10 GB de instalação |
| Instalar app próprio no iPhone | US$ 99/ano (Apple Developer) |
| API rodando na sua máquina, em casa | grátis |
| API hospedada para usar fora de casa | a partir de ~US$ 5/mês num VPS |
| Open Finance (Pluggy ou Belvo) | pago, cobrado por conexão — ainda a definir |
