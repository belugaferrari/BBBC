# Importando extratos do banco

Alternativa ao Open Finance: você exporta o extrato pelo site do banco e envia
pelo app. Funciona hoje, sem contratar nada.

## Formatos aceitos

| Formato | Qualidade da leitura | Quando usar |
|---|---|---|
| **OFX** (`.ofx`, `.ofc`, `.qfx`) | **Exata** | Sempre que o banco oferecer. Cada lançamento vem com identificador próprio (FITID), então a deduplicação é perfeita. |
| **CSV** (`.csv`, `.txt`) | Muito boa | Segunda opção. O leitor identifica as colunas pelo nome e, se não achar cabeçalho, deduz pelo conteúdo. |
| **Excel** (`.xlsx`, `.xlsm`) | Muito boa | Quando o banco entrega a fatura em planilha. Mesma leitura do CSV — o que muda é só como a grade é obtida. |
| **PDF** | Aproximada | Último recurso. Funciona, mas confira antes de confirmar. |

**Planilha em `.xls`** (formato antigo, de antes de 2007) **não abre**: é outro
formato por dentro, não um zip. Abra no Excel e salve como `.xlsx`, ou exporte em
CSV — o sistema avisa isso quando acontece, em vez de dizer que o arquivo está
corrompido.

Quase todo banco brasileiro exporta OFX — costuma aparecer como "Exportar para
o gerenciador financeiro", "OFX" ou "Money/Quicken". Vale procurar: é a
diferença entre importação exata e importação por aproximação.

**Sobre PDF, sem rodeios:** PDF não é formato de dados, é formato de impressão.
O leitor reconhece linhas no padrão `data … descrição … valor`, que cobre a
maioria dos extratos, mas cada banco diagrama do seu jeito e muda o leiaute sem
avisar. PDF escaneado (imagem) não funciona de jeito nenhum — não há texto para
extrair. Por isso lançamentos vindos de PDF ficam marcados com origem própria
no banco de dados: são os que merecem um olhar antes de virarem verdade.

## Como funciona

São dois passos, de propósito.

**1. Envio.** O arquivo é lido e devolvido como uma proposta. **Nada é gravado
aqui.** Você vê cada lançamento, com a categoria que o sistema sugeriu.

