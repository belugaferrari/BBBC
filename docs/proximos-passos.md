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

- **Trava por biometria** ao abrir o aplicativo. Com a cópia local dos dados no
  aparelho, ela passou a valer mais do que valia: hoje quem desbloqueia o celular
  vê os números (mascarados) da última sincronização. É o que falta do offline —
  o resto está feito, ver [`offline.md`](offline.md).
- **Abrir o aplicativo longe de casa** exige o APK instalado: no Expo Go o código
  vem do PC a cada abertura, então com o PC desligado o aplicativo não sobe (a
  cópia local e a fila estão dentro de um aplicativo que não subiu). O build é um
  comando e está no Caminho 2 de [`rodando-no-celular.md`](rodando-no-celular.md);
  falta rodar.
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

## O atalho do Expo Go, e quando ele deixa de servir

O Expo Go guarda os servidores abertos recentemente e deixa reabrir com um toque,
sem escanear o QR de novo — o atalho **é** o endereço, `exp://IP:8081`. Como o
roteador entrega o endereço por empréstimo, um dia ele muda, e aí o atalho aponta
para uma máquina que não existe mais. O sintoma no celular é um erro de rede que
não diz nada sobre IP.

O launcher passou a guardar o endereço da última vez e a comparar:

- mesmo endereço → diz que o atalho ainda serve, não precisa escanear;
- endereço diferente → avisa qual era, diz para escanear uma vez, e explica como
  pedir ao roteador um endereço fixo para o PC (`DHCP reservation`).

Falha na detecção não apaga o endereço guardado — senão a próxima partida
acusaria mudança sem ter havido nenhuma.

## O OFX que o sistema recusava

Ele mandou extratos OFX e o sistema não leu nenhum. Eram **dois** problemas
independentes, e o primeiro escondia o segundo.

### 1. No navegador, o arquivo nunca saía do aplicativo

O envio montava o arquivo como `{uri, name, type}` — que é o contrato do FormData
do React Native, e funciona no celular. No navegador o FormData é o do padrão
web: ele só entende `Blob` ou `File`, e um objeto comum **não dá erro** — é
convertido para texto. O que chegava no servidor era a palavra
`[object Object]`, e a resposta falava de um tipo de dado que não dizia nada a
quem estava tentando importar um extrato.

Agora o envio olha onde está rodando: no navegador anexa o `File` de verdade (o
seletor sempre entrega um), no celular mantém o objeto com `uri`. E erro de
validação do servidor, que vem como lista, virou frase.

### 2. O leitor de OFX não aguentava banco brasileiro

Três falhas reais, achadas com arquivos montados no formato de cada banco:

- **Agregado sem etiqueta de fechamento.** O padrão pede `</STMTTRN>`; Banco do
  Brasil e Caixa não escrevem, e abrem o lançamento seguinte em cima do anterior.
  O leitor procurava pelo fechamento, não achava lançamento nenhum e recusava o
  arquivo com *"o arquivo é mesmo um OFX?"* — para um OFX legítimo. Era o sintoma
  exato.
- **Encoding declarado que não é o usado.** O cabeçalho quase sempre diz
  `ENCODING:USASCII` / `CHARSET:1252` e boa parte dos bancos grava UTF-8. O
  leitor obedecia o cabeçalho e devolvia `FarmÃ¡cia`. O estrago não era só
  visual: é esse texto que alimenta a sugestão de categoria, então a regra
  `farmacia` deixava de casar.
- **UTF-16.** Byte zero intercalado fazia a etiqueta `<STMTTRN>` nem aparecer.

A ordem de decisão agora é: BOM primeiro (é fato, não declaração), depois o teste
de UTF-8 válido (acento em cp1252 é byte solto que não fecha sequência multibyte,
então um arquivo cp1252 não passa por aí por acidente), e só no fim o cabeçalho —
porque é justamente ele que mente.

Sete arquivos no formato de Itaú, BB, Nubank, Santander (OFX 2.x), um por linha,
com BOM e em UTF-16 passam pela API e chegam com a categoria sugerida certa —
inclusive `PAGAMENTO FATURA CARTAO` caindo em "Pagamento de fatura", que é o que
impede a duplicata do cartão.

## Olhar os meses anteriores

O Resumo e a lista de Gastos estavam presos ao mês atual. Agora têm o mesmo
seletor de mês das Categorias e do Cartão — `‹ setembro de 2026 ›`, com atalho
para voltar a hoje e a seta de avançar desligada no mês corrente.

### Um cuidado que o Resumo precisou ter

O que o servidor devolve não é todo do mês escolhido:

