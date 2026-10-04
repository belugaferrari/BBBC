# Começe aqui

Guia para quem nunca mexeu com programação. Nenhum passo pede que você entenda
código. São 4 etapas e leva uns 20 minutos na primeira vez — depois, é só um
duplo clique.

---

## Etapa 1 — Baixar o projeto para o seu computador

Os arquivos estão hoje na internet, não na sua máquina. Para trazê-los:

1. Abra https://github.com/belugaferrari/BBBC
2. Clique no botão verde **`< > Code`**
3. Clique em **Download ZIP**
4. Vá na pasta **Downloads**, clique duas vezes no arquivo baixado
   (`BBBC-main.zip`) para descompactar

Você fica com uma pasta chamada **BBBC-main**. É ela que interessa.

> Se preferir, mova essa pasta para a Área de Trabalho — facilita achar depois.

---

## Dois caminhos — escolha um

| | **Sem Docker** | **Com Docker** |
|---|---|---|
| O que instalar | Python e PostgreSQL | Docker Desktop |
| Peso na máquina | leve, roda direto | pesado: um Linux inteiro numa máquina virtual |
| Se o computador for modesto | **é este** | pode travar ou demorar 15 minutos |
| Arquivo para clicar | `INICIAR-SEM-DOCKER-windows.bat` | `INICIAR-windows.bat` |

**Na dúvida, vá pelo Sem Docker.** É mais rápido no dia a dia e tem menos peças
para dar errado. O caminho com Docker continua aqui para quem já o tem
funcionando.

---

# Caminho A — Sem Docker (recomendado)

## A1 — Instalar o Python

1. Abra https://www.python.org/downloads/
2. Clique no botão amarelo **Download Python**
3. Abra o arquivo baixado

> **O passo que todo mundo erra:** na primeira tela do instalador, marque a
> caixinha **"Add python.exe to PATH"**, embaixo, **antes** de clicar em
> *Install Now*. Sem ela o Windows não encontra o Python depois.

## A2 — Instalar o PostgreSQL

1. Abra https://www.postgresql.org/download/windows/
2. Clique em **Download the installer**
3. Baixe a versão mais recente e abra o arquivo

Durante a instalação ele pede uma **senha para o usuário `postgres`**.
**Anote essa senha** — vou pedi-la uma vez só, no próximo passo. O resto pode
aceitar como vem, inclusive a porta 5432.

## A3 — Ligar

Duplo clique em **`INICIAR-SEM-DOCKER-windows.bat`**.

Ele confere as duas instalações, cria o banco (pedindo aquela senha do
`postgres`), prepara o necessário e pergunta o seu e-mail, uma senha sua e o
nome das meninas.

No fim, o navegador abre em `http://localhost:8000/docs`.

> **Essa janela preta fica aberta** enquanto você usar o sistema — é ela que
> segura tudo no ar. Para desligar, feche-a ou aperte Ctrl+C.

Agora pule para a **Etapa 4**, do aplicativo no celular.

---

# Caminho B — Com Docker

## Etapa 2 — Instalar o Docker Desktop

O Docker é o programa que faz o sistema funcionar sem você precisar instalar
banco de dados, Python e mais uma dúzia de coisas. Instala uma vez e esquece.

1. Abra https://www.docker.com/products/docker-desktop/
2. Baixe a versão do seu computador (o site já detecta: Mac ou Windows)

   > **No Mac**, o site oferece duas opções: *Apple Silicon* (Macs de 2020 em
   > diante) e *Intel*. Se não souber qual é o seu: menu  → **Sobre este Mac**.
   > Se aparecer "Chip Apple M1/M2/M3/M4", é Apple Silicon.

3. Instale como qualquer outro programa
4. **Abra o Docker Desktop** e espere: no canto da tela aparece um ícone de
   baleia 🐳. Enquanto ele estiver se mexendo, o Docker está ligando. Quando
   parar, está pronto.

Deixe o Docker Desktop aberto. Ele precisa estar rodando para o sistema funcionar.

---

## Etapa 3 — Ligar o sistema

### Se você usa **Windows**

Dentro da pasta BBBC-main, clique duas vezes em:

> **`INICIAR-windows.bat`**

Abre uma janela preta com texto passando. É normal — é o sistema se montando.
Na primeira vez demora alguns minutos.

> O Windows pode mostrar uma tela azul dizendo **"O Windows protegeu o
> computador"**. É o aviso padrão para arquivos baixados da internet. Clique em
> **Mais informações** → **Executar assim mesmo**. Só aparece na primeira vez.

### Se você usa **Mac**

