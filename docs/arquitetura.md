# Decisões de arquitetura

Este documento registra o **porquê** de cada escolha estrutural. O código conta
o "como"; aqui fica o que não dá para ler no diff.

## 1. Taxonomia: árvore infinita com caminho materializado

`categories` é auto-referenciada e carrega um `path` do tipo `ltree`
(`despesas.essenciais.saude.plano_de_saude`). Duas triggers mantêm a coerência:

- `categories_sync_path` recalcula `path`/`depth` na inserção e quando o pai muda;
- `categories_move_subtree` reescreve a subárvore inteira quando uma categoria é
  movida.

Por que `ltree` e não recursão pura: as perguntas do app são quase sempre "some
tudo que está abaixo de Essenciais". Com `ltree` isso é `tc.path <@ c.path` com
índice GiST; com CTE recursiva seria uma varredura a cada tela.

O catálogo global vive com `family_id IS NULL` e é **clonado** para cada família
(`app.cli.clone_catalog`). Assim vocês podem renomear e reorganizar categorias
sem afetar o template — e o template pode evoluir sem mexer no que já é de vocês.

## 2. Segregação fiscal na própria taxonomia

Cada categoria carrega `ir_treatment` (tributável pela tabela, carnê-leão,
exclusiva na fonte, isento) e `ir_deduction_type` (saúde, educação, previdência,
pensão...). A transação pode sobrescrever ambos, e a view `v_transactions_ir`
resolve a precedência **override da transação > herdado da categoria**.

Consequência prática: quando a distribuição de lucros da Checkmotor cai na conta
e é categorizada, ela já entra como isenta; o pró-labore, como tributável. O
módulo de IR não precisa de nenhuma regra ad hoc.

Detalhes que a taxonomia já codifica:
- medicamento fica dentro de Saúde mas com dedução `NENHUMA` (não é dedutível);
- material escolar e curso livre ficam dentro de Educação, também não dedutíveis.

## 3. Motor de IR sem números mágicos

`tax_brackets` e `tax_parameters` guardam faixas, alíquotas, parcela a deduzir,
teto de instrução, dedução por dependente, limite de PGBL e afins — sempre por
ano-calendário. `tax_years.status` marca o ano como `PROVISORIO` até os números
serem conferidos contra a norma oficial, e a API devolve esse aviso junto com o
resultado.

O módulo `services/tax.py` é puro: recebe rendimentos e despesas já
materializados e devolve o memorial de cálculo dos dois modelos (completo e
simplificado), a recomendação e quanto se ganha com ela. Isso permite testar o
imposto sem banco — e é onde um erro custaria dinheiro de verdade.

O teto de instrução é aplicado **por pessoa**: o excedente da escola de uma
filha não migra para a outra. O campo `ir_deduction_member_id` na transação é o
que torna essa regra possível.

## 4. Categorização: regras explicáveis, não caixa-preta

`services/categorization.py` normaliza a descrição (minúsculo, sem acento, sem o
ruído típico de extrato: "COMPRA CARTAO", asteriscos, parcelas, datas) e aplica
a primeira regra que casa, na ordem `(prioridade, confiança, acertos,
especificidade)`.

Quando vocês corrigem uma categoria, a correção vira uma regra de fornecedor com
prioridade melhor que a das genéricas, e a regra que errou perde confiança. Toda
transação guarda qual regra a classificou e com que confiança — dá para auditar
e desfazer, o que um classificador estatístico não ofereceria neste tamanho de
base.

## 5. Conciliação idempotente

`transactions` tem índice único parcial em `(account_id, provider_tx_id)`.
Reprocessar o mesmo período não duplica nada. Antes de criar uma linha nova, o
sincronizador procura um lançamento manual equivalente (mesmo valor, mesma
direção, ±3 dias) e o marca como conciliado — o que vocês digitaram continua
sendo a mesma linha, agora com o carimbo do banco.

Credenciais bancárias nunca chegam ao nosso banco: o provedor guarda o vínculo,
nós guardamos o id do item e a validade do consentimento (que expira e precisa
ser renovado).

## 6. Open Finance atrás de um contrato

`integrations/openfinance/base.py` define o protocolo; Pluggy e Belvo são
implementações; `ManualProvider` é o padrão. O sistema inteiro funciona sem
nenhum contrato de Open Finance assinado — e trocar de provedor depois é trocar
uma linha de configuração, não reescrever o módulo de gastos.

Webhook sem assinatura válida é registrado e descartado, nunca processado.

## 7. Comparativo de investimentos honesto

Confrontar a rentabilidade da carteira com o CDI acumulado ignora que o dinheiro
entrou em datas diferentes. `compare_to_benchmark` constrói uma **carteira
sombra**: os mesmos aportes, nas mesmas datas, rendendo o indicador. A
rentabilidade da carteira usa TWR, que neutraliza o efeito do momento do aporte.

## 8. Sankey desenhado à mão

Não existe biblioteca de Sankey para React Native, então o layout é calculado em
`mobile/src/components/sankeyLayout.ts` (puro, testável) e desenhado com
`react-native-svg`. Todos os estágios usam a **mesma escala** — se cada coluna
tivesse a sua, fitas de valores diferentes apareceriam com a mesma espessura e o
gráfico mentiria. A sobra do mês vira um nó próprio, para a soma dos links que
saem do nó central fechar com a receita total.

