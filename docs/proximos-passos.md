# Onde paramos

Anotado em 01/10/2026, no ponto em que o sistema abriu pela primeira vez.

## O que já funciona

O app **abre no navegador do PC** e entra com o login. Isso prova a cadeia
inteira: PostgreSQL, API, autenticação e interface. Primeira versão de fato
funcional.

---

## 1. Expo Go não abre no celular

**Sintoma:** `java.io.IOException: Failed to download remote update`.

**O que já foi eliminado:**

| | |
|---|---|
| Endereço errado (`127.0.0.1`) | **resolvido** — o terminal mostra `exp://192.168.15.57:8081` |
| SDK velho demais para o Expo Go | **resolvido** — SDK 57 |
| `expo-notifications` derrubando o app | **resolvido** — carregado sob demanda |
| `expo-secure-store` no navegador | **resolvido** — não afeta o celular |

Sobrou a **rede entre os dois aparelhos**: Firewall do Windows bloqueando o
Node, roteador isolando aparelhos (comum com celular no 5GHz e PC no cabo), ou
celular em outra rede.

**Próximo passo, ainda não tentado:** a **opção 2** do `INICIAR-APP`, que serve
o app por túnel e atravessa os três casos de uma vez. Se funcionar, confirma o
diagnóstico de rede e o celular fica resolvido sem mexer em firewall.

---

## 2. Acumular mudanças antes de publicar

O ciclo de uma correção por vez ficou lento demais: cada ajuste obrigava a
apagar a pasta, baixar o ZIP e reinstalar.

**Combinado:** daqui em diante as mudanças são construídas e validadas em
lote, e só então publicadas. Um download cobre várias correções.

Vale enquanto o sistema está na máquina de casa. Hospedado, a atualização
deixaria de passar pelo usuário.

---

## 3. O sistema ligar junto com o Windows

Hoje é preciso clicar no `ABRIR-BBBC-windows.bat` toda vez.

**A fazer:** atalho na pasta de Inicialização do Windows, para o sistema já
estar no ar quando o computador liga. O dia a dia vira abrir o Expo Go no
celular, ou um favorito no navegador — sem arquivo nenhum para clicar.

Junto disso: o launcher **lembrar a última escolha** entre 1, 2 e 3, em vez de
perguntar sempre.

---

## 4. Pendente de resposta

- **Pró-labore, lucros ou adiantamento**, quando a Checkmotor paga uma conta
  pessoal. Decide o imposto. Hoje o padrão é *adiantamento*, que é o único que
  não afirma nada sobre tributo.
- Os **gastos fixos** (financiamento, escola, plano, condomínio): valor e dia
  do mês. Sem eles a previsão depende só da média do histórico.
- Qual **e-mail** recebe os avisos.

## 5. Construído e ainda sem tela

A separação pessoal/empresa está pronta no servidor — a conta marcada como da
empresa, a triagem linha a linha na importação, o par que mantém o caixa
honesto, e as categorias das duas pontas. Falta a **lista de pendências**
("a empresa me deve") e as telas no aplicativo.

## Lote de 03/10/2026 — o que entrou

- **Abrir mais rápido.** O `pip install` deixou de rodar a cada partida: uma
  marca dentro do `.venv` guarda a lista de dependências e a versão do Python, e
  a instalação só acontece quando essa linha muda (ou quando o ambiente não
  importa de verdade). Era um minuto e meio por partida, a troco de nada. A aba
  do `/docs` passou a abrir só na estreia, e a espera do sistema olha de segundo
  em segundo em vez de de três em três.
- **Lançar à mão.** Aba nova, "Lançar", para o gasto pago em dinheiro. Se não
  houver conta nenhuma, ela oferece criar a carteira "Dinheiro" num toque.
- **Contas.** Tela de cadastro em Mais › Contas e cartões. Só o nome do banco e o
  titular são pedidos; o resto fica atrás de "mais detalhes". O número de conta
  que vier grudado no nome é apagado antes de gravar, não só na hora de mostrar.
