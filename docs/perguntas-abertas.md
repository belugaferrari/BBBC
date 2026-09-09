# O que ainda preciso saber

O sistema já roda inteiro com os valores assumidos abaixo — nada aqui bloqueia
o uso. O que muda com as respostas é a **precisão** (principalmente do IR) e o
quanto de configuração manual sobra para vocês.

Cada item traz o que assumi, para você só confirmar ou corrigir.

---

## 1. Fiscal — é onde a resposta vale mais

| # | Pergunta | O que assumi hoje |
|---|---|---|
| 1.1 | A Checkmotor é **Simples Nacional, Lucro Presumido ou Real**? | Não modelado. Muda se a distribuição de lucros é integralmente isenta ou se há parcela tributável. |
| 1.2 | Você retira **pró-labore de valor fixo**? Qual, e há desconto de INSS na fonte? | Categoria `Pró-labore` como tributável pela tabela; INSS lançado à parte, dedutível. |
| 1.3 | A Clarissa tem renda própria e declara **em conjunto ou separado**? | Cada membro tem apuração própria; as filhas estão como dependentes do titular. Declaração conjunta ainda não é calculada. |
| 1.4 | As **duas filhas são dependentes de quem** na declaração? | Ambas do Felipe. Se uma for da Clarissa, muda a dedução dos dois. |
| 1.5 | O **negócio de leilões** é PF ou PJ? Se PF, já recolhe carnê-leão? | Modelado como PF sujeita a carnê-leão (endpoint `/tax/{ano}/carne-leao`). |
| 1.6 | Há **imóvel alugado**, pensão judicial, PGBL ou plano de previdência? | Categorias e regras existem, sem valores. PGBL limitado a 12% da renda tributável. |
| 1.7 | **Confirmar a tabela oficial de 2026.** A regra nova (isenção ampliada + redutor progressivo) está implementada de forma parametrizada, mas as faixas de 2026 hoje são uma **cópia das de 2025** e o ano está marcado `PROVISORIO`. | Ver `db/migrations/0002_seed_catalog.sql`. Corrigir é um `INSERT`, sem deploy. |
| 1.8 | Vocês têm **contador**? Ele deveria ter acesso de leitura (papel `CONTADOR` já existe no schema)? | Sem acesso criado. |

> Sobre 1.7: o motor não chuta. Ano sem tabela cadastrada devolve erro explícito
> em vez de calcular zero, e ano `PROVISORIO` volta com aviso na resposta da API.
> Nada do que sai daqui substitui a conferência do contador.

## 2. Família, contas e privacidade

| # | Pergunta | O que assumi |
|---|---|---|
| 2.1 | **Nomes e datas de nascimento das filhas** | Cadastradas como "Filha 1" e "Filha 2". |
| 2.2 | Vocês querem ver **os gastos um do outro** por completo, ou cada um tem uma parte privada? | Visão familiar mostra tudo; o filtro "só eu" é conveniência, não privacidade. Se quiserem gasto privado de verdade, é uma regra a mais no filtro. |
| 2.3 | Quais **bancos, cartões e corretoras** entram? | Nenhum pré-cadastrado. |
| 2.4 | Cartão de crédito: querem ver por **competência** (data da compra) ou por **caixa** (data da fatura)? | Ambas as datas existem (`booked_on` / `paid_on`); o dashboard usa competência. |
| 2.5 | Compra parcelada deve aparecer **integral no mês da compra** ou parcela a parcela? | Parcela a parcela (`installment_no` / `installment_total`). |

## 3. Open Finance

| # | Pergunta | O que assumi |
|---|---|---|
| 3.1 | **Pluggy ou Belvo?** Já existe conta/contrato? | Os dois implementados atrás do mesmo contrato; o padrão é modo manual, sem provedor. |
| 3.2 | Sincronização **automática (webhook) ou sob demanda**? | Os dois caminhos existem; sem agendador configurado. |
| 3.3 | Quem renova o **consentimento** quando expira (até 12 meses)? | Campo `consent_expires_at` existe; falta decidir se vira alerta no app. |

## 4. Investimentos

| # | Pergunta | O que assumi |
|---|---|---|
| 4.1 | A carteira vem da **corretora via Open Finance** ou entra por planilha/manual? | Modelo suporta os dois; sem importador de planilha. |
| 4.2 | Querem **preço de mercado atualizado** (ações/FII) — de qual fonte? | Só o valor informado no snapshot; sem cotação automática. |
| 4.3 | **CDI e IPCA**: puxar do Banco Central (SGS) automaticamente? | Tabela `benchmark_series` existe e está vazia; sem carga. |
| 4.4 | Precisam de **apuração de ganho de capital** (DARF de venda de ações, isenção de R$ 20 mil/mês)? | Parâmetros cadastrados; a apuração mês a mês ainda não foi escrita. |

## 5. Metas e orçamento

| # | Pergunta | O que assumi |
|---|---|---|
| 5.1 | **Viagem à Disney**: valor-alvo, data e quanto já está guardado? | Nenhuma meta cadastrada. O simulador aceita meta corrigida pela inflação. |
| 5.2 | O fundo da meta rende quanto ao ano? | Campo por meta, começa em 0%. |
| 5.3 | Tetos por categoria: **familiares, individuais ou os dois**? | Os dois são suportados (`member_id` nulo = familiar). Nenhum teto cadastrado. |
| 5.5 | **A sua árvore de categorias.** Você disse que manda depois. | O catálogo atual é um ponto de partida (90 categorias). Trocar depois é seguro: cada família tem a sua cópia, a árvore aceita qualquer profundidade e mover uma categoria leva a subárvore junto. Só as marcações de IR precisam vir com ela — quais são dedutíveis (saúde, educação, previdência) e quais receitas são isentas. |
| 5.6 | Quais são os **gastos fixos** de vocês (aluguel, escola, plano, seguros) — valor e dia do mês? | O evolutivo já lê gastos fixos cadastrados, mas ainda não há nenhum. Sem eles, a projeção usa só a média histórica, que é mais grosseira. |
| 5.4 | Querem **alerta antes de estourar** o teto (o padrão é 80%)? | 80%, configurável por teto; a projeção já avisa se o ritmo do mês estoura. |

## 6. Produto e operação

| # | Pergunta | O que assumi |
|---|---|---|
| 6.1 | **iOS, Android ou os dois?** | Expo cobre os dois. |
| 6.2 | Onde a API vai rodar (VPS, Fly, Render, Cloud Run)? | Só `docker compose`; sem pipeline de deploy. |
| 6.3 | **Backup do banco** — frequência e retenção? | Não configurado. É o item que eu resolveria primeiro depois do deploy. |
| 6.4 | Push notification para alertas (teto estourado, fatura, consentimento vencendo)? | Alertas são gravados e aparecem no dashboard; sem push. |
| 6.5 | Querem **importar histórico** (OFX/CSV do banco, planilha antiga)? | Enums `IMPORT_OFX`/`IMPORT_CSV` existem; o importador não foi escrito. |

---

## Se você só puder responder três

1. **1.1 + 1.2** — regime da Checkmotor e formato da sua retirada. É o que
   define se o número do IR sai certo ou aproximado.
2. **3.1** — Pluggy ou Belvo. Sem isso, tudo entra manualmente.
3. **5.1** — os números da viagem à Disney, que é a meta que dá sentido ao
   módulo de previsões.
