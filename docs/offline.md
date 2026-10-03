# Funcionar sem o PC ligado

Este documento diz **o que funciona offline, o que não funciona, e por quê**. A
parte que não funciona vem primeiro de propósito: é a que custa tempo descobrir
sozinho, no estacionamento do mercado, com o gasto na mão.

---

## O que o aplicativo faz sem servidor

| Situação | O que acontece |
|---|---|
| O PC desliga (ou dorme) com o aplicativo aberto | Os números continuam na tela, com uma faixa dizendo **"Sem o servidor · números de hoje às 14:12"**. |
| Você lança um gasto em dinheiro sem servidor | Fica **guardado no celular** e sobe sozinho quando o PC voltar. A tela diz isso na confirmação, com essas palavras. |
| O PC volta | A fila sobe sozinha — ao voltar a responder, e também quando você traz o aplicativo para a frente. |
| O mesmo lançamento sobe duas vezes | Não cobra duas vezes: cada lançamento carrega uma chave própria e o servidor devolve o que já gravou. |
| O servidor recusa o lançamento | Ele **fica na fila**, com o motivo, para você resolver. Nada é jogado fora em silêncio. |
| Você fecha o aplicativo com fila pendente | A fila continua lá na próxima abertura. |
| Sessão expirada | A fila espera o login em vez de ser descartada. |

O que **não** tem fila: criar categoria, mudar meta, cadastrar conta, importar
extrato. Esses esperam o servidor e dizem que não conseguiram falar com ele. É
escolha, não esquecimento — o lançamento do gasto é o único que não pode esperar,
porque gasto em dinheiro não lançado na hora não é lançado nunca. Os outros você
faz sentado, com o PC ligado.

## O que NÃO funciona — e é importante saber antes

**No Expo Go (o QR code), o aplicativo não ABRE com o PC desligado.**

O Expo Go não tem o aplicativo dentro dele: ele baixa o código do seu computador
cada vez que abre. Com o PC desligado, não há de onde baixar, e nem a cópia local
nem a fila ajudam — elas estão dentro de um aplicativo que não subiu. O que foi
descrito acima vale, no Expo Go, para a **conexão que cai com o aplicativo já
aberto**: PC que dorme, Wi-Fi que some, servidor reiniciando, você saindo de casa
com a tela ligada.

Para abrir de verdade longe de casa, o aplicativo precisa estar **instalado** no
aparelho. O caminho está em [`rodando-no-celular.md`](rodando-no-celular.md),
Caminho 2 — em resumo:

```bash
npm install -g eas-cli
eas login                                        # conta gratuita
eas build --platform android --profile preview   # devolve um link de .apk
```

Instalado, o aplicativo abre sem o PC: mostra a última cópia dos números (datada)
e aceita lançamento, que fica guardado até você chegar em casa. No iPhone não há
caminho gratuito para instalar fora da App Store (a Apple cobra US$ 99/ano), e lá
o Expo Go continua sendo o caminho — com a limitação acima.

E o servidor em si: ele só responde com o **PC ligado e o sistema no ar**. Para
não depender de alguém lembrar de ligar, use:

```
scripts/ligar-com-o-windows.ps1
```

Ele põe o sistema (banco e servidor) na inicialização do Windows — sem pedir
administrador, e sem abrir janela nenhuma. O aplicativo não entra junto: ele é uma
tela, e abrir uma aba a cada boot atrapalharia.

## Como é por dentro

Quatro peças pequenas, em `mobile/src/api/`:

- **`conexao.ts`** — se o aplicativo está ou não falando com o servidor. **Não usa
  o indicador de internet do sistema**, e isso é o ponto: o servidor desta família
  não está na internet, está no computador de casa. Dá para ter 5G perfeito e o
  servidor inalcançável porque o PC está desligado, e dá para a internet do
  provedor cair e o servidor responder normalmente. O que importa é só uma coisa —
  a última conversa com o servidor funcionou? Por isso o estado é alimentado pelo
  próprio cliente HTTP, a cada requisição.

- **`despensa.ts`** — onde os dados ficam no aparelho. É vizinha do `cofre.ts` e a
  separação é de propósito: o cofre (Keychain/Keystore) guarda o token, e no
  Android cada valor ali cabe em ~2 KB — o painel do mês não caberia, e falharia
  só no celular, só com dado grande, que é o pior jeito de descobrir um limite.

- **`cache.ts`** — a cópia local do que o servidor já respondeu, lida **antes** da
  primeira tela. Guarda só consulta que deu certo (guardar erro faria o aplicativo
  abrir repetindo a falha de ontem como se fosse de agora) e tem teto de tamanho,
  porque o armazenamento do Android recusa valor grande e recusa calado.

- **`fila.ts`** — os lançamentos feitos sem servidor. Três regras: nada sai da fila
  sem o servidor confirmar; nada é jogado fora em silêncio; e offline interrompe a
  subida, não descarta o resto.

A faixa que mostra tudo isso na tela é `components/AvisoDeConexao.tsx`, e ela
**não desenha nada quando está tudo normal** — faixa que aparece sempre vira parte
do fundo e ninguém lê.

## Segurança: o que fica gravado no aparelho

A cópia local é o que o servidor mandou — e o servidor **já manda mascarado**:
primeiro nome com inicial do sobrenome, sigla do banco em vez do nome, nenhum
número de agência, conta ou cartão (`backend/app/services/mascara.py`). Isso foi
escrito justamente porque o aplicativo guarda uma cópia e o aparelho sai de casa:
esconder só na hora de desenhar deixaria o nome completo e o número da conta em
texto puro no armazenamento local.

O token continua no cofre do sistema, cifrado e amarrado ao aparelho.

**O que ainda falta:** uma trava por biometria ao abrir o aplicativo. Hoje, quem
desbloquear o celular abre o aplicativo e vê os números (mascarados) da última
sincronização. Com a cópia local, essa trava passou a valer mais do que valia — é
o próximo passo natural deste documento, e está em
[`proximos-passos.md`](proximos-passos.md).