- **Leitura.** Corpo de texto em 17 e legenda em 14 (eram 15 e 12), e uma coluna
  de largura máxima centralizada — no navegador do PC o conteúdo esticava de
  borda a borda e o rótulo ficava a um palmo do valor.
- **Cinco abas** em vez de seis: Resumo, Lançar, Gastos, Previsões, Mais. O que
  se usa uma vez por mês (importar) ou por ano (IR) passou para dentro de Mais.

## Dois achados do caminho

- **Migrations.** A adoção de banco antigo marcava as seis primeiras migrations
  como aplicadas sempre que a tabela `families` existisse. Num banco parado no
  meio da lista isso era pior que não marcar nada: as que faltavam nunca mais
  rodariam. Agora cada uma tem uma pergunta que responde "isto está no banco?",
  e a adoção para na primeira que responde "não". Um banco de teste meio-migrado
  foi recuperado por esse caminho.
- **Comentário obrigatório herdado.** "Únicos" exige explicação, e o servidor
  herda a exigência para as filhas — mas as filhas chegam ao aplicativo com a
  marca apagada. Escolher "Únicos › Viagens" levava a um erro sem campo na tela
  para resolver. A herança agora desce no aplicativo também, nas duas telas que
  escolhem categoria.

## Lote de 03/10/2026, segunda parte — as categorias dele

### A árvore passou a ser a do Excel

As quinze categorias da lista do Felipe, com os nomes dele e na ordem em que ele
as escreveu: Gastos mensais, Condomínio, Financiamentos, Educação, Saúde,
Transporte, Mercado, Restaurantes, Market places, Delivery de comida, Limpeza,
Gastos anuais, Gastos únicos, Criação, Cla PJ.

Quase tudo já existia, espalhado de outro jeito. "Combustível",
"Estacionamento" e "Transportes" eram três categorias soltas de primeiro nível —
agora são subcategorias de Transporte, junto com "Pedágio e tag", que faltava.
"Assinaturas" desceu para dentro de Gastos mensais. "Faxina" virou "Limpeza" e
"Aplicativo de comida" virou "Delivery de comida". "Cla PJ" é nova.

O terceiro nível sobrevive onde ele citou exemplos ou onde a natureza fiscal
difere entre as filhas: plano de saúde deduz e farmácia não, e isso tem de
continuar separado ou a projeção de IR erra.

### Criar, renomear, excluir — e a meta de cada uma

Aba **Categorias** nova. Cada linha traz a meta do mês e o quanto já foi gasto,
com a barra ficando laranja a 80% e vermelha quando estoura. A seta abre as
subcategorias.

Tocar numa categoria (ou numa subcategoria — a tela é a mesma) abre a leitura no
tempo: o mês contra a meta, contra o mês anterior, contra o **mesmo mês do ano
passado** e contra a **média dos doze meses**, com treze barras e a média
marcada. Dali se define, muda ou apaga a meta, se renomeia, se cria subcategoria
e se exclui.

Excluir categoria que já tem lançamento **arquiva** em vez de apagar, e diz isso.
Apagar de verdade transformaria gasto classificado em gasto solto, e o estrago só
apareceria no fechamento do mês.

### O cartão, e a conta que não pode ser contada duas vezes

O cartão é o único lugar onde o mesmo dinheiro aparece em dois extratos: a compra
no extrato do cartão, e semanas depois o pagamento da fatura no da conta
corrente. A regra é que **a despesa é a compra, no dia dela** — o pagamento da
fatura é bolso trocando de lugar.

Duas coisas estavam erradas e foram corrigidas:

1. A categoria "Pagamento de fatura" contava como gasto (`counts_as_expense`
   estava `true` desde a 0004). Era a primeira coisa a estourar quando o extrato
   da conta corrente chegasse.