**2. Conferência.** Linhas que já existem vêm desmarcadas, com o motivo escrito
("já importado antes", "já importado em outro formato", "você já lançou este
valor à mão"). Você marca e desmarca o que quiser e confirma.

Gravar direto seria mais rápido, e seria a forma mais fácil de sujar a base.
Sujeira em base financeira custa horas de conferência depois.

### A categoria se troca na conferência

Em cada linha, a categoria é um botão: toque e escolha outra, **antes de
gravar**. É mais barato aí que depois — depois seria abrir a lista de gastos e
corrigir um por um.

Duas coisas aparecem diferentes de propósito:

| Na linha | O que significa |
|---|---|
| **Mercado**, em cinza | sugestão com base em algo — "SUPERMERCADO ANGELONI" casou com uma regra |
| **A definir**, em vermelho | nenhuma regra reconheceu: o sistema não está sugerindo, está admitindo que não sabe |

Mostrar as duas iguais faria a segunda passar por sugestão e ser confirmada sem
ninguém olhar. Por isso o rodapé também conta: "2 vão entrar como 'A definir'".

### "A definir" é uma categoria de verdade

Você pode confirmar sem resolver — é para isso que ela existe: *"nem sempre pelo
nome dos gastos vou saber o que é"*. O lançamento entra, conta no gasto do mês, e
fica num lugar visível:

- aparece no **Resumo**, numa linha que cobra: "3 lançamentos esperando
  categoria · R$ 850";
- aparece na tela de **Categorias**, com nome e total, como qualquer outra;
- some de lá assim que você escolher a categoria certa, na aba **Gastos** →
  "só os pendentes".

Isso é diferente de "sem categoria", que era um rótulo calculado: não abria, não
recebia meta, não aparecia na tela de Categorias — e o total daquela tela ficava
menor que o do Resumo, sem uma linha explicando a diferença.

A categoria "A definir" não pode ser excluída: ela é o destino do que o sistema
não soube classificar. Ela fica vazia sozinha, conforme você decide.

## Cartão de crédito: dois arquivos, e a conta que tem de fechar

O cartão é o único lugar onde o **mesmo dinheiro aparece em dois extratos**:

| Arquivo | O que traz |
|---|---|
| OFX da **conta corrente** | uma linha só: "PAGTO FATURA CARTAO", o total pago |
| OFX da **fatura do cartão** | cada compra, com data, descrição e valor |

A regra do sistema é: **a despesa é a compra, no dia dela**. O pagamento da
fatura é bolso trocando de lugar, e por isso a categoria "Pagamento de fatura"
não conta como gasto. Com os dois arquivos importados, as contas fecham sozinhas
e nada é contado duas vezes.

Só que essa regra erra para o outro lado quando a fatura **não** é importada: o
pagamento não conta como gasto, as compras não existem, e milhares de reais saem
da conta sem aparecer em gasto nenhum. O mês fica barato no papel. É o caso de
quem só baixa o extrato da conta corrente — e era silencioso.

Agora não é. Em **Mais › Cartão de crédito**, o sistema compara duas coisas:

- quanto de **fatura foi paga** no mês;
- quanto de **compra de cartão ele conhece** na janela que essa fatura cobre (o
  mês anterior e o atual — a fatura de outubro cobra compras de setembro).

Fatura paga com compra conhecida **zero** é um buraco do tamanho da fatura, e
vem escrito na tela. Duas saídas, e as duas servem:

1. **Importar a fatura** do cartão (o detalhe). É o melhor: cada compra na sua
   categoria, e os pontos do cartão com base certa.
2. **"Contar como gasto"**, no botão ao lado do pagamento. A linha vai para a
   categoria **"Cartão (sem detalhe)"** e passa a contar como um gasto só. O mês
   fica certo no total, sem o detalhe.

Se você escolher a 2 e depois importar a fatura, o sistema **aponta a duplicata**
— e o botão vira "Voltar a não contar". É a mesma vigilância que já existia para
a linha de fatura classificada como gasto por engano.

### A fatura fala pelo lado da dívida

Num extrato de **conta**, o sinal é o do saldo: gasto negativo, depósito
positivo. Na **fatura do cartão**, o sinal é o da **dívida**: cada compra aumenta
o que você deve, então vem **positiva**, e o pagamento da fatura (que abate a
dívida) vem negativo. O mesmo número, o mesmo sinal, dois significados opostos.

Lida com a regra da conta, a fatura inteira vira ao contrário: as compras entram
como **entrada** — dinheiro chegando —, pegam categoria de receita e inflam a
renda e a taxa de poupança; e o total da fatura, por ser o único negativo, entra
como o único gasto do mês.

O sistema corrige isso sozinho, e **diz na conferência o que corrigiu**:

- **o sinal.** Numa fatura, a esmagadora maioria das linhas é compra. Se a
  maioria chegou como entrada, foi o sinal que estava invertido — não o mês que
  foi de devoluções. A decisão é pela maioria das linhas, e não por uma tabela de
  bancos: assim funciona com o banco que exporta certo, com o que exporta errado,
  e com o próximo;
- **a linha do total.** A fatura repete, numa linha, a soma das outras ("TOTAL DA
  FATURA"). Ela não é um lançamento: importada junto, cobra o mês duas vezes. Sai
  por nome (frase inteira, para o posto "TOTAL ENERGIES" não ser confundido com
  rodapé) e por aritmética — a linha que é a soma das outras.

Isso só vale para conta do tipo **cartão de crédito**. Em conta corrente, o
depósito positivo é entrada de verdade, e inverter ali transformaria a renda do
mês em gasto.

### E se mesmo assim vier do lado errado

Na conferência, abrindo a linha (o botão de categoria), a primeira coisa é
**"Esta linha é: gasto / entrada"**. Vira ali, antes de gravar. Existe porque
leiaute de banco não acaba — e porque direção errada, depois de gravada, era o
único erro sem conserto pela tela.

Virar a linha **esquece a categoria sugerida**: ela era do outro lado, e
"Salário" num gasto não quer dizer nada. A linha vai para "A definir" se você não
escolher outra.

Uma coisa que a fatura do cartão **ainda não** faz: ler o parcelamento. A
descrição vem com "PARCELA 01/03", e cada fatura trará a sua parcela — o gasto do
mês fica certo —, mas a **Previsão não antecipa** as parcelas que faltam.

## Desfazer uma importação

Em **Importar**, abaixo do envio, ficam os **extratos já importados**, com um
botão **desfazer** (que pede confirmação: o segundo toque é que apaga). Ele apaga
os lançamentos **daquele arquivo**, e só deles — o que você lançou à mão não é
tocado.

Existe por causa de um caso concreto: a fatura entrou com o sinal invertido e as
compras viraram renda. Sem desfazer, a saída era apagar dezenas de linhas uma por
uma. E reimportar o arquivo corrigido **não** resolveria sozinho: a direção entra
na impressão digital, então as linhas corrigidas não são reconhecidas como
repetidas, e você terminaria com as duas versões somadas.

O lote fica registrado como descartado, com os avisos que apareceram na
conferência — o histórico de que aquele arquivo passou por aqui não se perde.

## O que impede lançamento duplicado

Três camadas, da mais exata para a mais tolerante:

1. **Identificador do banco.** Se o arquivo traz FITID (OFX), ele é soberano.
2. **Impressão digital.** Data + valor + direção + descrição normalizada,
   com índice único no banco por conta. Mesmo duas confirmações simultâneas não
   duplicam.
3. **Equivalência.** Mesmo valor, mesma direção, até 3 dias de diferença. É o
   que pega a compra que você digitou à mão antes de o banco publicar, e o
   mesmo período importado em dois formatos diferentes.

Isso está coberto por teste: importar o mesmo extrato duas vezes, e depois o
mesmo período em CSV e OFX, continua com cinco lançamentos.

## Se o seu banco não for reconhecido

O leitor de CSV entende as variações comuns (`Data`/`Date`, `Histórico`/
`Descrição`/`Lançamento`, `Valor` ou colunas separadas de `Débito` e `Crédito`,
separador `;` ou `,`, valores `1.234,56` ou `1,234.56`). Se ainda assim falhar,
a mensagem de erro diz o que não foi reconhecido — me mande o cabeçalho do
arquivo (sem os valores) e eu acrescento o padrão.

## Arquivos de exemplo

`backend/db/samples/` tem o mesmo extrato nos três formatos, para você testar o
fluxo antes de mexer com dados reais.