- o **fluxo** (entrou, gastou, sobrou), o **Sankey** e as **metas** são do mês —
  olhar agosto mostra agosto;
- os **saldos** (disponível, patrimônio, investido, fatura) são de **hoje**,
  porque saem do saldo atual de cada conta, não de uma foto do passado.

Mostrar o saldo de hoje embaixo do título "agosto" seria um número errado em
silêncio — o pior tipo. Em mês que não é o atual, esses quatro passaram a dizer
"hoje" no próprio rótulo, com uma linha explicando por quê. Os alertas, que
também são do agora, saem da tela nos meses passados.

## Atualizar com o sistema aberto

Ele clicou no `ATUALIZAR` com as duas janelas do BBBC abertas, e um terceiro
terminal apareceu. A pergunta era justa, e a resposta era um problema do script.

Trocar os arquivos não troca o programa que está de pé: o Python leu o código
quando subiu e segue com a versão velha na memória. Pior, no fim o atualizador
oferecia abrir o BBBC — e o `abrir-tudo` via o servidor **velho** respondendo,
concluía "já estava no ar" e abria só a tela. Tela nova conversando com servidor
velho é o estado mais confuso possível, e parece que deu certo.

Agora o atualizador detecta, no começo, o que está ligado (a API na 8000 e o
Metro na 8081, por socket, para não depender do nome de cmdlet de rede nenhum).
Avisa logo que será preciso fechar e abrir, e no fim, em vez de oferecer abrir,
dá os passos numerados conforme o que achou aberto. Nada de dado se perde em
nenhum momento — o banco não mora na pasta.

## A janela que abria e fechava

Ele clicou no `ABRIR-BBBC`, a janela do sistema piscou e sumiu, e a janela de
espera ficou enfileirando pontinhos. Dois defeitos, somados.

### O caminho ia sem aspas

O `abrir-tudo.ps1` abria a janela do sistema com
`Start-Process powershell -ArgumentList @('-File', $caminho)`. O `-ArgumentList`
junta a lista num único texto de linha de comando e **não põe aspas em nada** —
então, com a pasta num caminho que tenha espaço, o PowerShell do outro lado
recebe o caminho picado:

```
The argument 'C:\Users\...\OneDrive\Área' is not recognized as the
name of a script file.
```

Ele imprime o modo de usar, sai com código 64, e numa janela recém-aberta isso
aparece como um piscar. No Windows em português com OneDrive a Área de Trabalho
tem dois espaços no caminho, então era quase garantido. Os `.bat` nunca sofreram
disso porque o `cmd` passa `"%~dp0scripts\..."` entre aspas.

### E a janela de espera não percebia

Ela só olhava o relógio: quinze minutos de pontinhos para uma janela que já não
existia. Agora guarda o processo (`-PassThru`) e para no instante em que ele
morre — dois segundos, com uma mensagem que diz o que fazer. E, passados 45
segundos sem resposta, manda olhar a outra janela na barra de tarefas, dizendo o
que procurar lá (instalação correndo, pergunta parada, ou erro em vermelho).

### Erro em janela que fecha é erro perdido

Todos os `.bat` ganharam `pause` no fim. Sem ele, qualquer erro que mate o
PowerShell antes de o script chegar ao próprio "aperte Enter" fecha a janela
levando a mensagem junto — e o que se vê é só um piscar.

## Duas pastas com o mesmo nome

Atualizar pelo zip deixa duas pastas iguais na máquina: a instalada e a recém
extraída, que só serviu de fonte. Mesmo nome, mesmos arquivos — e abrir a errada
**não dá erro nenhum**: o sistema sobe, o banco é o mesmo (ele vive no
PostgreSQL, não na pasta), e tudo parece normal. Só que o trabalho vai para a
cópia que vai ser jogada fora.

O `ATUALIZAR` passou a dizer, antes de tocar em qualquer coisa, **qual pasta** vai
atualizar. E, quando não acha `backend\.venv` nem `mobile\node_modules` ali,
avisa que aquilo não parece a instalação e pergunta se é para seguir — com "não"
como padrão. Não dá para ter certeza só por isso (uma instalação nova também não
os tem), mas dá para desconfiar em voz alta.

## O primeiro extrato de conta corrente de verdade

Ele mandou um OFX do Itaú e achou que o sistema tinha lido só metade do mês. Não
tinha: **o arquivo é que só traz 18/09 a 01/10**, e diz isso nele mesmo
(`DTSTART` / `DTEND`). O leitor trouxe as 14 linhas que existiam. O banco é que
limita o período na hora de gerar o arquivo — é lá que o período se escolhe.

