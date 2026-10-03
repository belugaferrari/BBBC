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
| "Failed to download remote update", e o terminal diz `exp://127.0.0.1:8081` | O Expo nao descobriu o IP desta maquina e desistiu em silencio - os adaptadores virtuais do Docker sao a causa comum no Windows. O QR manda o celular procurar o app nele mesmo. Os INICIAR-APP descobrem o IP e informam via `REACT_NATIVE_PACKAGER_HOSTNAME`. |
| "Failed to download remote update", com o IP correto no terminal | Ai sim o celular nao alcanca o computador: firewall, ou redes diferentes. Use o modo tunel. |
| QR abre mas o app trava carregando | Celular e computador em redes diferentes (uma no Wi-Fi de visitantes, outra na principal). |
| "Something went wrong" logo ao abrir | Expo Go mais novo que o SDK do projeto. Toque em "View error log" para ver qual dos dois e. |
| "Falha na requisição" no login | Firewall do computador bloqueando a porta 8000. Libere-a na rede local. |
| "Sessão expirada" logo ao entrar | A API não subiu; confira `docker compose ps`. |
| Quero fixar o endereço na mão | Edite `extra.apiBaseUrl` em `mobile/app.json` com `http://SEU_IP:8000/api/v1`. |

## Caminho 2: um APK instalado no aparelho

É o caminho de quem quer **abrir o aplicativo com o PC desligado**. No Expo Go
isso não existe: o código vem do computador a cada abertura, então com o PC
desligado o aplicativo não sobe — e a cópia local dos números e a fila de
lançamentos ficam dentro de um aplicativo que não subiu (ver
[`offline.md`](offline.md)).

### O jeito curto

Clique duas vezes em **`GERAR-APK-windows.bat`**, na pasta do sistema. Ele
conduz tudo: confere o Node, pede o login da Expo (conta gratuita), manda
compilar e, no fim, imprime **o endereço desta máquina** para você digitar no
celular. São uns 20 minutos, e a maior parte é fila do serviço.

Antes de clicar, rode o **ATUALIZAR** uma vez: o APK é feito a partir do código
que está nesta máquina, e gerar antes de atualizar produziria um aplicativo sem
as novidades.

### O que o script faz, para quem quiser conferir

```bash
cd mobile
set EAS_NO_VCS=1
npx eas-cli@latest login                                     # conta gratuita
npx eas-cli@latest build --platform android --profile preview
```

Três detalhes que custam tempo descobrir sozinho, e por isso estão resolvidos no
script e no projeto:

- **`npx`, e não `npm install -g eas-cli`.** A instalação global no Windows pede
  administrador ou deixa o comando fora do PATH da janela atual — o erro seguinte
  é "eas não é reconhecido" num terminal onde a instalação acabou de dizer que
  deu certo.
- **`EAS_NO_VCS=1`.** A pasta instalada nasceu de um zip, não é um repositório
  git, e sem isso o EAS se recusa a enviar o projeto.
- **HTTP na rede local.** O Android bloqueia conexão sem HTTPS em aplicativo
  instalado, e o servidor de casa é `http://192.168.x.x:8000`. Sem tratar isso, o
  login falha com um erro de rede que não diz a causa. O projeto já carrega o
  `expo-build-properties` com `usesCleartextTraffic` ligado (e o equivalente no
  iOS, `NSAllowsLocalNetworking`), em `mobile/app.json`.

### Depois de instalar: o endereço do servidor

Um aplicativo instalado não tem servidor do Expo de onde deduzir o endereço, e o
padrão (`localhost`) no celular é o próprio aparelho. Por isso, no aplicativo
instalado, **o campo do servidor abre sozinho na tela de login**, com a
explicação. Digite o IP desta máquina e a porta:

```
192.168.0.10:8000
```

O script imprime o número certo no fim; o INICIAR-APP também mostra, no passo 3.
Fica guardado no Keychain/Keystore — você não digita de novo. Enquanto o sistema
estiver rodando em casa e o celular no mesmo Wi-Fi, funciona igual ao Expo Go;
com o PC desligado, funciona como descrito em [`offline.md`](offline.md). Fora de
casa com o PC desligado, só com a API hospedada — veja o checklist em
[`seguranca.md`](seguranca.md).

**Abra o aplicativo em casa uma vez antes de precisar dele na rua:** a cópia
local só existe depois da primeira conversa com o PC.

**A cada atualização que mexa no aplicativo, gere o APK de novo** e instale por
cima. O ATUALIZAR troca o código desta máquina; o que está instalado no celular
continua como estava.

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