2. O reconhecimento da linha não funcionava. `normalize()` apaga "pagamento de
   fatura" de propósito — é ruído quando se procura o fornecedor de uma compra.
   Só que é justamente essa frase que diz que a linha **não** é compra. As regras
   passaram a ser testadas contra as duas leituras da descrição.

Em **Mais › Cartão de crédito**: quanto foi comprado no mês (por cartão, que é a
base dos pontos), quanto saiu de fatura, e a lista das linhas que parecem fatura
e estão contando como gasto — com o passo a passo para arrumar.

### A sugestão pelo título do extrato

As 188 regras de fornecedor apontavam todas para a árvore antiga; depois da 0009
elas ficariam mudas, sem erro nenhum. Foram remapeadas e ampliadas (Sem Parar,
ConectCar, 99Food, Cheeta, padaria, DARF, Ri Happy...).

Um achado no caminho: o desempate entre regras é por tamanho do padrão, e
"IFOOD *RESTAURANTE SAO JOSE" casava com `restaurante` (11 letras) antes de
`ifood` (5) — o jantar entregue em casa entrava como refeição fora. Os padrões de
**plataforma** passaram a ter prioridade melhor: quem paga a conta é o aplicativo,
e é ele que define a natureza do gasto. Uma padaria pedida pelo iFood continua
sendo delivery. Qualquer correção dele continua vencendo as duas.

### Ligar junto com o Windows

`LIGAR-COM-O-WINDOWS.bat`: põe (ou tira) um atalho na pasta Inicializar do
usuário — o único caminho que não pede administrador. Sobe o **sistema**, não o
aplicativo: o sistema precisa ficar de pé o dia inteiro para o celular consultar,
e abrir uma aba de navegador a cada boot seria atrapalhar.

No boot o script roda com `-AoLigar`: não pergunta nada, não abre navegador e não
espera Enter (numa janela minimizada, uma pergunta é um travamento silencioso).
Espera até dois minutos pelo serviço do PostgreSQL, e se o cadastro não existe
escreve o motivo em `ao-ligar.log` e desiste. Primeira instalação é sempre à mão.

## Ainda pendente

- **Offline**: consultar e lançar com o PC desligado, com fila que sobe depois. O
  lado do servidor está pronto (a `client_key` já impede duplicata); falta o
  cache local, a trava por biometria e a fila no aplicativo.
- A triagem do que é da empresa e do que é pessoal, com a lista de pendências
  ("a empresa me deve").
- Expo Go no celular: a opção 2 (túnel) continua sem teste.
- Os valores dos gastos fixos (financiamento, escola, plano, condomínio) e qual
  e-mail recebe os avisos.

## Atualizar deixou de ser um ritual

Antes, cada ajuste custava: baixar o zip, extrair, rodar a instalação inteira de
novo, reler o QR code, apertar `w`. O caro ali nunca foi o download — foram os
minutos reinstalando bibliotecas que na maior parte das vezes não mudaram.

**`ATUALIZAR-windows.bat`** troca só o código. Ficam onde estão: o banco (que nem
mora na pasta — vive no PostgreSQL), o `backend\.venv`, o `mobile\node_modules` e
qualquer `.env`. Se a pasta for um clone do git, um `git pull` resolve; se for uma
pasta baixada como zip, ele baixa o zip novo e copia por cima, sem apagar nada —
o robocopy é chamado sem `/MIR`, então só adiciona e sobrescreve.

Junto com a marca de instalação do lote anterior, o ciclo fica: um clique em
ATUALIZAR, e o sistema sobe. As bibliotecas só são reinstaladas se a lista de
dependências mudou.

**O `w` e o QR code.** O `w` é do servidor do Expo, e existe porque ele não sabe
se você quer o navegador ou o celular. Agora o launcher **lembra a última
escolha**: quem escolheu a opção 3 (navegador) uma vez passa a só apertar Enter,
e a aba abre sozinha. O QR code continua sendo necessário no celular enquanto o
app roda pelo Expo Go — isso só desaparece com um APK instalado, que é outro
assunto.