Mas o arquivo revelou um problema de verdade, e grande.

### Uma de catorze

Fatura de cartão traz nome de loja: iFood, Uber, Netflix. **Extrato de conta
corrente traz sigla de banco e PIX para pessoas.** O catálogo só conhecia o
primeiro, e esse extrato chegou com **1 linha de 14** sugerida.

Entraram as siglas que dá para reconhecer com segurança: `FINANC IMOBILIARIO`,
`REND PAGO`, `APLIC AUT` / `RESGATE AUT` (a aplicação automática move dinheiro
todo dia entre a conta e o fundo — não é gasto nem receita, e contada como saída
encheria o mês de despesa que nunca existiu), `TARIFA`, `IOF`. Foram de 1 para 5.

### E as outras nove — o achado que vale mais

As nove restantes são PIX para pessoas. **Regra nenhuma vai adivinhar essas**, e
nem deveria. O que resolve é corrigir uma vez e o sistema lembrar.

Só que não lembrava. O Itaú cola o dia e o mês no fim da descrição —
`PIX TRANSF KARINA 27 09`, e quando o nome é longo sem espaço nenhum:
`GEORGET26 09`. A data entrava no padrão aprendido, então corrigir aquela linha
ensinava uma regra que **só casaria de novo no dia 27 de setembro**. O
aprendizado era inútil justamente onde era necessário.

A data colada passou a ser tratada como ruído, junto com os prefixos de
movimentação (`PIX QRS`, `PIX AUT`, `TED`, `DOC`). O padrão aprendido virou
`karina`, `georget`, `booma organ` — e atravessa o mês.

Conferido de ponta a ponta contra a API: PIX de setembro chega sem categoria, ele
corrige para Diarista, e o PIX de **outubro** para a mesma pessoa já chega
classificado.

## O Resumo: seletor preso, Sankey fora, metas com história

### O seletor de mês sumia quando mais fazia falta

Ele não achou o seletor no celular. O seletor existia — mas a tela saía **antes**
dele quando o mês estava carregando ou não tinha carregado:

```tsx
if (isLoading) return <Spinner/>;        // sem seletor
if (error) return <Erro/>;               // sem seletor
return (<ScrollView><MonthPicker/>…      // só aqui
```

Quem abrisse um mês vazio ficava preso nele, sem botão nenhum para sair. O
seletor passou para fora dos dois: é a única coisa que sempre dá para fazer.

### O Sankey saiu; entrou a curva do mês

O Sankey é bonito e responde "para onde foi o dinheiro" — pergunta que a aba
Categorias responde melhor, com números em vez de fitas. O que ele não respondia
é a que se faz no dia 12: **estou gastando rápido demais?**

No lugar dele, o gasto **acumulado** dia a dia, com três referências:

| | forma | por quê |
|---|---|---|
| Meta do mês | reta | é um teto |
| Mês passado | curva | mudou alguma coisa agora? |
| Mesmo mês do ano passado | curva tracejada | é mudança ou sazonalidade? |

As duas últimas vêm como **curva**, e não como reta no total delas. A reta diria
só "no fim do mês passado deu R$ 2.450"; a curva diz "no dia 12 do mês passado
você estava em R$ 980, e hoje está em R$ 1.900" — que é a leitura que faz alguém
mudar de comportamento no meio do mês, enquanto ainda dá. O total continua
legível: é onde a curva termina.

No mês corrente a curva para em hoje. Desenhá-la reta até o dia 31 faria o mês
parecer estagnado, quando ele apenas ainda não aconteceu.

### As metas passaram a ter história

Pedido dele, e estava errado antes: *"se eu mudar os valores das metas, a
informação não pode retroagir nos gráficos de meses anteriores"*.

A rota fazia o contrário — substituía a meta no lugar **e ainda puxava o
`starts_on` para trás**, então mudar o teto hoje reescrevia todos os meses
fechados. Setembro passava a ser julgado por uma meta criada em outubro. Eu
tinha até escrito um comentário justificando: *"o histórico de quanto foi o teto
em março não é informação que alguém tenha pedido"*.

Agora a meta é versionada: mudar o valor **encerra** a anterior no último dia do
mês anterior e abre uma nova. Com uma exceção que é correção e não mudança — se
a meta vigente já começou neste mês, não há passado dela para preservar, e o
valor é corrigido no lugar (digitar 280 em vez de 2.800 e arrumar em seguida).

Apagar também não reescreve o passado pelo outro lado: a meta que vem de antes é
encerrada no fim do mês anterior; só a que nasceu neste mês some de vez.
