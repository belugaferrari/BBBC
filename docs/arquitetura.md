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

## 9. O que ficou de fora de propósito

- **Alembic**: as migrations são SQL puro numerado enquanto não há dados em
  produção. Na primeira mudança de schema com dados reais, migrar para Alembic.
- **Refresh token**: o JWT é longo (30 dias) e o app guarda no Keychain/Keystore.
  Com mais de dois usuários, vale rotação de token.
- **Saldo materializado**: `accounts.current_balance` é atualizado pela
  conciliação. Se divergir do razão, `recompute_balance` recalcula a partir das
  transações.