O Mac bloqueia arquivos baixados da internet, então tem um passo extra, **uma
única vez**:

1. Aperte **⌘ + espaço** (a tecla Command e a barra de espaço juntas). Abre uma
   busca no meio da tela.
2. Digite **terminal** e aperte **Enter**. Abre uma janela com fundo escuro e
   texto. É só um lugar onde se digita comandos — nada vai quebrar.
3. **Copie a linha abaixo**, cole na janela do Terminal (⌘ + V) e aperte Enter:

```
cd ~/Downloads/BBBC-main && chmod +x *.command && open .
```

   > Se você moveu a pasta para a Área de Trabalho, troque `~/Downloads` por
   > `~/Desktop`.

4. Abre uma janela do Finder com a pasta. Pode fechar o Terminal — **não vai
   precisar dele nunca mais.**

Agora clique duas vezes em:

> **`INICIAR-mac.command`**

Na primeira vez o Mac pode dizer que "não pode ser aberto porque é de um
desenvolvedor não identificado". Se isso acontecer: clique com o **botão
direito** no arquivo → **Abrir** → **Abrir** de novo na caixa que aparece. Só
precisa fazer isso uma vez.

### O que vai acontecer (nos dois casos)

A janela vai mostrar, em português:

```
1. Conferindo o Docker         ✓
2. Ligando o sistema           ✓
3. Esperando a API responder   ✓
4. Conferindo o seu cadastro
```

Na **primeira vez**, ele pergunta o seu e-mail, uma senha (digitada duas vezes,
para não errar) e o nome das meninas. É o seu login — anote a senha.

No fim, o navegador abre sozinho em `http://localhost:8000/docs`.

> **Se aparecer erro:** a janela diz o que fazer, em português. Os dois casos
> comuns são "o Docker não está em execução" (abra o Docker Desktop e espere a
> baleia parar) e "porta ocupada" (feche outros programas e tente de novo).

---

## Etapa 4 — Ver o sistema no celular

De volta à pasta, clique duas vezes em:

- **Windows:** `INICIAR-APP-windows.bat`
- **Mac:** `INICIAR-APP-mac.command`

Ele pede o **Node.js** se você ainda não tiver — o link aparece na tela; baixe
a versão **LTS**, instale e rode o arquivo de novo.

Ele pergunta **como o celular vai se conectar**:

- **[1] Pelo Wi-Fi da casa** — mais rápido. Comece por esta (é só apertar Enter).
- **[2] Pela internet** — mais lenta, mas atravessa firewall e roteador.

Aparece um **QR code** na janela:

- **Android:** instale o app **Expo Go** (Play Store), abra e escaneie o QR
  **por dentro do Expo Go**
- **iPhone:** instale o **Expo Go** (App Store) e escaneie o QR com a **câmera
  normal** do celular

Entre com o e-mail e a senha que você escolheu na Etapa 3.

> **Se o celular disser "Failed to download remote update":** olhe na janela a
> linha `Metro waiting on exp://...`. Se o endereço ali for `127.0.0.1`, o QR
> code está mandando o celular procurar o app nele mesmo — feche a janela e
> abra o INICIAR-APP de novo, que ele descobre o endereço certo. Se o endereço
> já for o do seu computador (algo como `192.168.x.x`), então é a rede
> bloqueando: escolha a opção **2**, que atravessa firewall e roteador.

---

## Etapa 5 (opcional) — Instalar o app no celular, para abrir com o PC desligado

O Expo Go da Etapa 4 **não guarda o aplicativo no celular**: ele baixa o
programa do seu computador cada vez que abre. Ótimo para testar, e é por isso que
você não precisa instalar nada. Mas significa que, com o PC desligado, o app não
abre — não há de onde baixar.

Se você quiser **consultar os números na rua e lançar gasto em dinheiro na hora**,
o app precisa estar instalado de verdade. Aí ele abre sozinho, mostra os números
da última vez que falou com o PC (dizendo de quando são) e guarda os lançamentos
para subir quando você chegar em casa.

**No Android:** clique duas vezes em **`GERAR-APK-windows.bat`**. Ele conduz tudo
e pede uma conta gratuita na Expo (quem compila é o serviço dela, na nuvem — fazer
isso aqui exigiria uns 10 GB de programas). Leva uns 20 minutos, quase tudo fila.
No fim, ele mostra um QR code com o link do arquivo e **o endereço do seu
computador**, que você digita uma vez na tela de login do app instalado.

**No iPhone não há caminho gratuito:** a Apple cobra US$ 99/ano para instalar
aplicativo fora da App Store. Lá o Expo Go da Etapa 4 continua sendo o caminho,
com o PC ligado.

