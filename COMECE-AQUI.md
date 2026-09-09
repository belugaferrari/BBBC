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

Aparece um **QR code** na janela:

- **Android:** instale o app **Expo Go** (Play Store), abra e escaneie o QR
  **por dentro do Expo Go**
- **iPhone:** instale o **Expo Go** (App Store) e escaneie o QR com a **câmera
  normal** do celular

O celular precisa estar no **mesmo Wi-Fi** que o computador. Entre com o e-mail
e a senha que você escolheu na Etapa 3.

---

## Para desligar

Clique duas vezes em **`PARAR-windows.bat`** ou **`PARAR-mac.command`**.

Seus dados ficam salvos. Da próxima vez, é só abrir o INICIAR de novo — ele não
vai perguntar nada, só ligar.

---

## Perguntas que você provavelmente tem

**Preciso deixar o computador ligado?**
Enquanto quiser usar o app no celular, sim. O sistema roda na sua máquina, não
na internet. Para usar de qualquer lugar, ele precisaria ficar hospedado — veja
`docs/seguranca.md`.

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