## 9. Nem todo dinheiro que sai é gasto

`categories.counts_as_expense` separa **consumo** de **transferência
patrimonial**. Amortização de financiamento é dívida virando patrimônio; aporte
em investimento é dinheiro mudando de bolso. Os dois saem da conta corrente e
por isso continuam no fluxo de caixa — mas somá-los ao gasto faria o mês parecer
pior do que foi, e derrubaria a taxa de poupança justamente de quem está
construindo patrimônio.

O dashboard passa a informar três números onde antes havia dois: `outflow` (tudo
que saiu), `consumo` e `patrimonio`, com `outflow = consumo + patrimonio`. A
análise por categoria ignora as categorias patrimoniais; o fluxo de caixa, não.

A mesma coluna resolveu um erro que já existia e ninguém tinha notado: o aporte
mensal vinha sendo somado como despesa desde o começo.

## 10. Nem todo dinheiro que entra é renda

`categories.counts_as_income` é o espelho da coluna acima, para o outro lado do
caixa. Os avós depositam todo mês para pagar a escola das meninas: o dinheiro
passa pela conta da família, mas não é dela. Contar como renda estraga três
números — a renda do mês, a taxa de poupança e, pior, a projeção, que passaria a
contar com dinheiro que depende da vontade de outra pessoa.

Só que tirar a entrada sem tirar a saída trocaria um erro por outro, e o novo
seria pior: a escola paga pelos avós apareceria como gasto da casa todo mês. Por
isso a doação carrega **para que** foi dada (`donation_for_category_id`), e o
dashboard abate do consumo o que ela cobriu — com `LEAST`, até o que de fato se
gastou naquele destino no mês. Doação de R$ 3.000 num mês em que a escola custou
R$ 1.000 abate R$ 1.000, não R$ 3.000.

O fluxo do mês passa a devolver cinco números onde havia dois: `inflow` (tudo que
entrou), `renda`, `doacoes`, `consumo` e `consumo_proprio`. A taxa de poupança usa
`renda` e `consumo_proprio` — os dois honestos.

A doação também carrega **quem** deu (`donor_id`), e não por gosto de cadastro: o
ITCMD é estadual e seu limite de isenção conta **por doador e por ano**, então
somar tudo num balde só não responde à pergunta que o imposto faz. O limite em si
fica em `families.itcmd_annual_exemption`, **nulo por padrão** — ver o aviso em
`docs/perguntas-abertas.md`, item 1.9.

### Três baldes de entrada, e não um

`counts_as_income = false` diz "não é renda". Não diz "é doação" — e confundir as
duas coisas foi o primeiro erro desta parte do sistema. Transferência entre contas
próprias também não é renda; o crédito do pagamento da fatura, que vem dentro do
OFX do cartão, também não. Com um balde só, o Resumo chamaria de **doação dos
sogros** o pagamento do próprio cartão.

Então o mês devolve `renda`, `doacoes` (pelo **caminho** `receitas.doacoes`) e
`outras_entradas` (o resto que não é renda). E o cartão fica fora dos três:

```sql
AND NOT (t.direction = 'ENTRADA' AND a.type = 'CARTAO_CREDITO')
```

A regra é **estrutural, pelo tipo da conta**, e de propósito: numa conta de
cartão o saldo é dívida, e o que "entra" nela ou paga a dívida ou cancela uma
compra — nunca é dinheiro entrando na família. Depender da categoria estar certa
seria depender de classificação, e classificação erra; tipo de conta não. O valor
não desaparece: volta como `credito_no_cartao`, em linha própria.

## 11. Offline: duas peças com propósitos diferentes

O servidor mora no computador da casa, então "sem rede" aqui quer dizer "sem o
PC" — e as duas coisas que o aplicativo precisa fazer nesse estado não têm o mesmo
peso.

A **cópia local** (`api/cache.ts`) é conveniência: dá para viver uma hora sem ver
o painel. Ela é o cache de consultas desidratado, lido antes da primeira tela, e o
que ela não pode fazer é mentir — por isso a tela sempre diz **de quando** são os
números. Número velho sem data é pior que número ausente, porque ninguém desconfia
dele.

A **fila** (`api/fila.ts`) é o que importa: o gasto em dinheiro só existe se for
lançado na hora. Ela guarda o lançamento no aparelho, e nada sai dali sem o
servidor confirmar — nem o que ele recusa, que fica com o motivo para a tela
mostrar. A `client_key`, que já existia no servidor, é o que torna a subida segura:
reenviar não cobra duas vezes.

E o estado da conexão (`api/conexao.ts`) **não vem do indicador de internet do
sistema**. O servidor não está na internet: 5G perfeito com o PC desligado é
offline, e provedor caído com o PC ligado é online. O único sinal honesto é se a
última requisição obteve resposta — então é o cliente HTTP que alimenta o estado.

## 12. O que ficou de fora de propósito

- **Alembic**: as migrations são SQL puro numerado enquanto não há dados em
  produção. Na primeira mudança de schema com dados reais, migrar para Alembic.
- **Refresh token**: o JWT é longo (30 dias) e o app guarda no Keychain/Keystore.
  Com mais de dois usuários, vale rotação de token.
- **Saldo materializado**: `accounts.current_balance` é atualizado pela
  conciliação. Se divergir do razão, `recompute_balance` recalcula a partir das
  transações.