Detalhes, e o que funciona ou não sem o PC:
[`docs/offline.md`](docs/offline.md).

---

## No dia a dia, depois de tudo instalado

Duplo clique em **`ABRIR-BBBC-windows.bat`**. Um arquivo só: ele liga o sistema
numa janela e abre o aplicativo em seguida, na ordem certa, esperando o
primeiro ficar pronto.

São sempre **duas janelas abertas** enquanto você usa o BBBC:

| Janela | O que é |
|---|---|
| a primeira, que abre sozinha | **o sistema** — banco de dados e servidor |
| a segunda | **o aplicativo** — a tela, no navegador ou servindo o celular |

A primeira precisa ficar aberta. É ela que guarda e serve os seus dados; o
aplicativo só mostra. Fechou, o app perde o chão.

> Isso é consequência de o sistema rodar na sua máquina, e não hospedado na
> internet. Em troca, seus dados financeiros não saem daí.

---

## Atualizar sozinho (o jeito de não pensar nisso)

Em **`LIGAR-COM-O-WINDOWS.bat`**, a opção **1** faz duas coisas: o sistema sobe
junto com o Windows **e procura versão nova antes de subir**.

É o único momento em que atualizar não custa nada: no boot ainda não há janela
aberta, então não existe aquele "feche as duas janelas e abra de novo". Você liga
o computador e o sistema já está na versão nova.

Se a internet estiver fora, ou se a atualização falhar por qualquer motivo, **o
sistema sobe mesmo assim**, com a versão que já está na máquina — ficar sem
sistema por causa de uma atualização que não veio seria trocar um incômodo por um
problema. O relato de cada tentativa fica em `atualizacao-ao-ligar.log`, ao lado
dos arquivos do BBBC.

A opção **2** liga junto com o Windows sem atualizar sozinho, e a **3** desliga
tudo isso. Dá para trocar de ideia quando quiser, rodando o arquivo de novo — ele
diz, na abertura, como está hoje.

> Isso vale para o **sistema no computador**. O aplicativo instalado no celular
> (o APK) continua sendo atualizado à mão, gerando de novo — não há como um
> aplicativo do Android se trocar sozinho sem loja.

---

## Quando eu avisar que há novidade

Baixe o ZIP de novo e substitua a pasta. **Não refaz nada do que já foi feito:**

| | |
|---|---|
| Python e PostgreSQL | continuam instalados |
| Seu cadastro e sua senha | continuam valendo |
| Lançamentos e categorias | ficam no banco, intactos |
| O que muda | só os arquivos do programa |

O `INICIAR` reconhece o que já existe e pula direto. Da segunda vez em diante
ele não pergunta mais nada.

---

## Para desligar

Clique duas vezes em **`PARAR-windows.bat`** ou **`PARAR-mac.command`**.

Seus dados ficam salvos. Da próxima vez, é só abrir o INICIAR de novo — ele não
vai perguntar nada, só ligar.

---

## Perguntas que você provavelmente tem

**Preciso deixar o computador ligado?**
Para **lançar e consultar com os dados de agora**, sim: o sistema roda na sua
máquina, não na internet. Com o app instalado no celular (Etapa 5), você
consulta os números da última sincronização e lança gasto com o PC desligado —
o lançamento sobe sozinho quando o PC voltar. O que não existe com o PC
desligado é dado novo, porque é lá que ele mora. Para o sistema responder de
qualquer lugar, ele precisaria ficar hospedado — veja `docs/seguranca.md`.

**Tem como o sistema ligar junto com o Windows?**
Tem: `LIGAR-COM-O-WINDOWS.bat`. Ele põe o sistema (banco e servidor) na
inicialização, sem pedir administrador e sem abrir janela. O aplicativo não vai
junto de propósito — ele é uma tela, e abrir uma aba a cada boot atrapalharia.

**Aquela janela preta é perigosa?**
Não. Ela só mostra o que está acontecendo. Se fechar sem querer, é só abrir o
INICIAR de novo.

**Posso usar dados bancários de verdade agora?**
Ainda não recomendo. Faltam três coisas (HTTPS, backup e trava de senha) que
estão listadas em `docs/seguranca.md`. Para experimentar, o projeto traz
extratos fictícios em `backend/db/samples/`.

**Onde ponho meu extrato do banco?**
No app, aba **Importar extrato**. Aceita OFX, CSV e PDF — detalhes em
`docs/importando-extratos.md`.

**E se eu quiser entender o que cada comando faz?**
`docs/testando-o-sistema.md` é a mesma coisa, passo a passo, explicando cada
linha. Este guia aqui é o atalho.
